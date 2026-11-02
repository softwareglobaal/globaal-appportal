#!/usr/bin/env python3
"""Eenmalig (T-0154, overleg 02-11-2026 X2, 3-0): de samenvatting en de actiepunten van Fathom bijschrijven bij de
gesprekken die al in het archief staan. Tot 02-11-2026 vroeg De Fathomwacht ze niet op (koppelingen/fathom.py gaf
alleen include_transcript mee), en bewaar() slaat een gesprek dat al een map heeft over. Schrijft per gesprek alleen
samenvatting.md, actiepunten.md en de twee velden default_summary en action_items in gesprek.json; de herkenning en al
het andere blijven staan. Nooit in Dropbox, alleen in het archief op de VM (mijnagents-data/fathom-data).

    fathom_samenvatting_inhalen.py --droog               alleen tellen, niets schrijven
    fathom_samenvatting_inhalen.py --een                 het eerste gesprek dat iets mist bijwerken, dan stoppen (de proef)
    fathom_samenvatting_inhalen.py [--van 2026-10-01] [--tot 2026-11-03]

Draait op de VM met dezelfde omgeving als De Fathomwacht (~/agents/.venv, sleutels uit ~/agents/.env). Alleen aantallen
op de uitvoer, nooit namen of inhoud.
"""
import argparse
import os
import sys
import time
from datetime import date, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import fathom  # noqa: E402
import fathom_wacht as FW  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--van", default="2026-10-01")
    p.add_argument("--tot", default=(date.today() + timedelta(days=1)).isoformat())
    p.add_argument("--droog", action="store_true")
    p.add_argument("--een", action="store_true")
    a = p.parse_args()
    if not fathom.beschikbaar():
        print("geen Fathom-sleutel in de omgeving")
        return 2
    gesprekken = fathom.gesprekken(f"{a.van}T00:00:00Z", met_transcript=False, tot_iso=f"{a.tot}T00:00:00Z")
    tel = {"gezien": 0, "zonder_map": 0, "met_samenvatting": 0, "niets_nieuws": 0, "bijgewerkt": 0}
    for g in gesprekken:
        tel["gezien"] += 1
        if not fathom.samenvatting_md(g).strip() and not g.get("action_items"):
            continue
        tel["met_samenvatting"] += 1
        map_ = FW.bestaande_map(g)
        if not map_:
            tel["zonder_map"] += 1
            continue
        if a.droog:
            tel["bijgewerkt"] += 1
            continue
        if FW.samenvatting_aanvullen(map_, g):
            tel["bijgewerkt"] += 1
            if a.een:
                break
            time.sleep(0.05)
        else:
            tel["niets_nieuws"] += 1
    print(("droog: zou bijwerken " if a.droog else "bijgewerkt ") + ", ".join(f"{k} {v}" for k, v in tel.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
