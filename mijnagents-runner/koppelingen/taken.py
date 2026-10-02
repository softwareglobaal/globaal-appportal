"""Duurzame taken voor later: een toezegging van een agent is pas een toezegging als ze hier staat.

'Agendawacht - onderzoek en herstelvoorstel v1.1' (02-10-2026), A9-A11: een belofte in een gesprek ('acht dagen ervoor
pas ik het aan') bleef tekst, want de Regisseur had geen opslag voor toekomstig werk. Hier krijgt elke taak een ID,
een uitvoertijd (UTC, met de Brusselse weergave), een eigenaar, de toestemming, een status, pogingen, het volgende
moment en het bewijs. Een dubbele planning geeft dezelfde taak terug (zelfde sleutel), zodat een herhaalde ronde geen
tweede taak maakt.

Toestanden: gepland, bezig, wacht-op-bron, mislukt, geverifieerd, vervallen.
De opslag is SQLite op de VM (mijnagents-data/taken.db), atomair per schrijfactie; alles wordt teruggelezen.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DB = os.environ.get("TAKEN_DB", os.path.expanduser("~/appportal/mijnagents-data/taken.db"))
BRUSSEL = ZoneInfo("Europe/Brussels")
STATUSSEN = ("gepland", "bezig", "wacht-op-bron", "mislukt", "geverifieerd", "vervallen")
OPEN = ("gepland", "wacht-op-bron")
MAX_POGINGEN = 5
SOORTEN = ("agent_ronde", "regelwijziging")     # agent_ronde voert de Regisseur uit; regelwijziging is voor de ontwikkelaar

SCHEMA = """CREATE TABLE IF NOT EXISTS taak (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sleutel TEXT UNIQUE NOT NULL,
    soort TEXT NOT NULL,
    agent TEXT NOT NULL,
    parameters TEXT NOT NULL DEFAULT '{}',
    reden TEXT NOT NULL DEFAULT '',
    due_at TEXT NOT NULL,
    eigenaar TEXT NOT NULL DEFAULT 'mehdi',
    toestemming TEXT NOT NULL DEFAULT '',
    bron TEXT NOT NULL DEFAULT '',
    afspraak_kalender TEXT NOT NULL DEFAULT '',
    afspraak_id TEXT NOT NULL DEFAULT '',
    afspraak_dag TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'gepland',
    pogingen INTEGER NOT NULL DEFAULT 0,
    volgende TEXT NOT NULL DEFAULT '',
    bewijs TEXT NOT NULL DEFAULT '',
    aangemaakt TEXT NOT NULL,
    bijgewerkt TEXT NOT NULL
)"""


def _nu():
    return datetime.now(timezone.utc)


def _iso(t):
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def _db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute(SCHEMA)
    return c


def utc(wanneer):
    """Een tijdstip als tekst of datetime naar UTC. Zonder tijdzone is het Brusselse tijd (zo spreekt Mehdi)."""
    t = wanneer if isinstance(wanneer, datetime) else datetime.fromisoformat(str(wanneer).strip().replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=BRUSSEL)
    return t.astimezone(timezone.utc)


def brussel(iso):
    return datetime.fromisoformat(iso).astimezone(BRUSSEL).strftime("%d-%m-%Y %H:%M")


def _sleutel(soort, agent, parameters, due_at):
    raw = json.dumps([soort, agent, parameters, due_at], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def plannen(soort, agent, parameters, wanneer, reden="", eigenaar="mehdi", toestemming="", bron="",
            afspraak_kalender="", afspraak_id="", afspraak_dag=""):
    """Slaat een taak op en geeft haar zoals ze teruggelezen is (dict met id). Dezelfde taak twee keer plannen geeft
    dezelfde rij terug. Faalt de opslag of het teruglezen, dan een fout: nooit een succes zonder opgeslagen taak."""
    if soort not in SOORTEN:
        raise ValueError(f"onbekende soort '{soort}'; kan: {', '.join(SOORTEN)}")
    if not agent:
        raise ValueError("agent is verplicht")
    parameters = parameters or {}
    due = _iso(utc(wanneer))
    sleutel = _sleutel(soort, agent, parameters, due)
    nu = _iso(_nu())
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO taak(sleutel,soort,agent,parameters,reden,due_at,eigenaar,toestemming,bron,"
                  "afspraak_kalender,afspraak_id,afspraak_dag,aangemaakt,bijgewerkt) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (sleutel, soort, agent, json.dumps(parameters, ensure_ascii=False), reden[:500], due, eigenaar,
                   toestemming[:300], bron[:200], afspraak_kalender, afspraak_id, afspraak_dag, nu, nu))
    rij = haal_sleutel(sleutel)
    if not rij:
        raise RuntimeError("taak niet teruggevonden na het opslaan")
    return rij


def _dict(r):
    if r is None:
        return None
    d = dict(r)
    d["parameters"] = json.loads(d.get("parameters") or "{}")
    d["brussel"] = brussel(d["due_at"])
    return d


def haal(tid):
    with _db() as c:
        return _dict(c.execute("SELECT * FROM taak WHERE id=?", (int(tid),)).fetchone())


def haal_sleutel(sleutel):
    with _db() as c:
        return _dict(c.execute("SELECT * FROM taak WHERE sleutel=?", (sleutel,)).fetchone())


def lijst(status=None, agent=None, n=50):
    q, a = "SELECT * FROM taak WHERE 1=1", []
    if status:
        q += " AND status IN (%s)" % ",".join("?" * len(status)); a += list(status)
    if agent:
        q += " AND agent=?"; a.append(agent)
    q += " ORDER BY due_at LIMIT ?"; a.append(int(n))
    with _db() as c:
        return [_dict(r) for r in c.execute(q, a).fetchall()]


def te_doen(nu=None, soort="agent_ronde"):
    """Open taken van deze soort waarvan het moment gekomen is (de uitvoertijd, of het volgende moment na een poging)."""
    nu = _iso(nu or _nu())
    with _db() as c:
        rijen = c.execute("SELECT * FROM taak WHERE soort=? AND status IN ('gepland','wacht-op-bron') "
                          "AND (CASE WHEN volgende != '' THEN volgende ELSE due_at END) <= ? ORDER BY due_at", (soort, nu)).fetchall()
    return [_dict(r) for r in rijen]


def zet(tid, status, bewijs="", poging=False, parameters=None, afspraak_dag=None, nu=None):
    """Nieuwe status met bewijs; bij een mislukte poging komt er een volgend moment (15, 30, 45 ... min) tot het
    maximum, daarna 'mislukt'. Geeft de teruggelezen taak."""
    if status not in STATUSSEN:
        raise ValueError(status)
    nu_t = nu or _nu()
    with _db() as c:
        r = c.execute("SELECT * FROM taak WHERE id=?", (int(tid),)).fetchone()
        if not r:
            raise KeyError(tid)
        pogingen = r["pogingen"] + (1 if poging else 0)
        volgende = r["volgende"]
        if poging and status in OPEN:
            if pogingen >= MAX_POGINGEN:
                status = "mislukt"
                volgende = ""
            else:
                volgende = _iso(nu_t + timedelta(minutes=15 * pogingen))
        sets = "status=?, pogingen=?, volgende=?, bewijs=?, bijgewerkt=?"
        args = [status, pogingen, volgende, (bewijs or r["bewijs"])[:4000], _iso(nu_t)]
        if parameters is not None:
            sets += ", parameters=?"
            args.append(json.dumps(parameters, ensure_ascii=False))
        if afspraak_dag is not None:
            sets += ", afspraak_dag=?"
            args.append(afspraak_dag)
        c.execute(f"UPDATE taak SET {sets} WHERE id=?", args + [int(tid)])
    return haal(tid)
