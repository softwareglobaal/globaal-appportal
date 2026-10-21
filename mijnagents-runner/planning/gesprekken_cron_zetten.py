#!/usr/bin/env python3
"""Zet de planning van de gesprekkenketen op de VM uit planning/gesprekken.cron (ontwerp regie-zoom v1.2, Z16).

Vervangt alleen het beheerde blok tussen de merktekens en precies de drie oude, onbeheerde regels die De Dagbundelaar
(07:00 op werkdagen), De Fathomwacht (07:00 en 13:00) en De Zoomwacht (07:15 en 13:15) los startten, zonder slot en
zonder vaste volgorde (crontab-regels 57, 58 en 98, gemeten op 21-10-2026). Elke andere regel blijft staan.

Het aanvaardt maar twee vormen (RZ3-02, herstelcontrole van 22-10-2026): precies die drie oude regels, elk één keer en
zonder beheerd blok (de eerste keer), of het beheerde blok één keer en geen oude regel meer (elke volgende keer). Elke
andere vorm weigert het, zonder iets te zetten: twee of een van de drie, een dubbele, een oude regel naast het blok, twee
blokken, of een andere regel met een van die runners of met keten.py. Tot dan aanvaardde het ook twee van de drie, en dan
liep er na --zet nog een losse ronde naast de keten, of ontbrak er een. De melding noemt de gevonden regels van de
gesprekkenrunners (alleen paden en tijden), zodat de beheerder ze kan beoordelen; een toewijzing in zo'n regel
(NAAM=waarde, een sleutel in de omgeving) wordt '<waarde>' (tegenproef van 22-10-2026). Zonder --zet toont het alleen
het eigen blok; het toont nooit andere regels (die kunnen geheimen bevatten). Na het zetten leest het terug.

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


def samenvoegen(huidig, regels):
    """(de nieuwe crontab, het aantal vervangen oude regels). Weigert met ValueError elke vorm behalve precies de drie oude
    regels zonder blok, of het blok zonder oude regel (RZ3-02)."""
    def weiger(reden):
        raise ValueError(f"{reden}; niets gezet, eerst beoordelen. Verwacht: precies de drie oude regels "
                         "(fathom_wacht.py om 7 en 13, zoom_wacht.py om 7:15 en 13:15, dagbundelaar.py om 7:00 op werkdagen) "
                         "of al het beheerde blok. Gevonden regels: " + (" | ".join(gevonden_regels(huidig)) or "geen"))

    uit, binnen, blokken, oud = [], False, 0, []
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
