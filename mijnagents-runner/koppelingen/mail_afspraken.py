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

Een smalle uitzondering ('Opdracht voor Claude - kine en tandarts in de privéagenda' v1.0, 14-10-2026): een bevestigde
afspraak voor Mehdi bij een beheerde persoonlijke zorgpraktijk (tabel zorgpraktijk in dit privéregister, nooit in git)
krijgt een echt blok in de privé-agenda. Hier gebeurt de herkenning: welke praktijk, welke gebeurtenis (bevestiging,
herinnering, aanvraag, verplaatsing, annulering), patiënt, behandelaar, begin, einde en plaats, met een duurzame
identiteit per afspraak. Een tijd of duur wordt nooit verzonnen: wat ontbreekt, blijft een open punt.
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
    laatste_fout TEXT NOT NULL DEFAULT '')""",
          # beheerde persoonlijke zorgpraktijken: alleen hier, op de server, nooit in git (privé)
          """CREATE TABLE IF NOT EXISTS zorgpraktijk (
    id TEXT PRIMARY KEY, profiel TEXT NOT NULL, bijgewerkt TEXT NOT NULL DEFAULT '')""")


# kolommen die later bijkwamen (nacontrole v1.2): een bestaand register krijgt ze erbij, niets gaat verloren
EXTRA_KOLOMMEN = {"afspraak": {"detail": "TEXT NOT NULL DEFAULT ''", "prive": "INTEGER NOT NULL DEFAULT 0",
                               "melding": "TEXT NOT NULL DEFAULT ''", "zorg": "TEXT NOT NULL DEFAULT ''"},
                  "leesstand": {"dekking": "TEXT NOT NULL DEFAULT ''",
                                "eerste_fout": "TEXT NOT NULL DEFAULT ''",
                                "fout_rondes": "INTEGER NOT NULL DEFAULT 0",
                                "laatste_nood": "TEXT NOT NULL DEFAULT ''"}}
# Hoe ver terug de lezer de zorgafzenders opvraagt: een bevestiging komt soms maanden vooraf (gemeten: bijna zeven
# maanden). Goedkoop, want de lezer zoekt op afzender.
ZORG_DAGEN_TERUG = 300


def _db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    for s in SCHEMA:
        c.execute(s)
    for tabel, kolommen in EXTRA_KOLOMMEN.items():
        er = {r[1] for r in c.execute(f"PRAGMA table_info({tabel})")}
        for k, soort in kolommen.items():
            if k not in er:
                c.execute(f"ALTER TABLE {tabel} ADD COLUMN {k} {soort}")
    # het privacylabel volgt de mailbox, ook voor rijen van voor de kolom bestond (live gezien 03-10-2026: de VME-mail
    # uit Hotmail stond op 0)
    c.execute(f"UPDATE afspraak SET prive=1 WHERE prive=0 AND bron_mailbox IN ({','.join('?' * len(PRIVE))})", sorted(PRIVE))
    c.commit()                    # de upgrade meteen vastleggen: geen open schrijftransactie achterlaten
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
            # een veld dat niet te lezen is (DTSTART:20260231...), is geen stilte: de afspraak draagt de fout (R10)
            ev.setdefault("fouten", []).append(f"{naam} onleesbaar: {w.strip()[:40]}")
            continue
    for e in uit:
        e["geannuleerd"] = e["method"] == "CANCEL" or e["status"] == "CANCELLED"
    return uit


def ics_problemen(k):
    """Relevante uitnodigingen in deze mail die niet te gebruiken zijn (een veld onleesbaar, of geen start zonder dat het
    een annulering is): elk een verwerkingsfout met bron-ID, zodat de dekking niet 'volledig' heet (nacontrole v1.3, R10)."""
    uit = []
    for ics in k.get("ics") or []:
        try:
            evs = ics_afspraken(ics)
        except Exception as e:  # noqa: BLE001
            uit.append(f"ICS niet te ontleden ({type(e).__name__})")
            continue
        for e in evs:
            if e.get("fouten") or (e["uid"] and not e["start"] and not e["geannuleerd"]):
                uit.append(f"uitnodiging {e['uid'][:30] or '?'} niet te gebruiken: {'; '.join(e.get('fouten') or ['geen start'])}")
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


# ------------------------------------------------------------------------- zorgpraktijken (persoonlijk, privé) ---
def zorgprofiel_zet(profiel, nu=None):
    """Legt een beheerd profiel vast in het privéregister: id, naam, soort, afzenders (exacte adressen), praktijknamen,
    adres, telefoon, website, patiënten (Mehdi's namen), behandelaars {naam: rol}, bewijs en verificatiedatum."""
    nu = (nu or _nu()).isoformat(timespec="seconds")
    p = dict(profiel)
    p["afzenders"] = sorted({a.strip().lower() for a in p.get("afzenders") or [] if a.strip()})
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO zorgpraktijk(id, profiel, bijgewerkt) VALUES(?,?,?)",
                  (p["id"], json.dumps(p, ensure_ascii=False), nu))


ZORG_FOUT = ""      # laatste fout bij het lezen van de profielen: de ronde meldt de dekking dan gedeeltelijk (Codex A06)


def zorgprofielen():
    global ZORG_FOUT
    ZORG_FOUT, uit = "", []
    try:
        with _db() as c:
            rijen = c.execute("SELECT id, profiel FROM zorgpraktijk ORDER BY id").fetchall()
    except sqlite3.Error as e:
        ZORG_FOUT = f"zorgprofielen niet te lezen ({type(e).__name__})"
        return []
    for r in rijen:
        try:
            uit.append(json.loads(r["profiel"]))
        except ValueError:
            ZORG_FOUT = f"zorgprofiel {r['id']} niet te lezen"
    return uit


def _zorgprofiel(afzender, profielen):
    """Alleen een exact afzenderadres uit een beheerd profiel telt; een gelijkend domein niet (info@praktijk.be kan
    een heel andere praktijk zijn dan info@praktijkleuven.be)."""
    a = (afzender or "").lower()
    return next((p for p in profielen or [] if a and a in (p.get("afzenders") or [])), None)


def _naam_plat(t):
    return re.sub(r"\s+", " ", _plat_tekst(t)).strip()


_MAAND = r"(jan|feb|mrt|mar|maa|apr|mei|may|jun|jul|aug|sep|okt|oct|nov|dec)[a-z]*\.?"
_ZORG_TIJD = (
    # 'woensdag 14/10/2026 om 08:30', '08.07.2026 13:30', 'Woensdag 12.08.2026 om 08:30'
    re.compile(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})\s*(?:om|at|,|-)?\s*(\d{1,2})[:u.h](\d{2})", re.I),
    # 'op 09 dec 2026 om 08:30', 'on 09 dec 2026 at 08:30'
    re.compile(r"(\d{1,2})\s+" + _MAAND + r"\s+(\d{4})\s*(?:om|at|,|-)?\s*(\d{1,2})[:u.h](\d{2})", re.I),
)
_ZORG_DATUM_UUR = re.compile(r"Afspraakdatum:\s*(\d{1,2})[./](\d{1,2})[./](\d{4}).{0,120}?Afspraaktijd:\s*(\d{1,2})[:u.h](\d{2})",
                             re.I | re.S)
# de gebeurtenis, in deze volgorde; de standaardzin 'voor het annuleren van een afspraak' is geen annulering
_GEBEURTENIS = (
    ("annulering", re.compile(r"\b(geannuleerd|annulering van uw afspraak|is afgezegd|cancelled|canceled)\b", re.I)),
    ("verplaatsing", re.compile(r"\b(verplaatst|verzet|gewijzigd|rescheduled|moved)\s+(naar|tot|to)\b", re.I)),
    ("aanvraag", re.compile(r"\b(geregistreerd|wacht op bevestiging|in afwachting|aanvraag|pending|requested)\b", re.I)),
    ("herinnering", re.compile(r"\b(herinner\w*|reminder|remind)\b", re.I)),
    ("bevestiging", re.compile(r"\b(bevestig\w*|geaccepteerd|accepted|confirm\w*|uw afspraak bij|your appointment)\b", re.I)),
)
_AFSPRAAKWOORD_ZORG = re.compile(r"(afspraak|appointment|boeking|booking|consult|therapeut|afspraakdatum)", re.I)
_NAAM_STOP = {"We", "Wij", "Dear", "This", "Hierbij", "Uw", "Graag", "Details", "Met", "Kind"}
# een aanspreking is geen naam: 'Beste Dhr. Chegini' is alleen een familienaam, dus niet zeker Mehdi (open punt)
_AANSPREKING = re.compile(r"^(dhr|mevr|mr|mrs|ms|mw|meneer|mevrouw|heer|sir|madam)\.?$", re.I)


# een antwoord citeert de vorige mail: 'Op di 17 mrt 2026 om 18:17 schreef ...' is geen afspraaktijd (live gezien 15-10-2026)
_CITAAT = re.compile(r"(\bOp\s[^.\n]{4,80}?\bschreef\b|\bOn\s[^.\n]{4,80}?\bwrote\b|-{3,}\s*(Oorspronkelijk bericht|Original Message)|"
                     r"\bVan:\s.{3,120}?\bVerzonden:|\bFrom:\s.{3,120}?\bSent:)", re.I | re.S)


def _zonder_citaat(tekst):
    m = _CITAAT.search(tekst or "")
    return tekst[:m.start()] if m else (tekst or "")


def _zorg_tijden(tekst):
    """Alle datum-en-uur-plekken in de tekst als [(positie, ISO in Brussel)], in volgorde."""
    uit = []
    m = _ZORG_DATUM_UUR.search(tekst)
    if m:
        d, mn, j, u, mi = map(int, m.groups())
        uit.append((m.start(), datetime(j, mn, d, u, mi, tzinfo=BRUSSEL).isoformat()))
    for patroon in _ZORG_TIJD:
        for m in patroon.finditer(tekst):
            g = m.groups()
            try:
                if len(g) == 5 and g[1].isdigit():
                    d, mn, j, u, mi = map(int, g)
                else:
                    d, mn, j, u, mi = int(g[0]), MAANDEN.get(g[1][:3].lower(), MAANDEN.get(g[1].lower(), 0)), int(g[2]), int(g[3]), int(g[4])
                    if not mn and g[1][:3].lower() == "maa":
                        mn = 3
                uit.append((m.start(), datetime(j, mn, d, u, mi, tzinfo=BRUSSEL).isoformat()))
            except (ValueError, TypeError):
                continue
    return sorted(set(uit))


def _link_einde(links, start):
    """Het einde uit een meegeleverde agenda-link (dates=BEGIN/EINDE) waarvan het begin het bevestigde uur is."""
    for ln in links or []:
        try:
            b, e = ln.split("/", 1)
            tb = _tijd(b, {}) if b.endswith("Z") else datetime.strptime(b[:15], "%Y%m%dT%H%M%S").replace(tzinfo=BRUSSEL).isoformat()
            te = _tijd(e, {}) if e.endswith("Z") else datetime.strptime(e[:15], "%Y%m%dT%H%M%S").replace(tzinfo=BRUSSEL).isoformat()
        except ValueError:
            continue
        if start and abs((datetime.fromisoformat(tb) - datetime.fromisoformat(start)).total_seconds()) <= 60:
            return te
    return ""


def _plaats_netjes(loc):
    loc = re.sub(r"\s+", " ", loc or "").strip(" ,-")
    loc = re.sub(r"\s+-\s+(\d{4})\b", r", \1", loc)
    loc = re.sub(r"(\d+[a-zA-Z]?)\s+(\d{4})\s+", r"\1, \2 ", loc)
    return re.sub(r"\b(\d{4}) ([A-Z]{3,})\b", lambda m: f"{m.group(1)} {m.group(2).title()}", loc)


def zorg_locatie_is_adres(loc):
    """Een vrije LOCATION/Waar-zin is geen navigatieadres. Huisbezoek blijft thuis."""
    loc = (loc or "").strip()
    if re.search(r"\b(huisbezoek|aan[-\s]+huis|thuis)\b", loc, re.I) or loc.lower().startswith(("http:", "https:")):
        return False
    return bool(re.search(r"\b[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{2,60}\s+\d{1,4}[a-zA-Z]?\b", loc)
                or re.search(r"\b\d{4}\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]+\b", loc)
                or re.fullmatch(r"\s*-?\d+\.\d+\s*,\s*-?\d+\.\d+\s*", loc))


def zorg_herken(k, profiel):
    """Lees een mail van een beheerde zorgpraktijk. Geeft None voor een bericht zonder afspraak (een nieuwsbrief),
    anders een dict met gebeurtenis, patient, mehdi, behandelaar, start, einde, locatie, oude_start, ics_uid,
    recurrence_id en problemen. Niets wordt geraden: een eindtijd komt uit de ICS of de meegeleverde agenda-link."""
    onderwerp = re.sub(r"\s+", " ", k.get("onderwerp") or "")
    tekst = re.sub(r"\s+", " ", _zonder_citaat(k.get("tekst") or ""))
    alles = f"{onderwerp}\n{tekst}"
    ev = None
    for ics in k.get("ics") or []:
        try:
            ev = next((e for e in ics_afspraken(ics) if e["start"] or e["geannuleerd"]), None) or ev
        except Exception:  # noqa: BLE001
            continue
    tijden = _zorg_tijden(alles)
    gebeurtenis = next((g for g, p in _GEBEURTENIS if p.search(alles)), "onbekend")
    if not ev and not (tijden and _AFSPRAAKWOORD_ZORG.search(alles)):
        # een annulering of verplaatsing zonder leesbare tijd verdwijnt niet: ze wordt een open punt (Codex A03)
        if not (gebeurtenis in ("annulering", "verplaatsing") and _AFSPRAAKWOORD_ZORG.search(alles)):
            return None                                          # nieuwsbrief, informatie: geen afspraak
    if ev and ev.get("geannuleerd"):
        gebeurtenis = "annulering"
    elif ev and ev.get("status") == "TENTATIVE":
        gebeurtenis = "aanvraag"                                 # voorlopig is geen bevestiging (Codex A03)
    start, oude_start = "", ""
    if gebeurtenis == "verplaatsing":
        m = next(p for g, p in _GEBEURTENIS if g == "verplaatsing").search(alles)
        voor = [t for pos, t in tijden if pos < m.start()]
        na = [t for pos, t in tijden if pos > m.start()]
        start, oude_start = (na[0] if na else ""), (voor[-1] if voor else "")
    elif ev and ev.get("start"):
        start = ev["start"]
    elif tijden:
        start = tijden[0][1]
    einde = (ev or {}).get("einde", "") if ev and ev.get("start") == start else ""
    einde = einde or _link_einde(k.get("linktijden"), start)
    plaats = (ev or {}).get("locatie", "") if ev else ""
    if not plaats:
        m = re.search(r"\bWaar:\s*(.+?)\s+(?:Toevoegen|Indien|Google Agenda|$)", tekst)
        plaats = m.group(1) if m else ""
    if not zorg_locatie_is_adres(plaats):
        plaats = ""
    m = re.search(r"Pati[eë]nt:\s*(.+?)\s+(?:Uw therapeut|Wanneer|Waar|$)", tekst)
    if m:
        patient = m.group(1).strip()
    else:
        m = re.search(r"\b(?:Beste|Dear|Geachte)\s+((?:(?:Dhr|Mevr|Mr|Mrs|Ms|Mw)\.?\s+)?(?:[A-Z][\w'-]+\s?){1,5})", tekst)
        delen = (m.group(1).split() if m else [])
        while delen and delen[-1].strip(",.") in _NAAM_STOP:
            delen.pop()
        while delen and _AANSPREKING.match(delen[0]):
            delen.pop(0)
        patient = " ".join(d.strip(",.") for d in delen)
    eigen = {_naam_plat(n) for n in profiel.get("patienten") or []}
    behandelaar = next((n for n in (profiel.get("behandelaars") or {}) if _naam_plat(n) in _naam_plat(alles)), "")
    if not behandelaar:
        m = (re.search(r"(?:therapeut|therapist)\s*:\s*([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){1,3})", tekst)
             or re.search(r"\b(?:bij|with)\s+((?:[A-Z][a-z][\w'-]*\s?){2,4})\s*[.:]", alles))
        behandelaar = m.group(1).strip() if m else ""
    problemen = []
    if not start:
        problemen.append("geen datum of uur te lezen")
    if not patient:
        problemen.append("patiënt niet te lezen")
    return {"praktijk": profiel["id"], "gebeurtenis": gebeurtenis, "patient": patient,
            "mehdi": bool(patient) and _naam_plat(patient) in eigen, "behandelaar": behandelaar, "start": start,
            "einde": einde, "locatie": _plaats_netjes(plaats), "oude_start": oude_start,
            "ics_uid": (ev or {}).get("uid", ""), "recurrence_id": (ev or {}).get("recurrence_id", ""), "problemen": problemen}


def zorg_rol(z, profiel):
    """Wat op het blok staat: de rol van de behandelaar uit het profiel (Kine, Tandarts, Mondhygiëne), anders de soort
    van de praktijk. De naam uit de bevestiging is leidend."""
    rollen = profiel.get("behandelaars") or {}
    return rollen.get(z.get("behandelaar") or "") or {"kine": "Kine", "tandarts": "Tandarts"}.get(profiel.get("soort"), "Zorg")


def uit_kandidaat(k, profielen=None):
    """De afspraken (dicts met sleutel) in een kandidaat-mail van post_lezer."""
    profiel = _zorgprofiel(_adres(k.get("van")), zorgprofielen() if profielen is None else profielen)
    if profiel:
        return _zorg_uit_kandidaat(k, profiel)
    ontvangen = _ontvangen(k.get("datum"))
    herkomst = {"prive": int(k["mailbox"] in PRIVE), "bron_mailbox": k["mailbox"], "bron_message_id": k.get("message_id") or f"uid:{k.get('uid')}",
                "bron_onderwerp": (k.get("onderwerp") or "").replace("\n", " ")[:200], "bron_ontvangen": ontvangen,
                "bron_afzender": _adres(k.get("van")), "map": k.get("map", ""), "imap_uid": k.get("uid")}
    uit = []
    for ics in k.get("ics") or []:
        for e in ics_afspraken(ics):
            # Een annulering mag zonder DTSTART (RFC 5546, 3.2.5): die bewaar ik op haar UID, niet weggooien (V8)
            if not e["uid"] or (not e["start"] and not e["geannuleerd"]):
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


def _zorg_uit_kandidaat(k, profiel):
    """Een mail van een beheerde zorgpraktijk als registerrij (soort 'zorg'), altijd privé, ongeacht de mailbox. De
    voorlopige sleutel is praktijk plus bevestigd begin; bewaar() koppelt herinneringen, tweede mailbox en verplaatsing
    aan de afspraak die al bestaat."""
    z = zorg_herken(k, profiel)
    if z is None:
        return []
    ontvangen = _ontvangen(k.get("datum"))
    mid = k.get("message_id") or f"uid:{k.get('uid')}"
    z["laatst_ontvangen"] = ontvangen
    z["bronnen"] = [mid]
    rol = zorg_rol(z, profiel)
    return [{"prive": 1, "bron_mailbox": k["mailbox"], "bron_message_id": mid,
             "bron_onderwerp": (k.get("onderwerp") or "").replace("\n", " ").replace("\r", " ")[:200], "bron_ontvangen": ontvangen,
             "bron_afzender": _adres(k.get("van")), "map": k.get("map", ""), "imap_uid": k.get("uid"),
             "soort": "zorg", "sleutel": f"zorg|{profiel['id']}|{z['start']}" if z["start"] else f"zorg|{profiel['id']}|zonder|{mid}",
             "ics_uid": z["ics_uid"], "recurrence_id": z["recurrence_id"], "sequence": 0, "dtstamp": ontvangen,
             "method": z["gebeurtenis"], "geannuleerd": z["gebeurtenis"] == "annulering", "start": z["start"], "einde": z["einde"],
             # de plaats komt alleen uit de mail: een praktijk met meer vestigingen kan elders zijn (Codex A04)
             "titel": f"{rol} {z['behandelaar']}".strip(), "locatie": z["locatie"], "zorg": z}]


def _zorg_json(a):
    z = a.get("zorg") or {}
    if isinstance(z, str):
        try:
            z = json.loads(z or "{}")
        except ValueError:
            z = {}
    return z


def _bewaar_zorg(c, a):
    """Een zorgafspraak heeft een duurzame identiteit: de eerste sleutel blijft. Een herinnering, dezelfde mail via de
    tweede mailbox of een nieuwe ronde voegt alleen een bron toe en vult wat ontbrak; een verplaatsing (tekst met oude
    en nieuwe tijd, of een ICS met dezelfde UID op een ander uur) wijzigt dezelfde afspraak en bewaart de oude tijd in
    de historie; een oudere mail draait een nieuwere niet terug. Geeft 1 als er iets veranderde."""
    z = _zorg_json(a)
    pid = z.get("praktijk") or a["sleutel"].split("|")[1]
    like = f"zorg|{pid}|%"
    nu_iso = _nu().isoformat(timespec="seconds")
    # 1. Hetzelfde bericht (ook via de tweede mailbox of in een volgende ronde) is al verwerkt: alleen de bron bijzetten.
    #    Zo maakt een oude herinnering na een verplaatsing nooit een tweede rij (Codex A01).
    al = c.execute("SELECT sleutel FROM bron WHERE message_id=? AND sleutel LIKE ? LIMIT 1", (a["bron_message_id"], like)).fetchone()
    if al:
        c.execute("INSERT OR IGNORE INTO bron(mailbox,message_id,sleutel,map,imap_uid,ontvangen,afzender,onderwerp,gezien) "
                  "VALUES(?,?,?,?,?,?,?,?,?)", (a["bron_mailbox"], a["bron_message_id"], al["sleutel"], a.get("map", ""), a.get("imap_uid"),
                                                a["bron_ontvangen"], a["bron_afzender"], a["bron_onderwerp"], nu_iso))
        return 0
    eigen_patient = _naam_plat(z.get("patient") or "")

    def zelfde_patient(r, sterk=False):
        # twee patiënten op hetzelfde uur blijven twee afspraken. Alle namen van Mehdi uit het profiel ('Mohammad Mehdi
        # ...', 'Mehdi ...') zijn dezelfde persoon. Is de patiënt aan een kant niet te lezen, dan koppelt alleen een
        # sterke identiteit (dezelfde uitnodigings-UID), nooit een gelijk uur: een herinnering voor een gezinslid op
        # hetzelfde uur mag Mehdi's afspraak niet verzetten of annuleren (Codex A01, ronde 3). Ze wordt een eigen open punt.
        rz = _zorg_json(dict(r))
        p = _naam_plat(rz.get("patient") or "")
        if not p or not eigen_patient:
            return sterk
        if p == eigen_patient:
            return True
        return bool(rz.get("mehdi")) and bool(z.get("mehdi"))

    def zoek(sql, args, sterk=False):
        return next((r for r in c.execute(sql, args).fetchall() if zelfde_patient(r, sterk)), None)

    doel, alias = None, False
    if z.get("gebeurtenis") == "verplaatsing" and z.get("oude_start"):
        doel = (zoek("SELECT * FROM afspraak WHERE soort='zorg' AND start=? AND sleutel LIKE ?", (z["oude_start"], like))
                or zoek("SELECT * FROM afspraak WHERE sleutel=?", (f"zorg|{pid}|{z['oude_start']}",)))
    if doel is None and a.get("ics_uid"):
        doel = zoek("SELECT * FROM afspraak WHERE soort='zorg' AND ics_uid=? AND sleutel LIKE ?", (a["ics_uid"], like), sterk=True)
    if doel is None and a.get("start"):
        doel = zoek("SELECT * FROM afspraak WHERE soort='zorg' AND start=? AND sleutel LIKE ?", (a["start"], like))
    if doel is None and a.get("start"):
        # een oude tijd van een afspraak die intussen verplaatst is (tijdalias): koppelen, de tijd niet terugdraaien
        for r in c.execute("SELECT * FROM afspraak WHERE soort='zorg' AND sleutel LIKE ?", (like,)).fetchall():
            if zelfde_patient(r) and any(h.get("van") == a["start"] for h in _zorg_json(dict(r)).get("historie") or []):
                doel, alias = r, True
                break
    if doel is None and a.get("start"):
        doel = zoek("SELECT * FROM afspraak WHERE sleutel=?", (a["sleutel"],))
    sleutel = doel["sleutel"] if doel else a["sleutel"]
    if doel is None and c.execute("SELECT 1 FROM afspraak WHERE sleutel=?", (sleutel,)).fetchone():
        # andere patiënt: een eigen sleutel. Zonder leesbare patiënt het bronbericht, anders kregen twee zulke mails op
        # hetzelfde uur dezelfde sleutel en faalde de tweede (Codex A01, ronde 4)
        sleutel = f"{sleutel}|{hashlib.sha256((eigen_patient or a.get('bron_message_id') or '').encode()).hexdigest()[:8]}"
    c.execute("INSERT OR IGNORE INTO bron(mailbox,message_id,sleutel,map,imap_uid,ontvangen,afzender,onderwerp,gezien) "
              "VALUES(?,?,?,?,?,?,?,?,?)", (a["bron_mailbox"], a["bron_message_id"], sleutel, a.get("map", ""), a.get("imap_uid"),
                                            a["bron_ontvangen"], a["bron_afzender"], a["bron_onderwerp"], _nu().isoformat(timespec="seconds")))
    if doel is None:
        velden = ("sleutel", "soort", "ics_uid", "recurrence_id", "sequence", "dtstamp", "method", "geannuleerd", "start", "einde",
                  "titel", "locatie", "bron_mailbox", "bron_message_id", "bron_onderwerp", "bron_ontvangen", "bron_afzender", "prive")
        c.execute(f"INSERT INTO afspraak({','.join(velden)}, status, zorg) VALUES({','.join('?' * len(velden))}, 'nieuw', ?)",
                  [sleutel if v == "sleutel" else int(a[v]) if v == "geannuleerd" else a.get(v, "") for v in velden]
                  + [json.dumps(z, ensure_ascii=False)])
        return 1
    oud = _zorg_json(dict(doel))
    nieuw = dict(oud)
    for veld in ("behandelaar", "patient"):
        if z.get(veld) and not oud.get(veld):
            nieuw[veld] = z[veld]
    nieuw["mehdi"] = bool(oud.get("mehdi") or z.get("mehdi"))
    nieuw["bronnen"] = sorted(set(oud.get("bronnen") or []) | set(z.get("bronnen") or []))
    nieuw["historie"] = list(oud.get("historie") or [])
    start, einde, geannuleerd = doel["start"], doel["einde"], doel["geannuleerd"]
    nieuwer = (a.get("bron_ontvangen") or "") >= (oud.get("laatst_ontvangen") or "") and not alias
    if nieuwer:
        nieuw["laatst_ontvangen"] = a.get("bron_ontvangen") or oud.get("laatst_ontvangen", "")
        if z.get("gebeurtenis") == "annulering":
            geannuleerd = 1
        elif z.get("gebeurtenis") in ("bevestiging", "herinnering", "verplaatsing"):
            geannuleerd = 0              # een nieuwere bevestiging heft een eerdere annulering op (Codex A03)
        if z.get("gebeurtenis") != "aanvraag" and oud.get("gebeurtenis") in ("aanvraag", "onbekend", None):
            nieuw["gebeurtenis"] = z.get("gebeurtenis")
        if z.get("gebeurtenis") == "verplaatsing":
            nieuw["gebeurtenis"] = "verplaatsing"
        if a.get("start") and a["start"] != start:
            nieuw["historie"].append({"van": start, "naar": a["start"], "bron": a["bron_message_id"], "ontvangen": a.get("bron_ontvangen", "")})
            start, einde = a["start"], a.get("einde") or ""
    if a.get("einde") and not einde and a.get("start") == start:
        einde = a["einde"]
    c.execute("UPDATE afspraak SET start=?, einde=?, locatie=?, ics_uid=?, geannuleerd=?, prive=1, zorg=?, "
              "titel=CASE WHEN titel='' THEN ? ELSE titel END WHERE sleutel=?",
              (start, einde, doel["locatie"] or a.get("locatie", ""), doel["ics_uid"] or a.get("ics_uid", ""), int(geannuleerd),
               json.dumps(nieuw, ensure_ascii=False), a.get("titel", ""), sleutel))
    return int((start, einde, int(geannuleerd)) != (doel["start"], doel["einde"], doel["geannuleerd"]) or nieuw != oud)


# ------------------------------------------------------------------------------------------------- register ---
def bewaar(afspraken, nu=None):
    """Zet de afspraken in het register. Een nieuwere versie (hogere SEQUENCE, of gelijk en later DTSTAMP) vervangt de
    oude; een oudere (een doorgestuurde oude mail) niet. Elke bron wordt bewaard. Geeft het aantal nieuwe of gewijzigde."""
    nu = (nu or _nu()).isoformat(timespec="seconds")
    gewijzigd = 0
    with _db() as c:
        for a in afspraken:
            if a.get("soort") == "zorg":
                gewijzigd += _bewaar_zorg(c, a)
                continue
            c.execute("INSERT OR IGNORE INTO bron(mailbox,message_id,sleutel,map,imap_uid,ontvangen,afzender,onderwerp,gezien) "
                      "VALUES(?,?,?,?,?,?,?,?,?)", (a["bron_mailbox"], a["bron_message_id"], a["sleutel"], a.get("map", ""),
                                                    a.get("imap_uid"), a["bron_ontvangen"], a["bron_afzender"], a["bron_onderwerp"], nu))
            oud = c.execute("SELECT * FROM afspraak WHERE sleutel=?", (a["sleutel"],)).fetchone()
            if oud and (oud["sequence"], oud["dtstamp"]) >= (a["sequence"], a["dtstamp"]):
                continue
            if oud and not a["start"]:
                # een annulering zonder start: de bekende afspraak blijft, met de annulering erop (V8)
                c.execute("UPDATE afspraak SET geannuleerd=1, method=?, sequence=?, dtstamp=?, bron_mailbox=?, bron_message_id=?, "
                          "bron_onderwerp=?, bron_ontvangen=?, bron_afzender=?, prive=? WHERE sleutel=?",
                          (a["method"], a["sequence"], a["dtstamp"], a["bron_mailbox"], a["bron_message_id"], a["bron_onderwerp"],
                           a["bron_ontvangen"], a["bron_afzender"], a.get("prive", 0), a["sleutel"]))
                gewijzigd += 1
                continue
            velden = ("sleutel", "soort", "ics_uid", "recurrence_id", "sequence", "dtstamp", "method", "geannuleerd", "start",
                      "einde", "titel", "locatie", "bron_mailbox", "bron_message_id", "bron_onderwerp", "bron_ontvangen", "bron_afzender",
                      "prive")
            melding = oud["melding"] if oud else ""
            c.execute(f"INSERT OR REPLACE INTO afspraak({','.join(velden)}, status, melding) VALUES({','.join('?' * len(velden))}, 'nieuw', ?)",
                      [int(a[v]) if v == "geannuleerd" else a.get(v, 0 if v == "prive" else "") for v in velden] + [melding])
            gewijzigd += 1
        # Privacy volgt alle herkomsten: kwam dezelfde afspraak ooit uit een privémailbox, dan blijft ze privé, ook als
        # een nieuwere werkmail de rij vervangt (nacontrole v1.3, R2). Het label zakt nooit vanzelf.
        c.execute(f"UPDATE afspraak SET prive=1 WHERE prive=0 AND sleutel IN (SELECT sleutel FROM bron WHERE mailbox IN "
                  f"({','.join('?' * len(PRIVE))}))", sorted(PRIVE))
    return gewijzigd


def leesstand_zet(mailbox, gelukt, fout="", nu=None, dekking=None):
    """Volledig gelezen (alle mappen, alle berichten, verwerkt en bewaard) zet laatst_gelukt. Gedeeltelijk of mislukt
    laat laatst_gelukt staan en bewaart de fout en de dekking, zodat de zelfcontrole het ziet (V7)."""
    nu = (nu or _nu()).isoformat(timespec="seconds")
    dekking = dekking or ("volledig" if gelukt else "mislukt")
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO leesstand(mailbox) VALUES(?)", (mailbox,))
        if gelukt:
            c.execute("UPDATE leesstand SET laatst_gelukt=?, laatste_poging=?, laatste_fout='', dekking='volledig', "
                      "eerste_fout='', fout_rondes=0, laatste_nood='' WHERE mailbox=?",
                      (nu, nu, mailbox))
        else:
            oud = c.execute("SELECT eerste_fout, fout_rondes FROM leesstand WHERE mailbox=?", (mailbox,)).fetchone()
            onleesbaar = dekking == "mislukt"
            eerste = (oud["eerste_fout"] or nu) if onleesbaar else oud["eerste_fout"]
            rondes = oud["fout_rondes"] + 1 if onleesbaar else oud["fout_rondes"]
            c.execute("UPDATE leesstand SET laatste_poging=?, laatste_fout=?, dekking=?, eerste_fout=?, fout_rondes=? "
                      "WHERE mailbox=?", (nu, fout[:500], dekking, eerste, rondes, mailbox))


def mailbron_nood(mailbox, afhankelijk=False, nu=None):
    """Houd de nood open met dezelfde tekst; na 24 uur geeft een nieuwe tijdstempel een herinnering."""
    nu = nu or _nu()
    with _db() as c:
        st = c.execute("SELECT eerste_fout, fout_rondes, laatste_nood, dekking FROM leesstand WHERE mailbox=?",
                       (mailbox,)).fetchone()
        if not st or st["dekking"] != "mislukt" or not st["eerste_fout"]:
            return None
        eerste = datetime.fromisoformat(st["eerste_fout"])
        laatst = datetime.fromisoformat(st["laatste_nood"]) if st["laatste_nood"] else None
        oud_genoeg = st["fout_rondes"] >= 2 and nu - eerste >= timedelta(hours=2)
        if not (afhankelijk or oud_genoeg or laatst):
            return None
        if not laatst or nu - laatst >= timedelta(hours=24):
            laatst = nu
            c.execute("UPDATE leesstand SET laatste_nood=? WHERE mailbox=?", (nu.isoformat(timespec="seconds"), mailbox))
    return {"tekst": f"Postvak {mailbox} niet te lezen; dit kan ook tijdelijk zijn. "
                     f"Typ op je Mac in Terminal: `ssh -t globaal 'docker exec -it appportal-app-post-1 "
                     f"python oauth_koppel.py {mailbox}'`. "
                     f"Microsoft toont daarna een code; meld je daarmee aan. Melding {laatst:%d-%m-%Y %H:%M}.",
            "wie": "mehdi"}


def leesstand():
    with _db() as c:
        return {r["mailbox"]: dict(r) for r in c.execute("SELECT * FROM leesstand").fetchall()}


def alle():
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM afspraak ORDER BY start").fetchall()]


# ------------------------------------------------------------------------------------- vergelijken met de agenda ---
def _iso(t):
    return datetime.fromisoformat(t) if "T" in t else None


STOPWOORDEN = {"mehd", "afsp", "appo", "meet", "uitn", "invi", "heri", "remi", "your", "with", "voor", "over", "deze",
               "today", "toda", "bij", "event", "even", "updat", "upda", "bijg", "nieu", "conf", "beve", "teams", "zoom",
               "online", "onli"}


def _woorden(tekst):
    """De betekenisvolle woorden als prefix van vier letters ('kinevoorbeeld' en 'Kine' delen 'kine')."""
    return {w[:4] for w in re.findall(r"[a-z0-9]{4,}", _plat_tekst(tekst))} - STOPWOORDEN


def zelfde_onderwerp(mailtitel, agendatitel):
    """Gaat deze mail over dit agenda-item (op hetzelfde uur, zonder gedeelde uitnodigings-ID)? Een woorddeel volstaat
    niet: 'Project Alfa' en 'Project Beta' delen 'proj' (Codex A20, 15-10-2026). Ik vergelijk het onderwerp voor de eerste
    komma (de rest is het adres), twee projectnummers beslissen samen, en anders moet het ene onderwerp helemaal in het
    andere zitten of moeten twee woorden overeenkomen."""
    m_all, g_all = _woorden((mailtitel or "").split(",")[0]), _woorden((agendatitel or "").split(",")[0])
    # een jaartal (2020-2039) is geen projectnummer: 'overleg 2026' koppelt geen 2614 aan 2615 (Codex A20, ronde 3)
    jaar = re.compile(r"20[23]\d")
    mn = {w for w in m_all if w.isdigit() and not jaar.fullmatch(w)}
    gn = {w for w in g_all if w.isdigit() and not jaar.fullmatch(w)}
    m_all, g_all = {w for w in m_all if not jaar.fullmatch(w)}, {w for w in g_all if not jaar.fullmatch(w)}
    if mn and gn:
        return bool(mn & gn)
    m, g = m_all - mn, g_all - gn
    return bool(m and g and (m <= g or g <= m or len(m & g) >= 2))


def _plat_tekst(t):
    import unicodedata  # noqa: PLC0415
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def _instantie(kand, a):
    """De juiste reeksinstantie. Met RECURRENCE-ID: de instantie waarvan de oorspronkelijke start (Google:
    originalStartTime) die dag is, ook als ze intussen verplaatst werd (nacontrole v1.3, R11); anders de dag van de start."""
    if a["recurrence_id"]:
        rid = a["recurrence_id"][:10]
        return ([x for x in kand if (x.get("_origineel") or "")[:10] == rid]
                or [x for x in kand if not x.get("_origineel") and (x.get("start") or "")[:10] == rid])
    dag = (a["start"] or "")[:10]
    if not dag:
        return kand
    return [x for x in kand if (x.get("start") or "")[:10] == dag] or (kand[:1] if len(kand) == 1 else [])


ZORGMERK = "agendawacht_zorg"
_ZORGWOORD = re.compile(r"\bkine\b|kinesi|kinésit|tandarts|mondhygi|dentist", re.I)


def _uid_conflict(x, a):
    """Draagt het item de uitnodiging van een andere externe afzender (geen door Google gemaakte UID van een eigen item)?"""
    return bool(a.get("ics_uid") and x.get("_icaluid") and x["_icaluid"] != a["ics_uid"] and not x["_icaluid"].endswith("@google.com"))


def _ander_zorgitem(x, a):
    """Het merk van een andere zorgafspraak of een andere externe uitnodiging: nooit dit item wijzigen (Codex A02, ronde 5)."""
    m = (x.get("_merk") or {}).get(ZORGMERK)
    return bool(m and m != a["sleutel"]) or _uid_conflict(x, a)


def _zorgachtig(x, a, z, profiel):
    """Hoe sterk lijkt dit agenda-item op deze zorgafspraak? 2: ons eigen merk, of de praktijk, de behandelaar of het
    adres van de praktijk in titel, plaats of omschrijving. 1: alleen een algemeen zorgwoord (kine, tandarts). 0: niet.
    Alleen 2 koppelt; 1 is een vraag, want 'Tandarts' op dat uur kan de afspraak van iemand anders zijn (Codex A02,
    ronde 3)."""
    eigen_merk = (x.get("_merk") or {}).get(ZORGMERK)
    if _uid_conflict(x, a):
        return -1          # de UID gaat voor het merk: ook met ons merk is een andere uitnodiging een conflict (A02, ronde 6)
    if eigen_merk == a["sleutel"]:
        return 2
    # het merk van een andere zorgafspraak, of de uitnodiging van een andere externe afzender (geen door Google gemaakte
    # UID van een eigen item), is een andere afspraak: nooit koppelen, ook niet met de praktijknaam (Codex A02, ronde 4)
    if eigen_merk or _uid_conflict(x, a):
        return -1          # een andere afspraak: nooit koppelen; wel een conflict, zie _zorg_status (A35, ronde 5)
    # een zakelijke afspraak (firmacode in de titel, bv. EPB voor een tandartspraktijk) is nooit deze zorgafspraak (A02);
    # een afspraak van Lara ([LA]) is nooit die van Mehdi
    m = re.search(r"\[([A-Za-z]{2,6})(?:-[A-Za-z0-9]{1,4})?\]", x.get("titel") or "")
    if m and m.group(1).upper() not in ("PR", "PRIVE"):
        return 0
    tekst = _plat_tekst(" ".join(str(x.get(v) or "") for v in ("titel", "locatie", "omschrijving")))
    woorden = [_plat_tekst(w) for w in (profiel or {}).get("praktijknamen") or []]
    woorden += [_plat_tekst(n) for n in ((profiel or {}).get("behandelaars") or {})]
    if z.get("behandelaar"):
        woorden.append(_plat_tekst(z["behandelaar"]))
    straat = _plat_tekst(((profiel or {}).get("adres") or "").split(",")[0])
    if straat:
        woorden.append(straat)
    if any(w and w in tekst for w in woorden):
        return 2
    return 1 if _ZORGWOORD.search(tekst) else 0


def _zorg_status(a, items, nu, vorig_google=""):
    """Status van een zorgafspraak tegenover de agenda. Volgorde: geannuleerd, geen tijd, niet voor Mehdi, al in de
    agenda (ons merk of hetzelfde uur met een zorgwoord), verzet (het vorige gekoppelde item staat op een ander uur),
    voorbij (historisch, nooit terugboeken), aanvraag (wacht op bevestiging), geen eindtijd (open punt), anders ontbreekt
    (de agent zet het blok)."""
    z = _zorg_json(a)
    profiel = next((p for p in zorgprofielen() if p.get("id") == z.get("praktijk")), {})
    start = _iso(a["start"]) if a["start"] else None
    kand = [x for x in items if not x.get("hele_dag") and start and _iso(x.get("start") or "")
            and abs((_iso(x["start"]) - start).total_seconds()) <= 300 and _zorgachtig(x, a, z, profiel)]
    # -1: een zorgitem van een andere afspraak (ander merk of andere uitnodiging) op dit uur: een conflict, geen tweede blok
    # (Codex A35, ronde 5); 1: alleen een zorgwoord (een vraag); 2: koppelen
    conflict = [x for x in kand if _zorgachtig(x, a, z, profiel) < 0]
    zwak = [x for x in kand if _zorgachtig(x, a, z, profiel) == 1]
    kand = [x for x in kand if x not in zwak and x not in conflict]
    merk = [x for x in items if (x.get("_merk") or {}).get(ZORGMERK) == a["sleutel"] and not _uid_conflict(x, a)]
    # een oude verwijzing die intussen naar een item van een andere afspraak wijst, telt niet (Codex A02, ronde 5)
    vorig = [x for x in items if vorig_google and f"{x.get('kalender')}|{x.get('id')}" == vorig_google and not _ander_zorgitem(x, a)]
    recent = (a.get("bron_ontvangen") or "")[:10] >= (nu - timedelta(days=14)).astimezone(BRUSSEL).date().isoformat()
    if not start and a["geannuleerd"]:
        # een annulering zonder datum: niet te zeggen welke afspraak, dus een open punt, nooit stil (Codex A03)
        return {"status": "zorg_open" if recent else "zorg_historisch", "google": "",
                "detail": "annulering zonder datum of uur: welke afspraak?"}
    if a["geannuleerd"]:
        m = (kand or merk or vorig or [None])[0]
        return {"status": "geannuleerd_staat_er" if m else "geannuleerd", "google": f"{m['kalender']}|{m['id']}" if m else "",
                "detail": "in mail geannuleerd" if m else ""}
    if not start:
        return {"status": "zorg_open" if recent else "zorg_historisch", "google": "", "detail": "geen datum of uur te lezen"}
    if start < nu - timedelta(hours=1):
        # voorbij is historisch, ook als de patiënt niet te lezen was: nooit een open punt of een blok achteraf. De agent
        # leest de agenda veertien dagen terug: wat ouder is, is niet vergeleken (geen bewering 'niet gevonden').
        if kand:
            return {"status": "gekoppeld", "google": f"{kand[0]['kalender']}|{kand[0]['id']}", "detail": "historisch, in de agenda"}
        oud_venster = start < nu - timedelta(days=14)
        return {"status": "voorbij", "google": "",
                "detail": "historisch, ouder dan het leesvenster (niet vergeleken)" if oud_venster else "historisch: niet in de agenda gevonden"}
    if not z.get("mehdi"):
        return {"status": "zorg_open", "google": "", "detail": f"andere patiënt of patiënt niet te lezen ({z.get('patient') or '?'})"}
    eigen = [x for x in kand if (x.get("_merk") or {}).get(ZORGMERK) == a["sleutel"]]
    if conflict:
        # een zorgitem van een andere afspraak of uitnodiging op dit uur: ook als er een oud eigen item is, nooit verzetten
        # naar dat bezette uur of stil koppelen, maar een vraag (Codex A35, ronde 6)
        return {"status": "zorg_open", "google": "", "detail": "op dat uur staat een zorgafspraak van een andere afspraak of uitnodiging: welke is het?"}
    if len(kand) > 1 and not eigen:
        # twee kandidaten op hetzelfde uur: niet raden welke het is (Codex A02)
        return {"status": "zorg_open", "google": "", "detail": f"{len(kand)} afspraken op dat uur, niet eenduidig te koppelen"}
    if not kand and conflict and not (merk or vorig):
        return {"status": "zorg_open", "google": "", "detail": "op dat uur staat een zorgafspraak van een andere afspraak of uitnodiging: welke is het?"}
    if not kand and zwak and not (merk or vorig):
        # alleen een algemeen zorgwoord op dat uur: misschien deze afspraak, misschien die van iemand anders. Geen tweede
        # blok en geen stille koppeling, maar een vraag (Codex A02, ronde 3)
        return {"status": "zorg_open", "google": "",
                "detail": f"{len(zwak)} afspraken op dat uur, niet eenduidig te koppelen" if len(zwak) > 1 else
                "op dat uur staat al een zorgafspraak zonder de naam van de praktijk: is dat deze?"}
    kand = eigen or kand
    if kand:
        m = kand[0]
        return {"status": "gekoppeld", "google": f"{m['kalender']}|{m['id']}", "detail": ""}
    oud = (merk or vorig or [None])[0]
    if oud:
        return {"status": "afwijkend", "google": f"{oud['kalender']}|{oud['id']}",
                "detail": f"verzet: in de agenda {(oud.get('start') or '')[:16].replace('T', ' ')}, volgens mail {a['start'][:16].replace('T', ' ')}"}
    if z.get("gebeurtenis") == "aanvraag":
        return {"status": "zorg_wacht", "google": "", "detail": "wacht op bevestiging van de praktijk"}
    if not a["einde"]:
        return {"status": "zorg_open", "google": "", "detail": "eindtijd onbekend: niet in de mail, geen duur verzonnen"}
    return {"status": "ontbreekt", "google": "", "detail": ""}


def vergelijk(afspraken, items, nu=None):
    """Zet per afspraak de status tegenover de agenda-items (alle agenda's). Identiteit en inhoud zijn gescheiden
    (nacontrole v1.2, V6): dezelfde iCalUID met hetzelfde uur is gekoppeld, met een ander uur afwijkend (een vraag);
    zonder UID is hetzelfde uur alleen gekoppeld als ook de woorden overeenkomen, anders een kandidaat (onzeker, ook
    een vraag). Een annulering wordt beoordeeld voor de tijdsoort, ook zonder start (V8). Statussen: gekoppeld,
    afwijkend, kandidaat, ontbreekt, voorbij, geannuleerd, geannuleerd_staat_er, zonder_tijd. 'detail' zegt waarom."""
    nu = nu or _nu()
    per_uid = {}
    for x in items:
        if x.get("_icaluid"):
            per_uid.setdefault(x["_icaluid"], []).append(x)
    uit = []
    for a in afspraken:
        a = dict(a)
        vorig_google = a.get("google") or ""
        a["detail"], a["google"] = "", ""
        if a.get("soort") == "zorg":
            a.update(_zorg_status(a, items, nu, vorig_google))
            uit.append(a)
            continue
        start = _iso(a["start"]) if a["start"] else None
        uid_kand = _instantie(per_uid.get(a["ics_uid"], []), a) if a["ics_uid"] else []
        if a["soort"] == "zonder_tijd":
            a["status"] = "zonder_tijd"
        elif a["geannuleerd"]:
            m = uid_kand[0] if uid_kand else None
            if not m and not a["ics_uid"] and start:
                treffers = [x for x in items if _iso(x.get("start") or "") and abs((_iso(x["start"]) - start).total_seconds()) <= 300
                            and zelfde_onderwerp(a["titel"], x.get("titel"))]
                m = treffers[0] if len(treffers) == 1 else None      # twijfel wijst geen item aan om te schrappen (Codex A20)
            a["google"] = f"{m['kalender']}|{m['id']}" if m else ""
            a["status"] = "geannuleerd_staat_er" if m else "geannuleerd"
        elif uid_kand:
            m = uid_kand[0]
            a["google"] = f"{m['kalender']}|{m['id']}"
            if start is None:                                    # hele dag: dezelfde dag
                gelijk = (m.get("start") or "")[:10] == a["start"][:10]
            else:
                ms, me = _iso(m.get("start") or ""), _iso(m.get("einde") or "")
                ae = _iso(a["einde"]) if a["einde"] else None
                gelijk = bool(ms) and abs((ms - start).total_seconds()) <= 300 and not (ae and me and abs((me - ae).total_seconds()) > 300)
            a["status"] = "gekoppeld" if gelijk else "afwijkend"
            if not gelijk:
                a["detail"] = f"in de agenda {(m.get('start') or '')[:16].replace('T', ' ')}"
        else:
            if start is None and a["start"]:
                kand = [x for x in items if x.get("hele_dag") and (x.get("start") or "")[:10] == a["start"][:10]]
            elif start:
                kand = [x for x in items if not x.get("hele_dag") and _iso(x.get("start") or "")
                        and abs((_iso(x["start"]) - start).total_seconds()) <= 300]
            else:
                kand = []
            # een andere uitnodiging (een andere expliciete UID) is hoogstens een kandidaat, ook met gedeelde woorden (R3)
            goed = [x for x in kand if zelfde_onderwerp(a["titel"], x.get("titel"))
                    and not (a["ics_uid"] and x.get("_icaluid") and x["_icaluid"] != a["ics_uid"])]
            if len(goed) == 1:            # precies een treffer; twee is twijfel, dus een kandidaat (Codex A20)
                a["status"], a["google"] = "gekoppeld", f"{goed[0]['kalender']}|{goed[0]['id']}"
            elif start and start < nu - timedelta(hours=1) or (start is None and a["start"] and a["start"][:10] < nu.date().isoformat()):
                a["status"] = "voorbij"
            elif kand:
                a["status"], a["google"] = "kandidaat", f"{kand[0]['kalender']}|{kand[0]['id']}"
                a["detail"] = f"op dat uur staat '{(kand[0].get('titel') or '')[:40]}'"
            else:
                a["status"] = "ontbreekt"
        uit.append(a)
    return uit


def statussen_bewaren(afspraken, nu=None):
    nu = (nu or _nu()).isoformat(timespec="seconds")
    with _db() as c:
        for a in afspraken:
            c.execute("UPDATE afspraak SET status=?, google=?, detail=?, gecontroleerd=? WHERE sleutel=?",
                      (a["status"], a["google"], a.get("detail", ""), nu, a["sleutel"]))


# ---------------------------------------------------------------------------------------------------- lezen ---
def lees(sinds, mailboxen=MAILBOXEN, maximaal=2000, zorg=None):
    """Leest de kandidaten via de postcontainer. Geeft (kandidaten, fouten). Faalt het hele lezen, dan een fout per
    mailbox, nooit een stille lege lijst. zorg = {'zorg_afzenders': [...], 'zorg_sinds': 'JJJJ-MM-DD'}: die afzenders
    zoekt de lezer apart op, ook zonder afspraakwoord in het onderwerp en verder terug dan de gewone twee weken."""
    opdracht = json.dumps({"mailboxen": list(mailboxen), "sinds": sinds, "maximaal": maximaal, **(zorg or {})})
    try:
        r = subprocess.run(["docker", "exec", "-i", "-e", f"LEES={opdracht}", "-w", "/app", CONTAINER, "python", "-"],
                           stdin=open(LEZER, "rb"), capture_output=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="replace")[-300:] or f"exit {r.returncode}")
        d = json.loads(r.stdout.decode())
        return d.get("kandidaten") or [], d.get("fouten") or []
    except Exception as e:  # noqa: BLE001
        return [], [{"mailbox": m, "fout": f"{type(e).__name__}: {str(e)[:200]}"} for m in mailboxen]


def ronde(items, sinds, nu=None, mailboxen=MAILBOXEN, agenda_onvolledig=()):
    """Een volledige ronde: lezen, verwerken, bewaren, vergelijken met de agenda. Een mailbox heet pas volledig gelezen
    als alle mappen en berichten gelezen, verwerkt en bewaard zijn; een fout in een map, een bericht dat niet te halen
    of te ontleden is, of een afgekapte map maakt de dekking gedeeltelijk (V7). Een fout bericht houdt de andere niet
    tegen: elk krijgt zijn bron-ID in de fouten en komt de volgende ronde opnieuw. Geeft (afspraken, fouten)."""
    profielen = zorgprofielen()
    zorg = None
    if profielen:
        zorg = {"zorg_afzenders": sorted({x for p in profielen for x in p.get("afzenders") or []}),
                "zorg_sinds": ((nu or _nu()).astimezone(BRUSSEL).date() - timedelta(days=ZORG_DAGEN_TERUG)).isoformat()}
    kandidaten, fouten = lees(sinds, mailboxen, zorg=zorg) if zorg else lees(sinds, mailboxen)
    if ZORG_FOUT:
        # een onleesbaar profiel is geen volledige dekking, ook al lukte de rest (Codex A06)
        fouten += [{"mailbox": m, "map": "zorgprofielen", "fout": ZORG_FOUT} for m in mailboxen]
    # oudste mail eerst: een bevestiging komt voor haar verplaatsing, zodat die het bestaande item verzet (Codex A01)
    kandidaten = sorted(kandidaten, key=lambda k: _ontvangen(k.get("datum")) or "")
    for k in kandidaten:
        try:
            bewaar(uit_kandidaat(k, profielen), nu)
            for p in ics_problemen(k):
                fouten.append({"mailbox": k.get("mailbox", "?"), "map": k.get("map", ""), "uid": k.get("uid"),
                               "fout": f"{p}: {(k.get('message_id') or '')[:80]}"})
        except Exception as e:  # noqa: BLE001
            fouten.append({"mailbox": k.get("mailbox", "?"), "map": k.get("map", ""), "uid": k.get("uid"),
                           "fout": f"niet verwerkt ({type(e).__name__}): {(k.get('message_id') or '')[:80]}"})
    for m in mailboxen:
        eigen = [f for f in fouten if f.get("mailbox") == m]
        stuk = any(not f.get("map") for f in eigen)
        tekst = "; ".join(f"{f.get('map') or 'mailbox'}{(' uid ' + str(f['uid'])) if f.get('uid') else ''}: {f['fout']}" for f in eigen)
        leesstand_zet(m, not eigen, tekst, nu, None if not eigen else ("mislukt" if stuk else "gedeeltelijk"))
    if agenda_onvolledig:
        # een agenda die niet gelezen is, kan de uitnodiging bevatten: niet vergelijken, de statussen en Google-ID's van
        # de laatste volledige vergelijking blijven staan (Codex A15, 15-10-2026)
        return [], fouten
    afspraken = vergelijk(alle(), items, nu)
    statussen_bewaren(afspraken, nu)
    return afspraken, fouten


# statussen die Mehdi moet zien (een melding in de privé-agenda); gekoppeld, voorbij en geannuleerd niet. zorg_open:
# een zorgafspraak die nog niet vaststaat (eindtijd, patiënt of tijd onbekend): een concreet open punt.
VRAAG_STATUSSEN = ("ontbreekt", "afwijkend", "kandidaat", "geannuleerd_staat_er", "zorg_open")


def prive_teksten():
    """Titels, onderwerpen, afzenders en plaatsen van privé-afspraken uit mail, en de namen, adressen en telefoons van
    de zorgpraktijken en hun behandelaars: de bordklant maskeert ze (R1)."""
    try:
        with _db() as c:
            rijen = c.execute("SELECT titel, bron_onderwerp, bron_afzender, locatie FROM afspraak WHERE prive=1").fetchall()
    except sqlite3.Error:
        return set()
    uit = {v.strip() for r in rijen for v in r if v and v.strip()}
    for p in zorgprofielen():
        uit |= {str(v).strip() for v in [p.get("naam"), p.get("adres"), p.get("telefoon"), *(p.get("praktijknamen") or []),
                                         *(p.get("behandelaars") or {}), *(p.get("afzenders") or [])] if v and str(v).strip()}
    return uit


def melding_zet(sleutel, waarde):
    with _db() as c:
        c.execute("UPDATE afspraak SET melding=? WHERE sleutel=?", (waarde, sleutel))


def sleutel_kort(a):
    return hashlib.sha256(a["sleutel"].encode()).hexdigest()[:16]
