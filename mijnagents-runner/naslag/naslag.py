"""Zoek en citeer lokale Buildwise-naslag voor een conceptwerfverslag."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    from .bouw_register import PDF_BASIS, REGISTER
except ImportError:  # rechtstreekse CLI-aanroep
    from bouw_register import PDF_BASIS, REGISTER

CACHE = Path(os.environ.get("NASLAG_CACHE", "~/appportal/mijnagents-data/naslag/tekst")).expanduser()
FASE_ALIAS = {"dakwerken": "dak", "dakwerk": "dak", "buitenwerk": "gevel", "riolering": "technieken",
              "binnenafwerking": "afwerking", "ruwbouw": "ruwbouw", "afbraak": "afbraak",
              "buitenschrijnwerk": "buitenschrijnwerk", "technieken": "technieken", "oplevering": "oplevering"}
STOP = {"de", "het", "een", "en", "van", "voor", "bij", "met", "op", "in", "aan", "of", "deel", "werken"}


def register():
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def _woorden(tekst):
    return {w for w in re.findall(r"[\w]+", str(tekst).lower()) if len(w) > 2 and w not in STOP}


def _zoekscore(record, trefwoorden, fase, categorie):
    woorden = _woorden(" ".join(trefwoorden))
    punten = _woorden(" ".join(record["werfpunten"]))
    titel = _woorden(record["titel"])
    score = 5 * len(woorden & punten) + 3 * len(woorden & titel)
    score += 2 * sum(1 for woord in woorden for kandidaat in punten if len(kandidaat) > 3 and kandidaat != woord and kandidaat in woord)
    score += sum(1 for woord in woorden for kandidaat in titel if len(kandidaat) > 3 and kandidaat != woord and kandidaat in woord)
    tekst = " ".join(record["werfpunten"] + [record["titel"]]).lower()
    score += 9 * sum(1 for term in trefwoorden if len(term) > 3 and term.lower() in tekst)
    if fase and fase in record["fases"]:
        score += 5
    if categorie and categorie.lower() in (record["fases"] + [record["map"]]):
        score += 3
    return score


def zoek(categorie=None, trefwoorden=(), fase=None, max_n=4):
    if isinstance(trefwoorden, str):
        trefwoorden = (trefwoorden,)
    fase = FASE_ALIAS.get(str(fase or categorie or "").lower(), fase)
    if not fase:
        vraag = " ".join(trefwoorden).lower()
        for herkenning, gevonden_fase in (("dak", "dak"), ("raam", "buitenschrijnwerk"),
                                          ("gevel", "gevel"), ("beton", "ruwbouw"), ("vloertegel", "afwerking")):
            if herkenning in vraag:
                fase = gevonden_fase
                break
    gevonden = [(score, r) for r in register() if (score := _zoekscore(r, trefwoorden, fase, categorie)) > 0]
    geldig = any(r["status"] == "geldig" for _, r in gevonden)
    selectie = [(s, r) for s, r in gevonden if not (geldig and r["status"] == "verouderd")]
    selectie.sort(key=lambda sr: (sr[1]["status"] == "verouderd", -sr[0], sr[1]["status"] == "ongekend", sr[1]["sleutel"]))
    return [r for _, r in selectie[:max(0, max_n)]]


def _record(sleutel):
    for record in register():
        if record["sleutel"] == sleutel:
            return record
    raise KeyError(f"onbekende naslagsleutel: {sleutel}")


def tekst(sleutel):
    record = _record(sleutel)
    cache = CACHE / f"{sleutel}.txt"
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    from pypdf import PdfReader
    pad = PDF_BASIS / record["map"] / record["bestand"]
    if not pad.is_file():
        raise FileNotFoundError(f"naslag-pdf ontbreekt: {pad}")
    reader = PdfReader(str(pad))
    paginas = []
    for nummer, pagina in enumerate(reader.pages, 1):
        paginas.append(f"[p. {nummer}]\n{pagina.extract_text() or ''}")
    resultaat = "\n\n".join(paginas)
    CACHE.mkdir(parents=True, exist_ok=True)
    tijdelijk = cache.with_suffix(".txt.tmp")
    tijdelijk.write_text(resultaat, encoding="utf-8")
    tijdelijk.replace(cache)
    return resultaat


def fragmenten(sleutel, trefwoorden, max_tekens=1500, max_n=3):
    if max_n <= 0 or max_tekens <= 0:
        return []
    inhoud = tekst(sleutel)
    termen = _woorden(" ".join((trefwoorden,) if isinstance(trefwoorden, str) else trefwoorden))
    kandidaten = []
    for blok in re.split(r"(?=\[p\. \d+\])", inhoud):
        m = re.match(r"\[p\. (\d+)\]\s*", blok)
        if not m:
            continue
        pagina = int(m.group(1))
        # Sommige pdf's geven witregels, andere alleen regelafbrekingen.
        alinea = [re.sub(r"\s+", " ", a).strip() for a in re.split(r"\n\s*\n", blok[m.end():]) if a.strip()]
        if len(alinea) == 1 and len(alinea[0]) > 700:
            alinea = [re.sub(r"\s+", " ", a).strip() for a in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])", alinea[0]) if a.strip()]
        for index, stuk in enumerate(alinea):
            score = len(_woorden(stuk) & termen)
            if score:
                context = " ".join(alinea[max(0, index - 1):min(len(alinea), index + 2)])
                kandidaten.append((score, pagina, context))
    kandidaten.sort(key=lambda x: (-x[0], x[1]))
    uit, gezien, budget = [], set(), max(0, max_tekens)
    for _, pagina, context in kandidaten:
        if (pagina, context) in gezien:
            continue
        gezien.add((pagina, context))
        kop = f"[p. {pagina}] "
        if budget <= len(kop):
            break
        regel = kop + context[:budget - len(kop)]
        uit.append(regel)
        budget -= len(regel)
        if len(uit) >= max_n:
            break
    return uit


def naslag_voor_punten(onderdelen, max_bronnen=6, max_tekens=9000):
    """Maak één begrensd promptblok uit korte onderdelen of gegevens-onderdelen."""
    if max_tekens <= 0:
        return ""
    uit = "### NASLAG"[:max_tekens]
    gekozen = set()
    for onderdeel in onderdelen:
        if isinstance(onderdeel, dict):
            naam = str(onderdeel.get("onderdeel", ""))
            details = ", ".join(map(str, onderdeel.get("vaststellingen", [])))
            omschrijving = f"{naam}: {details}"
        else:
            omschrijving = str(onderdeel)
            naam = omschrijving.split(":", 1)[0]
        fase = FASE_ALIAS.get(naam.strip().lower())
        termen = tuple(t.strip() for t in re.split(r"[:,;]", omschrijving) if t.strip())
        kandidaten = zoek(categorie=naam, trefwoorden=termen, fase=fase, max_n=8)
        aantal = 0
        for bron in kandidaten:
            if bron["sleutel"] in gekozen or len(gekozen) >= max_bronnen or aantal >= 2:
                continue
            kop = f"\n\n{omschrijving}\n{bron['sleutel']}: {bron['titel']} ({bron['uitgever']} {bron['jaar'] or 'jaar onbekend'}; {bron['status']})"
            ruimte = max_tekens - len(uit) - len(kop)
            if ruimte <= 0:
                return uit[:max_tekens]
            try:
                delen = fragmenten(bron["sleutel"], termen, max_tekens=min(1500, ruimte), max_n=3)
            except Exception as fout:  # één kapotte pdf mag de werfproef niet blokkeren
                print(f"naslag {bron['sleutel']}: {fout}", file=sys.stderr)
                continue
            if not delen:
                continue
            blok = kop + "\n" + "\n".join(delen)
            uit += blok[:max_tekens - len(uit)]
            gekozen.add(bron["sleutel"])
            aantal += 1
            if len(uit) >= max_tekens:
                return uit
    return uit if gekozen else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="actie", required=True)
    p_zoek = sub.add_parser("zoek")
    p_zoek.add_argument("trefwoorden", nargs="+")
    p_tekst = sub.add_parser("tekst")
    p_tekst.add_argument("sleutel")
    sub.add_parser("index")
    args = parser.parse_args()
    if args.actie == "zoek":
        for r in zoek(trefwoorden=args.trefwoorden):
            print(f"{r['sleutel']} | {r['titel']} | {r['jaar'] or '?'} | {r['status']}")
    elif args.actie == "tekst":
        print(tekst(args.sleutel))
    else:
        records = register()
        fouten = 0
        for nummer, r in enumerate(records, 1):
            try:
                tekst(r["sleutel"])
                print(f"{nummer}/{len(records)} {r['sleutel']}: klaar", flush=True)
            except Exception as fout:  # per pdf doorgaan en fout melden
                fouten += 1
                print(f"{nummer}/{len(records)} {r['sleutel']}: fout: {fout}", file=sys.stderr, flush=True)
        print(f"{len(records) - fouten}/{len(records)} gecachet, {fouten} fouten")
        if fouten:
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
