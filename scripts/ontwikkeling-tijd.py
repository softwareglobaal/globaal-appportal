"""Verzamelt gemeten Claude Code-tijd per applicatie per dag (migratie 094).

Draait op de ontwikkelmachine, leest de lokale Claude Code-transcripts en
stuurt UITSLUITEND een optelsom naar het organisatie-dashboard: dag,
applicatie, actieve seconden, aantal sessies en prompts. Gespreksinhoud,
bestandsnamen en sessie-detail verlaten de machine niet.

Waarom niet de hook uit migratie 074? Die noemt de applicatie naar de map
waarin je toevallig staat (werk vanuit een verzamelmap komt onder een
verzamelnaam terecht) en meet de wandkloktijd van een sessie, pauzes
inbegrepen. Hier gebeurt het andersom:

  - toedeling volgt de BESTANDEN die worden aangeraakt, niet de werkmap;
  - de tijd tussen twee gebeurtenissen telt mee tot een pauzegrens
    (standaard 5 minuten); langere gaten zijn pauze en tellen niet;
  - een interval gaat naar het DICHTSTBIJZIJNDE signaal binnen tien minuten,
    voor of na. Is er geen signaal in de buurt, dan komt de tijd onder
    "(niet toegedeeld)" te staan in plaats van bij de applicatie waar
    toevallig het laatst aan gewerkt werd.

Gebruik:
    python ontwikkeling-tijd.py --droog        alleen tonen
    python ontwikkeling-tijd.py                meten en versturen
    python ontwikkeling-tijd.py --alles        negeer de voortgangsmarkering

Nodig: ONTWIKKELING_TOKEN in de omgeving (zelfde token als de hook).
"""
import argparse
import glob
import json
import os
import subprocess
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

URL = os.environ.get("ONTWIKKELING_TIJD_URL",
                     "https://organisatie.globaal.be/ontwikkeling/tijd")
TRANSCRIPTS = os.environ.get(
    "CLAUDE_TRANSCRIPTS", os.path.expanduser("~/.claude/projects/*/*.jsonl"))
STAND = os.path.expanduser("~/.claude/ontwikkeling-tijd-stand.json")
PAUZE = int(os.environ.get("ONTWIKKELING_PAUZE", "300"))
# Hoelang een signaal (een aangeraakt bestand) hoogstens iets zegt over de
# tijd eromheen.
GELDIG = int(os.environ.get("ONTWIKKELING_GELDIG", "600"))
# Tijd zonder signaal in de buurt: wel meegeteld, maar onder een eigen naam,
# zodat zichtbaar blijft hoeveel er niet is toegedeeld.
NIET_TOEGEDEELD = "(niet toegedeeld)"

# Toedeling: welke sporen horen bij welke applicatie. Van specifiek naar
# algemeen; het eerste patroon dat past wint. Nieuwe app erbij? Regel hier.
#
# Trefwoorden moeten SMAL zijn. "desktime" stond hier eerst bij globaal-hr en
# trok al het werk aan desktime.py (organisatie) en kosten.desktime_medewerker
# naar het HR-dashboard: 3,1 uur werd zo 8,7 uur. Een trefwoord dat in meer
# dan een repo voorkomt hoort hier niet thuis.
APPS = [
    ("globaal-hr", ("globaal-hr", "appportal/hr", "appportal\\hr",
                    "hr.globaal.be", "hds-hr-dashboard", "hr.medewerker",
                    "hr.app_gebruik", "hr.handmatig", "hr.dag",
                    "dashboard-template.html")),
    ("globaal-stavingsstukken", ("stavingsstukken", "epb-pedia", "epbpedia")),
    ("globaal-organisatie", ("globaal-organisatie", "organisatie.globaal.be",
                             "graaf.py", "signalen.py", "desktime.py")),
    ("globaal-appportal", ("globaal-appportal", "appportal/scripts",
                           "db/migrations")),
    ("globaal-kosten", ("globaal-kosten", "kosten.globaal.be")),
    ("globaal-sales", ("globaal-sales", "sales.globaal.be")),
    ("globaal-communicatie", ("globaal-communicatie", "communicatie.globaal.be",
                              "xelion")),
    ("globaal-agents", ("globaal-agents", "agents.globaal.be",
                        "gezondheidsagent")),
    ("globaal-monday", ("monday-sandbox", "monday.globaal.be")),
    ("elevait", ("elevait",)),
    ("items-te-koop", ("items-te-koop",)),
    ("omv-pipeline", ("omv-pipeline", "omv.globaal.be")),
    ("onedrive-migratie", ("onedrive-migratie",)),
    ("bitwarden-audit", ("bitwarden",)),
]

VELDEN = ("file_path", "path", "command", "pattern", "notebook_path", "url")


def _sporen(o):
    """Alleen paden en commando's uit gereedschapsaanroepen; geen prozatekst.
    Wat hier niet uit komt, kan ook nooit per ongeluk verstuurd worden."""
    uit = []
    inhoud = (o.get("message") or {}).get("content")
    if isinstance(inhoud, list):
        for c in inhoud:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                inv = c.get("input") or {}
                for sleutel in VELDEN:
                    w = inv.get(sleutel)
                    if isinstance(w, str):
                        uit.append(w)
    return " ".join(uit).lower()


def _app(spoor):
    for naam, sleutels in APPS:
        if any(s in spoor for s in sleutels):
            return naam
    return None


def _tijd(o):
    ts = o.get("timestamp")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def meet_bestand(pad, pauze=PAUZE):
    """De bijdrage van een enkel transcript: per (applicatie, dag) seconden,
    prompts en het aantal sessies (hier altijd 0 of 1)."""
    return meet([pad], pauze)


def meet(paden, pauze=PAUZE):
    """Per (applicatie, dag): actieve seconden, sessies en prompts."""
    per = defaultdict(lambda: {"sec": 0.0, "prompts": 0, "sessies": set()})
    for pad in paden:
        rijen = []
        try:
            with open(pad, encoding="utf-8", errors="replace") as f:
                for regel in f:
                    try:
                        o = json.loads(regel)
                    except ValueError:
                        continue
                    t = _tijd(o)
                    if t:
                        rijen.append((t, _app(_sporen(o)),
                                      o.get("type") == "user"
                                      and o.get("userType") == "external"))
        except OSError:
            continue
        rijen.sort(key=lambda x: x[0])
        sessie = os.path.basename(pad)
        # Toedelen op het DICHTSTBIJZIJNDE signaal binnen het geldigheidsvenster,
        # voor of na. Eerder gold het laatste signaal onbeperkt door: een uur
        # overleg zonder bestanden bleef dan op de vorige applicatie staan.
        # Tijd zonder signaal in de buurt is eerlijker als "niet toegedeeld"
        # dan als een cijfer bij een applicatie die er niets mee te maken had.
        signalen = [(t, a) for t, a, _ in rijen if a]
        j = 0
        for i in range(1, len(rijen)):
            vorig_t = rijen[i - 1][0]
            t, _, is_prompt = rijen[i]
            gat = (t - vorig_t).total_seconds()
            # Signalen staan op tijd gesorteerd: schuif mee in plaats van
            # telkens de hele lijst af te lopen.
            while j + 1 < len(signalen) and signalen[j + 1][0] <= vorig_t:
                j += 1
            app, beste = None, None
            for k in (j - 1, j, j + 1):
                if 0 <= k < len(signalen):
                    afstand = abs((signalen[k][0] - vorig_t).total_seconds())
                    if afstand <= GELDIG and (beste is None or afstand < beste):
                        beste, app = afstand, signalen[k][1]
            sleutel = (app or NIET_TOEGEDEELD, t.astimezone().date().isoformat())
            if 0 < gat <= pauze:
                per[sleutel]["sec"] += gat
                per[sleutel]["sessies"].add(sessie)
            if is_prompt:
                per[sleutel]["prompts"] += 1
    return per


def _wie():
    """De identiteit moet STABIEL zijn, ongeacht waar de verzamelaar draait.

    Eerst gebruikte dit `git config user.email` zonder --global: vanuit een
    repo gaf dat het e-mailadres, vanuit een gewone map niets, en dan viel hij
    terug op de Windows-gebruikersnaam. Dezelfde persoon kwam zo onder twee
    namen in de tabel en al zijn tijd telde dubbel."""
    wie = os.environ.get("ONTWIKKELING_GEBRUIKER", "").strip()
    if not wie:
        try:
            r = subprocess.run(["git", "config", "--global", "user.email"],
                               capture_output=True, text=True, timeout=5)
            wie = (r.stdout or "").strip()
        except Exception:
            wie = ""
    return (wie or os.environ.get("USERNAME") or "onbekend").lower()


def _verstuur(regels, gebruiker, machine):
    token = os.environ.get("ONTWIKKELING_TOKEN", "").strip()
    if not token:
        raise SystemExit("ONTWIKKELING_TOKEN ontbreekt; niets verstuurd")
    # De dagen erbij: de ontvanger vervangt die dagen volledig. Zonder dat
    # blijft een oude, verkeerd toegedeelde regel staan zodra een applicatie
    # op zo'n dag helemaal wegvalt.
    body = json.dumps({"gebruiker": gebruiker, "machine": machine,
                       "pauzegrens": PAUZE, "regels": regels,
                       "dagen": sorted({r["datum"] for r in regels})}).encode()
    req = urllib.request.Request(
        URL, data=body, headers={"Content-Type": "application/json",
                                 "X-Ontwikkeling-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--droog", action="store_true",
                   help="tonen wat er verstuurd zou worden")
    p.add_argument("--alles", action="store_true",
                   help="ook al verwerkte transcripts opnieuw meten")
    p.add_argument("--vanaf", help="alleen dagen vanaf deze datum versturen")
    a = p.parse_args()

    stand = {}
    if not a.alles and os.path.exists(STAND):
        try:
            stand = json.load(open(STAND, encoding="utf-8"))
        except ValueError:
            stand = {}

    paden = sorted(glob.glob(TRANSCRIPTS))
    # Een transcript dat sinds de vorige ronde niet veranderde levert dezelfde
    # bijdrage: die bewaren we, zodat een ronde seconden duurt in plaats van
    # de hele geschiedenis opnieuw te lezen. Dat maakt automatisch draaien na
    # elke sessie haalbaar.
    cache = {} if a.alles else (stand.get("cache") or {})
    bijdragen, gewijzigd = {}, []
    for pad in paden:
        stempel = str(os.path.getmtime(pad))
        oud = cache.get(pad)
        if oud and oud.get("mtime") == stempel:
            bijdragen[pad] = oud
            continue
        gewijzigd.append(pad)
        per_bestand = meet_bestand(pad)
        bijdragen[pad] = {"mtime": stempel, "regels": [
            {"repo": app, "datum": dag, "sec": round(w["sec"], 1),
             "prompts": w["prompts"], "sessies": len(w["sessies"])}
            for (app, dag), w in per_bestand.items()]}
    if not gewijzigd and not a.alles:
        print("geen gewijzigde transcripts")
        return

    # Optellen over alle transcripts: een dag is pas juist als elke sessie van
    # die dag meetelt.
    per = defaultdict(lambda: {"sec": 0.0, "prompts": 0, "sessies": 0})
    for b in bijdragen.values():
        for r in b["regels"]:
            w = per[(r["repo"], r["datum"])]
            w["sec"] += r["sec"]
            w["prompts"] += r["prompts"]
            w["sessies"] += r["sessies"]
    dagen_nieuw = None
    if not a.alles:
        dagen_nieuw = {r["datum"] for p_ in gewijzigd
                       for r in bijdragen[p_]["regels"]}
    regels = []
    for (app, dag), w in sorted(per.items()):
        if a.vanaf and dag < a.vanaf:
            continue
        if dagen_nieuw is not None and dag not in dagen_nieuw:
            continue
        regels.append({"datum": dag, "repo": app,
                       "actieve_sec": int(round(w["sec"])),
                       "sessies": int(w["sessies"]),
                       "prompts": int(w["prompts"])})

    gebruiker, machine = _wie(), os.environ.get("COMPUTERNAME", "")[:60]
    if a.droog:
        totaal = defaultdict(float)
        for (app, dag), w in per.items():
            totaal[app] += w["sec"]
        print(f"gebruiker={gebruiker} machine={machine} pauzegrens={PAUZE}s")
        print(f"transcripts: {len(paden)} ({len(gewijzigd)} opnieuw gelezen)")
        for app, sec in sorted(totaal.items(), key=lambda x: -x[1]):
            print(f"  {sec / 3600:6.1f} u  {app}")
        print(f"te versturen regels: {len(regels)}")
        return

    antwoord = _verstuur(regels, gebruiker, machine) if regels else {"ok": True,
                                                                    "rijen": 0}
    os.makedirs(os.path.dirname(STAND), exist_ok=True)
    json.dump({"cache": bijdragen,
               "laatste": datetime.now(timezone.utc).isoformat()},
              open(STAND, "w", encoding="utf-8"))
    print(f"verstuurd: {len(regels)} regels, antwoord: {antwoord}")


if __name__ == "__main__":
    main()
