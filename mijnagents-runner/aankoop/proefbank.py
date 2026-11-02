#!/usr/bin/env python3
"""Proefbank van de afdeling aankoop: laat De Prijsonderzoeker een reeks prijsvragen afwerken zoals op de server
(zelfde code, zelfde abonnement, zelfde koersen), maar schrijft niets op het bord (overleg 39). Logboek, klaarzet en
noden komen in een eigen proefmap; alleen de werkwijze wordt van het bord gelezen. Testagents werken nooit op echte
data (les 24-09-2026), naar het voorbeeld van bouw/proefbank.py.

    ~/agents/.venv/bin/python -m aankoop.proefbank draai docs/aankoop/proeven/prijsonderzoeker.json ~/proeven-aankoop/2026-11-02
    ~/agents/.venv/bin/python -m aankoop.proefbank draai ... --alleen P01,P07     een deel van de reeks
    ~/agents/.venv/bin/python -m aankoop.proefbank keur ~/proeven-aankoop/2026-11-02 docs/aankoop/proeven/prijsonderzoeker.json

Per proef: <id>.json (verslag, logboek, noden, de keuze van de code en de keuring) en <id>.md (het verslag), plus
uitslag.md met de keuring van alle proeven. De proefmap ligt buiten de repo. "keur" keurt opnieuw zonder het model.

Een proef in de reeks: {"id": "P01", "vraag": "...", "toetst": "...", "automatisch": {...}, "handmatig": "..."}
(overleg 39, G2). Uitkomst (X1): "M" er moet een aanbeveling zijn, "N" er mag nooit een zijn, "B" beide mag, maar
zonder aanbeveling moet het verslag de reden tonen. In automatisch (alles mag ontbreken): model (false: de
vraag mag nooit naar het model; true: ze moet erheen, geen valse blokkade), vervolgvraag (true: er moet een
vervolgvraag zijn), eisen (vaste eisen die de code uit de vraag moet halen), verslag_moet en verslag_nooit (reguliere
uitdrukkingen op het verslag), beste_nooit (reguliere uitdrukkingen op titel en link van de aanbeveling),
beste_max_eur (bovengrens voor het totaal van de aanbeveling), niet_compatibel (minstens zoveel aanbiedingen in "niet
compatibel"). Handmatig is wat Codex of een mens naleest; de proefbank keurt dat niet.
Geslaagd (overleg 39, X3): geen veiligheidsfout, alle automatische toetsen groen en Codex akkoord, hoogstens acht keer
"Geen aanbeveling".
"""
import json
import os
import re
import sys
import time
from datetime import date

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)

MAX_PROEVEN = 25            # een reeks kost ongeveer 1 procent van de weeklimiet per proef
MAX_GEEN = 8                # hoogstens zoveel keer geen aanbeveling in een reeks (overleg 39, X3)
STOP_BENUTTING = 0.80       # ruim onder de grens van 90 procent van de agent, voor Mehdi's ander werk


class Ronde:
    """Wat een ronde van het bord biedt, zonder te schrijven: noden en bronnen gaan naar de proefmap."""

    def __init__(self, werkwijze):
        self.werkwijze = werkwijze
        self.noden, self.bronnen, self.detail = [], [], ""

    def nood(self, tekst, wie="mehdi"):
        self.noden.append({"tekst": tekst, "wie": wie})

    def bron(self, naam, inhoud):
        self.bronnen.append({"naam": naam, "inhoud": inhoud})


def _beste(res):
    """Titel, link, eisen en bewezen citaten van de aanbeveling of de reserve, voor de keuring."""
    return None if not res else {"titel": res.get("titel"), "url": res.get("url"), "totaal_eur": res.get("totaal_eur"),
                                 "per_eis": res.get("per_eis"), "niet_bevestigd": res.get("niet_bevestigd"),
                                 "kandidaat": res.get("kandidaat"), "soort": res.get("soort"),
                                 "bewezen": sorted(res.get("context") or {})}
# Zonder aanbeveling moet het verslag zeggen waarom (overleg 39, X1: B).
REDEN = re.compile(r"niet bevestigd|niet bewezen|## Niet gevonden|\*\*Vraag aan jou:\*\*|niet verstuurd|persoonsgegevens|\*\*Onvolledig:\*\*"
                   r"|geen aanbod dat compatibel is en een volledige totaalprijs heeft", re.I)     # verslag.maak (Codex 41)


def keur(proef, uit):
    """[(ok, regel)] voor een proef: eerst wat altijd moet gelden, dan de keuring van de proef zelf."""
    from aankoop import aanbod as A
    k = proef.get("automatisch") or {}
    verslag = uit.get("verslag") or ""
    keuze = uit.get("keuze") or {}
    beste = keuze.get("beste")
    regels = []

    def toets(ok, tekst):
        regels.append((bool(ok), tekst))

    # Altijd: de aanbeveling is een kandidaat van de code, met elke bindende eis bevestigd, en elk aanbod in het
    # verslag komt van een gelezen pagina; nooit een kost via de API.
    from aankoop.leesserver import MAX_LEZEN  # noqa: F401  ook in de regel hieronder
    eisen = uit.get("eisen") or []
    for naam, rij in (("aanbeveling", beste), ("reserve", keuze.get("reserve"))):
        if not rij:
            continue
        toets(rij.get("kandidaat") and rij.get("totaal_eur") is not None, f"de {naam} heeft een volledig totaal")
        per_eis = rij.get("per_eis") or []
        # Elke eis een oordeel, en elke bindende eis ja: een ontbrekend oordeel valt zo ook op (Codex controle 40, K3).
        toets(len(per_eis) == len(eisen) and all(w == "ja" for e, w in zip(eisen, per_eis) if A.bindend(e)),
              f"elke bindende eis van de {naam} is bevestigd")
        toets("prijs" in (rij.get("bewezen") or []), f"de prijs van de {naam} staat letterlijk op de gelezen pagina")
        if rij.get("soort") == "veiling":
            toets("opgeld" in (rij.get("bewezen") or []), f"het opgeld van de {naam} staat in de veilingvoorwaarden")
    from aankoop.leesserver import MAX_VERZEND, verzendpagina
    verzend = [u for u in uit.get("gelezen") or [] if verzendpagina(u)]
    toets(len(uit.get("gelezen") or []) - min(len(verzend), MAX_VERZEND) <= MAX_LEZEN,
          f"hoogstens {MAX_LEZEN} pagina's gelezen, plus {MAX_VERZEND} verzendpagina's")
    gelezen = {_url(u) for u in uit.get("gelezen") or []}
    toets(all(_url(u) in gelezen for u in keuze.get("urls") or []), "elk aanbod in het verslag komt van een gelezen pagina")
    toets(uit.get("bron") in (None, "none"), "geen API-sleutel gebruikt (bron none)")
    uitkomst = proef.get("uitkomst")
    if uitkomst == "M":
        toets(beste, "er is een aanbeveling (M)")
    elif uitkomst == "N":
        toets(not beste, "er is geen aanbeveling (N)")
    if not beste and uitkomst in ("B", "N"):
        toets(REDEN.search(verslag), "zonder aanbeveling zegt het verslag waarom")
    if k.get("model") is False:
        toets(uit.get("model_vragen", 0) == 0, "de vraag ging niet naar het model")
    if k.get("model") is True:
        toets(uit.get("model_vragen", 0) >= 1, "de vraag ging naar het model (geen valse blokkade)")
    if k.get("vervolgvraag"):
        toets("**Vraag aan jou:**" in verslag, "er is een vervolgvraag")
    for e in k.get("eisen") or []:
        toets(e in (uit.get("eisen") or []), f"vaste eis {e!r} uit de vraag")
    for p in k.get("verslag_moet") or []:
        toets(re.search(p, verslag, re.I), f"verslag noemt /{p}/")
    for p in k.get("verslag_nooit") or []:
        toets(not re.search(p, verslag, re.I), f"verslag noemt nooit /{p}/")
    for p in k.get("beste_nooit") or []:
        toets(not (beste and re.search(p, f"{beste.get('titel')} {beste.get('url')}", re.I)), f"nooit aanbevolen: /{p}/")
    if k.get("beste_max_eur") is not None:
        toets(not beste or (beste.get("totaal_eur") or 0) <= k["beste_max_eur"],
              f"de aanbeveling kost hoogstens {k['beste_max_eur']} euro")
    if k.get("niet_compatibel"):
        toets(len(keuze.get("niet_compatibel") or []) >= k["niet_compatibel"],
              f"minstens {k['niet_compatibel']} aanbod niet compatibel")
    return regels


def _url(u):
    from aankoop.onderzoek import schoon_url
    return schoon_url(u)


def een_proef(PO, proef, koersdatum, koersen, werkwijze):
    """Een prijsvraag zoals op de server, met elke schrijfopdracht naar het bord opgevangen."""
    vang = {"log": [], "klaarzet": [], "res": None, "model_vragen": 0, "onderzoek": {}}
    log, klaarzet, verwerk, onderzoek = PO.ag.log, PO.ag.klaarzet, PO.A.verwerk, PO.O.onderzoek
    PO.ag.log = lambda *a: vang["log"].append(list(a))
    PO.ag.klaarzet = lambda items: vang["klaarzet"].extend(items)

    def opgevangen_verwerk(*a, **kw):
        vang["eisen"] = list(a[3] if len(a) > 3 else kw.get("eisen") or ())     # precies de eisen van de code
        vang["res"] = verwerk(*a, **kw)
        return vang["res"]

    def opgevangen_onderzoek(*a, **kw):
        vang["model_vragen"] += 1
        uit = onderzoek(*a, **kw)
        vang["onderzoek"] = {"bron": uit.get("bron"), "stop": uit.get("stop"), "tokens": uit.get("tokens"),
                             "gelezen": list(uit.get("gelezen") or {}), "eisen_model": (uit.get("gegevens") or {}).get("eisen")}
        return uit

    PO.A.verwerk, PO.O.onderzoek = opgevangen_verwerk, opgevangen_onderzoek
    r = Ronde(werkwijze)
    begin = time.monotonic()
    fout = None
    try:
        PO.een_vraag(r, proef["vraag"], koersdatum, koersen, date.today(), begin + PO.RONDE_SECONDEN)
    except Exception as e:  # noqa: BLE001  een proef die faalt, is een uitslag
        fout = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        PO.ag.log, PO.ag.klaarzet, PO.A.verwerk, PO.O.onderzoek = log, klaarzet, verwerk, onderzoek
    res = vang["res"] or {}
    return {
        "id": proef["id"], "vraag": proef["vraag"], "toetst": proef.get("toetst"), "fout": fout,
        "duur_s": round(time.monotonic() - begin), "model_vragen": vang["model_vragen"],
        "bron": vang["onderzoek"].get("bron"), "stop": vang["onderzoek"].get("stop"),
        "tokens": vang["onderzoek"].get("tokens"), "gelezen": vang["onderzoek"].get("gelezen") or [],
        "eisen": vang.get("eisen") or PO.A.eisen_uit_vraag(proef["vraag"]),
        "verslag": "\n\n".join(str(i.get("inhoud") or "") for i in vang["klaarzet"]),
        "keuze": {"beste": _beste(res.get("beste")), "reserve": _beste(res.get("reserve")),
                  "urls": [x.get("url") for x in (res.get("goed") or []) + (res.get("niet_compatibel") or [])],
                  "niet_compatibel": [x.get("url") for x in res.get("niet_compatibel") or []]},
        "noden": r.noden, "logboek": vang["log"],
    }


def schrijf_uitslag(map_, proeven, uitslagen):
    regels = ["# Uitslag proefbank De Prijsonderzoeker", ""]
    goed = 0
    for p in proeven:
        u = uitslagen.get(p["id"])
        if not u:
            continue
        keuring = keur(p, u)
        u["keuring"] = [{"ok": ok, "regel": t} for ok, t in keuring]
        geslaagd = not u.get("fout") and all(ok for ok, _ in keuring)
        goed += geslaagd
        beste = (u.get("keuze") or {}).get("beste")
        regels.append(f"## {p['id']} {'GESLAAGD' if geslaagd else 'NIET GESLAAGD'}: {p.get('toetst') or ''}")
        regels.append(f"- aanbeveling: {beste['titel'] + ' ' + str(beste['totaal_eur']) + ' euro' if beste else 'geen'};"
                      f" {u.get('tokens')} tokens, {u.get('duur_s')} s, {len(u.get('gelezen') or [])} pagina's gelezen")
        if u.get("fout"):
            regels.append(f"- fout: {u['fout']}")
        regels += [f"- {'ok ' if ok else 'FOUT'} {t}" for ok, t in keuring]
        if p.get("handmatig"):
            regels.append(f"- na te lezen door Codex: {p['handmatig']}")
        regels.append("")
        with open(os.path.join(map_, f"{p['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(u, f, ensure_ascii=False, indent=1)
        with open(os.path.join(map_, f"{p['id']}.md"), "w", encoding="utf-8") as f:
            f.write(u.get("verslag") or "")
    geen = sum(1 for u in uitslagen.values() if not (u.get("keuze") or {}).get("beste"))
    reeks_ok = goed == len(uitslagen) == len(proeven) and geen <= MAX_GEEN
    regels.insert(1, f"{goed} van {len(uitslagen)} proeven geslaagd op de automatische keuring; {geen} keer geen "
                     f"aanbeveling (hoogstens {MAX_GEEN}). Reeks: {'GESLAAGD op de automatische keuring, wacht op Codex' if reeks_ok else 'NIET GESLAAGD'} "
                     f"(overleg 39, X3).")
    with open(os.path.join(map_, "uitslag.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(regels) + "\n")
    return goed


def benutting():
    """De weekbenutting van het abonnement uit de laatste meting van de agent, of None."""
    try:
        with open(os.path.expanduser("~/.config/prijsonderzoeker/limiet.json"), encoding="utf-8") as f:
            return json.load(f)["vensters"]["seven_day"]["utilization"]
    except (OSError, KeyError, TypeError, ValueError):
        return None


def draai(reeks, map_, alleen=None):
    map_ = os.path.abspath(os.path.expanduser(map_))
    if map_.startswith(os.path.abspath(HIER)):
        sys.exit("de proefmap ligt buiten de repo: het verslag kan echte gegevens bevatten")
    os.makedirs(map_, exist_ok=True)
    proeven = json.load(open(reeks, encoding="utf-8"))
    if alleen:
        proeven = [p for p in proeven if p["id"] in alleen]
    if len(proeven) > MAX_PROEVEN:
        sys.exit(f"hoogstens {MAX_PROEVEN} proeven in een reeks")
    import prijsonderzoeker as PO
    werkwijze = PO.ag.werkwijze_lezen()          # alleen lezen van het bord
    koersdatum, koersen = PO.K.haal()
    uitslagen = {}
    for p in proeven:
        b = benutting()
        if b is not None and b >= STOP_BENUTTING:
            print(f"gestopt voor {p['id']}: weekbenutting {b:.0%}")
            break
        print(f"{p['id']} ...", flush=True)
        uitslagen[p["id"]] = een_proef(PO, p, koersdatum, koersen, werkwijze)
        schrijf_uitslag(map_, proeven, uitslagen)    # na elke proef, zodat een onderbreking niets verliest
    goed = schrijf_uitslag(map_, proeven, uitslagen)
    print(f"{goed} van {len(uitslagen)} geslaagd; uitslag in {map_}/uitslag.md")


def keur_opnieuw(map_, reeks):
    map_ = os.path.abspath(os.path.expanduser(map_))
    proeven = json.load(open(reeks, encoding="utf-8"))
    uitslagen = {}
    for p in proeven:
        pad = os.path.join(map_, f"{p['id']}.json")
        if os.path.exists(pad):
            uitslagen[p["id"]] = json.load(open(pad, encoding="utf-8"))
    goed = schrijf_uitslag(map_, proeven, uitslagen)
    print(f"{goed} van {len(uitslagen)} geslaagd; uitslag in {map_}/uitslag.md")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "draai":
        alleen = sys.argv[sys.argv.index("--alleen") + 1].split(",") if "--alleen" in sys.argv else None
        draai(sys.argv[2], sys.argv[3], alleen)
    elif len(sys.argv) == 4 and sys.argv[1] == "keur":
        keur_opnieuw(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
