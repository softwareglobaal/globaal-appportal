#!/usr/bin/env python3
"""Zet de planning van de gesprekkenketen op de VM uit planning/gesprekken.cron (ontwerp regie-zoom v1.2, Z16).

Vervangt alleen het beheerde blok tussen de merktekens en precies de drie oude, onbeheerde regels die De Dagbundelaar
(07:00 op werkdagen), De Fathomwacht (07:00 en 13:00) en De Zoomwacht (07:15 en 13:15) los startten, zonder slot en
zonder vaste volgorde (crontab-regels 57, 58 en 98, gemeten op 21-10-2026). Staat er nog een andere regel met een van
die runners of met keten.py, dan weigert het: eerst beoordelen. Elke andere regel blijft staan. Zonder --zet toont het
alleen het eigen blok; het toont nooit andere regels (die kunnen geheimen bevatten). Na het zetten leest het terug.
"""
import argparse
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BEGIN = "# begin gesprekken (beheerd door planning/gesprekken_cron_zetten.py)"
EINDE = "# einde gesprekken"
# De drie oude regels: (tijd, runner). Ze startten met de venv-python en schreven naar hun eigen logboek.
OUDE_REGELS = {("0 7 * * 1-5", "dagbundelaar"), ("0 7,13 * * *", "fathom_wacht"), ("15 7,13 * * *", "zoom_wacht")}
OUD = re.compile(r"^(?P<tijd>\S+ \S+ \S+ \S+ \S+) \S*python3? /home/ubuntu/appportal/mijnagents-runner/(?P<runner>\w+)\.py"
                 r"(?: >> ?\S+ 2>&1)?$")
RUNNERS = ("dagbundelaar.py", "fathom_wacht.py", "zoom_wacht.py", "keten.py")


def blok(regels):
    """Het beheerde blok: de merktekens, de regel met de tijden in UTC en Brussel, en de cronregels zelf."""
    tijden = [r for r in regels if r.startswith("# 07:00 UTC")][:1]
    return [BEGIN] + tijden + [r for r in regels if r.strip() and not r.startswith("#")] + [EINDE]


def samenvoegen(huidig, regels):
    uit, binnen, oud = [], False, 0
    for regel in huidig:
        if regel == BEGIN:
            if binnen:
                raise ValueError("dubbele beginmarker")
            binnen = True
            continue
        if regel == EINDE:
            if not binnen:
                raise ValueError("eindmarker zonder beginmarker")
            binnen = False
            continue
        if binnen:
            continue
        m = OUD.match(regel.strip())
        if m and (m.group("tijd"), m.group("runner")) in OUDE_REGELS:
            oud += 1
            continue
        if not regel.lstrip().startswith("#"):
            for runner in RUNNERS:
                if f"mijnagents-runner/{runner}" in regel:
                    raise ValueError(f"onbekende planning van {runner} buiten het blok; eerst beoordelen")
        uit.append(regel)
    if binnen:
        raise ValueError("beginmarker zonder eindmarker")
    while uit and not uit[-1].strip():
        uit.pop()
    return uit + [""] + blok(regels), oud


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--zet", action="store_true")
    a = p.parse_args()
    meting = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if meting.returncode and "no crontab" not in meting.stderr.lower():
        raise RuntimeError("huidige crontab niet leesbaar")
    huidig = meting.stdout.splitlines()
    regels = open(os.path.join(HIER, "gesprekken.cron"), encoding="utf-8").read().splitlines()
    doel, oud = samenvoegen(huidig, regels)
    print("planning wijzigen" if huidig != doel else "planning al gelijk", f"(oude regels vervangen: {oud})")
    print("\n".join(blok(regels)))
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
