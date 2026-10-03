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


# Later bijgekomen (nacontrole v1.2, V3-V5): de start van de afspraak en de relatieve termijn (due_at = start + offset),
# de lease van een uitvoering en wanneer de afspraak laatst nagekeken is. Een bestaand register krijgt ze erbij.
EXTRA_KOLOMMEN = {"afspraak_start": "TEXT NOT NULL DEFAULT ''", "offset_s": "INTEGER", "lease_tot": "TEXT NOT NULL DEFAULT ''",
                  "herpland": "TEXT NOT NULL DEFAULT ''"}
LEASE_MINUTEN = 20          # een agent-ronde duurt hoogstens tien minuten (time-out); daarna is 'bezig' een crash


def _db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute(SCHEMA)
    er = {r[1] for r in c.execute("PRAGMA table_info(taak)")}
    for k, soort in EXTRA_KOLOMMEN.items():
        if k not in er:
            c.execute(f"ALTER TABLE taak ADD COLUMN {k} {soort}")
    c.commit()
    return c


def utc(wanneer):
    """Een tijdstip als tekst of datetime naar UTC. Zonder tijdzone is het Brusselse tijd (zo spreekt Mehdi)."""
    t = wanneer if isinstance(wanneer, datetime) else datetime.fromisoformat(str(wanneer).strip().replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=BRUSSEL)
    return t.astimezone(timezone.utc)


def brussel(iso):
    return datetime.fromisoformat(iso).astimezone(BRUSSEL).strftime("%d-%m-%Y %H:%M")


def _sleutel(soort, agent, parameters, due_at, afspraak_kalender="", afspraak_id="", offset_s=None, reden=""):
    """De betekenis van een taak: wat, voor welke afspraak, wanneer ten opzichte van die afspraak. Twee afspraken
    geven twee taken, ook met dezelfde parameters en hetzelfde uur (nacontrole v1.2, V5)."""
    wanneer = ["relatief", offset_s] if afspraak_id and offset_s is not None else ["vast", due_at]
    raw = json.dumps([soort, agent, parameters, afspraak_kalender, afspraak_id, wanneer, reden.strip().lower()],
                     sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def plannen(soort, agent, parameters, wanneer, reden="", eigenaar="mehdi", toestemming="", bron="",
            afspraak_kalender="", afspraak_id="", afspraak_dag="", afspraak_start=""):
    """Slaat een taak op en geeft haar zoals ze teruggelezen is (dict met id). Dezelfde taak twee keer plannen geeft
    dezelfde rij terug. Hangt de taak aan een afspraak met een bekende start, dan bewaar ik de termijn ten opzichte van
    die start (bv. acht dagen ervoor): verschuift de afspraak, dan verschuift de taak mee (V3). Faalt de opslag of het
    teruglezen, dan een fout: nooit een succes zonder opgeslagen taak."""
    if soort not in SOORTEN:
        raise ValueError(f"onbekende soort '{soort}'; kan: {', '.join(SOORTEN)}")
    if not agent:
        raise ValueError("agent is verplicht")
    parameters = parameters or {}
    due = _iso(utc(wanneer))
    offset_s = None
    if afspraak_id and afspraak_start:
        offset_s = int((utc(due) - utc(afspraak_start)).total_seconds())
        afspraak_dag = afspraak_dag or str(afspraak_start)[:10]
    sleutel = _sleutel(soort, agent, parameters, due, afspraak_kalender, afspraak_id, offset_s, reden)
    nu = _iso(_nu())
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO taak(sleutel,soort,agent,parameters,reden,due_at,eigenaar,toestemming,bron,"
                  "afspraak_kalender,afspraak_id,afspraak_dag,afspraak_start,offset_s,aangemaakt,bijgewerkt) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (sleutel, soort, agent, json.dumps(parameters, ensure_ascii=False), reden[:500], due, eigenaar,
                   toestemming[:300], bron[:200], afspraak_kalender, afspraak_id, afspraak_dag, str(afspraak_start or ""),
                   offset_s, nu, nu))
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
    """Open taken van deze soort waarvan het moment gekomen is (de uitvoertijd, of het volgende moment na een poging),
    en taken die op 'bezig' bleven staan terwijl hun lease verliep (een crash of herstart midden in de uitvoering,
    V4): die worden opnieuw opgepakt."""
    nu = _iso(nu or _nu())
    with _db() as c:
        rijen = c.execute("SELECT * FROM taak WHERE soort=? AND ("
                          "(status IN ('gepland','wacht-op-bron') AND (CASE WHEN volgende != '' THEN volgende ELSE due_at END) <= ?) "
                          "OR (status='bezig' AND lease_tot != '' AND lease_tot <= ?)) ORDER BY due_at", (soort, nu, nu)).fetchall()
    return [_dict(r) for r in rijen]


def herplan(tid, afspraak_start, nu=None):
    """De afspraak staat nu op afspraak_start: met een relatieve termijn verschuift de uitvoertijd mee (due_at = start +
    offset), de dag in de parameters volgt. Geeft de teruggelezen taak (V3)."""
    nu_t = nu or _nu()
    t = haal(tid)
    sets, args = ["afspraak_start=?", "afspraak_dag=?", "herpland=?", "bijgewerkt=?"], [str(afspraak_start), str(afspraak_start)[:10], _iso(nu_t), _iso(nu_t)]
    p = dict(t["parameters"])
    if p.get("dag"):
        p["dag"] = str(afspraak_start)[:10]
        sets.append("parameters=?"); args.append(json.dumps(p, ensure_ascii=False))
    if t.get("offset_s") is not None and afspraak_start:
        # een hele-dag-afspraak (datum zonder uur) telt als middernacht in Brussel, net als bij het plannen (v1.3, R5)
        sets.append("due_at=?"); args.append(_iso(utc(afspraak_start) + timedelta(seconds=int(t["offset_s"]))))
        sets.append("volgende=?"); args.append("")
    with _db() as c:
        c.execute(f"UPDATE taak SET {', '.join(sets)} WHERE id=?", args + [int(tid)])
    return haal(tid)


def te_herzien(grens, n=20):
    """Open taken aan een afspraak die het langst niet nagekeken zijn (nooit eerst), hoogstens n: elke open taak komt aan
    de beurt, ook de 21ste (nacontrole v1.3, R6). grens: alleen wat voor dat tijdstip het laatst nagekeken is."""
    with _db() as c:
        rijen = c.execute("SELECT * FROM taak WHERE status IN ('gepland','wacht-op-bron') AND afspraak_id != '' "
                          "AND herpland < ? ORDER BY herpland, id LIMIT ?", (grens, int(n))).fetchall()
    return [_dict(r) for r in rijen]


def nagekeken(tid, nu=None):
    with _db() as c:
        c.execute("UPDATE taak SET herpland=? WHERE id=?", (_iso(nu or _nu()), int(tid)))


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
        sets = "status=?, pogingen=?, volgende=?, bewijs=?, bijgewerkt=?, lease_tot=?"
        lease = _iso(nu_t + timedelta(minutes=LEASE_MINUTEN)) if status == "bezig" else ""
        args = [status, pogingen, volgende, (bewijs or r["bewijs"])[:4000], _iso(nu_t), lease]
        if parameters is not None:
            sets += ", parameters=?"
            args.append(json.dumps(parameters, ensure_ascii=False))
        if afspraak_dag is not None:
            sets += ", afspraak_dag=?"
            args.append(afspraak_dag)
        c.execute(f"UPDATE taak SET {sets} WHERE id=?", args + [int(tid)])
    return haal(tid)
