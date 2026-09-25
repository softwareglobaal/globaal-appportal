#!/usr/bin/env python3
"""Eenmalig: het Calendly-type 'HA: Klant' van het account light@h-architects.be uitzetten.

Waarom: dat type boekt in de archiefagenda haagendalightprojects (FR-39). Klanten boeken voortaan
via 'H-Architects: Klant' van het account General, dat op werk schrijft. Mehdi zei op 25-09-2026
'doe maar', na de laatste geboekte afspraak van 30-09.

Wat het doet, en in deze volgorde:
  1. alleen op of na 01-10-2026, en maar een keer (vlag in mijnagents-data);
  2. nagaan of er op light@ nog komende boekingen staan: zo ja, niets uitzetten en melden;
  3. anders het type uitzetten (active = false) en teruglezen of het uit staat;
  4. het resultaat op het bord zetten.
Het verwijdert niets: een uitgezet type kan in Calendly met een klik weer aan.
Cron (VM, UTC): 0 7 1 10 *  (09:00 Brusselse tijd)
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))

TYPE_URI = "https://api.calendly.com/event_types/5c6238ec-8f84-4ee2-8c53-20d75b15d2c1"   # HA: Klant op light@
VLAG = Path.home() / "appportal/mijnagents-data/calendly-ha-klant-uit.json"
NIEUWE_LINK = "https://calendly.com/general-meetings-2026/h-architects-klant"


def sleutel():
    for pad in ("~/appportal/mijnagents-data/.env", "~/appportal/.env"):
        try:
            for r in open(os.path.expanduser(pad)):
                if r.startswith("CALENDLY_TOKEN_LIGHT="):
                    return r.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return ""


def api(methode, url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=methode,
                                 headers={"Authorization": f"Bearer {sleutel()}", "Content-Type": "application/json",
                                          "User-Agent": "agendawacht/1.0"})   # zonder eigen User-Agent geeft Calendly 403
    return json.load(urllib.request.urlopen(req, timeout=30))


def melden(titel, inhoud):
    try:
        import agenda_wacht as W
        W.ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": datetime.now().date().isoformat(), "titel": titel,
                        "uniek": "calendly-ha-klant-uit", "inhoud": inhoud}])
        W.ag.log(datetime.now().date().isoformat(), "schrijf", titel, inhoud)
        W.ag.log_verstuur()
    except Exception as e:  # noqa: BLE001
        print("bord niet bereikt:", type(e).__name__, file=sys.stderr)


def main():
    nu = datetime.now(timezone.utc)
    if nu.date().isoformat() < "2026-10-01" and "--nu" not in sys.argv:
        print("nog niet: pas vanaf 01-10-2026"); return 0
    if VLAG.exists():
        print("al gedaan:", VLAG.read_text()[:200]); return 0
    ik = api("GET", "https://api.calendly.com/users/me")["resource"]
    komend = api("GET", f"https://api.calendly.com/scheduled_events?user={ik['uri']}&status=active"
                        f"&min_start_time={nu.strftime('%Y-%m-%dT%H:%M:%SZ')}&count=20")["collection"]
    if komend:
        lijst = "\n".join(f"- {e['start_time'][:16]} UTC {e['name']}" for e in komend)
        melden("HA: Klant NIET uitgezet: er staan nog boekingen op", lijst + "\n\nIk zet het niet vanzelf later uit; zeg het als het mag.")
        print("niet uitgezet, nog boekingen:\n" + lijst); return 0
    api("PATCH", TYPE_URI, {"active": False})
    terug = api("GET", TYPE_URI)["resource"]
    staat = "uit" if not terug.get("active") else "NOG AAN"
    VLAG.write_text(json.dumps({"tijd": nu.isoformat(), "type": terug.get("name"), "staat": staat}, ensure_ascii=False))
    melden(f"Calendly 'HA: Klant' (light@) staat {staat}",
           f"Klanten boeken voortaan via {NIEUWE_LINK} (account General, schrijft op werk). Weer aanzetten kan in Calendly met een klik.")
    print("HA: Klant staat", staat); return 0


if __name__ == "__main__":
    sys.exit(main())
