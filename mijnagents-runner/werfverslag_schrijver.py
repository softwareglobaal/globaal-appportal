#!/usr/bin/env python3
"""Werfverslag schrijver (H-Architects) — schrijft de voorbereiding en de proef van een werfverslag.

Hij werkt alleen op opdracht: van Werfverslag voorbereider (na verificatie: "voorbereid <dossier> <bezoek>")
of van Mehdi via de bezoekpagina ("voorbereid ..." of "proef ..."). Hij leest de bezoekmap, haalt de
gegevens eruit met bron en zekerheid, en schrijft het concept in het eigen sjabloon (Word + markdown)
in de bezoekmap. Hij verstuurt nooit en overschrijft nooit.

Gebruik:
    werfverslag_schrijver.py --opdrachten          # cron elke 5 min: opdrachten uit de bak uitvoeren
    werfverslag_schrijver.py --voorbereid 2309 1   # handmatig
    werfverslag_schrijver.py --proef 2309 1
"""
import argparse
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import werfverslag_proef as wp  # noqa: E402

NAAM = "werfverslag-schrijver"
ag = bord.Agent(NAAM)


def opdrachten():
    items = [it for it in bord.klaargezet_voor(NAAM, n=30) if it.get("soort") == "opdracht"]
    if not items:
        ag.hartslag("waakt", taak="wacht op opdrachten", detail="van Werfverslag voorbereider of van de bezoekpagina")
        return 0
    ag.hartslag("actief", taak=f"{len(items)} opdracht(en)")
    gedaan, fouten = 0, 0
    for it in reversed(items):
        m = re.match(r"(voorbereid|proef)\s+(\d{4})\s+(\d+)", it.get("titel", ""))
        # Regel van Mehdi (13-09-2026): alleen opdrachten van de knop op het bord (van = bord:<gebruiker>);
        # een opdracht van een agent voer ik niet uit, want elke stap kost tokens.
        if not m or not str(it.get("van", "")).startswith("bord:"):
            ag.log(it.get("sleutel", "?"), "besluit", f"opdracht overgeslagen (niet van de knop): {it.get('titel','')} van {it.get('van','')}")
            bord.opgepakt(it["id"], NAAM)
            continue
        soort, d, n = m.group(1), m.group(2), int(m.group(3))
        try:
            if soort == "voorbereid":
                wp.voorbereid(ag, d, n)
            else:
                wp.proef(ag, d, n)
            gedaan += 1
        except Exception as e:  # noqa: BLE001
            fouten += 1
            ag.log(f"{d}-{n}", "fout", f"{soort} mislukt: {type(e).__name__}: {str(e)[:300]}")
        bord.opgepakt(it["id"], NAAM)
        ag.log_verstuur()
    ag.hartslag("klaar" if not fouten else "fout", taak=f"{gedaan} opdracht(en) uitgevoerd, {fouten} mislukt",
                detail="voorbereiding of proef; bewijs in het werkverslag en op de bezoekpagina")
    return gedaan


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--opdrachten", action="store_true")
    p.add_argument("--voorbereid", nargs=2, metavar=("DOSSIER", "BEZOEK"))
    p.add_argument("--proef", nargs=2, metavar=("DOSSIER", "BEZOEK"))
    p.add_argument("--herlayout", nargs=2, metavar=("DOSSIER", "BEZOEK"), help="Word opnieuw opmaken uit de bewaarde proef, zonder Claude")
    a = p.parse_args()
    if a.opdrachten:
        print("opdrachten:", opdrachten())
        return
    if a.herlayout:
        d, n = a.herlayout
        ag.hartslag("actief", taak=f"nieuwe opmaak {d}-{n}")
        try:
            print(wp.herlayout(ag, d, int(n)))
            ag.hartslag("klaar", taak=f"nieuwe opmaak {d}-{n} klaar")
        finally:
            ag.log_verstuur()
        return
    if a.voorbereid or a.proef:
        d, n = a.voorbereid or a.proef
        wat = "voorbereiding" if a.voorbereid else "proef"
        ag.hartslag("actief", taak=f"{wat} {d}-{n}")
        try:
            uit = wp.voorbereid(ag, d, int(n)) if a.voorbereid else wp.proef(ag, d, int(n))
            print(json.dumps(uit, ensure_ascii=False, indent=1) if a.voorbereid else uit[0])
            ag.hartslag("klaar", taak=f"{wat} {d}-{n} klaar")
        except Exception as e:
            ag.log(f"{d}-{n}", "fout", f"{type(e).__name__}: {str(e)[:300]}")
            ag.hartslag("fout", taak=f"{d}-{n} mislukt", detail=str(e)[:200])
            raise
        finally:
            ag.log_verstuur()
        return
    p.print_help()


if __name__ == "__main__":
    main()
