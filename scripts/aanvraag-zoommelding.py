#!/usr/bin/env python3
"""Meldt elke nieuwe websiteaanvraag van UNABO meteen in Zoom, kanaal
"General (Sales team)".

Waarom (vraag van Siyan, 24 sep 2026): sales moet weten dat er een aanvraag
aankomt VOORDAT de automaat ze in Pipedrive zet. Verschijnt de deal daarna
niet, dan merkt een mens het ("melding gehad, na een uur niets in Pipedrive")
en weten we dat de keten stuk is. Van 18 tot 24 sep kwam er geen enkele
meldingsmail aan zonder dat iemand het zag; dat mag niet opnieuw gebeuren.

Daarom leest dit script bewust de EERSTE schakel: het bestand dat de website
zelf wegschrijft (/data/aanvragen.jsonl in container unabo-web). Het hangt
niet af van de wachtrij, de verwerker, Google Contacts of Pipedrive. Valt één
daarvan om, dan komt deze melding nog steeds.

Geen e-mailadres of telefoonnummer in Zoom: alleen naam en dienst. De rest
staat in de mail en in Pipedrive.

Cron (elke minuut):
  * * * * * /usr/bin/flock -n /tmp/aanvraag-zoommelding.lock /usr/bin/python3 /home/ubuntu/appportal/scripts/aanvraag-zoommelding.py >> /home/ubuntu/aanvraag-zoommelding.log 2>&1

Droogdraaien (toont wat er zou vertrekken, verstuurt en onthoudt niets):
  python3 ~/appportal/scripts/aanvraag-zoommelding.py --droog
Testbericht naar het kanaal:
  python3 ~/appportal/scripts/aanvraag-zoommelding.py --test
"""
import base64
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KANAAL = "General (Sales team)"
LEADS_CONTAINER = "unabo-web"
LEADS_PAD = "/data/aanvragen.jsonl"
STAND = os.path.expanduser("~/appportal/aanvraag-data/zoommelding.state")
ZOOM_ENV = os.path.expanduser("~/pipedrive-won-deals/.env")   # zelfde Zoom-app als de won-deal-melder


def nu():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def env():
    waarden = {}
    for regel in open(ZOOM_ENV):
        regel = regel.strip()
        if regel and not regel.startswith("#") and "=" in regel:
            k, v = regel.split("=", 1)
            waarden[k.strip()] = v.strip().strip('"').strip("'")
    return waarden


def aanvragen():
    uit = subprocess.run(["/usr/bin/docker", "exec", LEADS_CONTAINER, "cat", LEADS_PAD],
                         check=True, timeout=30, capture_output=True, text=True).stdout
    rijen = []
    for regel in uit.splitlines():
        try:
            rijen.append(json.loads(regel))
        except ValueError:
            continue
    return rijen


def sleutel(a):
    return f"{a.get('tijdstip', '')}|{(a.get('email') or '').lower()}"


def bericht(a):
    naam = f"{a.get('voornaam', '')} {a.get('achternaam', '')}".strip() or "(geen naam)"
    diensten = ", ".join(a.get("diensten") or []) or "niet opgegeven"
    try:
        t = datetime.fromisoformat(str(a.get("tijdstip")).replace("Z", "+00:00"))
        moment = t.astimezone(ZoneInfo("Europe/Brussels")).strftime("%d-%m om %H:%M")
    except ValueError:
        moment = "zonet"
    return ("📩 Nieuwe aanvraag via de website\n"
            f"Klant: {naam}\n"
            f"Dienst: {diensten}\n"
            f"Binnengekomen: {moment} (Belgische tijd)\n"
            "De deal en de mail naar sales@unabo.be volgen binnen 15 minuten. "
            "Na een uur nog niets in Pipedrive? Meld het aan Siyan.")


class Zoom:
    def __init__(self):
        e = env()
        self.sender = e["ZOOM_SENDER"]
        url = "https://zoom.us/oauth/token?" + urllib.parse.urlencode(
            {"grant_type": "account_credentials", "account_id": e["ZOOM_ACCOUNT_ID"]})
        req = urllib.request.Request(url, method="POST")
        req.add_header("Authorization", "Basic " + base64.b64encode(
            f"{e['ZOOM_CLIENT_ID']}:{e['ZOOM_CLIENT_SECRET']}".encode()).decode())
        with urllib.request.urlopen(req, timeout=20) as r:
            self.token = json.load(r)["access_token"]

    def _api(self, pad, body=None):
        req = urllib.request.Request("https://api.zoom.us/v2" + pad,
                                     data=json.dumps(body).encode() if body else None,
                                     method="POST" if body else "GET")
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=20) as r:
            tekst = r.read().decode()
            return json.loads(tekst) if tekst else {}

    def kanaal(self, naam):
        volgende = ""
        while True:
            d = self._api(f"/chat/users/{urllib.parse.quote(self.sender)}/channels?page_size=100"
                          + (f"&next_page_token={volgende}" if volgende else ""))
            for c in d.get("channels") or []:
                if (c.get("name") or "").lower() == naam.lower():
                    return c["id"]
            volgende = d.get("next_page_token") or ""
            if not volgende:
                raise RuntimeError(f'kanaal "{naam}" niet gevonden; is {self.sender} lid?')

    def stuur(self, kanaal_id, tekst):
        self._api(f"/chat/users/{urllib.parse.quote(self.sender)}/messages",
                  {"to_channel": kanaal_id, "message": tekst})


def main(argv):
    droog = "--droog" in argv

    if "--test" in argv:
        z = Zoom()
        z.stuur(z.kanaal(KANAAL),
                "✅ Test: vanaf nu meldt de automaat hier elke nieuwe aanvraag via unabo.be, "
                "nog vóór ze in Pipedrive staat. Zie je een melding maar na een uur geen deal? "
                "Laat het Siyan weten.")
        print(f"{nu()} testbericht verstuurd naar {KANAAL}")
        return 0

    try:
        rijen = aanvragen()
    except Exception as e:  # noqa: BLE001
        print(f"{nu()} aanvraagbestand niet leesbaar: {type(e).__name__}: {e}"[:300])
        return 1

    try:
        stand = json.load(open(STAND))
    except (OSError, ValueError):
        stand = None

    if stand is None:
        # Eerste keer: alles wat er al staat als gemeld beschouwen, anders krijgt
        # sales in één klap alle oude aanvragen opnieuw te zien.
        if not droog:
            os.makedirs(os.path.dirname(STAND), exist_ok=True)
            json.dump({"gezien": [sleutel(a) for a in rijen]}, open(STAND, "w"))
        print(f"{nu()} eerste run: {len(rijen)} bestaande aanvragen als gemeld gemarkeerd")
        return 0

    gezien = set(stand.get("gezien") or [])
    nieuw = [a for a in rijen if sleutel(a) not in gezien]
    if not nieuw:
        return 0

    if droog:
        for a in nieuw:
            print(bericht(a) + "\n---")
        return 0

    z = Zoom()
    kanaal_id = z.kanaal(KANAAL)
    for a in nieuw:
        try:
            z.stuur(kanaal_id, bericht(a))
        except Exception as e:  # noqa: BLE001
            # Niet als gezien markeren: de volgende minuut opnieuw proberen.
            print(f"{nu()} melding mislukt voor {a.get('tijdstip')}: {type(e).__name__}: {e}"[:300])
            continue
        gezien.add(sleutel(a))
        json.dump({"gezien": sorted(gezien)}, open(STAND, "w"))
        print(f"{nu()} gemeld in {KANAAL}: {a.get('voornaam', '')} {a.get('achternaam', '')} "
              f"({', '.join(a.get('diensten') or [])})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
