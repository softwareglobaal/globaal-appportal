#!/usr/bin/env python3
"""Zet de planning van de gesprekkenketen op de VM uit planning/gesprekken.cron (ontwerp regie-zoom v1.2, Z16).

Vervangt alleen het beheerde blok tussen de merktekens en precies de drie oude, onbeheerde regels die De Dagbundelaar
(07:00 op werkdagen), De Fathomwacht (07:00 en 13:00) en De Zoomwacht (07:15 en 13:15) los startten, zonder slot en
zonder vaste volgorde (crontab-regels 57, 58 en 98, gemeten op 21-10-2026). Elke andere regel blijft staan. Het nieuwe
blok heeft alleen de regel van de keten: De Dagbundelaar is sinds RZ4-04 de laatste stap van keten.py.

Het aanvaardt maar twee vormen (RZ3-02, herstelcontrole van 22-10-2026): precies die drie oude regels, elk één keer en
zonder beheerd blok (de eerste keer), of het beheerde blok één keer en geen oude regel meer (elke volgende keer). Elke
andere vorm weigert het, zonder iets te zetten: twee of een van de drie, een dubbele, een oude regel naast het blok, twee
blokken, of een andere regel met een van die runners of met keten.py. Tot dan aanvaardde het ook twee van de drie, en dan
liep er na --zet nog een losse ronde naast de keten, of ontbrak er een. De melding noemt de gevonden regels van de
gesprekkenrunners (alleen paden en tijden), zodat de beheerder ze kan beoordelen; een toewijzing in zo'n regel
(NAAM=waarde, een sleutel in de omgeving) wordt '<waarde>' (tegenproef van 22-10-2026). Zonder --zet toont het alleen
het eigen blok; het toont nooit andere regels (die kunnen geheimen bevatten). Na het zetten leest het terug.

Het beheerde blok vervangt het alleen als zijn inhoud precies een bekende vorm is (RZ4-06, herstelcontrole van Codex,
22-10-2026): het huidige blok uit gesprekken.cron, of het vorige uit deze branch (VORIG_BLOK, met de losse regel van De
Dagbundelaar); spaties achteraan tellen niet. Tot dan verving het alles tussen de merktekens, ook een opdracht die er
niet van ons is, en die verdween dan stil. Een andere inhoud weigert het, met de regels van het blok in de melding: een
regel van een gesprekkenrunner zoals hierboven, de regel met de tijden voluit, van ander commentaar en van een onbekende
opdracht niets meer dan haar tijdvelden (de opdracht zelf kan een geheim bevatten). De blokken van voor RZ2-03 en van de
eerste bouw (3600 s) zijn geen bekende vorm: deze branch stond nooit op de VM.

--zet zet alleen als het bord herbouwd is (RZ3-02, tegenproef van 22-10-2026): ~/appportal/mijnagents-data/.built moet
gelijk zijn aan HEAD:mijnagents, zoals mijnagents/deploy.sh het na een geslaagde build schrijft. Mislukt die build, dan
draait de oude bordcontainer verder terwijl de runnercode al nieuw is, en dan hoort de nieuwe planning er nog niet. Dan:
'geweigerd: bord nog niet herbouwd', exit 2, niets gezet. Zonder --zet staat dat als waarschuwing.
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
# Een toewijzing in een cronregel (NAAM=waarde, ook tussen aanhalingstekens): in een melding wordt ze '<waarde>'.
TOEWIJZING = re.compile(r"\b\w+=(?:\"[^\"]*\"|'[^']*'|\S+)")
# RZ4-06: de inhoud van het vorige beheerde blok uit deze branch (be314cc, 22-10-2026), letterlijk, tussen de merktekens.
# De regel van De Dagbundelaar daarin bestaat sinds RZ4-04 niet meer; het nieuwe blok vervangt hem.
VORIG_BLOK = (
    "# 07:00 UTC is 09:00 Brussel tot en met 24-10-2026, vanaf 25-10 08:00; 13:00 UTC is 15:00, vanaf 25-10 14:00.",
    "0 7,13 * * * /usr/bin/flock -w 1800 /tmp/gesprekken.lock /home/ubuntu/agents/.venv/bin/python "
    "/home/ubuntu/appportal/mijnagents-runner/keten.py >> /home/ubuntu/agents/keten.log 2>&1",
    "5 7 * * 1-5 /usr/bin/flock -w 5400 -E 75 /tmp/gesprekken.lock /home/ubuntu/agents/.venv/bin/python "
    "/home/ubuntu/appportal/mijnagents-runner/dagbundelaar.py >> /home/ubuntu/agents/dagbundelaar.log 2>&1; "
    "if [ $? -eq 75 ]; then echo \"$(date -u -Iseconds) slot /tmp/gesprekken.lock na 5400 s niet vrij: De Dagbundelaar "
    "niet gestart\" >> /home/ubuntu/agents/dagbundelaar.log; fi",
)
TIJDVELD = re.compile(r"[0-9*/,\-]+")
# De checkout op de VM (~/appportal) en het merkteken van deploy.sh; een proef zet ze op een tijdelijke map.
REPO = os.path.dirname(os.path.dirname(HIER))
BUILT = os.path.join(REPO, "mijnagents-data", ".built")


def bord_herbouwd():
    """(ja of nee, reden): staat het bord op de code van deze checkout? deploy.sh schrijft na een geslaagde build de
    boom van HEAD:mijnagents in mijnagents-data/.built; wijkt die af, dan draait nog de vorige bordcontainer (RZ3-02).
    De reden noemt nooit de hash."""
    try:
        boom = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD:mijnagents"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False, "git niet te lezen"
    if boom.returncode or not boom.stdout.strip():
        return False, "HEAD:mijnagents niet te lezen"
    try:
        with open(BUILT, encoding="utf-8") as f:
            gebouwd = f.read().strip()
    except OSError:
        return False, ".built ontbreekt"
    if gebouwd != boom.stdout.strip():
        return False, ".built wijkt af van HEAD:mijnagents"
    return True, ""


def blok(regels):
    """Het beheerde blok: de merktekens, de regel met de tijden in UTC en Brussel, en de cronregels zelf."""
    tijden = [r for r in regels if r.startswith("# 07:00 UTC")][:1]
    return [BEGIN] + tijden + [r for r in regels if r.strip() and not r.startswith("#")] + [EINDE]


def gevonden_regels(huidig):
    """De regels van de huidige crontab die een van de gesprekkenrunners starten, binnen en buiten het blok. Alleen die
    komen in een melding: ze dragen paden en tijden, en geen andere regel (die kan een geheim bevatten). Een toewijzing
    in zo'n regel wordt '<waarde>': ook daar kan een sleutel staan."""
    return [TOEWIJZING.sub("<waarde>", r.strip()) for r in huidig
            if not r.lstrip().startswith("#") and any(f"mijnagents-runner/{runner}" in r for runner in RUNNERS)]


def blok_getoond(inhoud):
    """De regels binnen een beheerd blok zoals ze in een melding komen (RZ4-06): een regel van een gesprekkenrunner zoals
    in gevonden_regels, de regel met de tijden voluit, van ander commentaar niets, en van een andere opdracht alleen haar
    tijdvelden. Zo kan de beheerder het blok beoordelen zonder dat een geheim uit de crontab op het scherm komt."""
    uit = []
    for r in inhoud:
        s = r.strip()
        if not s:
            uit.append("(lege regel)")
        elif s.startswith("# 07:00 UTC"):
            uit.append(s)
        elif s.startswith("#"):
            uit.append("# (ander commentaar, niet getoond)")
        elif any(f"mijnagents-runner/{runner}" in s for runner in RUNNERS):
            uit.append(TOEWIJZING.sub("<waarde>", s))
        else:
            tijd = []
            for veld in s.split()[:5]:
                if not TIJDVELD.fullmatch(veld):
                    break
                tijd.append(veld)
            uit.append(" ".join(tijd + ["<onbekende opdracht, niet getoond>"]))
    return uit


def samenvoegen(huidig, regels):
    """(de nieuwe crontab, het aantal vervangen oude regels). Weigert met ValueError elke vorm behalve precies de drie oude
    regels zonder blok, of het blok zonder oude regel (RZ3-02), en een blok waarvan de inhoud geen bekende vorm is
    (RZ4-06): het huidige blok of VORIG_BLOK."""
    def weiger(reden):
        raise ValueError(f"{reden}; niets gezet, eerst beoordelen. Verwacht: precies de drie oude regels "
                         "(fathom_wacht.py om 7 en 13, zoom_wacht.py om 7:15 en 13:15, dagbundelaar.py om 7:00 op werkdagen) "
                         "of al het beheerde blok, in de huidige of de vorige vorm. Gevonden regels: "
                         + (" | ".join(gevonden_regels(huidig)) or "geen"))

    uit, binnen, blokken, oud, inhoud = [], False, 0, [], []
    for regel in huidig:
        if regel == BEGIN:
            if binnen:
                weiger("dubbele beginmarker")
            binnen, blokken = True, blokken + 1
            continue
        if regel == EINDE:
            if not binnen:
                weiger("eindmarker zonder beginmarker")
            binnen = False
            continue
        if binnen:
            inhoud.append(regel)
            continue
        m = OUD.match(regel.strip())
        if m and (m.group("tijd"), m.group("runner")) in OUDE_REGELS:
            oud.append((m.group("tijd"), m.group("runner")))
            continue
        if not regel.lstrip().startswith("#"):
            for runner in RUNNERS:
                if f"mijnagents-runner/{runner}" in regel:
                    weiger(f"onbekende planning van {runner} buiten het blok")
        uit.append(regel)
    if binnen:
        weiger("beginmarker zonder eindmarker")
    if blokken > 1:
        weiger(f"het beheerde blok staat er {blokken} keer")
    if blokken and oud:
        weiger(f"het beheerde blok staat er al, en er staan nog {len(oud)} oude regel(s) naast")
    if blokken and [r.rstrip() for r in inhoud] not in (blok(regels)[1:-1], list(VORIG_BLOK)):
        # RZ4-06: nooit stil een opdracht vervangen die er niet van ons is
        weiger("onbekende inhoud in het beheerde blok (" + " | ".join(blok_getoond(inhoud) or ["leeg"]) + ")")
    if not blokken and sorted(oud) != sorted(OUDE_REGELS):
        weiger(f"niet precies de drie oude regels ({len(oud)} gevonden, {len(set(oud))} verschillend)")
    while uit and not uit[-1].strip():
        uit.pop()
    return uit + [""] + blok(regels), len(oud)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--zet", action="store_true")
    a = p.parse_args(argv)
    meting = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if meting.returncode and "no crontab" not in meting.stderr.lower():
        raise RuntimeError("huidige crontab niet leesbaar")
    huidig = meting.stdout.splitlines()
    regels = open(os.path.join(HIER, "gesprekken.cron"), encoding="utf-8").read().splitlines()
    try:
        doel, oud = samenvoegen(huidig, regels)
    except ValueError as e:
        print(f"geweigerd: {e}", file=sys.stderr)
        return 2
    print("planning wijzigen" if huidig != doel else "planning al gelijk", f"(oude regels vervangen: {oud})")
    print("\n".join(blok(regels)))
    herbouwd, reden = bord_herbouwd()
    if not herbouwd:
        print(f"let op: bord nog niet herbouwd ({reden}); --zet weigert tot deploy.sh het bord herbouwde", file=sys.stderr)
    if not a.zet or huidig == doel:
        return 0
    if not herbouwd:
        # RZ3-02: de oude bordcontainer draait nog; de nieuwe planning wacht op een geslaagde build
        print(f"geweigerd: bord nog niet herbouwd ({reden}); niets gezet", file=sys.stderr)
        return 2
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
