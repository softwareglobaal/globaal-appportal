#!/usr/bin/env python3
"""Zet de planning van De Plaudwacht op de VM uit planning/plaud.cron (verbeteropdracht v1.0).

Vervangt alleen het beheerde blok tussen de merktekens en de ene oude, onbeheerde regel die
plaud_wacht.py zonder slot en tijdslimiet startte. Elke andere regel blijft staan. Zonder --zet
toont het alleen wat het zou doen; het toont nooit andere regels (die kunnen geheimen bevatten).
"""
import argparse
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BEGIN = "# >>> plaud (beheerd vanuit mijnagents-runner/planning/plaud.cron)"
EINDE = "# <<< plaud"
OUDE_REGEL = ("20 * * * * /home/ubuntu/agents/.venv/bin/python /home/ubuntu/appportal/mijnagents-runner/plaud_wacht.py "
              ">> /home/ubuntu/agents/plaud_wacht.log 2>&1")


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
        if regel.strip() == OUDE_REGEL:
            oud += 1
            continue
        if "mijnagents-runner/plaud_wacht.py" in regel:
            raise ValueError("onbekende planning van plaud_wacht.py buiten het blok; eerst beoordelen")
        uit.append(regel)
    if binnen:
        raise ValueError("beginmarker zonder eindmarker")
    while uit and not uit[-1].strip():
        uit.pop()
    return uit + [""] + [BEGIN] + [r for r in regels if r.strip() and not r.startswith("#")] + [EINDE], oud


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--zet", action="store_true")
    a = p.parse_args()
    meting = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if meting.returncode and "no crontab" not in meting.stderr.lower():
        raise RuntimeError("huidige crontab niet leesbaar")
    huidig = meting.stdout.splitlines()
    regels = open(os.path.join(HIER, "plaud.cron"), encoding="utf-8").read().splitlines()
    doel, oud = samenvoegen(huidig, regels)
    print("planning wijzigen" if huidig != doel else "planning al gelijk", f"(oude regel vervangen: {oud})")
    print("\n".join([BEGIN] + [r for r in regels if r.strip() and not r.startswith("#")] + [EINDE]))
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
