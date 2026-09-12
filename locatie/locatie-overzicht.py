#!/usr/bin/env python3
"""
locatie-overzicht.py - vat het locatielogboek samen over een periode.

Leest de dagboeken die locatie-ophalen.py in Dropbox heeft gezet. Werkt dus
zonder verbinding met de VM: wat er in Dropbox staat is de bron.

Gebruik:
    locatie-overzicht.py                 alles wat er is
    locatie-overzicht.py --van 2026-09-10
    locatie-overzicht.py --van 2026-09-01 --tot 2026-09-30
    locatie-overzicht.py --plek Thuis    alleen de dagen met die plek
"""
import argparse
import glob
import json
import os
from collections import defaultdict
from datetime import datetime

DAGEN = os.path.expanduser(
    "~/TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude/"
    "Locatielogboek/dagen")

NL_WIJZE = {"automotive": "auto", "walking": "te voet", "cycling": "fiets",
            "running": "lopend"}


def duur(minuten):
    u, m = divmod(int(minuten), 60)
    return f"{u}u{m:02d}" if u else f"{m} min"


def main():
    p = argparse.ArgumentParser(description="Samenvatting van het locatielogboek")
    p.add_argument("--van")
    p.add_argument("--tot")
    p.add_argument("--plek", help="alleen dagen waarop je hier was")
    a = p.parse_args()

    bestanden = sorted(glob.glob(os.path.join(DAGEN, "*.json")))
    if a.van:
        bestanden = [b for b in bestanden if os.path.basename(b)[:10] >= a.van]
    if a.tot:
        bestanden = [b for b in bestanden if os.path.basename(b)[:10] <= a.tot]
    if not bestanden:
        raise SystemExit("Geen dagboeken gevonden in " + DAGEN)

    per_plek = defaultdict(lambda: {"min": 0, "keer": 0, "dagen": set(),
                                    "dossier": None})
    per_wijze = defaultdict(float)
    rijen = []
    tot = {"km": 0.0, "bez": 0, "rit": 0, "pnt": 0}

    for b in bestanden:
        dag = os.path.basename(b)[:10]
        d = json.load(open(b, encoding="utf-8"))
        ind = d.get("indeling", [])
        bez = [s for s in ind if s["soort"] == "bezoek"]
        rit = [s for s in ind if s["soort"] == "verplaatsing"]

        if a.plek and not any(s.get("plek") == a.plek for s in bez):
            continue

        km = sum(s.get("meter", 0) for s in rit) / 1000
        punten = d.get("punten", [])
        zwijg = sum(s["minuten"] for s in ind if s["soort"] == "gat")
        tot["gat"] = tot.get("gat", 0) + zwijg
        rijen.append((dag, len(bez), len(rit), km, len(punten), duur(zwijg) if zwijg else "-"))
        tot["km"] += km; tot["bez"] += len(bez)
        tot["rit"] += len(rit); tot["pnt"] += len(punten)

        for s in bez:
            naam = s.get("plek") or "(naamloos)"
            per_plek[naam]["min"] += s["minuten"]
            per_plek[naam]["keer"] += 1
            per_plek[naam]["dagen"].add(dag)
            if s.get("dossier"):
                per_plek[naam]["dossier"] = s["dossier"]
        for s in rit:
            # Eén wijze per rit: de app levert de dominante. Zou hier een lijst
            # binnenkomen (oudere dagboeken), dan telt de eerste, want delen
            # schrijft kilometers op de verkeerde wijze.
            w = (s.get("wijze") or "").split(",")[0].strip()
            if w:
                per_wijze[w] += s.get("meter", 0) / 1000

    breed = 68
    print("PERIODEOVERZICHT  %s t/m %s" % (rijen[0][0], rijen[-1][0]))
    print("=" * breed)
    print()
    print("%-13s %8s %8s %9s %9s %11s" % ("dag", "bezoeken", "ritten", "km",
                                          "punten", "zonder meet"))
    print("-" * breed)
    for r in rijen:
        print("%-13s %8d %8d %9.1f %9d %11s" % r)
    print("-" * breed)
    print("%-13s %8d %8d %9.1f %9d %11s" % ("TOTAAL", tot["bez"], tot["rit"],
                                            tot["km"], tot["pnt"],
                                            duur(tot.get("gat", 0)) if tot.get("gat") else "-"))
    print()

    print("WAAR JE TIJD NAARTOE GING")
    print("-" * breed)
    print("%-30s %6s %8s %10s" % ("plek", "keer", "dagen", "tijd"))
    for naam, v in sorted(per_plek.items(), key=lambda x: -x[1]["min"]):
        etiket = naam if not v["dossier"] else f"{naam} [{v['dossier']}]"
        print("%-30s %6d %8d %10s" % (etiket[:30], v["keer"], len(v["dagen"]),
                                      duur(v["min"])))
    print()

    print("AFSTAND PER VERVOERSWIJZE")
    print("-" * breed)
    for w, km in sorted(per_wijze.items(), key=lambda x: -x[1]):
        print("%-30s %8.1f km" % (NL_WIJZE.get(w, w), km))


if __name__ == "__main__":
    main()
