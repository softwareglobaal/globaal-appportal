#!/usr/bin/env python3
"""De proef van De Gespreksanalist (T-0120, besluit X5): droog, op zes gesprekken uit een maand.

Twee Fathom, twee Plaud en een Zoom-tekst, verspreid over de maand (de eerste en de tweede helft), waarvan een zonder
actiepunt (bij voorkeur een Fathom-gesprek met een samenvatting maar zonder actiepunten van Fathom; is er geen, dan
zegt de rol "fathom" en staat het in de tekorten als ook de uitkomst geen gesprek zonder actiepunt heeft), plus een
privégesprek dat alleen "privégesprek, N min" mag geven. De Zoom-tekst is zelf ook altijd privé (zoom_wacht.py:266). Dezelfde code als de
nachtronde (gespreksanalist.verwerk), maar:
- alleen lezen: de gesprekkentabel (alleen lezend), de archieven op de VM, de agenda op het bord en de bewaarde
  projectindex (nooit een nieuwe uit Dropbox);
- alleen schrijven: het proefbestand (rechten 600) in ~/appportal/mijnagents-data/gespreksanalist/proef/. Nooit
  gesprek.json, nooit de uitvoer of de dagteller van de nachtronde, nooit het bord (geen hartslag, logboek of klaarzet).
  Een uitzondering, alleen met het model aan: claude_abonnement schrijft bij elke vraag zelf zijn limietbestand
  (~/.cache/claude-abonnement/limiet.json), de grendel tegen extra verbruik die elke agent op het abonnement deelt;
- Plaud gaat alleen naar het model als gespreksanalist.MODEL_AAN aan staat (het ja van Mehdi, T-0122 keuze 1), en
  binnen hetzelfde budget (5 per dag, met een verse meting van het weekvenster onder 60 procent); de modelvragen van de
  nachtronde (dagteller) en van eerdere proeven die dag (hun proefbestand) tellen mee; anders zegt de proef waarom niet.

Meet per gesprek: actiepunten, weggegooide actiepunten, het aandeel met een letterlijk citaat (doel 100 procent),
tokens en duur. Codex leest het proefbestand. Op het scherm alleen het pad en aantallen, geen naam of inhoud.

Gebruik (op de VM, pas na de merge en niet vannacht, X6): ~/agents/.venv/bin/python gespreksanalist_proef.py --maand 2026-10
"""
import json
import os
import sys
import time
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import archivaris as AR  # noqa: E402  de leesweg en geval_van van de nachtronde
import gespreksanalist as GA  # noqa: E402

ROLLEN = (("fathom zonder actiepunt", 1), ("fathom met actiepunten", 2), ("plaud", 1), ("plaud", 2), ("zoom-tekst", 0),
          ("privé", 0))


def bewaarde_projecten():
    """De projectindex die De Agendawacht al bewaarde, zonder hem uit Dropbox opnieuw op te bouwen; {} als hij er niet is."""
    try:
        with open(AR.projectadressen.CACHE, encoding="utf-8") as f:
            return json.load(f).get("projecten") or {}
    except (OSError, ValueError, AttributeError):
        return {}


def fathom_punten(map_):
    try:
        with open(os.path.join(map_ or "-", "actiepunten.md"), encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError):
        return 0
    return len(items) if isinstance(items, list) else 0


def pak(lijst, helft=0, niet=()):
    """Het middelste gesprek van die helft van de maand (1: dag 1 tot 15, 2: vanaf 16, 0: de hele maand), dat nog niet
    gekozen is; uit de andere helft als die helft leeg is; None als er niets is."""
    vrij = [g for g in lijst if g["uniek"] not in niet]
    deel = [g for g in vrij if not helft or (int(g["datum"][8:10]) <= 15) == (helft == 1)] or vrij
    return sorted(deel, key=lambda g: (g["datum"], g["start"]))[len(deel) // 2] if deel else None


def kies(gevallen, zoom):
    """[(rol, geval of None)] volgens ROLLEN, en de tekorten in woorden (zonder naam of onderwerp)."""
    werk = [g for g in gevallen if not GA.is_prive(g) and os.path.exists(os.path.join(g.get("map") or "-", "transcript.json"))]
    fathom = [g for g in werk if g["bron"] == "fathom" and os.path.exists(os.path.join(g["map"], "samenvatting.md"))]
    groepen = {"fathom zonder actiepunt": [g for g in fathom if not fathom_punten(g["map"])],
               "fathom met actiepunten": [g for g in fathom if fathom_punten(g["map"])],
               "plaud": [g for g in werk if g["bron"] == "plaud"], "zoom-tekst": zoom,
               "privé": [g for g in gevallen if GA.is_prive(g)]}
    gekozen, tekort, keuze = set(), [], []
    for rol, helft in ROLLEN:
        g = pak(groepen[rol], helft, gekozen)
        if g is None and rol.startswith("fathom"):
            g, rol = pak(fathom, helft, gekozen), "fathom"    # een ander Fathom-gesprek, onder zijn eigen naam
        if g is None:
            tekort.append(f"{rol}: geen gesprek" + (" met een samenvatting van Fathom (FATHOM-1 eerst)" if rol.startswith("fathom") else ""))
        else:
            gekozen.add(g["uniek"])
        keuze.append((rol, g))
    return keuze, tekort


def meet(rol, geval, budget, vraag=None):
    """De uitkomst van een gesprek, met de metingen; het record zelf gaat mee in het proefbestand."""
    begin = time.monotonic()
    rec, toestand = GA.verwerk(geval, budget, vraag)
    punten, weg = len((rec or {}).get("actiepunten") or []), int((rec or {}).get("weggegooid") or 0)
    uit = {"rol": rol, "bron": geval["bron"], "uniek": geval["uniek"], "datum": geval["datum"], "toestand": toestand,
           "duur_s": round(time.monotonic() - begin, 2), "tokens": int((rec or {}).get("tokens") or 0),
           "actiepunten": punten, "weggegooid": weg,
           "letterlijk_procent": round(100 * punten / (punten + weg)) if punten + weg else None, "record": rec}
    if rol == "privé" or (rec or {}).get("prive"):
        uit["alleen_privegesprek"] = bool(rec) and set(rec) == {"versie", "uniek", "bron", "datum", "start", "minuten",
                                                                  "prive", "regel", "ts"} and rec["regel"].startswith("privégesprek, ")
    return uit


def proef(maand, vraag=None, uitmap=None, nu=None):
    """Het pad van het proefbestand. vraag: in een test het nepmodel."""
    nu = nu or datetime.now().astimezone()
    uitmap = uitmap or os.path.join(GA.UITVOER, "proef")
    van, tot = f"{maand}-01", f"{maand}-31"
    rijen = [dict(r) for r in AR.db().execute("select * from gesprek_log where bron in ('fathom','plaud') and datum "
                                              "between ? and ? order by datum, start", (van, tot))]
    lijst, projecten = AR.afspraken(van, tot), bewaarde_projecten()
    keuze, tekort = kies([AR.geval_van(g, lijst, projecten) for g in rijen], GA.zoom_gevallen(van, tot))  # Fathom: archiefmap
    # de dagteller van de nachtronde en de eerdere proeven van vandaag tellen mee; de dagteller blijft ongemoeid
    budget = GA.Budget(nu.strftime("%Y-%m-%d"), teller=None, proefmap=uitmap)
    begin, voor = budget.vandaag, GA.weekbenutting()[0]
    gevallen = [meet(rol, g, budget, vraag) for rol, g in keuze if g]
    werk = [g for g in gevallen if g["record"] and not g["record"].get("prive")]
    punten, weg = sum(g["actiepunten"] for g in werk), sum(g["weggegooid"] for g in werk)
    if not any(not g["actiepunten"] for g in werk):
        tekort.append("geen werkgesprek zonder actiepunt in de uitkomst")
    uitslag = {"proef": "De Gespreksanalist, besluit X5 (T-0120)", "maand": maand, "ts": nu.isoformat(),
               "model_aan": GA.MODEL_AAN, "modelvragen": budget.vandaag - begin, "gekozen": len(gevallen), "tekort": tekort,
               "actiepunten": punten, "weggegooid": weg,
               "letterlijk_procent": round(100 * punten / (punten + weg)) if punten + weg else None,
               "zonder_actiepunt": any(not g["actiepunten"] for g in werk),
               "prive_alleen_regel": all(g.get("alleen_privegesprek", True) for g in gevallen),
               "tokens": sum(g["tokens"] for g in gevallen), "duur_s": round(sum(g["duur_s"] for g in gevallen), 2),
               "weekvenster_voor": voor, "weekvenster_na": GA.weekbenutting()[0], "gesprekken": gevallen}
    stam, n = os.path.join(uitmap, f"proef-{maand}-{nu.strftime('%Y%m%d-%H%M%S')}"), 1
    pad = stam + ".json"
    while os.path.exists(pad):                      # een tweede proef in dezelfde seconde overschrijft de eerste niet
        n += 1
        pad = f"{stam}-{n}.json"
    return GA.schrijf_600(pad, uitslag), uitslag


def main():
    maand = sys.argv[sys.argv.index("--maand") + 1] if "--maand" in sys.argv else "2026-10"
    pad, u = proef(maand)
    print(f"proefbestand: {pad}")
    print(f"{u['gekozen']} gesprekken, {u['actiepunten']} actiepunten, {u['weggegooid']} weggegooid, "
          f"letterlijk {u['letterlijk_procent']} procent, {u['tokens']} tokens, {u['duur_s']} s; tekort: {len(u['tekort'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
