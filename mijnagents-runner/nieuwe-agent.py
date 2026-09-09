#!/usr/bin/env python3
"""nieuwe-agent.py — de generator van Mehdi's agent-omgeving.

Maakt in één keer een nieuwe agent: registreert hem op het bord
(mijnagents.globaal.be) en schrijft een runner-skelet met de hartslag al
ingebouwd. Daarna hoef je alleen werk() in te vullen en de cron-regel toe te
voegen die het script afdrukt.

Gebruik interactief:
    python3 nieuwe-agent.py

Of niet-interactief met vlaggen (voor scripting / vanuit een Claude-sessie):
    python3 nieuwe-agent.py --naam post-wacht --label "Postwacht" \
        --type post --rol "sorteert nieuwe post op info@" \
        --cadans "elk uur" --mag "post labelen" --grens "nooit verwijderen" \
        --tool "gmail lezen" --tool "labels zetten"

Registreren gaat token-gated naar de app; het token komt uit
~/appportal/mijnagents-data/.env (AGENTS_TOKEN), nooit uit een argument.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
SJABLOON = os.path.join(HIER, "_sjabloon_agent.py")
POORT = os.environ.get("MIJNAGENTS_PORT", "3022")
PLATFORM = os.environ.get("PLATFORM_URL", f"http://127.0.0.1:{POORT}")


def env(pad):
    pad = os.path.expanduser(pad)
    if not os.path.exists(pad):
        return
    for regel in open(pad):
        regel = regel.strip()
        if regel and not regel.startswith("#") and "=" in regel:
            k, v = regel.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def vraag(tekst, verplicht=True):
    while True:
        a = input(tekst).strip()
        if a or not verplicht:
            return a
        print("  (verplicht)")


def vraag_lijst(tekst):
    print(tekst + " (leeg = klaar)")
    uit = []
    while True:
        a = input("  - ").strip()
        if not a:
            return uit
        uit.append(a)


def registreer(agent, token):
    req = urllib.request.Request(
        f"{PLATFORM}/api/agent",
        data=json.dumps(agent).encode(),
        headers={"Content-Type": "application/json", "X-Agents-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def schrijf_runner(naam):
    doel = os.path.join(HIER, f"{naam.replace('-', '_')}.py")
    if os.path.exists(doel):
        print(f"LET OP: {doel} bestaat al — niet overschreven.")
        return doel
    sjab = open(SJABLOON).read()
    sjab = sjab.replace("%%NAAM%%", naam).replace("%%POORT%%", POORT)
    # %%LABEL%% vervangen we door de naam als placeholder-koptekst; de echte
    # label staat in de registratie.
    sjab = sjab.replace("%%LABEL%%", naam)
    with open(doel, "w") as f:
        f.write(sjab)
    os.chmod(doel, 0o755)
    return doel


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--naam"); p.add_argument("--label"); p.add_argument("--type", default="")
    p.add_argument("--rol", default=""); p.add_argument("--mandaat", default="")
    p.add_argument("--cadans", default=""); p.add_argument("--eigenaar", default="mehdi")
    p.add_argument("--mag", action="append", default=[])
    p.add_argument("--grens", action="append", default=[])
    p.add_argument("--tool", action="append", default=[])
    p.add_argument("--cron", default="0 * * * *", help="cron-schema voor de runner")
    p.add_argument("--werkwijze", help="markdown-bestand met het volledige proces (komt op het bord, daar bewerkbaar)")
    a = p.parse_args()

    env("~/appportal/mijnagents-data/.env")
    token = os.environ.get("AGENTS_TOKEN", "")
    if not token:
        print("Geen AGENTS_TOKEN gevonden in ~/appportal/mijnagents-data/.env.")
        print("Zet die eerst (zie README) — registreren kan niet zonder.")
        sys.exit(1)

    if a.naam and a.label:
        agent = dict(naam=a.naam, label=a.label, type=a.type, rol=a.rol,
                     mandaat=a.mandaat, mag=a.mag, grenzen=a.grens, cadans=a.cadans,
                     tools=a.tool, eigenaar=a.eigenaar)
        cron = a.cron
    else:
        print("== Nieuwe agent ==")
        naam = vraag("naam (kort, kleine letters, met koppelteken): ")
        naam = re.sub(r"[^a-z0-9-]", "-", naam.lower()).strip("-")
        agent = dict(
            naam=naam,
            label=vraag("label (weergavenaam): "),
            type=vraag("type (groepering op het bord, bv. post/onderhoud): ", False),
            rol=vraag("rol (een regel: wat doet hij): "),
            mandaat=vraag("mandaat (wat doet hij en voor wie): ", False),
            mag=vraag_lijst("mag zelfstandig"),
            grenzen=vraag_lijst("grenzen (doet nooit)"),
            cadans=vraag("cadans (hoe vaak / wanneer): ", False),
            tools=vraag_lijst("gereedschap (de echte tools)"),
            eigenaar="mehdi",
        )
        cron = vraag("cron-schema voor de runner [0 * * * *]: ", False) or "0 * * * *"

    uit = registreer(agent, token)
    naam = uit["naam"]
    print(f"\nGeregistreerd op het bord: {naam}")

    if a.werkwijze:
        tekst = open(os.path.expanduser(a.werkwijze), encoding="utf-8").read()
        req = urllib.request.Request(f"{PLATFORM}/api/agent/{naam}/werkwijze",
                                     data=json.dumps({"werkwijze": tekst}).encode(),
                                     headers={"Content-Type": "application/json", "X-Agents-Token": token},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            w = json.loads(r.read())
        print("Werkwijze op het bord gezet." if w.get("ok") else f"Werkwijze niet gezet: {w.get('reden')}")

    runner = schrijf_runner(naam)
    print(f"Runner-skelet: {runner}")
    print("  -> vul werk() in met wat de agent echt doet.\n")

    venv = "~/agents/.venv/bin/python"
    print("Voeg deze cron-regel toe (crontab -e) zodat hij draait en meldt:")
    print(f"  {cron} {venv} {runner} >> ~/agents/{naam}.log 2>&1\n")
    print("Klaar. De kaart staat op https://mijnagents.globaal.be zodra de eerste hartslag binnen is.")


if __name__ == "__main__":
    main()
