#!/usr/bin/env python3
"""Beheer alleen het crontab-blok voor de terugkijktaken van De Agendawacht.

Zonder --zet toon ik alleen mijn eigen blok. Andere regels blijven bij zetten intact
en verschijnen nooit in de uitvoer: daarin kunnen geheimen staan.
"""
import argparse
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BEGIN = "# >>> agenda-terugkijken (beheerd vanuit mijnagents-runner/planning/agenda-terugkijken.cron)"
EINDE = "# <<< agenda-terugkijken"


def samenvoegen(huidig, regels):
    uit, binnen, gevonden = [], False, False
    for regel in huidig:
        if regel == BEGIN:
            if binnen or gevonden:
                raise ValueError("dubbele beginmarker voor agenda-terugkijken")
            binnen, gevonden = True, True
            continue
        if regel == EINDE:
            if not binnen:
                raise ValueError("eindmarker zonder beginmarker voor agenda-terugkijken")
            binnen = False
            continue
        if not binnen:
            if "agenda_wacht.py --taken" in regel and not regel.lstrip().startswith("#"):
                raise ValueError("onbekende agenda-terugkijkplanning buiten het eigen blok; eerst beoordelen")
            uit.append(regel)
    if binnen:
        raise ValueError("beginmarker zonder eindmarker voor agenda-terugkijken")
    return uit + ([""] if uit and uit[-1].strip() else []) + [BEGIN] + regels + [EINDE]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--zet", action="store_true")
    a = p.parse_args(argv)
    meting = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if meting.returncode and "no crontab" not in meting.stderr.lower():
        raise RuntimeError("huidige crontab niet leesbaar")
    huidig = meting.stdout.splitlines()
    with open(os.path.join(HIER, "agenda-terugkijken.cron"), encoding="utf-8") as bron:
        regels = [r for r in bron.read().splitlines() if r.strip() and not r.startswith("#")]
    if len(regels) != 1:
        raise ValueError("agenda-terugkijken.cron moet precies één planningsregel hebben")
    doel = samenvoegen(huidig, regels)
    print("planning wijzigen" if huidig != doel else "planning al gelijk")
    print("\n".join([BEGIN] + regels + [EINDE]))
    if not a.zet or huidig == doel:
        return 0
    r = subprocess.run(["crontab", "-"], input="\n".join(doel) + "\n", text=True)
    if r.returncode:
        raise RuntimeError("crontab niet gezet")
    na = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines()
    if na != doel:
        raise RuntimeError("crontab na het zetten wijkt af")
    print("gezet en nagelezen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
