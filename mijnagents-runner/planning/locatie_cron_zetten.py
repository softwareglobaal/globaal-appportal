#!/usr/bin/env python3
"""Zet de planning van het Locatielogboek in de crontab van de VM.

Vervangt alleen het blok tussen de merktekens, en de oude regels van De
Locatiewacht (die met 21:30 UTC en 'om de twee uur'). De rest van de crontab blijft
staan. Eerst kijken, dan zetten:

    python3 ~/appportal/mijnagents-runner/planning/locatie_cron_zetten.py         toont het verschil
    python3 ~/appportal/mijnagents-runner/planning/locatie_cron_zetten.py --zet   zet het, met een kopie

De kopie van de vorige crontab komt in ~/agents/crontab-voor-locatie-<tijd>.txt.
"""
import difflib
import os
import subprocess
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
BEGIN = "# >>> locatielogboek (beheerd vanuit mijnagents-runner/planning/locatie.cron)"
EINDE = "# <<< locatielogboek"


def nieuw_blok():
    regels = [r for r in open(os.path.join(HIER, "locatie.cron"), encoding="utf-8").read().splitlines()
              if r.strip() and not r.startswith("#")]
    return [BEGIN] + regels + [EINDE]


def samenvoegen(huidig):
    uit, binnen = [], False
    for r in huidig:
        if r == BEGIN:
            binnen = True
            continue
        if r == EINDE:
            binnen = False
            continue
        if binnen or "mijnagents-runner/locatie_wacht.py" in r or "projectsync.py" in r:
            continue
        uit.append(r)
    while uit and not uit[-1].strip():
        uit.pop()
    return uit + [""] + nieuw_blok()


def main():
    huidig = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines()
    doel = samenvoegen(huidig)
    verschil = list(difflib.unified_diff(huidig, doel, "crontab nu", "crontab straks", lineterm=""))
    print("\n".join(verschil) or "geen verschil")
    if "--zet" in sys.argv and verschil:
        kopie = os.path.expanduser("~/agents/crontab-voor-locatie-%s.txt" % time.strftime("%Y%m%dT%H%M%S"))
        open(kopie, "w").write("\n".join(huidig) + "\n")
        subprocess.run(["crontab", "-"], input="\n".join(doel) + "\n", text=True, check=True)
        print("gezet; vorige crontab in", kopie)
    return 0


if __name__ == "__main__":
    sys.exit(main())
