#!/usr/bin/env python3
"""De gesprekkenketen: De Fathomwacht en daarna De Zoomwacht, elk met een eigen time-out, en een bewijs dat de keten
geslaagd is (ontwerp regie-zoom v1.2, 13.5 X3).

De cron start dit script om 07:00 en 13:00 UTC onder /tmp/gesprekken.lock (planning/gesprekken.cron). De Dagbundelaar
draait daarna binnen hetzelfde slot (RZ2-03). Een stap die faalt, houdt de volgende niet tegen, zoals bij de losse
cronregels van voordien. Een Fathomwacht die Fathom niet kon lezen (geen sleutel, of een sleutel die faalt), eindigt niet
op 0 (RZ2-02), dus is de keten dan niet geslaagd.
De uitvoer van elke stap gaat naar zijn eigen logboek in ~/agents.

Het schrijft mijnagents-data/keten.json, altijd atomisch (tijdelijk bestand ernaast, dan os.replace):
    {"keten_id": de start in UTC, "start": ..., "einde": ..., "stappen": {"fathom-wacht": {"exit": n, "einde": ...},
     "zoom-wacht": {...}}, "geslaagd": true alleen als beide stappen met exit 0 eindigden}
Bij de start staat er al een versie met einde null en geslaagd false; zo is een keten die nog loopt of halverwege
stopte nooit geslaagd. Alleen dit script schrijft keten.json: een ronde die De Regisseur start, niet. De Regisseur maakt
het ochtendbericht pas als keten.json een start na het geplande startmoment van vandaag heeft en geslaagd is.

Een stap die te lang loopt, krijgt eerst SIGTERM (De Fathomwacht en De Zoomwacht sluiten dan zelf hun hartslag af, J1),
na dertig seconden SIGKILL; zijn exit is dan 124, zoals bij /usr/bin/timeout.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
KETEN = os.path.expanduser("~/appportal/mijnagents-data/keten.json")
LOGMAP = os.path.expanduser("~/agents")
PYTHON = sys.executable
# (naam op het bord, runner, time-out in seconden, logboek): dezelfde time-outs en logboeken als de losse cronregels.
STAPPEN = (("fathom-wacht", "fathom_wacht.py", 2700, "fathom_wacht.log"),
           ("zoom-wacht", "zoom_wacht.py", 1200, "zoom_wacht.log"))
TIJDSLIMIET = 124
NADRUK = 30


def nu():
    return datetime.now(timezone.utc)


def stempel(t):
    return t.isoformat(timespec="seconds")


def schrijf(keten):
    """Atomisch: een lezer ziet altijd een hele versie van keten.json, nooit een half bestand."""
    map_ = os.path.dirname(KETEN)
    os.makedirs(map_, exist_ok=True)
    fd, tijdelijk = tempfile.mkstemp(prefix=".keten-", dir=map_)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(keten, f, ensure_ascii=False, indent=1)
        os.replace(tijdelijk, KETEN)
    except BaseException:
        if os.path.exists(tijdelijk):
            os.unlink(tijdelijk)
        raise


def stap(runner, tijdslimiet, logboek):
    """Een runner met zijn eigen time-out. Geeft zijn exitcode, of 124 als hij te lang liep. Stopt de keten zelf
    (SIGTERM), dan stopt ook de runner die nog loopt."""
    os.makedirs(LOGMAP, exist_ok=True)
    with open(os.path.join(LOGMAP, logboek), "a", encoding="utf-8") as log:
        p = subprocess.Popen([PYTHON, os.path.join(HIER, runner)], stdout=log, stderr=subprocess.STDOUT, cwd=HIER)
        try:
            return p.wait(timeout=tijdslimiet)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:
                p.wait(timeout=NADRUK)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
            return TIJDSLIMIET
        finally:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=NADRUK)
                except subprocess.TimeoutExpired:
                    p.kill()


def stop_bij_sigterm(signum, frame):
    """Stopt iemand de keten, dan gaat dat als SystemExit door main(): de lopende stap stopt mee en keten.json zegt
    'niet geslaagd'."""
    raise SystemExit(128 + signum)


def main():
    start = nu()
    keten = {"keten_id": stempel(start), "start": stempel(start), "einde": None, "stappen": {}, "geslaagd": False}
    schrijf(keten)
    try:
        for naam, runner, tijdslimiet, logboek in STAPPEN:
            code = stap(runner, tijdslimiet, logboek)
            keten["stappen"][naam] = {"exit": code, "einde": stempel(nu())}
            print(f"{stempel(nu())} {naam}: exit {code}" + (" (time-out)" if code == TIJDSLIMIET else ""), flush=True)
            schrijf(keten)
    finally:
        keten["einde"] = stempel(nu())
        keten["geslaagd"] = (len(keten["stappen"]) == len(STAPPEN)
                             and all(s["exit"] == 0 for s in keten["stappen"].values()))
        schrijf(keten)
    print(f"{keten['einde']} keten {'geslaagd' if keten['geslaagd'] else 'niet geslaagd'}", flush=True)
    return 0 if keten["geslaagd"] else 1


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_bij_sigterm)
    sys.exit(main())
