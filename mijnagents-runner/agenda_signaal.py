#!/usr/bin/env python3
"""Kijkt of er iets aan de agenda veranderd is en zet de Agendawacht dan meteen aan.

De wacht draait 's ochtends, maar een afspraak die om elf uur verplaatst wordt mag geen
dag wachten op zijn reistijd, kleur en melding. Dit script vraagt elke keer welke
afspraken er sinds de vorige keer gewijzigd zijn, en start de wacht voor de dagen die
het betreft. Verandert er niets, dan doet het niets en kost het niets.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/agenda_signaal.py
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
from koppelingen import agenda as A           # noqa: E402

STAND = Path.home() / "appportal/mijnagents-data/agenda-signaal.json"
PYTHON = str(Path.home() / "agents/.venv/bin/python")


def vorige():
    try:
        return json.loads(STAND.read_text())
    except (OSError, ValueError):
        return {}


def bewaar(d):
    STAND.parent.mkdir(parents=True, exist_ok=True)
    STAND.write_text(json.dumps(d, indent=0))


def main():
    st = vorige()
    sinds = st.get("gekeken") or (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    nu = datetime.now(timezone.utc)
    kop = {"Authorization": "Bearer " + A._toegang()}
    dagen, wat = set(), []
    for kal in W.kalenders():
        q = {"updatedMin": sinds, "singleEvents": "true", "showDeleted": "true", "maxResults": "250",
             "timeMin": (nu - timedelta(days=1)).isoformat(),
             "timeMax": (nu + timedelta(days=30)).isoformat(),
             "fields": "items(summary,status,updated,start/dateTime,start/date)"}
        url = f"{A.API}/calendars/{urllib.parse.quote(kal, safe='')}/events?" + urllib.parse.urlencode(q)
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=kop), timeout=40))
        except urllib.error.HTTPError as e:
            print(f"{kal[:32]}: HTTP {e.code}", file=sys.stderr)
            continue
        for ev in d.get("items", []):
            s = (ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or "")[:10]
            if not s:
                continue
            # reistijdblokken van de wacht zelf tellen niet mee, anders start hij zichzelf
            if W.lees_titel(ev.get("summary", "") or "")["reistijd"]:
                continue
            dagen.add(s)
            wat.append(f"{s} {ev.get('status','')[:9]:<9} {(ev.get('summary') or '(zonder titel)')[:52]}")

    bewaar({"gekeken": nu.isoformat(), "laatste_dagen": sorted(dagen)})
    tijd = f"{W.nu_lokaal():%d-%m %H:%M}"          # elke regel met zijn tijd (Brussel)
    if not dagen:
        print(tijd, "niets gewijzigd")
        return 0
    print(f"{tijd} {len(wat)} wijziging(en) op {len(dagen)} dag(en):")
    for r in sorted(set(wat))[:20]:
        print("  ", r)
    for dag in sorted(dagen):
        r = subprocess.run([PYTHON, str(HIER / "agenda_wacht.py"), "--dag", dag],
                           capture_output=True, text=True, timeout=900)
        laatste = [x for x in r.stdout.splitlines() if "[schrijf]" in x or "[bevinding]" in x]
        print(f"  wacht gedraaid voor {dag}: " + ("; ".join(x.strip()[:70] for x in laatste[:3]) or "geen uitvoer"))
    return 0


if __name__ == "__main__":
    # cron start dit om de 12 minuten, de klok rond; ik kijk van 06:00 tot 23:59 Brusselse
    # tijd. Mehdi verzet ook 's avonds laat nog afspraken. Gezien 24-09-2026: op UTC liep het
    # van 08:00 tot 23:59 en miste het de vroege ochtend.
    if "--ronde" in sys.argv and not W.binnen_uren(6, 23):
        sys.exit(0)
    sys.exit(main())
