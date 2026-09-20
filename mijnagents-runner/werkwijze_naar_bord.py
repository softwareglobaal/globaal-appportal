#!/usr/bin/env python3
"""Een werkwijze uit werkwijze/<naam>.md naar het bord zetten.

Het bord is de waarheid (norm N6). Het bestand in werkwijze/ is het zaad: de
eerste versie, en daarna een kopie die kan verouderen. Dit is het gereedschap om
ze weer gelijk te zetten wanneer de repo de nieuwere tekst heeft, bijvoorbeeld
nadat Claude Code een werkwijze heeft uitgebreid.

    werkwijze_naar_bord.py ontwikkelaar            toont het verschil, schrijft niets
    werkwijze_naar_bord.py ontwikkelaar --zet      zet het zaad op het bord
    werkwijze_naar_bord.py --verschillen           welke agents lopen uit elkaar

Schrijft nooit zonder --zet. Wie het bord overschrijft, gooit weg wat Mehdi daar
misschien zelf heeft bijgewerkt: kijk dus altijd eerst naar het verschil.
"""
import argparse
import difflib
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402


def zaadpad(naam):
    return os.path.join(HIER, "werkwijze", f"{naam}.md")


def genormaliseerd(s):
    return "\n".join(r.rstrip() for r in (s or "").strip().splitlines())


def haal_bord(naam):
    return bord.call(f"/api/agent/{naam}/werkwijze").get("werkwijze") or ""


def agents():
    return [a["naam"] for a in bord.call("/api/overzicht").get("agents", [])]


def verschil(naam, toon=True):
    p = zaadpad(naam)
    if not os.path.exists(p):
        return None
    zaad = genormaliseerd(open(p, encoding="utf-8").read())
    opbord = genormaliseerd(haal_bord(naam))
    if zaad == opbord:
        return False
    if toon:
        for regel in difflib.unified_diff(opbord.splitlines(), zaad.splitlines(),
                                          fromfile=f"{naam} op het bord", tofile=f"{naam} in de repo",
                                          lineterm="", n=1):
            print(regel)
    return True


def zet(naam):
    tekst = open(zaadpad(naam), encoding="utf-8").read()
    uit = bord.call(f"/api/agent/{naam}/werkwijze", {"werkwijze": tekst, "overschrijf": True})
    return uit.get("ok"), uit.get("reden", "")


def main():
    p = argparse.ArgumentParser(description="Zet een werkwijze uit de repo op het bord.")
    p.add_argument("naam", nargs="?")
    p.add_argument("--zet", action="store_true", help="schrijven; zonder dit toont hij alleen het verschil")
    p.add_argument("--verschillen", action="store_true", help="welke agents lopen uit elkaar")
    a = p.parse_args()

    if a.verschillen:
        uit_elkaar = [n for n in agents() if verschil(n, toon=False)]
        print("\n".join(uit_elkaar) if uit_elkaar else "Alle werkwijzen zijn gelijk aan het bord.")
        return 0 if not uit_elkaar else 1

    if not a.naam:
        p.error("geef een agentnaam, of gebruik --verschillen")
    if not os.path.exists(zaadpad(a.naam)):
        print(f"geen zaad gevonden: {zaadpad(a.naam)}", file=sys.stderr)
        return 2

    anders = verschil(a.naam)
    if not anders:
        print(f"{a.naam}: zaad en bord zijn al gelijk.")
        return 0
    if not a.zet:
        print(f"\n{a.naam}: het bovenstaande zou naar het bord gaan. Draai met --zet om het te doen.")
        return 1
    ok, reden = zet(a.naam)
    print(f"{a.naam}: op het bord gezet." if ok else f"{a.naam}: niet gezet, {reden}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
