"""Het regelregister van De Deontologiewacht (opdrachtkaart v0.3, stap 1 van de bouw).

Het register (`regels.json`) is de enige plaats waar staat welke beroepsplichten de agent toetst. Elke regel steunt op
een artikel met een letterlijk citaat uit een bron in `bronnen/`. `valideer()` is de grendel die het driehoeksoverleg
van 27-10-2026 vroeg (3-0, X1, X2, X3 en de correcties van Claude op G2 en G3):

- elk citaat staat letterlijk in het artikel dat de regel noemt, in de bron met de vastgelegde sha256;
- elke regel is HARD of OORDEEL, en LETTERLIJK of AFGELEID; een afgeleide regel zegt waarom;
- rood kan alleen bij HARD en LETTERLIJK, al de rest is hoogstens oranje;
- de controlepunten A tot F hebben elk minstens een regel;
- elk artikel van de bron is ingedeeld: een regel, het toepassingsgebied, geen toets (met reden) of niet van toepassing.

Verandert de bron (een nieuwe stand van de bibliotheek), dan klopt de sha256 niet meer en faalt de validatie tot
iemand de citaten opnieuw heeft nagekeken en de sha bijwerkt. Zo toetst de agent nooit stil tegen een tekst die hij
niet kent.

Draaien: python3 mijnagents-runner/deontologie/register.py (exitcode 1 bij een fout).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
REGISTER = HIER / "regels.json"

PUNTEN = {
    "A": "ereloon",
    "B": "verplichte inhoud van het contract",
    "C": "werfcontrole",
    "D": "budget en verzekering",
    "E": "beëindiging en opvolging",
    "F": "aannemers en onverenigbaarheid",
    "G": "overige beroepsplichten",
}
VERPLICHT = "ABCDEF"  # Mehdi's controlepunten A tot D, plus beëindiging en aannemers (opdrachtkaart, hoofdstuk 1)
DOCUMENTEN = {"contract", "offerte", "werfverslag", "deskundigenverslag", "mail", "kantoor"}
VELDEN = ("code", "punt", "titel", "bron", "artikel", "citaat", "status", "type", "max_kleur", "documenten", "toets")
MIN_CITAAT = 30
STREEPJES = re.compile(r"[–—]| - ")  # geen gedachtestreepjes in eigen tekst (afspraak 04-07-2026)

_ARTIKELKOP = r"(?:Artikel|Art\.)\s*{nr}\s*\."


def laad(pad=REGISTER):
    return json.loads(Path(pad).read_text(encoding="utf-8"))


def normaliseer(tekst):
    return re.sub(r"\s+", " ", tekst).strip()


def artikels(brontekst, aantal):
    """Splits de bron in artikels 1..aantal. Zoekt elke kop na de vorige, zodat een verwijzing als "artikel 21 van de
    wet" in de lopende tekst nooit als kop telt. Het laatste artikel stopt bij de ondertekening."""
    tekst = normaliseer(brontekst)
    start = re.search(_ARTIKELKOP.format(nr=1) + r" De ", tekst)
    if not start:
        return {}
    posities = [(1, start.start())]
    for nr in range(2, aantal + 1):
        kop = re.compile(_ARTIKELKOP.format(nr=nr) + r" ")
        m = kop.search(tekst, posities[-1][1] + 1)
        if not m:
            break
        posities.append((nr, m.start()))
    einde = tekst.find(" Handtekening ", posities[-1][1])
    if einde < 0:
        einde = len(tekst)
    uit = {}
    for i, (nr, begin) in enumerate(posities):
        tot = posities[i + 1][1] if i + 1 < len(posities) else einde
        uit[str(nr)] = tekst[begin:tot]
    return uit


def _bronnen(register, basis, fouten):
    teksten = {}
    for code, bron in register.get("bronnen", {}).items():
        pad = Path(basis) / bron["bestand"]
        if not pad.is_file():
            fouten.append(f"bron {code}: bestand {bron['bestand']} ontbreekt")
            continue
        inhoud = pad.read_bytes()
        sha = hashlib.sha256(inhoud).hexdigest()
        if sha != bron.get("sha256"):
            fouten.append(f"bron {code}: sha256 klopt niet ({sha[:12]}), de citaten moeten opnieuw nagekeken worden")
            continue
        delen = artikels(inhoud.decode("utf-8"), bron["artikels"])
        if len(delen) != bron["artikels"]:
            fouten.append(f"bron {code}: {len(delen)} artikels gevonden in plaats van {bron['artikels']}")
        teksten[code] = delen
    return teksten


def _citaat(waar, item, teksten, fouten):
    bron, artikel, citaat = item.get("bron"), str(item.get("artikel", "")), item.get("citaat") or ""
    if bron not in teksten:
        fouten.append(f"{waar}: bron {bron} onbekend of niet geldig")
        return
    if artikel not in teksten[bron]:
        fouten.append(f"{waar}: artikel {artikel} bestaat niet in {bron}")
        return
    if len(normaliseer(citaat)) < MIN_CITAAT:
        fouten.append(f"{waar}: citaat te kort, minstens {MIN_CITAAT} tekens")
    elif normaliseer(citaat) not in teksten[bron][artikel]:
        fouten.append(f"{waar}: citaat staat niet letterlijk in {bron} artikel {artikel}")


def _regel(r, teksten, fouten):
    code = r.get("code", "?")
    for veld in VELDEN:
        if r.get(veld) in (None, "", []):
            fouten.append(f"{code}: veld {veld} ontbreekt")
    if not re.fullmatch(r"[A-G][1-9]\d*", code) or code[0] != r.get("punt"):
        fouten.append(f"{code}: code moet beginnen met de letter van het punt ({r.get('punt')}) en een nummer")
    if r.get("punt") not in PUNTEN:
        fouten.append(f"{code}: punt {r.get('punt')} onbekend")
    if r.get("status") not in ("LETTERLIJK", "AFGELEID"):
        fouten.append(f"{code}: status moet LETTERLIJK of AFGELEID zijn")
    if r.get("type") not in ("HARD", "OORDEEL"):
        fouten.append(f"{code}: type moet HARD of OORDEEL zijn")
    if r.get("max_kleur") not in ("oranje", "rood"):
        fouten.append(f"{code}: max_kleur moet oranje of rood zijn")
    if r.get("max_kleur") == "rood" and not (r.get("type") == "HARD" and r.get("status") == "LETTERLIJK"):
        fouten.append(f"{code}: rood kan alleen bij HARD en LETTERLIJK")
    if r.get("status") == "AFGELEID" and not (r.get("afleiding") or "").strip():
        fouten.append(f"{code}: een afgeleide regel zegt in afleiding waarom")
    onbekend = set(r.get("documenten") or []) - DOCUMENTEN
    if onbekend:
        fouten.append(f"{code}: onbekende documenten {sorted(onbekend)}")
    for veld in ("titel", "toets", "afleiding"):
        if STREEPJES.search(r.get(veld) or ""):
            fouten.append(f"{code}: gedachtestreepje in {veld}")
    _citaat(code, r, teksten, fouten)


def _dekking(register, teksten, fouten):
    for code, bron in register.get("bronnen", {}).items():
        if code not in teksten:
            continue
        ingedeeld = {}

        def zet(nr, waar):
            ingedeeld.setdefault(nr, set()).add(waar)

        for r in register.get("regels", []):
            if r.get("bron") == code:
                zet(str(r.get("artikel")), "regel")
        tg = register.get("toepassingsgebied", {})
        if tg.get("bron") == code:
            zet(str(tg.get("artikel")), "regel")
        for g in register.get("geen_toets", []):
            if not (g.get("reden") or "").strip():
                fouten.append(f"geen toets {g.get('artikels')}: reden ontbreekt")
            for nr in g.get("artikels", []):
                zet(str(nr), "geen_toets")
        for n in register.get("niet_van_toepassing", []):
            for nr in range(int(n["van"]), int(n["tot"]) + 1):
                zet(str(nr), "niet_van_toepassing")
        for nr, soorten in sorted(ingedeeld.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
            if len(soorten) > 1:
                fouten.append(f"{code} artikel {nr}: dubbel ingedeeld ({' en '.join(sorted(soorten))})")
        missend = [str(nr) for nr in range(1, bron["artikels"] + 1) if str(nr) not in ingedeeld]
        if missend:
            fouten.append(f"{code}: artikels zonder indeling: {', '.join(missend)}")


def valideer(register, basis=HIER):
    """Geeft de lijst fouten terug; leeg betekent dat het register klopt."""
    fouten = []
    teksten = _bronnen(register, basis, fouten)
    regels = register.get("regels", [])
    codes = [r.get("code") for r in regels]
    for dubbel in sorted({c for c in codes if codes.count(c) > 1}):
        fouten.append(f"{dubbel}: code komt meer dan een keer voor")
    for r in regels:
        _regel(r, teksten, fouten)
    _citaat("toepassingsgebied", register.get("toepassingsgebied", {}), teksten, fouten)
    for punt in VERPLICHT:
        if not any(r.get("punt") == punt for r in regels):
            fouten.append(f"punt {punt} ({PUNTEN[punt]}) heeft geen regel")
    _dekking(register, teksten, fouten)
    return fouten


def regels(documentsoort=None, register=None):
    """De regels voor een soort document (contract, werfverslag, ...), of alle regels."""
    register = register or laad()
    return [r for r in register["regels"] if documentsoort is None or documentsoort in r["documenten"]]


if __name__ == "__main__":
    fouten = valideer(laad())
    for f in fouten:
        print("FOUT", f)
    reg = laad()
    print(f"{len(reg['regels'])} regels, {len(fouten)} fouten")
    sys.exit(1 if fouten else 0)
