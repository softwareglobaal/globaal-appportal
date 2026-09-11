"""Google Agenda van Mehdi, alleen lezen, vanaf de host.

Sleutels bij naam uit ~/appportal/.env: GOOGLE_AGENDA_CLIENT_ID,
GOOGLE_AGENDA_CLIENT_SECRET, GOOGLE_AGENDA_REFRESH_TOKEN (Mehdi's eigen account,
zelfde toegang als globaal-calendar-mehdi). Welke agenda's: CONTRACTEN_KALENDERS
(komma-gescheiden), zelfde lijst als het contract-dashboard gebruikt.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://www.googleapis.com/calendar/v3"
_token = {"waarde": "", "tot": 0.0}


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/.env")


def beschikbaar():
    return all(os.environ.get(n, "").strip() for n in
               ("GOOGLE_AGENDA_CLIENT_ID", "GOOGLE_AGENDA_CLIENT_SECRET", "GOOGLE_AGENDA_REFRESH_TOKEN"))


def kalenders():
    ruw = os.environ.get("CONTRACTEN_KALENDERS", "").strip()
    return [k.strip() for k in ruw.split(",") if k.strip()] or ["primary"]


def _toegang():
    if _token["waarde"] and time.time() < _token["tot"]:
        return _token["waarde"]
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": os.environ["GOOGLE_AGENDA_REFRESH_TOKEN"].strip(),
        "client_id": os.environ["GOOGLE_AGENDA_CLIENT_ID"].strip(),
        "client_secret": os.environ["GOOGLE_AGENDA_CLIENT_SECRET"].strip(),
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data, timeout=20) as r:
        a = json.load(r)
    _token["waarde"], _token["tot"] = a["access_token"], time.time() + int(a.get("expires_in", 3600)) - 120
    return _token["waarde"]


def afspraken(van_dagen=-1, tot_dagen=8):
    """Alle afspraken van alle kalenders tussen vandaag+van_dagen en vandaag+tot_dagen.
    Elk item: kalender, id, titel, start, einde, hele_dag, locatie, omschrijving, deelnemers."""
    nu = datetime.now(timezone.utc)
    tmin = (nu + timedelta(days=van_dagen)).replace(hour=0, minute=0, second=0, microsecond=0)
    tmax = (nu + timedelta(days=tot_dagen)).replace(hour=0, minute=0, second=0, microsecond=0)
    uit = []
    for kal in kalenders():
        params = {"timeMin": tmin.isoformat(), "timeMax": tmax.isoformat(), "singleEvents": "true",
                  "orderBy": "startTime", "maxResults": 250}
        url = f"{API}/calendars/{urllib.parse.quote(kal, safe='')}/events?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_toegang()}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            uit.append({"kalender": kal, "fout": f"{e.code}"})
            continue
        for ev in d.get("items", []):
            if ev.get("status") == "cancelled":
                continue
            s, e_ = ev.get("start", {}), ev.get("end", {})
            uit.append({
                "kalender": kal, "id": ev.get("id", ""), "titel": ev.get("summary", "(zonder titel)"),
                "start": s.get("dateTime") or s.get("date", ""), "einde": e_.get("dateTime") or e_.get("date", ""),
                "hele_dag": "date" in s and "dateTime" not in s,
                "locatie": ev.get("location", ""), "omschrijving": (ev.get("description") or "")[:2000],
                "deelnemers": [a.get("email", "") for a in ev.get("attendees", []) if a.get("email")],
                "link": ev.get("htmlLink", ""),
                "_reminders": ev.get("reminders") or {},
            })
    uit.sort(key=lambda x: x.get("start", ""))
    return uit
