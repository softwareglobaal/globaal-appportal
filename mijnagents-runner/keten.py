#!/usr/bin/env python3
"""De gesprekkenketen: De Fathomwacht en daarna De Zoomwacht, elk met een eigen time-out, en een bewijs dat de keten
geslaagd is (ontwerp regie-zoom v1.2, 13.5 X3). In de ochtendketen van een werkdag draait De Dagbundelaar als laatste
stap (RZ4-04).

De cron start dit script om 07:00 en 13:00 UTC onder /tmp/gesprekken.lock (planning/gesprekken.cron). Een stap die
faalt, houdt de volgende niet tegen, zoals bij de losse cronregels van voordien. Een Fathomwacht die Fathom niet kon
lezen (geen sleutel, of een sleutel die faalt), eindigt niet op 0 (RZ2-02), dus is de keten dan niet geslaagd.
De uitvoer van elke stap gaat naar zijn eigen logboek in ~/agents.

De Dagbundelaar (RZ4-04, herstelcontrole van Codex, besluit van de regie 22-10-2026): tot dan had hij een eigen
cronregel om 07:05 die tot 5400 s op hetzelfde slot wachtte. Een handmatige ronde kan dat slot 1800 s vasthouden; dan
wachtte ook de keten, en kon De Dagbundelaar het slot vóór de keten krijgen (een dagverslag zonder de gesprekken van die
ochtend) of afhaken. Nu is hij de laatste stap van de keten zelf, na De Fathomwacht en De Zoomwacht, en alleen:
  - in de ochtendketen: de keten die start binnen het eerste geplande uur uit planning/gesprekken.cron (07:00 UTC, zoals
    koppelingen/ochtend.ketenstart het leest), ook als ze tot 1800 s op het slot wachtte;
  - op werkdagen, maandag tot vrijdag in Brusselse tijd.
Hij draait ook als een eerdere stap faalde: hij meldt zelf wat ontbreekt (de Zoom-dagregel bijvoorbeeld). Is de
planning niet te lezen, dan draait hij niet en zegt de keten dat in keten.log; het ochtendbericht noemt hem dan onder
wat ontbreekt.
Inhalen (tegenproef op RZ4-04, 22-10-2026): krijgt de ochtendketen het slot niet binnen 1800 s, dan start ze niet
(flock -E 75 zet dat in keten.log). Een latere keten op dezelfde werkdag, in de planning die van 13:00 UTC, draait De
Dagbundelaar dan toch, net als wanneer hij in de vorige keten van vandaag niet met exit 0 eindigde. Dat leest ze uit
keten.json zoals het voor haar start stond (vorige_keten). Tot dan draaide hij zo'n dag nergens. Een tweede ronde op
dezelfde dag is veilig: hij zet zijn bundels klaar op een vaste uniek.

Het schrijft mijnagents-data/keten.json, altijd atomisch (tijdelijk bestand ernaast, dan os.replace):
    {"keten_id": de start in UTC, "start": ..., "einde": ..., "stappen": {"fathom-wacht": {"exit": n, "einde": ...},
     "zoom-wacht": {...}, "dagbundelaar": {...} (alleen in de ochtendketen van een werkdag, of bij het inhalen)},
     "geslaagd": true alleen als De Fathomwacht en De Zoomwacht met exit 0 eindigden}
De stap van De Dagbundelaar telt niet voor geslaagd; De Regisseur leest hem apart (koppelingen/ochtend.py, RZ4-04).
Bij de start staat er al een versie met einde null en geslaagd false; zo is een keten die nog loopt of halverwege
stopte nooit geslaagd. Alleen dit script schrijft keten.json: een ronde die De Regisseur start, niet. De Regisseur maakt
het ochtendbericht pas als keten.json een start na het geplande startmoment van vandaag heeft en geslaagd is.

Een stap die te lang loopt, krijgt eerst SIGTERM (De Fathomwacht en De Zoomwacht sluiten dan zelf hun hartslag af, J1),
na dertig seconden SIGKILL; zijn exit is dan 124, zoals bij /usr/bin/timeout.

De keten duurt zo hoogstens de som van de time-outs plus de nadruk per stap: 2700 + 1200 + 900 + 3 x 30 = 4890 seconden
(tests/test_keten.py rekent het na).
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
KETEN = os.path.expanduser("~/appportal/mijnagents-data/keten.json")
LOGMAP = os.path.expanduser("~/agents")
PYTHON = sys.executable
# (naam op het bord, runner, time-out in seconden, logboek): dezelfde time-outs en logboeken als de losse cronregels.
STAPPEN = (("fathom-wacht", "fathom_wacht.py", 2700, "fathom_wacht.log"),
           ("zoom-wacht", "zoom_wacht.py", 1200, "zoom_wacht.log"))
# RZ4-04: de laatste stap van de ochtendketen op een werkdag. Een ronde duurt gewoonlijk enkele seconden; 900 s is ruim.
DAGBUNDELAAR = ("dagbundelaar", "dagbundelaar.py", 900, "dagbundelaar.log")
# De nachtketen (keten.py --nacht, ontwerp dagvaststelling v1.2, Codex F9): elke nacht om 23:30 UTC De Zoomwacht, zodat de
# gesprekken van de avond in de tabel staan, en daarna De Dagbundelaar --nacht, die de dagvaststelling maakt. Ze schrijft
# nacht.json, nooit keten.json: het ochtendbericht en het inhalen van de ochtendketen kijken er niet naar. De Dagbundelaar
# leest in nacht.json de exit van De Zoomwacht. Een ronde over veertien dagen duurt minuten; 1800 s is ruim.
NACHT = os.path.expanduser("~/appportal/mijnagents-data/nacht.json")
NACHTSTAPPEN = (("zoom-wacht", "zoom_wacht.py", 1200, "zoom_wacht.log"),)
NACHTBUNDELAAR = ("dagbundelaar", ("dagbundelaar.py", "--nacht"), 1800, "dagbundelaar.log")
# Het startmoment staat op een plek: de regel met keten.py in de planning. Een proef zet CRON op een eigen bestand.
CRON = os.path.join(HIER, "planning", "gesprekken.cron")
KOPPELINGEN = os.path.join(HIER, "koppelingen")
# De ochtendketen start binnen een uur na het eerste geplande moment: de flock van de keten wacht hoogstens 1800 s.
OCHTENDVENSTER = timedelta(hours=1)
BRUSSEL = ZoneInfo("Europe/Brussels")
TIJDSLIMIET = 124
NADRUK = 30


def nu():
    return datetime.now(timezone.utc)


def stempel(t):
    return t.isoformat(timespec="seconds")


def schrijf(keten, pad=None):
    """Atomisch: een lezer ziet altijd een hele versie van keten.json (of nacht.json), nooit een half bestand."""
    pad = pad or KETEN
    map_ = os.path.dirname(pad)
    os.makedirs(map_, exist_ok=True)
    fd, tijdelijk = tempfile.mkstemp(prefix=".keten-", dir=map_)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(keten, f, ensure_ascii=False, indent=1)
        os.replace(tijdelijk, pad)
    except BaseException:
        if os.path.exists(tijdelijk):
            os.unlink(tijdelijk)
        raise


def stap(runner, tijdslimiet, logboek):
    """Een runner met zijn eigen time-out. Geeft zijn exitcode, of 124 als hij te lang liep. Stopt de keten zelf
    (SIGTERM), dan stopt ook de runner die nog loopt. runner: een bestandsnaam, of (bestandsnaam, argumenten...)."""
    os.makedirs(LOGMAP, exist_ok=True)
    naam, *argumenten = (runner,) if isinstance(runner, str) else tuple(runner)
    with open(os.path.join(LOGMAP, logboek), "a", encoding="utf-8") as log:
        p = subprocess.Popen([PYTHON, os.path.join(HIER, naam), *argumenten], stdout=log, stderr=subprocess.STDOUT, cwd=HIER)
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


def vorige_keten():
    """keten.json zoals het er voor deze keten stond (tegenproef op RZ4-04, inhalen), of None als het er niet is of niet
    te lezen valt. Alleen keten.py schrijft het, atomisch."""
    try:
        with open(KETEN, encoding="utf-8") as f:
            inhoud = json.load(f)
    except (OSError, ValueError):
        return None
    return inhoud if isinstance(inhoud, dict) else None


def ochtendketen(start, vorige=None):
    """(ja of nee, reden): draait deze keten De Dagbundelaar (RZ4-04)? Ja als ze start binnen het eerste geplande uur uit
    de planning (ochtend.ketenstart, dezelfde lezing als De Regisseur) en het in Brussel maandag tot vrijdag is.
    En ja als inhaalronde (tegenproef op RZ4-04, 22-10-2026): een keten na dat uur op dezelfde werkdag, als de vorige
    keten (vorige: keten.json zoals het voor deze start stond) niet van vandaag is, of geen stap dagbundelaar met exit 0
    heeft. Zo haalt de keten van 13:00 hem in als de ochtendketen niet startte (het slot bleef langer dan 1800 s bezet,
    keten.log zegt het) of hij daarin faalde of niet aan de beurt kwam. Tot dan draaide hij die dag dan nergens. Zonder
    leesbare vorige keten niet: dan is onbekend of hij al liep (de eerste keten na de uitrol)."""
    try:
        if KOPPELINGEN not in sys.path:
            sys.path.insert(0, KOPPELINGEN)
        import ochtend  # noqa: PLC0415  pas hier: een fout bij het importeren houdt Fathom en Zoom niet tegen
        eerste = ochtend.ketenstart(ochtend.lees_cron(CRON))
    except Exception as e:  # noqa: BLE001
        return False, f"planning niet te lezen ({type(e).__name__})"
    if eerste is None:
        return False, "eerste geplande uur onbekend (planning/gesprekken.cron niet te lezen)"
    if start.astimezone(BRUSSEL).weekday() >= 5:
        return False, "weekend in Brussel"
    utc = start.astimezone(timezone.utc)
    gepland = datetime.combine(utc.date(), time(*eerste), tzinfo=timezone.utc)
    if gepland <= utc < gepland + OCHTENDVENSTER:
        return True, ""
    if utc < gepland:
        return False, "niet de ochtendketen"
    if not isinstance(vorige, dict):
        return False, "niet de ochtendketen, en geen leesbare vorige keten om in te halen"
    begin = ochtend.tijdstip(vorige.get("start")) or ochtend.tijdstip(vorige.get("keten_id"))
    stappen = vorige.get("stappen") if isinstance(vorige.get("stappen"), dict) else {}
    stap = stappen.get("dagbundelaar") if isinstance(stappen.get("dagbundelaar"), dict) else {}
    van_vandaag = begin is not None and begin >= gepland
    if van_vandaag and stap.get("exit") == 0 and not isinstance(stap.get("exit"), bool):
        return False, "liep vandaag al in een keten"
    if not van_vandaag:
        return True, "inhaalronde: de ochtendketen van vandaag startte niet"
    return True, "inhaalronde: de vorige keten van vandaag draaide hem niet met exit 0"


def voer_uit(keten, naam, runner, tijdslimiet, logboek, pad=None):
    code = stap(runner, tijdslimiet, logboek)
    keten["stappen"][naam] = {"exit": code, "einde": stempel(nu())}
    print(f"{stempel(nu())} {naam}: exit {code}" + (" (time-out)" if code == TIJDSLIMIET else ""), flush=True)
    schrijf(keten, pad)


def nachtketen():
    """De nachtketen (Codex F9): De Zoomwacht en daarna De Dagbundelaar --nacht, ook als De Zoomwacht faalde (hij meldt
    dat zelf, uit nacht.json). Schrijft nacht.json met einde null tot het einde; De Dagbundelaar ziet zo dat hij in een
    lopende nachtketen draait. Exit 0 alleen als beide stappen met 0 eindigden."""
    start = nu()
    nacht = {"start": stempel(start), "einde": None, "stappen": {}}
    schrijf(nacht, NACHT)
    try:
        for naam, runner, tijdslimiet, logboek in NACHTSTAPPEN + (NACHTBUNDELAAR,):
            voer_uit(nacht, naam, runner, tijdslimiet, logboek, NACHT)
    finally:
        nacht["einde"] = stempel(nu())
        schrijf(nacht, NACHT)
    geslaagd = all(s.get("exit") == 0 for s in nacht["stappen"].values()) and len(nacht["stappen"]) == len(NACHTSTAPPEN) + 1
    print(f"{nacht['einde']} nachtketen {'geslaagd' if geslaagd else 'niet geslaagd'}", flush=True)
    return 0 if geslaagd else 1


def main():
    start = nu()
    # tegenproef op RZ4-04: de vorige keten lezen voor deze haar overschrijft, om De Dagbundelaar zo nodig in te halen
    vorige = vorige_keten()
    keten = {"keten_id": stempel(start), "start": stempel(start), "einde": None, "stappen": {}, "geslaagd": False}
    schrijf(keten)
    try:
        for naam, runner, tijdslimiet, logboek in STAPPEN:
            voer_uit(keten, naam, runner, tijdslimiet, logboek)
        # RZ4-04: De Dagbundelaar als laatste stap, ook na een stap die faalde; hij meldt zelf wat ontbreekt
        ochtend, reden = ochtendketen(start, vorige)
        if ochtend:
            if reden:
                print(f"{stempel(nu())} dagbundelaar: {reden}", flush=True)
            voer_uit(keten, *DAGBUNDELAAR)
        else:
            print(f"{stempel(nu())} dagbundelaar: niet in deze keten ({reden})", flush=True)
    finally:
        keten["einde"] = stempel(nu())
        # geslaagd blijft bij De Fathomwacht en De Zoomwacht; de stap van De Dagbundelaar leest De Regisseur apart
        keten["geslaagd"] = all(keten["stappen"].get(naam, {}).get("exit") == 0 for naam, *_ in STAPPEN)
        schrijf(keten)
    print(f"{keten['einde']} keten {'geslaagd' if keten['geslaagd'] else 'niet geslaagd'}", flush=True)
    return 0 if keten["geslaagd"] else 1


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_bij_sigterm)
    sys.exit(nachtketen() if "--nacht" in sys.argv else main())
