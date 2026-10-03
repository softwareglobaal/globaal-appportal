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


# Leesstand per agenda: laatste poging, laatste geslaagde lezing en fout (nacontrole v1.3, R7). Alleen geschreven als de
# datamap al bestaat: een test of de Mac maakt nooit een map aan.
LEESSTAND = os.environ.get("AGENDA_LEESSTAND", os.path.expanduser("~/appportal/mijnagents-data/agenda-leesstand.json"))


def leesstand():
    try:
        with open(LEESSTAND, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _leesstand_zet(per_kal):
    if not per_kal or not os.path.isdir(os.path.dirname(LEESSTAND)):
        return
    d, nu = leesstand(), datetime.now(timezone.utc).isoformat(timespec="seconds")
    for kal, fout in per_kal.items():
        r = d.setdefault(kal, {})
        r["laatste_poging"], r["fout"] = nu, fout or ""
        if not fout:
            r["laatst_gelukt"] = nu
    tmp = LEESSTAND + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEESSTAND)


def interne_adressen():
    """De agenda-adressen van collega's en partners (organisatie.globaal.be, migratie 185). Faalt die bron, dan een
    lege set: dan telt elke gast als extern, zoals voor 03-10-2026. Dat is de veilige kant: de agent doet dan minder
    aan zo'n afspraak, niet meer."""
    try:
        import organisatie  # noqa: PLC0415
        return set(organisatie.agenda_adressen())
    except Exception:  # noqa: BLE001
        return set()


def afspraken(van_dagen=-1, tot_dagen=8):
    """Alle afspraken van alle kalenders tussen vandaag+van_dagen en vandaag+tot_dagen.
    Elk item: kalender, id, titel, start, einde, hele_dag, locatie, omschrijving, deelnemers."""
    nu = datetime.now(timezone.utc)
    tmin = (nu + timedelta(days=van_dagen)).replace(hour=0, minute=0, second=0, microsecond=0)
    tmax = (nu + timedelta(days=tot_dagen)).replace(hour=0, minute=0, second=0, microsecond=0)
    uit = []
    gezien = set()
    _intern = interne_adressen()
    per_kal = {}
    for kal in kalenders():
        # Alle pagina's, niet alleen de eerste 250. Gezien 21-09-2026: de agenda van Lara
        # heeft er over een schooljaar meer, en alles na maart viel stil weg.
        items, pagina, mislukt = [], None, False
        while True:
            params = {"timeMin": tmin.isoformat(), "timeMax": tmax.isoformat(), "singleEvents": "true",
                      "orderBy": "startTime", "maxResults": 250}
            if pagina:
                params["pageToken"] = pagina
            url = f"{API}/calendars/{urllib.parse.quote(kal, safe='')}/events?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_toegang()}"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.load(r)
            except urllib.error.HTTPError as e:
                uit.append({"kalender": kal, "fout": f"{e.code}"})
                per_kal[kal] = f"HTTP {e.code}"
                mislukt = True
                break
            items += d.get("items", [])
            pagina = d.get("nextPageToken")
            if not pagina:
                break
        if mislukt:
            continue
        per_kal[kal] = ""
        for ev in items:
            if ev.get("status") == "cancelled":
                continue
            # Een uitnodiging staat op elke agenda die ze kreeg (bv. Contrax en
            # mehdiprivewerkagenda) met hetzelfde id: één keer tellen, anders
            # botst een afspraak met zichzelf (gemeten 17-09-2026).
            if ev.get("id") in gezien:
                continue
            gezien.add(ev.get("id"))
            s, e_ = ev.get("start", {}), ev.get("end", {})
            uit.append({
                "kalender": kal, "id": ev.get("id", ""), "titel": ev.get("summary", "(zonder titel)"),
                "start": s.get("dateTime") or s.get("date", ""), "einde": e_.get("dateTime") or e_.get("date", ""),
                "hele_dag": "date" in s and "dateTime" not in s,
                "locatie": ev.get("location", ""), "omschrijving": (ev.get("description") or "")[:2000],
                # gasten van buiten; een agendagast (collega of partner met een agenda-adres op organisatie.globaal.be)
                # telt niet mee: met hem erbij blijft het een eigen afspraak (Mehdi, 03-10-2026)
                "deelnemers": [a.get("email", "") for a in ev.get("attendees", []) if a.get("email")
                               and a["email"].lower() not in _intern],
                "_agendagasten": [a["email"].lower() for a in ev.get("attendees", []) if a.get("email", "").lower() in _intern],
                "_organisator_zelf": bool((ev.get("organizer") or {}).get("self")),
                # wie de afspraak heeft aangemaakt (Google: creator). Zo is achteraf te zien
                # wie iets zette en waarom het ergens staat. Mandaat van Mehdi, 22-09-2026.
                "maker": (ev.get("creator") or {}).get("email", ""),
                "_gemaakt": ev.get("created", ""),
                "_conferentie": bool(ev.get("hangoutLink") or ev.get("conferenceData")),
                "link": ev.get("htmlLink", ""),
                "_reminders": ev.get("reminders") or {},
                "_terugkerend": bool(ev.get("recurringEventId")),
                "_reeks": ev.get("recurringEventId", ""),
                "_kleur": ev.get("colorId", ""),
                "_gewijzigd": ev.get("updated", ""),
                # het merk dat de Agendawacht achterlaat (welke kleur zette hij zelf)
                "_merk": (ev.get("extendedProperties") or {}).get("private") or {},
                # 'Beschikbaar' in Google (transparent): Calendly telt het niet als bezet (FR-84)
                "_vrij": ev.get("transparency") == "transparent",
                # de UID van de uitnodiging (ICS): zo koppelt een afspraak uit mail aan dit item (mail als bron, audit 02-10-2026)
                "_icaluid": ev.get("iCalUID", ""),
                # de oorspronkelijke start van een reeksinstantie, ook na verplaatsing (Google: originalStartTime, R11)
                "_origineel": (ev.get("originalStartTime") or {}).get("dateTime") or (ev.get("originalStartTime") or {}).get("date") or "",
            })
    try:
        _leesstand_zet(per_kal)
    except OSError:
        pass
    uit.sort(key=lambda x: x.get("start", ""))
    return uit


def kalendernamen():
    """id -> naam zoals die nu in Google staat, voor alle agenda's van dit account.
    Gebruikt om te zien wat Mehdi op ZZ ARCHIEF heeft gezet."""
    kop = {"Authorization": "Bearer " + _toegang()}
    uit, pagina = {}, None
    while True:
        q = {"maxResults": "250", "showHidden": "true", "fields": "items(id,summary,summaryOverride),nextPageToken"}
        if pagina:
            q["pageToken"] = pagina
        req = urllib.request.Request(API + "/users/me/calendarList?" + urllib.parse.urlencode(q), headers=kop)
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        for c in d.get("items", []):
            uit[c["id"]] = c.get("summaryOverride") or c.get("summary") or ""
        pagina = d.get("nextPageToken")
        if not pagina:
            return uit
