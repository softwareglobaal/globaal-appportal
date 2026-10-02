"""Mail als afsprakenbron: mch@h-architects.be en mehdichegini@hotmail.com ('Agendawacht - onderzoek en herstelvoorstel
v1.1', werkpakket 2, A1-A3).

Een afspraak die alleen per mail binnenkwam (een uitnodiging, een bevestiging, een herinnering van de kinesist) bleef
buiten elke controle: de Agendawacht las alleen Google, en postvak.py zette afspraakmails bij 'melding'. Nu:
- lezen: koppelingen/post_lezer.py draait in de postcontainer (daar staan mailboxconfig en het OAuth-token van
  Hotmail), alleen lezen en met PEEK; zo leest de server Hotmail zelf, zonder de Mac;
- ontleden: ICS (VEVENT: METHOD, UID, SEQUENCE, DTSTAMP, RECURRENCE-ID, DTSTART, DTEND, SUMMARY, LOCATION, STATUS) of,
  zonder ICS, datum en uur uit onderwerp of tekst;
- bewaren: een register met herkomst (mailbox, Message-ID, ontvangen, afzender). Sleutel is de ICS-UID (en
  RECURRENCE-ID): dezelfde uitnodiging via twee mailboxen is een afspraak, en de hoogste SEQUENCE wint, zodat een oude
  doorgestuurde mail een nieuwere versie niet terugdraait;
- vergelijken met de agenda: gekoppeld (zelfde iCalUID, of hetzelfde uur op een van de agenda's), ontbreekt,
  geannuleerd (en staat er nog: een vraag), of zonder tijdstip (een controlepunt met bron-ID).
De agent maakt uit mail nooit zelf een afspraak, verplaatst niets en verstuurt niets: wat ontbreekt, toont hij.
"""
import email.utils
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
DB = os.environ.get("MAIL_AFSPRAKEN_DB", os.path.expanduser("~/appportal/mijnagents-data/afspraken_mail.db"))
MAILBOXEN = ("mch@h-architects.be", "mehdichegini@hotmail.com")
PRIVE = {"mehdichegini@hotmail.com"}
CONTAINER = os.environ.get("POST_CONTAINER", "appportal-app-post-1")
LEZER = Path(__file__).with_name("post_lezer.py")
# Outlook schrijft Windows-namen; alles in West-Europa valt voor Mehdi samen met Brussel
TZ_WINDOWS = {"romance standard time": "Europe/Brussels", "w. europe standard time": "Europe/Brussels",
              "central europe standard time": "Europe/Brussels", "central european standard time": "Europe/Brussels",
              "gmt standard time": "Europe/London", "utc": "UTC"}
AFSPRAAKWOORD = re.compile(r"(afspraak|appointment|meeting|vergadering|uitnodiging|invitation|new event|rendez-vous|"
                           r"reservatie|reservation|consultatie|bezoek)", re.I)
MAANDEN = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
MAANDEN.update({"mrt": 3, "mei": 5, "okt": 10, "januari": 1, "februari": 2, "maart": 3, "april": 4, "juni": 6, "juli": 7,
                "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12})

SCHEMA = ("""CREATE TABLE IF NOT EXISTS afspraak (
    sleutel TEXT PRIMARY KEY, soort TEXT NOT NULL, ics_uid TEXT NOT NULL DEFAULT '', recurrence_id TEXT NOT NULL DEFAULT '',
    sequence INTEGER NOT NULL DEFAULT 0, dtstamp TEXT NOT NULL DEFAULT '', method TEXT NOT NULL DEFAULT '',
    geannuleerd INTEGER NOT NULL DEFAULT 0, start TEXT NOT NULL DEFAULT '', einde TEXT NOT NULL DEFAULT '',
    titel TEXT NOT NULL DEFAULT '', locatie TEXT NOT NULL DEFAULT '', bron_mailbox TEXT NOT NULL, bron_message_id TEXT NOT NULL,
    bron_onderwerp TEXT NOT NULL DEFAULT '', bron_ontvangen TEXT NOT NULL DEFAULT '', bron_afzender TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'nieuw', google TEXT NOT NULL DEFAULT '', gecontroleerd TEXT NOT NULL DEFAULT '')""",
          """CREATE TABLE IF NOT EXISTS bron (
    mailbox TEXT NOT NULL, message_id TEXT NOT NULL, sleutel TEXT NOT NULL, map TEXT NOT NULL DEFAULT '',
    imap_uid INTEGER, ontvangen TEXT NOT NULL DEFAULT '', afzender TEXT NOT NULL DEFAULT '', onderwerp TEXT NOT NULL DEFAULT '',
    gezien TEXT NOT NULL, PRIMARY KEY (mailbox, message_id, sleutel))""",
          """CREATE TABLE IF NOT EXISTS leesstand (
    mailbox TEXT PRIMARY KEY, laatst_gelukt TEXT NOT NULL DEFAULT '', laatste_poging TEXT NOT NULL DEFAULT '',
    laatste_fout TEXT NOT NULL DEFAULT '')""")


def _db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    for s in SCHEMA:
        c.execute(s)
    return c


def _nu():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------------------- ICS ontleden ---
def _regels(ics):
    """Ontvouwde regels (RFC 5545: een regel die met een spatie of tab begint, hoort bij de vorige)."""
    uit = []
    for r in ics.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if r[:1] in (" ", "\t") and uit:
            uit[-1] += r[1:]
        elif r:
            uit.append(r)
    return uit


def _veld(regel):
    kop, _, waarde = regel.partition(":")
    naam, *params = kop.split(";")
    p = {}
    for x in params:
        k, _, v = x.partition("=")
        p[k.upper()] = v.strip('"')
    return naam.upper(), p, waarde


def _tijd(waarde, params):
    """DTSTART/DTEND naar een ISO-tijd in Brussel; een datum zonder uur blijft een datum."""
    w = waarde.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", w):
        return date(int(w[:4]), int(w[4:6]), int(w[6:8])).isoformat()
    t = datetime.strptime(w[:15], "%Y%m%dT%H%M%S")
    if w.endswith("Z"):
        t = t.replace(tzinfo=timezone.utc)
    else:
        tzid = (params.get("TZID") or "").strip()
        try:
            zone = ZoneInfo(TZ_WINDOWS.get(tzid.lower(), tzid)) if tzid else BRUSSEL
        except Exception:  # noqa: BLE001
            zone = BRUSSEL
        t = t.replace(tzinfo=zone)
    return t.astimezone(BRUSSEL).isoformat()


def ics_afspraken(ics):
    """De VEVENT's van een ICS als dicts. VTIMEZONE (met zijn DTSTART 1601) telt niet."""
    method, uit, ev, diepte = "", [], None, []
    for r in _regels(ics):
        naam, p, w = _veld(r)
        if naam == "BEGIN":
            diepte.append(w.upper())
            if w.upper() == "VEVENT":
                ev = {"method": method, "uid": "", "sequence": 0, "dtstamp": "", "recurrence_id": "", "start": "",
                      "einde": "", "titel": "", "locatie": "", "status": ""}
            continue
        if naam == "END":
            if diepte:
                diepte.pop()
            if w.upper() == "VEVENT" and ev is not None:
                uit.append(ev)
                ev = None
            continue
        if diepte == ["VCALENDAR"] and naam == "METHOD":
            method = w.strip().upper()
        if ev is None or (diepte and diepte[-1] != "VEVENT"):
            continue
        try:
            if naam == "UID":
                ev["uid"] = w.strip()
            elif naam == "SEQUENCE":
                ev["sequence"] = int(w.strip() or 0)
            elif naam == "DTSTAMP":
                ev["dtstamp"] = w.strip()
            elif naam == "RECURRENCE-ID":
                ev["recurrence_id"] = _tijd(w, p)
            elif naam == "DTSTART":
                ev["start"] = _tijd(w, p)
            elif naam == "DTEND":
                ev["einde"] = _tijd(w, p)
            elif naam == "SUMMARY":
                ev["titel"] = w.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()
            elif naam == "LOCATION":
                ev["locatie"] = w.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()
            elif naam == "STATUS":
                ev["status"] = w.strip().upper()
        except ValueError:
            continue
    for e in uit:
        e["geannuleerd"] = e["method"] == "CANCEL" or e["status"] == "CANCELLED"
    return uit


# -------------------------------------------------------------------------------- zonder ICS: datum uit de tekst ---
def tijd_uit_tekst(onderwerp, tekst, ontvangen):
    """(start als ISO in Brussel, of '' als er geen uur te vinden is). Herkent wat in Mehdi's mail staat:
    'woensdag 30/09/2026 om 08:30' (kinesist), 'New Event: Benny Desmedt - 10:00 Fri, 2 Oct 2026' (Calendly),
    "Today's 14:00 meeting", '12 oktober 2026 om 19:30'."""
    for bron in (onderwerp or "", tekst or ""):
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*(?:om|at|,)?\s*(\d{1,2})[:u.h](\d{2})", bron)
        if m:
            d, mn, j, u, mi = map(int, m.groups())
            return datetime(j, mn, d, u, mi, tzinfo=BRUSSEL).isoformat()
        m = re.search(r"(\d{1,2}):(\d{2})\s+\w{3},?\s+(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", bron)
        if m and m.group(4)[:3].lower() in MAANDEN:
            u, mi, d, mn, j = int(m.group(1)), int(m.group(2)), int(m.group(3)), MAANDEN[m.group(4)[:3].lower()], int(m.group(5))
            return datetime(j, mn, d, u, mi, tzinfo=BRUSSEL).isoformat()
        m = re.search(r"(\d{1,2})\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)"
                      r"\s+(\d{4})\s*(?:om|,|-|–)?\s*(\d{1,2})[:u.h](\d{2})", bron, re.I)
        if m:
            return datetime(int(m.group(3)), MAANDEN[m.group(2).lower()], int(m.group(1)), int(m.group(4)), int(m.group(5)),
                            tzinfo=BRUSSEL).isoformat()
        m = re.search(r"today'?s\s+(\d{1,2}):(\d{2})|vandaag\s+om\s+(\d{1,2})[:u.h](\d{2})", bron, re.I)
        if m and ontvangen:
            u, mi = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            d = datetime.fromisoformat(ontvangen).astimezone(BRUSSEL)
            return d.replace(hour=int(u), minute=int(mi), second=0, microsecond=0).isoformat()
    return ""


def _ontvangen(datum_kop):
    try:
        return email.utils.parsedate_to_datetime(datum_kop).astimezone(BRUSSEL).isoformat()
    except (TypeError, ValueError):
        return ""


def _adres(van):
    return (email.utils.parseaddr(van or "")[1] or "").lower()


def uit_kandidaat(k):
    """De afspraken (dicts met sleutel) in een kandidaat-mail van post_lezer."""
    ontvangen = _ontvangen(k.get("datum"))
    herkomst = {"bron_mailbox": k["mailbox"], "bron_message_id": k.get("message_id") or f"uid:{k.get('uid')}",
                "bron_onderwerp": (k.get("onderwerp") or "").replace("\n", " ")[:200], "bron_ontvangen": ontvangen,
                "bron_afzender": _adres(k.get("van")), "map": k.get("map", ""), "imap_uid": k.get("uid")}
    uit = []
    for ics in k.get("ics") or []:
        for e in ics_afspraken(ics):
            if not e["uid"] or not e["start"]:
                continue
            uit.append({**herkomst, "soort": "ics", "sleutel": f"ics|{e['uid']}|{e['recurrence_id']}", "ics_uid": e["uid"],
                        "recurrence_id": e["recurrence_id"], "sequence": e["sequence"], "dtstamp": e["dtstamp"],
                        "method": e["method"], "geannuleerd": e["geannuleerd"], "start": e["start"], "einde": e["einde"],
                        "titel": e["titel"], "locatie": e["locatie"]})
    if uit or not AFSPRAAKWOORD.search(k.get("onderwerp") or ""):
        return uit
    start = tijd_uit_tekst(k.get("onderwerp"), k.get("tekst"), ontvangen)
    domein = herkomst["bron_afzender"].split("@")[-1]
    sleutel = f"tekst|{start}|{domein}" if start else f"zonder|{herkomst['bron_message_id']}"
    return [{**herkomst, "soort": "tekst" if start else "zonder_tijd", "sleutel": sleutel, "ics_uid": "", "recurrence_id": "",
             "sequence": 0, "dtstamp": ontvangen, "method": "", "geannuleerd": bool(re.search(r"geannuleerd|cancel", k.get("onderwerp") or "", re.I)),
             "start": start, "einde": "", "titel": herkomst["bron_onderwerp"][:120], "locatie": ""}]


# ------------------------------------------------------------------------------------------------- register ---
def bewaar(afspraken, nu=None):
    """Zet de afspraken in het register. Een nieuwere versie (hogere SEQUENCE, of gelijk en later DTSTAMP) vervangt de
    oude; een oudere (een doorgestuurde oude mail) niet. Elke bron wordt bewaard. Geeft het aantal nieuwe of gewijzigde."""
    nu = (nu or _nu()).isoformat(timespec="seconds")
    gewijzigd = 0
    with _db() as c:
        for a in afspraken:
            c.execute("INSERT OR IGNORE INTO bron(mailbox,message_id,sleutel,map,imap_uid,ontvangen,afzender,onderwerp,gezien) "
                      "VALUES(?,?,?,?,?,?,?,?,?)", (a["bron_mailbox"], a["bron_message_id"], a["sleutel"], a.get("map", ""),
                                                    a.get("imap_uid"), a["bron_ontvangen"], a["bron_afzender"], a["bron_onderwerp"], nu))
            oud = c.execute("SELECT sequence, dtstamp FROM afspraak WHERE sleutel=?", (a["sleutel"],)).fetchone()
            if oud and (oud["sequence"], oud["dtstamp"]) >= (a["sequence"], a["dtstamp"]):
                continue
            velden = ("sleutel", "soort", "ics_uid", "recurrence_id", "sequence", "dtstamp", "method", "geannuleerd", "start",
                      "einde", "titel", "locatie", "bron_mailbox", "bron_message_id", "bron_onderwerp", "bron_ontvangen", "bron_afzender")
            c.execute(f"INSERT OR REPLACE INTO afspraak({','.join(velden)}, status) VALUES({','.join('?' * len(velden))}, 'nieuw')",
                      [int(a[v]) if v == "geannuleerd" else a[v] for v in velden])
            gewijzigd += 1
    return gewijzigd


def leesstand_zet(mailbox, gelukt, fout="", nu=None):
    nu = (nu or _nu()).isoformat(timespec="seconds")
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO leesstand(mailbox) VALUES(?)", (mailbox,))
        if gelukt:
            c.execute("UPDATE leesstand SET laatst_gelukt=?, laatste_poging=?, laatste_fout='' WHERE mailbox=?", (nu, nu, mailbox))
        else:
            c.execute("UPDATE leesstand SET laatste_poging=?, laatste_fout=? WHERE mailbox=?", (nu, fout[:300], mailbox))


def leesstand():
    with _db() as c:
        return {r["mailbox"]: dict(r) for r in c.execute("SELECT * FROM leesstand").fetchall()}


def alle():
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM afspraak ORDER BY start").fetchall()]


# ------------------------------------------------------------------------------------- vergelijken met de agenda ---
def _iso(t):
    return datetime.fromisoformat(t) if "T" in t else None


def vergelijk(afspraken, items, nu=None):
    """Zet per afspraak de status tegenover de agenda-items (van alle agenda's): gekoppeld, ontbreekt, geannuleerd (staat
    er niet meer), geannuleerd_staat_er (een vraag), zonder_tijd (controlepunt), voorbij. Geeft de afspraken met
    'status' en 'google' ingevuld."""
    nu = nu or _nu()
    per_uid = {}
    for x in items:
        if x.get("_icaluid"):
            per_uid.setdefault(x["_icaluid"], []).append(x)
    uit = []
    for a in afspraken:
        a = dict(a)
        start = _iso(a["start"]) if a["start"] else None
        match = None
        kand = per_uid.get(a["ics_uid"], []) if a["ics_uid"] else []
        if kand and a["recurrence_id"]:
            kand = [x for x in kand if x.get("start", "")[:10] in (a["recurrence_id"][:10], a["start"][:10])]
        if kand:
            match = kand[0]
        elif start:
            for x in items:
                xs = _iso(x.get("start") or "")
                if xs and not x.get("hele_dag") and abs((xs - start).total_seconds()) <= 300:
                    match = x
                    break
        a["google"] = f"{match['kalender']}|{match['id']}" if match else ""
        if a["soort"] == "zonder_tijd":
            a["status"] = "zonder_tijd"
        elif start is None and a["start"]:
            a["status"] = "gekoppeld" if match else "ontbreekt"       # een hele-dag-afspraak
        elif a["geannuleerd"]:
            a["status"] = "geannuleerd_staat_er" if match else "geannuleerd"
        elif match:
            a["status"] = "gekoppeld"
        elif start and start < nu - timedelta(hours=1):
            a["status"] = "voorbij"
        else:
            a["status"] = "ontbreekt"
        uit.append(a)
    return uit


def statussen_bewaren(afspraken, nu=None):
    nu = (nu or _nu()).isoformat(timespec="seconds")
    with _db() as c:
        for a in afspraken:
            c.execute("UPDATE afspraak SET status=?, google=?, gecontroleerd=? WHERE sleutel=?", (a["status"], a["google"], nu, a["sleutel"]))


# ---------------------------------------------------------------------------------------------------- lezen ---
def lees(sinds, mailboxen=MAILBOXEN, maximaal=400):
    """Leest de kandidaten via de postcontainer. Geeft (kandidaten, fouten). Faalt het hele lezen, dan een fout per
    mailbox, nooit een stille lege lijst."""
    opdracht = json.dumps({"mailboxen": list(mailboxen), "sinds": sinds, "maximaal": maximaal})
    try:
        r = subprocess.run(["docker", "exec", "-i", "-e", f"LEES={opdracht}", "-w", "/app", CONTAINER, "python", "-"],
                           stdin=open(LEZER, "rb"), capture_output=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="replace")[-300:] or f"exit {r.returncode}")
        d = json.loads(r.stdout.decode())
        return d.get("kandidaten") or [], d.get("fouten") or []
    except Exception as e:  # noqa: BLE001
        return [], [{"mailbox": m, "fout": f"{type(e).__name__}: {str(e)[:200]}"} for m in mailboxen]


def ronde(items, sinds, nu=None):
    """Een volledige ronde: lezen, bewaren, vergelijken met de agenda. Geeft (afspraken met status, fouten)."""
    kandidaten, fouten = lees(sinds)
    stuk = {f["mailbox"] for f in fouten if not f.get("map")}          # de hele mailbox; een map apart is geen uitval
    for m in MAILBOXEN:
        leesstand_zet(m, m not in stuk, "; ".join(f"{f.get('map', '')}: {f['fout']}" for f in fouten if f["mailbox"] == m), nu)
    for k in kandidaten:
        bewaar(uit_kandidaat(k), nu)
    afspraken = vergelijk(alle(), items, nu)
    statussen_bewaren(afspraken, nu)
    return afspraken, fouten


def sleutel_kort(a):
    return hashlib.sha256(a["sleutel"].encode()).hexdigest()[:16]
