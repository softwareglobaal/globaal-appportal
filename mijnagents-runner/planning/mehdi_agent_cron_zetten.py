#!/usr/bin/env python3
"""Zet de planning van De Mehdi-agent op de VM uit planning/mehdi-agent.cron.

Vervangt alleen het beheerde blok tussen de merktekens; elke andere regel blijft staan. Een regel voor mehdi_agent.py
buiten het blok is onbekend en wordt eerst beoordeeld, nooit stil overschreven. Zonder --zet toont het alleen wat het
zou doen; het toont nooit andere regels (die kunnen geheimen bevatten). Zelfde opbouw als plaud_cron_zetten.py.
"""
import argparse
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BEGIN = "# >>> mehdi-agent (beheerd vanuit mijnagents-runner/planning/mehdi-agent.cron)"
EINDE = "# <<< mehdi-agent"


def blok(regels):
    return [BEGIN] + [r for r in regels if r.strip() and not r.startswith("#")] + [EINDE]


def samenvoegen(huidig, regels):
    uit, binnen = [], False
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
        if "mijnagents-runner/mehdi_agent.py" in regel:
            raise ValueError("onbekende planning van mehdi_agent.py buiten het blok; eerst beoordelen")
        uit.append(regel)
    if binnen:
        raise ValueError("beginmarker zonder eindmarker")
    while uit and not uit[-1].strip():
        uit.pop()
    return uit + [""] + blok(regels)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--zet", action="store_true")
    a = p.parse_args()
    meting = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if meting.returncode and "no crontab" not in meting.stderr.lower():
        raise RuntimeError("huidige crontab niet leesbaar")
    huidig = meting.stdout.splitlines()
    regels = open(os.path.join(HIER, "mehdi-agent.cron"), encoding="utf-8").read().splitlines()
    doel = samenvoegen(huidig, regels)
    print("planning wijzigen" if huidig != doel else "planning al gelijk")
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
