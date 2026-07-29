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
  - een interval krijgt de applicatie van het laatste herkende signaal
    ervoor. Zonder signaal telt het als "onbekend" en wordt het niet
    verstuurd (wel getoond bij --droog, zodat zichtbaar blijft hoeveel er
    buiten de toedeling valt).

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

# Toedeling: welke sporen horen bij welke applicatie. Van specifiek naar
# algemeen; het eerste patroon dat past wint. Nieuwe app erbij? Regel hier.
APPS = [
    ("globaal-hr", ("globaal-hr", "appportal/hr", "appportal\\hr",
                    "hr.globaal.be", "hds-hr-dashboard", "hr.medewerker",
                    "hr.app_gebruik", "dashboard-template.html", "desktime")),
    ("globaal-stavingsstukken", ("stavingsstukken", "epb-pedia", "epbpedia")),
    ("globaal-organisatie", ("globaal-organisatie", "organisatie.globaal.be",
                             "graaf.py", "signalen.py")),
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
        huidig = None
        for i in range(1, len(rijen)):
            vorig_t, vorige_app, _ = rijen[i - 1]
            t, _, is_prompt = rijen[i]
            if vorige_app:
                huidig = vorige_app
            gat = (t - vorig_t).total_seconds()
            if not huidig:
                continue
            sleutel = (huidig, t.astimezone().date().isoformat())
            if 0 < gat <= pauze:
                per[sleutel]["sec"] += gat
                per[sleutel]["sessies"].add(sessie)
            if is_prompt:
                per[sleutel]["prompts"] += 1
    return per


def _wie():
    try:
        r = subprocess.run(["git", "config", "user.email"],
                           capture_output=True, text=True, timeout=5)
        wie = (r.stdout or "").strip()
    except Exception:
        wie = ""
    return (wie or os.environ.get("USERNAME") or "onbekend").lower()


def _verstuur(regels, gebruiker, machine):
    token = os.environ.get("ONTWIKKELING_TOKEN", "").strip()
    if not token:
        raise SystemExit("ONTWIKKELING_TOKEN ontbreekt; niets verstuurd")
    body = json.dumps({"gebruiker": gebruiker, "machine": machine,
                       "pauzegrens": PAUZE, "regels": regels}).encode()
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
    # Een transcript dat sinds de vorige ronde niet veranderde, kan de
    # uitkomst niet veranderen: overslaan scheelt het meeste werk.
    nieuw = [p_ for p_ in paden
             if str(os.path.getmtime(p_)) != stand.get("mtimes", {}).get(p_)]
    if not nieuw and not a.alles:
        print("geen gewijzigde transcripts")
        return
    # Alle dagen die de gewijzigde transcripts raken opnieuw optellen: een
    # sessie kan over meerdere dagen lopen, dus per dag is de optelsom pas
    # juist als alle transcripts van die dag meetellen.
    per = meet(paden)

    dagen_nieuw = {d for (app, d) in meet(nieuw).keys()} if not a.alles else None
    regels = []
    for (app, dag), w in sorted(per.items()):
        if a.vanaf and dag < a.vanaf:
            continue
        if dagen_nieuw is not None and dag not in dagen_nieuw:
            continue
        regels.append({"datum": dag, "repo": app,
                       "actieve_sec": int(round(w["sec"])),
                       "sessies": len(w["sessies"]),
                       "prompts": int(w["prompts"])})

    gebruiker, machine = _wie(), os.environ.get("COMPUTERNAME", "")[:60]
    if a.droog:
        totaal = defaultdict(float)
        for (app, dag), w in per.items():
            totaal[app] += w["sec"]
        print(f"gebruiker={gebruiker} machine={machine} pauzegrens={PAUZE}s")
        print(f"transcripts: {len(paden)} ({len(nieuw)} gewijzigd)")
        for app, sec in sorted(totaal.items(), key=lambda x: -x[1]):
            print(f"  {sec / 3600:6.1f} u  {app}")
        print(f"te versturen regels: {len(regels)}")
        return

    antwoord = _verstuur(regels, gebruiker, machine) if regels else {"ok": True,
                                                                    "rijen": 0}
    os.makedirs(os.path.dirname(STAND), exist_ok=True)
    json.dump({"mtimes": {p_: str(os.path.getmtime(p_)) for p_ in paden},
               "laatste": datetime.now(timezone.utc).isoformat()},
              open(STAND, "w", encoding="utf-8"))
    print(f"verstuurd: {len(regels)} regels, antwoord: {antwoord}")


if __name__ == "__main__":
    main()
