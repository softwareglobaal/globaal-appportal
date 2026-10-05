#!/usr/bin/env python3
"""Registreer twee controleagents en voeg alleen hun beheerde planning toe."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord

BEGIN = "# >>> naamstructuur (beheerd vanuit mijnagents-runner/planning/naamstructuur.cron)"
EINDE = "# <<< naamstructuur"


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
        if not binnen:
            # Buiten ons eigen blok nooit een bestaande regel verwijderen.
            if "mijnagents-runner/benamingen_wacht.py" in regel or "mijnagents-runner/mappen_wacht.py" in regel:
                raise ValueError("bestaande planning buiten beheerd blok; eerst samenvoegen beoordelen")
            uit.append(regel)
    if binnen:
        raise ValueError("beginmarker zonder eindmarker")
    while uit and not uit[-1].strip():
        uit.pop()
    return uit + [""] + [BEGIN] + [r for r in regels if r.strip() and not r.startswith("#")] + [EINDE]


def registreer():
    bestaand = {a["naam"]: a for a in bord.call("/api/agents")}
    for naam, label, rol, levert in (
        ("benamingen-wacht", "Benamingenwacht", "controleert namen en deelt bronbewijs met Mappenwacht", "mappen-wacht"),
        ("mappen-wacht", "Mappenwacht", "controleert folderstructuur op dezelfde bronindex", "benamingen-wacht")):
        zaad = open(os.path.join(RUNNER, "werkwijze", naam + ".md"), encoding="utf-8").read()
        huidige = bord.call(f"/api/agent/{naam}/werkwijze").get("werkwijze", "") if naam in bestaand else ""
        if huidige and huidige.strip() != zaad.strip():
            raise ValueError("werkwijze op bord wijkt af; bestaande bron wordt niet overschreven")
        bord.call("/api/agent", {"naam": naam, "label": label, "type": "regie", "rol": rol,
                  "mandaat": "namen en structuur alleen controleren binnen bestaande bronrechten",
                  "cadans": "elk kwartier, dagelijks dekkingscontrole", "eigenaar": "mehdi",
                  "mag": ["cloudmetadata lezen", "brongebonden controlevoorstellen bijhouden"],
                  "grenzen": ["nooit hernoemen, verplaatsen of verwijderen", "geen externe berichten of extra leesrechten"],
                  "tools": ["Dropbox metadata lezen", "bestaande agenda- en gespreksindex", "gedeeld overzicht /naamstructuur"],
                  "prive": True, "levert_aan": [levert], "draait_op": "VM"})
        if not huidige:
            antwoord = bord.call(f"/api/agent/{naam}/werkwijze", {"werkwijze": zaad})
            if not antwoord.get("ok"):
                raise RuntimeError("werkwijze niet geregistreerd")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--zet", action="store_true")
    a = p.parse_args()
    meting = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if meting.returncode and "no crontab" not in meting.stderr.lower():
        raise RuntimeError("huidige crontab niet leesbaar")
    huidig = meting.stdout.splitlines()
    regels = open(os.path.join(HIER, "naamstructuur.cron"), encoding="utf-8").read().splitlines()
    doel = samenvoegen(huidig, regels)
    verschil = huidig != doel
    # Bestaande cronregels kunnen geheimen bevatten; toon uitsluitend ons eigen blok.
    print("planning wijzigen" if verschil else "planning al gelijk")
    print("\\n".join([BEGIN] + [r for r in regels if r.strip() and not r.startswith("#")] + [EINDE]))
    if not a.zet:
        print("Registratie en planning worden pas met --zet toegepast.")
        return 0
    registreer()
    if verschil:
        map_ = os.path.expanduser("~/agents")
        os.makedirs(map_, exist_ok=True)
        pad = os.path.join(map_, "crontab-voor-naamstructuur-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".txt")
        with open(pad, "x", encoding="utf-8") as f:
            f.write(meting.stdout)
        subprocess.run(["crontab", "-"], input="\n".join(doel) + "\n", text=True, check=True)
    print("Twee controleagents geregistreerd; planning gezet. Geen bestanden in Dropbox gewijzigd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
