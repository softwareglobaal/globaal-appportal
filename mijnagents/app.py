#!/usr/bin/env python3
"""mijnagents — Mehdi's eigen agent-besturingscentrum (mijnagents.globaal.be).

Bewust zelfstandig, naar het patroon van agents/ en siyanagents/: een eigen
SQLite in het datavolume, forward-auth ervoor (nginx), en het gedeelde
hartslag-contract zodat agents interoperabel blijven met de rest.

HET VERSCHIL met siyanagents: agents staan hier NIET hardgecodeerd in de code
maar in de tabel `agent`. De generator (mijnagents-runner/nieuwe-agent.py)
voegt een rij toe; dit bord leest de rijen. Een agent toevoegen kost dus geen
code-wijziging en geen herbouw.

Zichtbaarheidsregel (net als de agents-tegel, want de groep `agents` bevat ook
mensen buiten het beheer): op het bord staat ALLEEN werkstatus, nooit inhoud.
Geen klantnamen, geen bedragen, geen dossierinhoud. Tellingen en neutrale
taakomschrijvingen zijn de grens.
"""
import json
import re
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)

DB_PAD = os.environ.get("AGENTS_DB", os.path.join(os.path.dirname(__file__), "mijnagents.db"))
TOKEN = os.environ.get("AGENTS_TOKEN", "")
APP_NAAM = os.environ.get("APP_NAME", "Mijn agents")

# Wie mag beslissen over voorstellen (goedkeuren/weigeren). Zien mag iedereen
# die door de forward-auth komt; beslissen is beheer.
BESLIS_GROEPEN = {"admin", "manager"}

# Stilte-detectie: een hartslag ouder dan dit (minuten) maakt de kaart "stil".
# Ruime marges op een uurlijkse cadans, gelijk aan de agents-tegel.
STILTE_MIN = {"actief": 60, "waakt": 150, "klaar": 1440, "fout": 1440, "rust": 1440}
STATUS_LABEL = {
    "rust": "in rust", "waakt": "waakt", "actief": "actief",
    "klaar": "klaar", "fout": "fout", "stil": "stil", "onbekend": "niet gekoppeld",
}


# ---------------------------------------------------------------- database ---
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PAD)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.after_request
def _geen_cache(resp):
    # Het bord verandert elke minuut (hartslagen, noden, nieuwe agents). Een
    # telefoon die een oude pagina vasthoudt toont anders een verouderd
    # organogram; daarom nooit bewaren.
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@app.teardown_appcontext
def _sluit(_exc):
    d = g.pop("db", None)
    if d is not None:
        d.close()


def init_db():
    conn = sqlite3.connect(DB_PAD)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent (
            naam     TEXT PRIMARY KEY,   -- kort, kleine letters, met koppelteken
            label    TEXT NOT NULL,      -- weergavenaam
            type     TEXT DEFAULT '',    -- groepering op het bord
            rol      TEXT DEFAULT '',    -- een regel: wat hij doet
            mandaat  TEXT DEFAULT '',    -- wat hij doet en voor wie
            mag      TEXT DEFAULT '[]',  -- json-lijst: wat hij zelfstandig mag
            grenzen  TEXT DEFAULT '[]',  -- json-lijst: wat hij nooit doet
            cadans   TEXT DEFAULT '',    -- hoe vaak / wanneer
            tools    TEXT DEFAULT '[]',  -- json-lijst: echte gereedschappen
            eigenaar TEXT DEFAULT 'mehdi',
            actief   INTEGER DEFAULT 1,  -- 0 = uit het bord (gearchiveerd)
            aangemaakt TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS status (
            naam   TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            taak   TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            tokens INTEGER,
            ts     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS voorstel (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            naam       TEXT NOT NULL,       -- welke agent stelt voor
            actie      TEXT NOT NULL,       -- korte titel
            doel       TEXT DEFAULT '',
            reden      TEXT DEFAULT '',
            parameters TEXT DEFAULT '',     -- json; leeg = louter signaal (nooit uitvoerbaar)
            runbook    TEXT DEFAULT '',     -- naam van een toegestaan runbook (optioneel)
            status     TEXT DEFAULT 'open', -- open | goedgekeurd | geweigerd | uitgevoerd | mislukt
            besluit_door TEXT DEFAULT '',
            besluit_ts   TEXT DEFAULT '',
            bewijs     TEXT DEFAULT '',
            ts         TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS handeling (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            naam   TEXT NOT NULL,
            wat    TEXT NOT NULL,
            ts     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logboek (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            naam      TEXT NOT NULL,        -- agent
            onderwerp TEXT DEFAULT '',      -- bv. 'deal 14474 · 2611 Kim Venken'
            stap      TEXT NOT NULL,        -- bron | bevinding | besluit | schrijf | proef | melding | fout
            tekst     TEXT NOT NULL,        -- leesbare regel
            detail    TEXT DEFAULT '',      -- optioneel: langere tekst / json
            ts        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS logboek_naam_ts ON logboek(naam, ts);
        CREATE TABLE IF NOT EXISTS klaarzet (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            van       TEXT NOT NULL,        -- bron-agent (bv. agenda-wacht)
            voor      TEXT NOT NULL,        -- afdeling of agent die het gebruikt (bv. h-architects, contracten-agent, mehdi)
            soort     TEXT NOT NULL,        -- afspraak | transcript | opname | dagplan | signaal
            sleutel   TEXT DEFAULT '',      -- koppeling: deal_id, projectnummer, datum
            titel     TEXT NOT NULL,
            inhoud    TEXT DEFAULT '',      -- tekst of json
            verwijzing TEXT DEFAULT '',     -- pad in Dropbox, url
            uniek     TEXT DEFAULT '',      -- idempotentiesleutel (bv. fathom:816732165)
            status    TEXT DEFAULT 'klaar', -- klaar | opgepakt | vervallen
            ts        TEXT NOT NULL,
            opgepakt_door TEXT DEFAULT '',
            opgepakt_ts   TEXT DEFAULT ''
        );
        CREATE UNIQUE INDEX IF NOT EXISTS klaarzet_uniek ON klaarzet(uniek) WHERE uniek<>'';
        CREATE TABLE IF NOT EXISTS nood (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            naam    TEXT NOT NULL,       -- agent
            tekst   TEXT NOT NULL,       -- wat hij nodig heeft of wat niet werkt
            wie     TEXT DEFAULT '',     -- wie het kan oplossen: mehdi | claude-code | collega
            open    INTEGER DEFAULT 1,
            ts      TEXT NOT NULL,
            opgelost_ts TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS gesprek_log (
            uniek     TEXT PRIMARY KEY,   -- bv. fathom:816732165
            datum     TEXT, start TEXT, minuten INTEGER,
            personen  TEXT DEFAULT '', bedrijf TEXT DEFAULT '', afdeling TEXT DEFAULT '',
            thema     TEXT DEFAULT '', project TEXT DEFAULT '', prive INTEGER DEFAULT 0,
            zekerheid TEXT DEFAULT '', waarom TEXT DEFAULT '', archief TEXT DEFAULT '',
            link      TEXT DEFAULT '', opgenomen_door TEXT DEFAULT '', bron TEXT DEFAULT 'fathom',
            ts        TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS afdeling (
            naam         TEXT PRIMARY KEY,   -- sleutel, gelijk aan agent.type
            label        TEXT NOT NULL,
            omschrijving TEXT DEFAULT '',
            volgorde     INTEGER DEFAULT 100
        );
        CREATE TABLE IF NOT EXISTS gesprek (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            aan        TEXT NOT NULL,          -- agentnaam, of 'regisseur' voor de hoofdagent
            van        TEXT NOT NULL,          -- wie het vroeg (gebruikersnaam)
            tekst      TEXT NOT NULL,          -- de vraag of opdracht
            antwoord   TEXT DEFAULT '',        -- het antwoord van de agent
            status     TEXT DEFAULT 'open',    -- open | bezig | beantwoord | mislukt
            detail     TEXT DEFAULT '',        -- wat de agent deed om te antwoorden
            ts         TEXT NOT NULL,
            beantwoord_ts TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS werkwijze_versie (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            naam  TEXT NOT NULL,
            tekst TEXT NOT NULL,
            wie   TEXT DEFAULT '',
            ts    TEXT NOT NULL
        );
        """
    )
    # Latere kolommen op agent: de werkwijze (het volledige proces, door Mehdi
    # te bewerken op het bord; de agent leest het elke ronde) en de kennis
    # (wat de agent in zijn laatste ronde als instructie las, door hem gemeld).
    # Vaste afdelingen (idempotent). Nieuwe afdelingen via POST /api/afdeling.
    for naam, label, oms, volg in (
        ("regie", "Regie", "Het overzicht, het gesprek met Mehdi en de voorstellen.", 10),
        ("h-architects", "H-Architects", "Het kantoor: contracten, dossiers, klanten.", 20),
        ("prive", "Privé", "Mehdi zelf: agenda, gegevens van de Mac, persoonlijke dossiers.", 30),
    ):
        conn.execute("INSERT OR IGNORE INTO afdeling(naam, label, omschrijving, volgorde) VALUES(?,?,?,?)",
                     (naam, label, oms, volg))
    bestaand = {r[1] for r in conn.execute("PRAGMA table_info(agent)")}
    for kolom, definitie in (("werkwijze", "TEXT DEFAULT ''"), ("kennis", "TEXT DEFAULT ''"),
                             ("kennis_ts", "TEXT DEFAULT ''"), ("kennis_bron", "TEXT DEFAULT ''"),
                             ("levert_aan", "TEXT DEFAULT '[]'"), ("draait_op", "TEXT DEFAULT 'VM'"),
                             ("prive", "INTEGER DEFAULT 0")):  # 1 = alleen zichtbaar voor beheer (Mehdi)
        if kolom not in bestaand:
            conn.execute(f"ALTER TABLE agent ADD COLUMN {kolom} {definitie}")
    conn.commit()
    conn.close()


def md(tekst):
    """Markdown naar HTML voor de werkwijze en de kennis (tekst van beheer of
    van het contract-dashboard, dus vertrouwd)."""
    try:
        import markdown
        return markdown.markdown(tekst or "", extensions=["tables", "fenced_code"])
    except Exception:  # noqa: BLE001
        from html import escape
        return "<pre style='white-space:pre-wrap'>" + escape(tekst or "") + "</pre>"


# ------------------------------------------------------------------ helpers ---
def nu():
    return datetime.now(timezone.utc).isoformat()


def groepen():
    # Authentik scheidt groepen met "|" (forward auth); onze eigen tests en oudere
    # koppelingen gebruiken ",". Allebei aanvaarden, anders herkent het bord
    # beheer niet en verdwijnen gespreksvak, werkverslag en bewerken.
    ruw = request.headers.get("X-authentik-groups", "")
    return {x.strip() for x in re.split(r"[|,]", ruw) if x.strip()}


def gebruiker():
    return request.headers.get("X-authentik-username", "") or "?"


def mag_beslissen():
    return bool(groepen() & BESLIS_GROEPEN)


def leeftijd_min(ts):
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 60.0
    except Exception:
        return None


def _lijst(val):
    try:
        v = json.loads(val or "[]")
        return v if isinstance(v, list) else [str(v)]
    except Exception:
        return [s for s in (val or "").split("\n") if s.strip()]


def zichtbaar_sql():
    """Privé-agents (bv. het locatielogboek) bestaan alleen voor beheer."""
    return "" if mag_beslissen() else " AND prive=0"


def kaarten():
    conn = db()
    rijen = conn.execute(f"SELECT * FROM agent WHERE actief=1{zichtbaar_sql()} ORDER BY type, label").fetchall()
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    open_per = {}
    for r in conn.execute(
        "SELECT naam, COUNT(*) n FROM voorstel WHERE status='open' GROUP BY naam"
    ).fetchall():
        open_per[r["naam"]] = r["n"]
    nood_per = {}
    for r in conn.execute("SELECT naam, tekst, wie FROM nood WHERE open=1 ORDER BY id").fetchall():
        nood_per.setdefault(r["naam"], []).append(dict(r))

    uit = []
    for a in rijen:
        s = st.get(a["naam"])
        if not s:
            toestand, taak, detail, ts, leeftijd = "onbekend", "", "", None, None
        else:
            leeftijd = leeftijd_min(s["ts"])
            toestand = s["status"] if s["status"] in STILTE_MIN else "waakt"
            drempel = STILTE_MIN.get(toestand, 150)
            if leeftijd is not None and leeftijd > drempel:
                toestand = "stil"
            taak, detail, ts = s["taak"], s["detail"], s["ts"]
        uit.append(
            {
                "naam": a["naam"], "label": a["label"], "type": a["type"] or "overig",
                "rol": a["rol"], "eigenaar": a["eigenaar"],
                "toestand": toestand, "toestand_label": STATUS_LABEL.get(toestand, toestand),
                "taak": taak, "detail": detail, "ts": ts,
                "leeftijd_min": None if leeftijd is None else int(leeftijd),
                "open_voorstellen": open_per.get(a["naam"], 0),
                "nood": nood_per.get(a["naam"], []),
            }
        )
    return uit


@app.route("/api/nood")
def api_nood():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    rijen = db().execute("SELECT * FROM nood WHERE open=1 ORDER BY naam, id").fetchall()
    return jsonify(nood=[dict(r) for r in rijen])


# ------------------------------------------------------------------- routes ---
@app.route("/")
def bord():
    ks = kaarten()
    afd = {r["naam"]: dict(r) for r in db().execute("SELECT * FROM afdeling").fetchall()}
    groepering = {}
    for k in ks:
        groepering.setdefault(k["type"], []).append(k)
    # Afdelingen in vaste volgorde, ook als ze (nog) geen agent hebben; onbekende types achteraan.
    volgorde = sorted(set(list(afd) + list(groepering)),
                      key=lambda n: (afd.get(n, {}).get("volgorde", 999), n))
    groepering = {n: groepering.get(n, []) for n in volgorde}
    afdelingen = {n: afd.get(n, {"naam": n, "label": n, "omschrijving": ""}) for n in volgorde}
    open_voorstellen = db().execute(
        "SELECT v.*, a.label FROM voorstel v LEFT JOIN agent a ON a.naam=v.naam "
        "WHERE v.status='open' ORDER BY v.id DESC"
    ).fetchall()
    return render_template(
        "board.html", app_naam=APP_NAAM, groepen=groepering, aantal=len(ks),
        voorstellen=open_voorstellen, mag_beslissen=mag_beslissen(),
        gebruiker=gebruiker(),
        gesprekken=gesprekken_voor("regisseur", 12) if mag_beslissen() else [],
        regisseur_html=md, afdelingen=afdelingen,
    )


# --- klaargezet: bron-agents (Privé) zetten iets klaar; afdelingsagents pakken het op.
@app.route("/api/klaarzet", methods=["POST"])
def api_klaarzet():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    items = p.get("items") if isinstance(p.get("items"), list) else [p]
    conn = db()
    nieuw, bestaand, bijgewerkt = 0, 0, 0
    for it in items:
        if not (it.get("van") and it.get("voor") and it.get("soort") and it.get("titel")):
            continue
        uniek = (it.get("uniek") or "")[:200]
        inhoud = it.get("inhoud")
        if not isinstance(inhoud, str):
            inhoud = json.dumps(inhoud, ensure_ascii=False)
        oud = conn.execute("SELECT id, voor, titel, inhoud, verwijzing, status FROM klaarzet WHERE uniek=?", (uniek,)).fetchone() if uniek else None
        if oud:
            # Les van 12-09-2026: een item dat nog niet opgepakt is, volgt de bron. Toen de Agendawacht TKN leerde
            # herkennen, bleef de afspraak van Britt Verboven bij h-architects staan omdat de bak nooit bijwerkte.
            if oud["status"] == "klaar" and (oud["voor"], oud["titel"], oud["inhoud"], oud["verwijzing"] or "") != \
                    (it["voor"], it["titel"][:300], inhoud[:60000], (it.get("verwijzing") or "")[:500]):
                conn.execute("UPDATE klaarzet SET voor=?, titel=?, inhoud=?, verwijzing=?, sleutel=? WHERE id=?",
                             (it["voor"], it["titel"][:300], inhoud[:60000], (it.get("verwijzing") or "")[:500],
                              str(it.get("sleutel") or "")[:120], oud["id"]))
                bijgewerkt += 1
            else:
                bestaand += 1
            continue
        conn.execute(
            "INSERT INTO klaarzet(van, voor, soort, sleutel, titel, inhoud, verwijzing, uniek, ts) VALUES(?,?,?,?,?,?,?,?,?)",
            (it["van"], it["voor"], it["soort"][:40], str(it.get("sleutel") or "")[:120], it["titel"][:300],
             inhoud[:60000], (it.get("verwijzing") or "")[:500], uniek, nu()))
        nieuw += 1
    conn.commit()
    return jsonify(ok=True, nieuw=nieuw, bestaand=bestaand, bijgewerkt=bijgewerkt)


@app.route("/api/klaarzet")
def api_klaarzet_lezen():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    voor = request.args.get("voor")
    sleutel = request.args.get("sleutel")
    status = request.args.get("status", "klaar")
    q, a = "SELECT * FROM klaarzet WHERE 1=1", []
    if voor:
        q += " AND (voor=? OR voor=?)"; a += [voor, request.args.get("afdeling") or voor]
    if sleutel:
        q += " AND sleutel=?"; a.append(sleutel)
    if status != "alle":
        q += " AND status=?"; a.append(status)
    q += " ORDER BY id DESC LIMIT ?"; a.append(min(int(request.args.get("n", 100)), 500))
    return jsonify(items=[dict(r) for r in db().execute(q, a).fetchall()])


@app.route("/api/klaarzet/<int:kid>/opgepakt", methods=["POST"])
def api_klaarzet_opgepakt(kid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    db().execute("UPDATE klaarzet SET status='opgepakt', opgepakt_door=?, opgepakt_ts=? WHERE id=?",
                 ((p.get("door") or "")[:80], nu(), kid))
    db().commit()
    return jsonify(ok=True)


# --- gesprekkentabel: het "Excel-achtige" logboek van gesprekken (Fathom, later Plaud,
#     telefoon). Alleen beheer ziet het; privé-rijen zijn er, maar alleen voor beheer.
@app.route("/api/gesprekken", methods=["POST"])
def api_gesprekken_zetten():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    n = 0
    for r in p.get("rijen") or []:
        if not r.get("uniek"):
            continue
        conn.execute(
            "INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,bedrijf,afdeling,thema,project,prive,zekerheid,waarom,archief,link,opgenomen_door,bron,ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uniek) DO UPDATE SET datum=excluded.datum, start=excluded.start, minuten=excluded.minuten, "
            "personen=excluded.personen, bedrijf=excluded.bedrijf, afdeling=excluded.afdeling, thema=excluded.thema, project=excluded.project, prive=excluded.prive, "
            "zekerheid=excluded.zekerheid, waarom=excluded.waarom, archief=excluded.archief, link=excluded.link, opgenomen_door=excluded.opgenomen_door, ts=excluded.ts",
            (r["uniek"], r.get("datum", ""), r.get("start", ""), int(r.get("minuten") or 0), r.get("personen", ""), r.get("bedrijf", ""),
             r.get("afdeling", ""), r.get("thema", ""), r.get("project", ""), 1 if r.get("prive") else 0, r.get("zekerheid", ""),
             r.get("waarom", ""), r.get("archief", ""), r.get("link", ""), r.get("opgenomen_door", ""), r.get("bron", "fathom"), nu()))
        n += 1
    conn.commit()
    return jsonify(ok=True, rijen=n)


@app.route("/gesprekken")
def gesprekken_pagina():
    if not mag_beslissen():
        abort(403)
    rijen = db().execute("SELECT * FROM gesprek_log ORDER BY datum DESC, start DESC LIMIT 2000").fetchall()
    return render_template("gesprekken.html", app_naam=APP_NAAM, rijen=rijen)


# --- dagen: het dagdashboard van de logboek-laag. Per dag wat de Dagbundelaar
#     samenbracht: uren onderweg, bezoeken, gesprekken en met wie, afspraken,
#     foto's, lichaam, en de spiegel van De Levenscoach. Alleen beheer.
@app.route("/dagen")
def dagen_pagina():
    if not mag_beslissen():
        abort(403)
    conn = db()
    dagen = {}

    def dag_van(it):
        inhoud = it["inhoud"] or ""
        try:
            d = json.loads(inhoud) if inhoud.startswith("{") else {}
        except ValueError:
            d = {}
        return (d.get("datum") or d.get("start") or it["sleutel"] or "")[:10], d

    for it in conn.execute("SELECT * FROM klaarzet ORDER BY id").fetchall():
        dag, d = dag_van(it)
        if not (len(dag) == 10 and dag[4] == "-"):
            continue
        r = dagen.setdefault(dag, {"dag": dag, "afspraken": 0, "gesprekken": 0, "gesprek_min": 0, "personen": set(), "bezoeken": 0,
                                   "km": 0.0, "onderweg_min": 0, "fotos": 0, "slaap": "", "hartslag": "", "spiegel": "", "bundels": 0,
                                   "signalen": 0, "transcripten": 0})
        s = it["soort"]
        if s == "afspraak":
            r["afspraken"] += 1
        elif s == "transcript":
            r["transcripten"] += 1
        elif s == "foto":
            r["fotos"] += int(d.get("aantal") or 0)
        elif s == "locatie":
            for regel in (it["inhoud"] or "").splitlines():
                if regel.startswith("| ") and "| bezoek" in regel:
                    r["bezoeken"] += 1
                if regel.startswith("| ") and "verplaatsing" in regel:
                    try:
                        r["km"] += float(regel.rsplit("|", 2)[-2].strip().replace(" km", "").replace(",", "."))
                        m = regel.split("|")[3].strip()
                        r["onderweg_min"] += (int(m.split("u")[0]) * 60 + int(m.split("u")[1])) if "u" in m else int(m.replace(" min", "") or 0)
                    except (ValueError, IndexError):
                        pass
        elif s == "gezondheid":
            r["slaap"] = (d.get("samenvatting") or "")[:160]
        elif s == "coaching" and not it["sleutel"].startswith("week"):
            r["spiegel"] = it["inhoud"] or ""
        elif s == "dagbundel":
            r["bundels"] += 1
        elif s == "signaal":
            r["signalen"] += 1
    for g in conn.execute("SELECT datum, minuten, personen, prive FROM gesprek_log").fetchall():
        r = dagen.setdefault(g["datum"], {"dag": g["datum"], "afspraken": 0, "gesprekken": 0, "gesprek_min": 0, "personen": set(), "bezoeken": 0,
                                          "km": 0.0, "onderweg_min": 0, "fotos": 0, "slaap": "", "hartslag": "", "spiegel": "", "bundels": 0,
                                          "signalen": 0, "transcripten": 0})
        r["gesprekken"] += 1
        r["gesprek_min"] += int(g["minuten"] or 0)
        for p in (g["personen"] or "").split(","):
            if p.strip():
                r["personen"].add(p.strip())
    rijen = sorted(dagen.values(), key=lambda x: x["dag"], reverse=True)[:120]
    for r in rijen:
        r["personen"] = ", ".join(sorted(r["personen"]))[:200]
        r["spiegel_html"] = md(r["spiegel"]) if r["spiegel"] else ""
    return render_template("dagen.html", app_naam=APP_NAAM, rijen=rijen)


# --- kantoor: het virtuele kantoor. Elke afdeling een kamer, elke agent een
#     bureau met een figuurtje; de tekstballon is zijn laatste taak. Alles uit
#     de gegevens, dus een nieuwe agent krijgt vanzelf een bureau.
PROPS = (("regisseur", "megafoon"), ("ontwikkelaar", "schroevendraaier"), ("bode", "envelop"), ("contract", "pen"),
         ("agenda", "kalender"), ("fathom", "koptelefoon"), ("plaud", "microfoon"), ("locatie", "kompas"),
         ("icloud", "camera"), ("gezondheid", "hart"), ("levenscoach", "kopje"), ("dagbundel", "map"),
         ("mail", "brief"), ("zoom", "scherm"), ("whatsapp", "telefoon"), ("bel", "hoorn"), ("communicatie", "netwerk"))


def _kantoor_gegevens():
    conn = db()
    afd = [dict(r) for r in conn.execute("SELECT * FROM afdeling ORDER BY volgorde, naam").fetchall()]
    agents = [dict(r) for r in conn.execute(f"SELECT naam,label,type,rol,draait_op,cadans,prive FROM agent WHERE actief=1{zichtbaar_sql()} ORDER BY label").fetchall()]
    st = {r["naam"]: dict(r) for r in conn.execute("SELECT * FROM status").fetchall()}
    for a in agents:
        s = st.get(a["naam"])
        a["toestand"], a["taak"], a["detail"] = "onbekend", "", ""
        if s:
            leeftijd = leeftijd_min(s["ts"])
            t = s["status"] if s["status"] in STILTE_MIN else "waakt"
            a["toestand"] = "stil" if (leeftijd is not None and leeftijd > STILTE_MIN.get(t, 150)) else t
            a["taak"], a["detail"] = s["taak"] or "", (s["detail"] or "")[:90]
        a["prop"] = next((p for k, p in PROPS if k in a["naam"]), "laptop")
        a["kleur"] = sum(ord(c) for c in a["naam"]) % 6
    return afd, agents


@app.route("/kantoor")
def kantoor():
    afd, agents = _kantoor_gegevens()
    # kamers: Regie apart bovenaan; de rest in rijen van drie, met de agents per kamer
    kamers = []
    for a in afd:
        leden = [x for x in agents if x["type"] == a["naam"]]
        kamers.append({**a, "leden": leden})
    return render_template("kantoor.html", app_naam=APP_NAAM, kamers=kamers, mag_beslissen=mag_beslissen())


@app.route("/api/kantoor")
def api_kantoor():
    _, agents = _kantoor_gegevens()
    return jsonify(agents=[{k: a[k] for k in ("naam", "toestand", "taak", "detail")} for a in agents])


@app.route("/dag/<datum>")
def dag_pagina(datum):
    """Alles van één dag bij elkaar: overzicht en bundels van de Dagbundelaar, de
    spiegel van De Levenscoach, het locatiedagboek, de gesprekken, de afspraken,
    de foto's, het lichaam, de mails. Alleen beheer."""
    if not mag_beslissen() or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        abort(404 if mag_beslissen() else 403)
    conn = db()
    items = []
    for it in conn.execute("SELECT * FROM klaarzet ORDER BY id").fetchall():
        inhoud = it["inhoud"] or ""
        try:
            d = json.loads(inhoud) if inhoud.startswith("{") else {}
        except ValueError:
            d = {}
        dag = (d.get("datum") or d.get("start") or it["sleutel"] or "")[:10]
        if dag == datum or (it["soort"] in ("dagbundel", "coaching", "locatie", "dagplan", "mail", "gezondheid") and it["sleutel"] == datum):
            r = dict(it)
            r["json"] = d
            r["tekst"] = inhoud if not inhoud.startswith("{") else ""
            items.append(r)
    def van_soort(*s):
        return [i for i in items if i["soort"] in s]
    gesprekken = conn.execute("SELECT * FROM gesprek_log WHERE datum=? ORDER BY start", (datum,)).fetchall()
    return render_template(
        "dag.html", app_naam=APP_NAAM, datum=datum, mdf=md,
        overzichten=van_soort("dagbundel"), spiegels=van_soort("coaching"), locaties=van_soort("locatie"),
        dagplannen=van_soort("dagplan"), afspraken=van_soort("afspraak"), fotos=van_soort("foto"),
        gezondheid=van_soort("gezondheid"), mails=van_soort("mail"), signalen=van_soort("signaal"),
        transcripten=van_soort("transcript", "werfbezoek"), gesprekken=gesprekken,
    )


# --- organogram: getekend uit de gegevens zelf (afdelingen, agents, levert_aan)
@app.route("/organogram")
def organogram():
    conn = db()
    afd = [dict(r) for r in conn.execute("SELECT * FROM afdeling ORDER BY volgorde, naam").fetchall()]
    agents = [dict(r) for r in conn.execute(f"SELECT naam,label,type,rol,levert_aan,draait_op,cadans FROM agent WHERE actief=1{zichtbaar_sql()} ORDER BY label").fetchall()]
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    for a in agents:
        a["levert_aan"] = _lijst(a["levert_aan"])
        s = st.get(a["naam"])
        a["toestand"] = "onbekend"
        if s:
            leeftijd = leeftijd_min(s["ts"])
            t = s["status"] if s["status"] in STILTE_MIN else "waakt"
            a["toestand"] = "stil" if (leeftijd is not None and leeftijd > STILTE_MIN.get(t, 150)) else t
    klaar = conn.execute("SELECT voor, COUNT(*) n FROM klaarzet WHERE status='klaar' GROUP BY voor").fetchall()
    return render_template("organogram.html", app_naam=APP_NAAM, afdelingen=afd, agents=agents,
                           klaar={r["voor"]: r["n"] for r in klaar}, mag_beslissen=mag_beslissen())


@app.route("/api/afdeling", methods=["POST"])
def api_afdeling():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    if not p.get("naam") or not p.get("label"):
        return jsonify(fout="naam en label vereist"), 400
    db().execute("INSERT INTO afdeling(naam, label, omschrijving, volgorde) VALUES(?,?,?,?) "
                 "ON CONFLICT(naam) DO UPDATE SET label=excluded.label, omschrijving=excluded.omschrijving, volgorde=excluded.volgorde",
                 (p["naam"], p["label"], p.get("omschrijving", ""), int(p.get("volgorde") or 100)))
    db().commit()
    return jsonify(ok=True)


@app.route("/agent/<naam>")
def detail(naam):
    a = db().execute(f"SELECT * FROM agent WHERE naam=?{zichtbaar_sql()}", (naam,)).fetchone()
    if not a:
        abort(404)
    s = db().execute("SELECT * FROM status WHERE naam=?", (naam,)).fetchone()
    vs = db().execute(
        "SELECT * FROM voorstel WHERE naam=? ORDER BY id DESC LIMIT 20", (naam,)
    ).fetchall()
    # Het werkverslag (wat de agent las, vond, besliste en schreef) is inhoud,
    # geen werkstatus. Daarom alleen voor beheer (admin/manager); de groep
    # agents ziet de kaart en de status, niet het verslag.
    verslag, onderwerpen = [], []
    if mag_beslissen():
        verslag = db().execute(
            "SELECT * FROM logboek WHERE naam=? ORDER BY id DESC LIMIT 300", (naam,)
        ).fetchall()
        onderwerpen = db().execute(
            "SELECT onderwerp, MAX(ts) laatst, COUNT(*) n FROM logboek WHERE naam=? "
            "AND onderwerp<>'' GROUP BY onderwerp ORDER BY laatst DESC LIMIT 40", (naam,)
        ).fetchall()
    versies = db().execute(
        "SELECT id, wie, ts, length(tekst) n FROM werkwijze_versie WHERE naam=? ORDER BY id DESC LIMIT 10", (naam,)
    ).fetchall()
    return render_template(
        "detail.html", app_naam=APP_NAAM, a=a, s=s, voorstellen=vs,
        mag=_lijst(a["mag"]), grenzen=_lijst(a["grenzen"]), tools=_lijst(a["tools"]),
        mag_beslissen=mag_beslissen(), verslag=verslag, onderwerpen=onderwerpen,
        gekozen=request.args.get("onderwerp", ""),
        werkwijze_html=md(a["werkwijze"]), kennis_html=md(a["kennis"]), versies=versies,
        bewerken=request.args.get("bewerken") == "1",
        gesprekken=gesprekken_for_detail(naam) if mag_beslissen() else [], mdf=md,
    )


def gesprekken_for_detail(naam):
    return gesprekken_voor(naam, 20)


# --- werkwijze: het volledige proces van een agent, door beheer te bewerken
#     op het bord. De agent haalt het elke ronde op (GET, token) en volgt het.
@app.route("/agent/<naam>/werkwijze", methods=["POST"])
def werkwijze_opslaan(naam):
    if not mag_beslissen():
        abort(403)
    tekst = (request.form.get("werkwijze") or "").replace("\r\n", "\n").strip()
    conn = db()
    if not conn.execute("SELECT 1 FROM agent WHERE naam=?", (naam,)).fetchone():
        abort(404)
    oud = conn.execute("SELECT werkwijze FROM agent WHERE naam=?", (naam,)).fetchone()["werkwijze"] or ""
    if oud.strip() != tekst:
        conn.execute("INSERT INTO werkwijze_versie(naam, tekst, wie, ts) VALUES(?,?,?,?)",
                     (naam, oud, "vorige versie", nu()))
        conn.execute("UPDATE agent SET werkwijze=? WHERE naam=?", (tekst, naam))
        conn.execute("INSERT INTO handeling(naam, wat, ts) VALUES(?,?,?)",
                     (naam, f"werkwijze bijgewerkt door {gebruiker()}", nu()))
        conn.commit()
    return redirect(url_for("detail", naam=naam) + "#werkwijze")


@app.route("/api/agent/<naam>/werkwijze")
def api_werkwijze(naam):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    a = db().execute("SELECT werkwijze FROM agent WHERE naam=?", (naam,)).fetchone()
    if not a:
        abort(404)
    return jsonify(naam=naam, werkwijze=a["werkwijze"] or "")


@app.route("/api/agent/<naam>/werkwijze", methods=["POST"])
def api_werkwijze_zetten(naam):
    """Voor de generator: de eerste werkwijze zetten. Overschrijft niet wat
    beheer intussen op het bord bewerkte, tenzij 'overschrijf' waar is."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    a = conn.execute("SELECT werkwijze FROM agent WHERE naam=?", (naam,)).fetchone()
    if not a:
        abort(404)
    if (a["werkwijze"] or "").strip() and not p.get("overschrijf"):
        return jsonify(ok=False, reden="werkwijze bestaat al op het bord; niet overschreven")
    conn.execute("INSERT INTO werkwijze_versie(naam, tekst, wie, ts) VALUES(?,?,?,?)",
                 (naam, a["werkwijze"] or "", "vorige versie", nu()))
    conn.execute("UPDATE agent SET werkwijze=? WHERE naam=?", ((p.get("werkwijze") or "").strip(), naam))
    conn.commit()
    return jsonify(ok=True)


# --- kennis: de agent meldt wat hij in zijn laatste ronde als instructie las,
#     zodat beheer op het bord ziet wat hij wist toen hij werkte.
@app.route("/api/agent/<naam>/kennis", methods=["POST"])
def api_kennis(naam):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    if not conn.execute("SELECT 1 FROM agent WHERE naam=?", (naam,)).fetchone():
        abort(404)
    conn.execute("UPDATE agent SET kennis=?, kennis_ts=?, kennis_bron=? WHERE naam=?",
                 (str(p.get("kennis") or "")[:200000], nu(), str(p.get("bron") or "")[:300], naam))
    conn.commit()
    return jsonify(ok=True)


# --- werkverslag: een agent legt vast wat hij las, vond, besliste en schreef.
#     Token-gated. Eén regel per stap; 'detail' mag langer zijn (bv. het plan).
@app.route("/api/logboek", methods=["POST"])
def api_logboek():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    regels = p.get("regels") if isinstance(p.get("regels"), list) else [p]
    conn = db()
    n = 0
    for r in regels:
        naam, stap, tekst = (r.get("naam") or "").strip(), (r.get("stap") or "").strip(), (r.get("tekst") or "").strip()
        if not naam or not stap or not tekst:
            continue
        conn.execute(
            "INSERT INTO logboek(naam, onderwerp, stap, tekst, detail, ts) VALUES(?,?,?,?,?,?)",
            (naam, (r.get("onderwerp") or "")[:200], stap[:40], tekst[:1000],
             str(r.get("detail") or "")[:20000], nu()),
        )
        n += 1
    conn.commit()
    return jsonify(ok=True, geschreven=n)


# --- hartslag: de agent-runner meldt hier zijn status. Deze route passeert de
#     forward-auth (nginx laat hem door); we toetsen zelf het token. ----------
@app.route("/agent-status", methods=["POST"])
def agent_status():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    naam = (p.get("naam") or "").strip()
    status = (p.get("status") or "").strip()
    if not naam or status not in STILTE_MIN:
        return jsonify(fout="naam en geldige status vereist"), 400
    conn = db()
    conn.execute(
        "INSERT INTO status(naam,status,taak,detail,tokens,ts) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(naam) DO UPDATE SET status=excluded.status, taak=excluded.taak, "
        "detail=excluded.detail, tokens=excluded.tokens, ts=excluded.ts",
        (naam, status, p.get("taak", ""), p.get("detail", ""), p.get("tokens"), nu()),
    )
    # Wat de agent nodig heeft of wat bij hem niet werkt: hij meldt de volledige
    # lijst; wat er niet meer in staat is opgelost. Zo ziet beheer in één
    # overzicht waar geholpen moet worden.
    if isinstance(p.get("nood"), list):
        nieuw = [(str(n.get("tekst") if isinstance(n, dict) else n).strip()[:400],
                  (n.get("wie") if isinstance(n, dict) else "mehdi") or "mehdi") for n in p["nood"]]
        nieuw = [(t, w) for t, w in nieuw if t]
        open_ = {r["tekst"]: r["id"] for r in conn.execute("SELECT id, tekst FROM nood WHERE naam=? AND open=1", (naam,)).fetchall()}
        for t, w in nieuw:
            if t not in open_:
                conn.execute("INSERT INTO nood(naam, tekst, wie, ts) VALUES(?,?,?,?)", (naam, t, w, nu()))
        for t, nid in open_.items():
            if t not in {x for x, _ in nieuw}:
                conn.execute("UPDATE nood SET open=0, opgelost_ts=? WHERE id=?", (nu(), nid))
    # Optioneel voorstel meegestuurd (mens-in-de-lus).
    v = p.get("voorstel")
    if isinstance(v, dict) and v.get("actie"):
        params = v.get("parameters")
        pjson = json.dumps(params) if params else ""
        # Hetzelfde voorstel (agent, runbook, actie en parameters) dat al open staat, goedgekeurd op uitvoering
        # wacht of door Mehdi geweigerd is, zet je niet opnieuw: een agent die elke ronde voorstelt, zou hem
        # anders elke ronde opnieuw vragen (werfverslag-voorbereider, opruiming van dubbele rijen, 24-09-2026).
        zelfde = pjson and conn.execute(
            "SELECT id FROM voorstel WHERE naam=? AND runbook=? AND actie=? AND parameters=? "
            "AND status IN ('open','goedgekeurd','geweigerd')", (naam, v.get("runbook", ""), v["actie"], pjson)).fetchone()
        # Eén open voorstel per agent, runbook en deal (of sleutel): een nieuw voorstel
        # (bv. een ander nummer) vervangt het vorige, anders blijven er twee
        # tegenstrijdige voorstellen open staan (deal 14531: 2616 en 5609).
        deal = None
        if isinstance(params, dict):
            deal = params.get("deal_id") if params.get("deal_id") is not None else params.get("sleutel")
        if deal is not None and v.get("runbook") and not zelfde:
            for r in conn.execute("SELECT id, parameters FROM voorstel WHERE naam=? AND runbook=? AND status='open'",
                                  (naam, v["runbook"])).fetchall():
                try:
                    oud_p = json.loads(r["parameters"] or "{}")
                    oud_deal = oud_p.get("deal_id") if oud_p.get("deal_id") is not None else oud_p.get("sleutel")
                except Exception:
                    oud_deal = None
                if str(oud_deal) == str(deal):
                    conn.execute("UPDATE voorstel SET status='vervallen', besluit_door='systeem', besluit_ts=?, "
                                 "bewijs=? WHERE id=?", (nu(), f"vervangen door een nieuw voorstel: {v['actie']}", r["id"]))
        if not zelfde:
            conn.execute(
                "INSERT INTO voorstel(naam,actie,doel,reden,parameters,runbook,ts) "
                "VALUES(?,?,?,?,?,?,?)",
                (naam, v["actie"], v.get("doel", ""), v.get("reden", ""), pjson, v.get("runbook", ""), nu()),
            )
    conn.commit()
    return jsonify(ok=True)


# --- registratie: de generator registreert of werkt een agent bij. Token-gated.
@app.route("/api/agent", methods=["POST"])
def api_agent():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    naam = (p.get("naam") or "").strip()
    if not naam or not p.get("label"):
        return jsonify(fout="naam en label vereist"), 400
    conn = db()
    conn.execute(
        "INSERT INTO agent(naam,label,type,rol,mandaat,mag,grenzen,cadans,tools,"
        "eigenaar,actief,aangemaakt,levert_aan,draait_op) VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?,?) "
        "ON CONFLICT(naam) DO UPDATE SET label=excluded.label, type=excluded.type, "
        "rol=excluded.rol, mandaat=excluded.mandaat, mag=excluded.mag, "
        "grenzen=excluded.grenzen, cadans=excluded.cadans, tools=excluded.tools, "
        "eigenaar=excluded.eigenaar, actief=1, levert_aan=excluded.levert_aan, draait_op=excluded.draait_op",
        (naam, p["label"], p.get("type", ""), p.get("rol", ""), p.get("mandaat", ""),
         json.dumps(p.get("mag", [])), json.dumps(p.get("grenzen", [])),
         p.get("cadans", ""), json.dumps(p.get("tools", [])),
         p.get("eigenaar", "mehdi"), nu(), json.dumps(p.get("levert_aan", [])), p.get("draait_op", "VM")),
    )
    if "prive" in p:
        conn.execute("UPDATE agent SET prive=? WHERE naam=?", (1 if p.get("prive") else 0, naam))
    conn.commit()
    return jsonify(ok=True, naam=naam)


@app.route("/api/agents")
def api_agents():
    rijen = db().execute("SELECT naam,label,type,rol,cadans,eigenaar,actief FROM agent").fetchall()
    return jsonify([dict(r) for r in rijen])


# --- beslissen over een voorstel (alleen beheer) ---------------------------
@app.route("/voorstel/<int:vid>/besluit", methods=["POST"])
def besluit(vid):
    if not mag_beslissen():
        abort(403)
    keuze = request.form.get("keuze")
    if keuze not in ("goedgekeurd", "geweigerd"):
        abort(400)
    db().execute(
        "UPDATE voorstel SET status=?, besluit_door=?, besluit_ts=? WHERE id=? AND status='open'",
        (keuze, gebruiker(), nu(), vid),
    )
    db().commit()
    return redirect(request.referrer or url_for("bord"))


# --- uitvoerder: haalt goedgekeurde voorstellen MET parameters op en meldt de
#     uitkomst terug. Token-gated. Uitvoeren gebeurt nooit hier maar in
#     mijnagents-runner/mijnagents_uitvoerder.py (allowlist van runbooks). ---
@app.route("/api/uitvoer-wacht")
def uitvoer_wacht():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    rijen = db().execute(
        "SELECT id, naam, actie, runbook, parameters FROM voorstel "
        "WHERE status='goedgekeurd' AND parameters<>'' ORDER BY id"
    ).fetchall()
    return jsonify(wacht=[dict(r) for r in rijen])


@app.route("/uitvoer-resultaat", methods=["POST"])
def uitvoer_resultaat():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    vid = p.get("id")
    uitvoering = p.get("uitvoering")
    nieuw = {"gelukt": "uitgevoerd", "mislukt": "mislukt", "overgeslagen": "overgeslagen"}.get(uitvoering)
    if not vid or not nieuw:
        return jsonify(fout="id en uitvoering (gelukt|mislukt|overgeslagen) vereist"), 400
    conn = db()
    v = conn.execute("SELECT naam, actie FROM voorstel WHERE id=? AND status='goedgekeurd'", (vid,)).fetchone()
    if not v:
        return jsonify(fout="geen goedgekeurd voorstel met dit id"), 404
    bewijs = (p.get("detail", "") or "")[:400]
    if p.get("bewijs"):
        bewijs += "\n" + str(p["bewijs"])[:4000]
    conn.execute("UPDATE voorstel SET status=?, bewijs=? WHERE id=?", (nieuw, bewijs, vid))
    conn.execute("INSERT INTO handeling(naam, wat, ts) VALUES(?,?,?)",
                 (v["naam"], f"voorstel {vid} '{v['actie']}': {nieuw}", nu()))
    conn.commit()
    return jsonify(ok=True, status=nieuw)


# --- gesprek: beheer zegt iets tegen een agent (of tegen de hoofdagent);
#     de hoofdagent-runner haalt open berichten op en antwoordt op het bord.
def gesprekken_voor(aan, limiet=30):
    return db().execute(
        "SELECT * FROM gesprek WHERE aan=? ORDER BY id DESC LIMIT ?", (aan, limiet)
    ).fetchall()


@app.route("/gesprek", methods=["POST"])
def gesprek_sturen():
    if not mag_beslissen():
        abort(403)
    aan = (request.form.get("aan") or "regisseur").strip()
    tekst = (request.form.get("tekst") or "").strip()
    if not tekst:
        abort(400)
    if aan != "regisseur" and not db().execute("SELECT 1 FROM agent WHERE naam=?", (aan,)).fetchone():
        abort(404)
    db().execute("INSERT INTO gesprek(aan, van, tekst, ts) VALUES(?,?,?,?)", (aan, gebruiker(), tekst[:8000], nu()))
    db().commit()
    doel = url_for("bord") if aan == "regisseur" else url_for("detail", naam=aan)
    return redirect(doel + "#gesprek")


@app.route("/api/gesprek", methods=["POST"])
def api_gesprek_sturen():
    """Voor De Bode: een bericht van Mehdi uit Telegram als gesprek op het bord."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    aan = (p.get("aan") or "regisseur").strip()
    tekst = (p.get("tekst") or "").strip()
    if not tekst:
        return jsonify(fout="tekst vereist"), 400
    conn = db()
    if aan != "regisseur" and not conn.execute("SELECT 1 FROM agent WHERE naam=?", (aan,)).fetchone():
        aan = "regisseur"
    cur = conn.execute("INSERT INTO gesprek(aan, van, tekst, ts) VALUES(?,?,?,?)", (aan, (p.get("van") or "mehdi (telegram)")[:60], tekst[:8000], nu()))
    conn.commit()
    return jsonify(ok=True, id=cur.lastrowid, aan=aan)


@app.route("/api/gesprek/open")
def api_gesprek_open():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    rijen = db().execute("SELECT id, aan, van, tekst, ts FROM gesprek WHERE status='open' ORDER BY id").fetchall()
    return jsonify(open=[dict(r) for r in rijen])


@app.route("/api/gesprek/<int:gid>/status", methods=["POST"])
def api_gesprek_status(gid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    status = p.get("status")
    if status not in ("bezig", "beantwoord", "mislukt"):
        return jsonify(fout="status bezig|beantwoord|mislukt"), 400
    conn = db()
    conn.execute(
        "UPDATE gesprek SET status=?, antwoord=COALESCE(?, antwoord), detail=COALESCE(?, detail), "
        "beantwoord_ts=CASE WHEN ? IN ('beantwoord','mislukt') THEN ? ELSE beantwoord_ts END WHERE id=?",
        (status, p.get("antwoord"), p.get("detail"), status, nu(), gid),
    )
    conn.commit()
    return jsonify(ok=True)


@app.route("/api/gesprek/<int:gid>")
def api_gesprek(gid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    r = db().execute("SELECT * FROM gesprek WHERE id=?", (gid,)).fetchone()
    if not r:
        abort(404)
    # eerdere wisselingen in dezelfde draad (zelfde 'aan'), voor context
    eerder = db().execute(
        "SELECT van, tekst, antwoord, ts FROM gesprek WHERE aan=? AND id<? AND status='beantwoord' "
        "ORDER BY id DESC LIMIT 6", (r["aan"], gid)
    ).fetchall()
    return jsonify(gesprek=dict(r), eerder=[dict(x) for x in eerder][::-1])


# --- overzicht voor de hoofdagent: alle agents met werkwijze, status en recent verslag
@app.route("/api/overzicht")
def api_overzicht():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    agents = [dict(r) for r in conn.execute("SELECT naam,label,type,rol,mandaat,mag,grenzen,cadans,tools,werkwijze,kennis_ts,kennis_bron FROM agent WHERE actief=1").fetchall()]
    status = {r["naam"]: dict(r) for r in conn.execute("SELECT * FROM status").fetchall()}
    for a in agents:
        a["status"] = status.get(a["naam"])
        a["open_voorstellen"] = conn.execute("SELECT COUNT(*) c FROM voorstel WHERE naam=? AND status='open'", (a["naam"],)).fetchone()["c"]
    return jsonify(agents=agents)


@app.route("/api/logboek/<naam>")
def api_logboek_lezen(naam):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    n = min(int(request.args.get("n", 60)), 300)
    onderwerp = request.args.get("onderwerp")
    if onderwerp:
        rijen = db().execute("SELECT onderwerp, stap, tekst, detail, ts FROM logboek WHERE naam=? AND onderwerp LIKE ? ORDER BY id DESC LIMIT ?", (naam, f"%{onderwerp}%", n)).fetchall()
    else:
        rijen = db().execute("SELECT onderwerp, stap, tekst, detail, ts FROM logboek WHERE naam=? ORDER BY id DESC LIMIT ?", (naam, n)).fetchall()
    return jsonify(regels=[dict(r) for r in rijen][::-1])


@app.route("/gezondheid")
def gezondheid():
    n = db().execute("SELECT COUNT(*) c FROM agent WHERE actief=1").fetchone()["c"]
    return jsonify(ok=True, agents=n, app=APP_NAAM)


init_db()

# --- werfverslagen: de pagina's van Werfverslag voorbereider en Werfverslag schrijver, in de logica
#     van het contractsysteem: per dossier en per bezoek een rij met Openen · Keuzes · Bijlagen ·
#     Proef · Herkomst · Controle. Alleen beheer (dossiernummers en adressen zijn inhoud).
WERF_KOLOMMEN = ("gegevens", "verslag_md", "proef_pad", "proef_ts", "keuzes", "bijlagen", "proef_info")
WERF_JSON = {"gegevens": {}, "keuzes": {}, "bijlagen": [], "proef_info": {}, "bronnen": {}, "controles": [], "taken": []}


def _werfbezoek_tabel(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS werfbezoek (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier   TEXT NOT NULL,
            datum     TEXT NOT NULL,
            volgnr    INTEGER DEFAULT 0,
            adres     TEXT DEFAULT '',
            soort_project TEXT DEFAULT '',
            projectmap TEXT DEFAULT '',
            bezoekmap TEXT DEFAULT '',
            bronnen   TEXT DEFAULT '{}',   -- json: fotos, opnames, transcripten, verslagen, notities
            controles TEXT DEFAULT '[]',   -- json: [{code, naam, stand, toelichting}]
            taken     TEXT DEFAULT '[]',   -- json: [{voor, titel, uniek}]
            stand     TEXT DEFAULT '',
            open      INTEGER DEFAULT 1,
            ts        TEXT NOT NULL,
            UNIQUE(dossier, bezoekmap, datum)
        )""")
    bestaand = {r[1] for r in conn.execute("PRAGMA table_info(werfbezoek)").fetchall()}
    for k in WERF_KOLOMMEN:
        if k not in bestaand:
            conn.execute(f"ALTER TABLE werfbezoek ADD COLUMN {k} TEXT DEFAULT ''")


def _json(v, leeg):
    try:
        return json.loads(v) if v else leeg
    except ValueError:
        return leeg


# Een rij die na de verhuis van haar projectmap vervangen is door de rij op het nieuwe pad. Ze blijft staan
# (niets wissen zonder Mehdi's ja) tot hij het opruimvoorstel van Werfverslag voorbereider goedkeurt.
WERF_DUBBEL = "dubbel na verhuis; opruiming wacht op Mehdi"
WERF_GEWIST = os.path.join(os.path.dirname(DB_PAD), "werfbezoek_gewist.jsonl")


def _werf_leeg(v):
    return (v or "").strip() in ("", "{}", "[]", "null")


def _pad_vervang(v, oud, nieuw):
    # hoofdletterongevoelig, zoals Dropbox zelf: bij 2145 stond de fasemap als 'waiting to start' op de rij en
    # als 'Waiting to start' in de bijlagen, en een gewone replace liet de bijlagen op het oude pad staan
    if isinstance(v, str):
        return re.sub(re.escape(oud), lambda _: nieuw, v, flags=re.IGNORECASE)
    if isinstance(v, list):
        return [_pad_vervang(x, oud, nieuw) for x in v]
    if isinstance(v, dict):
        return {k: _pad_vervang(x, oud, nieuw) for k, x in v.items()}
    return v


def _werf_verhuisd(kolom, tekst, oud, nieuw):
    """Een kolom met het oude pad erin (bijlagen, proef_pad, gegevens) naar het nieuwe pad."""
    if kolom in WERF_JSON:
        try:
            return json.dumps(_pad_vervang(json.loads(tekst), oud, nieuw), ensure_ascii=False)
        except ValueError:
            pass
    return _pad_vervang(tekst or "", oud, nieuw)


def _werf_rel(r):
    """Het pad van de bezoekmap binnen de projectmap, in kleine letters: gelijk voor en na een verhuis van fasemap."""
    pm, bm = r["projectmap"] or "", r["bezoekmap"] or ""
    return bm[len(pm):].lower() if pm and bm.lower().startswith(pm.lower() + "/") else None


def _werf_herkoppel(conn, dossier, datum, bezoekmap, projectmap, vorige):
    """De projectmap verhuisde van fasemap (zelfde dossier, zelfde bezoekmapnaam, ander fasepad). De rij van het
    oude pad gaat mee naar het nieuwe, met gegevens, keuzes, bijlagen en proef, in plaats van een nieuwe rij.
    Bestaat er op het nieuwe pad al een rij (2145 op 24-09-2026: 19-23 en 145-149), dan vult de oude rij alleen de
    lege kolommen van die rij aan en krijgt ze de stand WERF_DUBBEL; wissen doet pas het runbook na Mehdi's ja."""
    oud = conn.execute("SELECT * FROM werfbezoek WHERE dossier=? AND bezoekmap=? AND datum=?", (dossier, vorige, datum)).fetchone()
    if not oud:
        return None
    oud_pm = oud["projectmap"] or ""
    if oud_pm and projectmap and vorige.lower().startswith(oud_pm.lower() + "/") and bezoekmap.startswith(projectmap + "/"):
        van, naar = oud_pm, projectmap
    else:
        van, naar = vorige, bezoekmap
    data = {k: _werf_verhuisd(k, oud[k], van, naar) for k in WERF_KOLOMMEN if not _werf_leeg(oud[k])}
    nieuw = conn.execute("SELECT * FROM werfbezoek WHERE dossier=? AND bezoekmap=? AND datum=?", (dossier, bezoekmap, datum)).fetchone()
    if not nieuw:
        velden = {"bezoekmap": bezoekmap, "projectmap": projectmap or oud_pm, **data}
        conn.execute(f"UPDATE werfbezoek SET {', '.join(f'{k}=?' for k in velden)} WHERE id=?", (*velden.values(), oud["id"]))
        return {"wat": "herkoppeld", "id": oud["id"], "van": vorige}
    # ook wat al op de blijvende rij stond, wijst voortaan naar het nieuwe pad (het oude bestaat niet meer)
    huidig = {k: _werf_verhuisd(k, nieuw[k], van, naar) for k in WERF_KOLOMMEN if not _werf_leeg(nieuw[k])}
    aangevuld = [k for k in data if k not in huidig]
    zet = {**{k: v for k, v in huidig.items() if v != nieuw[k]}, **{k: data[k] for k in aangevuld}}
    if zet:
        conn.execute(f"UPDATE werfbezoek SET {', '.join(f'{k}=?' for k in zet)} WHERE id=?", (*zet.values(), nieuw["id"]))
    conn.execute("UPDATE werfbezoek SET stand=? WHERE id=?", (WERF_DUBBEL, oud["id"]))
    return {"wat": "aangevuld", "id": nieuw["id"], "dubbel": oud["id"], "kolommen": aangevuld,
            "omgezet": [k for k in zet if k not in aangevuld],
            "botsing": [k for k in data if k in huidig and huidig[k] != data[k]]}


@app.route("/api/werfbezoek", methods=["POST"])
def api_werfbezoek():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _werfbezoek_tabel(conn)
    n, herkoppeld = 0, []
    for r in p.get("rijen") or []:
        if not (r.get("dossier") and r.get("datum")):
            continue
        sleutel = (str(r["dossier"])[:10], (r.get("bezoekmap") or "")[:500], r["datum"][:10])
        alleen = r.get("_alleen")
        if not alleen:
            for vorige in r.get("vorige_bezoekmappen") or []:
                vorige = str(vorige)[:500]
                if vorige and vorige != sleutel[1]:
                    uit = _werf_herkoppel(conn, sleutel[0], sleutel[2], sleutel[1], (r.get("projectmap") or "")[:500], vorige)
                    if uit:
                        herkoppeld.append(uit)
        if alleen:
            # gerichte bijwerking (voorbereiding, proef, keuzes): alleen die kolommen, de verificatie blijft staan
            velden = {k: r.get(k) for k in alleen if k in WERF_KOLOMMEN}
            for k, v in velden.items():
                velden[k] = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            velden["ts"] = nu()
            zet = ", ".join(f"{k}=?" for k in velden)
            cur = conn.execute(f"UPDATE werfbezoek SET {zet} WHERE dossier=? AND bezoekmap=? AND datum=?",
                               (*velden.values(), *sleutel))
            n += cur.rowcount
            continue
        conn.execute(
            "INSERT INTO werfbezoek(dossier,datum,volgnr,adres,soort_project,projectmap,bezoekmap,bronnen,controles,taken,stand,ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(dossier,bezoekmap,datum) DO UPDATE SET volgnr=excluded.volgnr, "
            "adres=excluded.adres, soort_project=excluded.soort_project, projectmap=excluded.projectmap, bronnen=excluded.bronnen, "
            "controles=excluded.controles, taken=excluded.taken, stand=excluded.stand, ts=excluded.ts",
            (sleutel[0], sleutel[2], int(r.get("volgnr") or 0), (r.get("adres") or "")[:200],
             (r.get("soort_project") or "")[:20], (r.get("projectmap") or "")[:500], sleutel[1],
             json.dumps(r.get("bronnen") or {}, ensure_ascii=False), json.dumps(r.get("controles") or [], ensure_ascii=False),
             json.dumps(r.get("taken") or [], ensure_ascii=False), (r.get("stand") or "")[:80], nu()))
        n += 1
    conn.commit()
    return jsonify(ok=True, rijen=n, herkoppeld=herkoppeld)


@app.route("/api/werfbezoek/opruimen", methods=["POST"])
def api_werfbezoek_opruimen():
    """Alleen via het runbook werfbezoek-dubbels, na Mehdi's ja op het bord. Wist een oude rij pas als ze echt een
    dubbel is van de rij die blijft (zelfde dossier, datum en bezoekmap binnen de projectmap, andere fasemap) en als
    alles wat ze droeg ook op die rij staat. Elke gewiste rij komt eerst volledig in werfbezoek_gewist.jsonl."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _werfbezoek_tabel(conn)
    gewist, overgeslagen = [], []
    for paar in p.get("paren") or []:
        try:
            oud_id, blijft_id = int(paar[0]), int(paar[1])
        except (TypeError, ValueError, IndexError):
            overgeslagen.append({"paar": paar, "reden": "geen paar van twee rij-id's"})
            continue
        oud = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (oud_id,)).fetchone()
        blijft = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (blijft_id,)).fetchone()
        reden = ""
        if not oud or not blijft:
            reden = "rij bestaat niet (meer)"
        elif oud_id == blijft_id:
            reden = "dezelfde rij"
        elif (oud["dossier"], oud["datum"]) != (blijft["dossier"], blijft["datum"]):
            reden = "ander dossier of andere datum"
        elif _werf_rel(oud) is None or _werf_rel(oud) != _werf_rel(blijft):
            reden = "geen verhuisde bezoekmap (ander pad binnen de projectmap)"
        else:
            kwijt = [k for k in WERF_KOLOMMEN if not _werf_leeg(oud[k]) and _werf_leeg(blijft[k])]
            if kwijt:
                reden = f"de rij die blijft mist nog {', '.join(kwijt)}"
        if reden:
            overgeslagen.append({"id": oud_id, "blijft": blijft_id, "reden": reden})
            continue
        with open(WERF_GEWIST, "a") as f:
            f.write(json.dumps({"gewist_ts": nu(), "blijft": blijft_id, "rij": dict(oud)}, ensure_ascii=False) + "\n")
        conn.execute("DELETE FROM werfbezoek WHERE id=?", (oud_id,))
        gewist.append(oud_id)
    conn.commit()
    return jsonify(ok=True, gewist=gewist, overgeslagen=overgeslagen)


def _werf_dict(r):
    d = dict(r)
    for k, leeg in WERF_JSON.items():
        d[k] = _json(d.get(k), leeg)
    return d


@app.route("/api/werfbezoek")
def api_werfbezoek_lezen():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    if request.args.get("dossier"):
        q, a = "SELECT * FROM werfbezoek WHERE dossier=?", [request.args["dossier"]]
        if request.args.get("volgnr"):
            q += " AND volgnr=?"; a.append(int(request.args["volgnr"]))
        # bij hetzelfde volgnummer eerst de levende rij, nooit de dubbel van een verhuisde projectmap:
        # de schrijver neemt rijen[0] en las anders een bezoekmap die niet meer bestaat
        q += " ORDER BY volgnr, (stand=?), id DESC"; a.append(WERF_DUBBEL)
        return jsonify(rijen=[_werf_dict(r) for r in conn.execute(q, a).fetchall()])
    q = "SELECT dossier, MAX(ts) AS ts, COUNT(*) AS bezoeken FROM werfbezoek"
    if request.args.get("open"):
        q += " WHERE open=1"
    q += " GROUP BY dossier ORDER BY dossier"
    return jsonify(dossiers=[dict(r) for r in conn.execute(q).fetchall()])


def _taak_status(conn):
    return {r["uniek"]: dict(r) for r in conn.execute(
        "SELECT uniek, status, opgepakt_door, opgepakt_ts, voor FROM klaarzet WHERE soort IN ('taak','opdracht') AND van='werfverslag-voorbereider'").fetchall()}


# Vertaling van de standen van de agent naar de tekens van de dossiercontrole (contractsysteem).
WERF_STAND = {"ok": "ok", "ontbreekt": "fout", "onbekend": "onbekend", "nvt": "onbekend"}
WERF_ACTIE = {
    "W1": "Agendawacht: afspraak van die dag zoeken en klaarzetten",
    "W4": "iCloud-wacht: foto's van die dag binnen 300 m klaarzetten; of foto's van de klant in de bezoekmap zetten",
    "W5": "Plaudwacht: opname van die dag koppelen; geen opname = verslag uit geheugen (E8)",
    "W6": "Plaudwacht: transcript maken of ophalen",
    "W7": "Keuzes bewaren en Proef maken; Werfverslag schrijver schrijft het concept",
    "W9": "Mailwacht: verzending aan de klant terugvinden",
    "W11": "Werfverslag schrijver bereidt voor (opdracht staat klaar), daarna Keuzes en Proef",
}


def _werf_rij(d, taak_status):
    for t in d["taken"]:
        s = taak_status.get(t.get("uniek"))
        t["status"] = (s["status"] if s else "niet klaargezet")
        t["door"] = (s["opgepakt_door"] if s else "")
    d["controle_rijen"] = []
    for c in d["controles"]:
        st = WERF_STAND.get(c["stand"], "onbekend")
        d["controle_rijen"].append({"nummer": c["code"], "titel": c["naam"], "status": st, "bevinding": c["toelichting"],
                                    "actie": WERF_ACTIE.get(c["code"], "") if st != "ok" else ""})
    d["telling"] = {k: sum(1 for c in d["controle_rijen"] if c["status"] == k) for k in ("ok", "let_op", "fout", "onbekend")}
    g = d["gegevens"] or {}
    for x in g.get("gegevens", []):
        x["status"] = {"zeker": "ok", "na te kijken": "let_op", "ontbreekt": "fout"}.get(x.get("zekerheid"), "onbekend")
    d["voorbereid"] = bool(g.get("gegevens"))
    d["heeft_proef"] = bool(d.get("proef_pad"))
    d["heeft_keuzes"] = bool(d["keuzes"])
    # wat nog nodig is, in de woorden van het contractdashboard
    nodig = []
    if not d["voorbereid"]:
        nodig.append("voorbereiding door de schrijver")
    elif not d["heeft_keuzes"]:
        nodig.append("keuzes van Mehdi")
    if not d["heeft_proef"]:
        nodig.append("proef")
    else:
        op = (d["proef_info"] or {}).get("open") or {}
        if isinstance(op, dict) and any(op.values()):
            nodig.append(f"nakijken: {op.get('in_te_vullen', 0)} in te vullen, {op.get('na_te_kijken', 0)} na te kijken")
    for c in d["controle_rijen"]:
        if c["status"] == "fout" and c["nummer"] in ("W4", "W5", "W6"):
            nodig.append(c["titel"])
    d["nodig"] = nodig
    if d["heeft_proef"]:
        d["fase"] = "proef klaar, nakijken"
    elif d["voorbereid"]:
        d["fase"] = "te controleren"
    else:
        d["fase"] = "te vervolledigen"
    return d


@app.route("/werfverslagen")
def werfverslagen_pagina():
    if not mag_beslissen():
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    taak_status = _taak_status(conn)
    rijen = [_werf_rij(_werf_dict(r), taak_status) for r in conn.execute("SELECT * FROM werfbezoek WHERE open=1 ORDER BY dossier, datum, volgnr").fetchall()]
    dossiers = {}
    for d in rijen:
        ds = dossiers.setdefault(d["dossier"], {"dossier": d["dossier"], "adres": d["adres"], "soort": d["soort_project"],
                                                "projectmap": d["projectmap"], "bezoeken": [], "dubbels": []})
        # een dubbel na verhuis telt niet als bezoek; hij staat apart tot Mehdi de opruiming goedkeurt
        ds["dubbels" if d["stand"] == WERF_DUBBEL else "bezoeken"].append(d)
    for ds in dossiers.values():
        if ds["bezoeken"]:
            ds["projectmap"] = ds["bezoeken"][-1]["projectmap"]
    noden = [dict(r) for r in conn.execute("SELECT naam, tekst, wie, ts FROM nood WHERE naam IN ('werfverslag-voorbereider','werfverslag-schrijver') AND open=1 ORDER BY id").fetchall()]
    st = {r["naam"]: dict(r) for r in conn.execute("SELECT * FROM status WHERE naam IN ('werfverslag-voorbereider','werfverslag-schrijver')").fetchall()}
    return render_template("werfverslagen.html", app_naam=APP_NAAM, dossiers=list(dossiers.values()), noden=noden, status=st,
                           gebruiker=gebruiker())


@app.route("/werfverslag/<dossier>/<int:volgnr>")
def werfbezoek_pagina(dossier, volgnr):
    if not mag_beslissen():
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    r = conn.execute("SELECT * FROM werfbezoek WHERE dossier=? AND volgnr=? ORDER BY (stand=?), id DESC LIMIT 1",
                     (dossier, volgnr, WERF_DUBBEL)).fetchone()
    if not r:
        abort(404)
    b = _werf_rij(_werf_dict(r), _taak_status(conn))
    open_opdr = [dict(x) for x in conn.execute(
        "SELECT id, titel, status, ts, van FROM klaarzet WHERE soort='opdracht' AND voor='werfverslag-schrijver' AND sleutel=? ORDER BY id DESC LIMIT 6",
        (f"{dossier}-{volgnr}",)).fetchall()]
    logboek = [dict(x) for x in conn.execute(
        "SELECT naam, stap, tekst, ts FROM logboek WHERE naam IN ('werfverslag-voorbereider','werfverslag-schrijver') AND onderwerp IN (?, ?) ORDER BY id DESC LIMIT 30",
        (f"{dossier}-{volgnr}", dossier)).fetchall()]
    return render_template("werfbezoek.html", app_naam=APP_NAAM, b=b, g=b["gegevens"], opdrachten=open_opdr, logboek=logboek,
                           verslag_html=md(b.get("verslag_md") or "") if b.get("verslag_md") else "", tab=request.args.get("tab", ""))


@app.route("/werfverslag/<dossier>/<int:volgnr>/keuzes", methods=["POST"])
def werfbezoek_keuzes(dossier, volgnr):
    """Keuzes van Mehdi (zoals Keuzes in het contractsysteem): verslagtype, taal, doorlopende punten,
    aanwezigen, opmerking voor de schrijver. Bewaard op de rij; de schrijver leest ze bij de proef."""
    if not mag_beslissen():
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    f = request.form
    aanwezigen = []
    for regel in (f.get("aanwezigen") or "").splitlines():
        delen = [x.strip() for x in regel.split("|")]
        if len(delen) >= 3 and any(delen):
            while len(delen) < 5:
                delen.append("")
            aanwezigen.append({"rol": delen[0], "firma": delen[1], "naam": delen[2], "contact": delen[3], "aanwezig": delen[4] or "ja"})
    keuzes = {"verslagtype": f.get("verslagtype", ""), "taal": f.get("taal", "nl"), "doorlopend": f.get("doorlopend", "ja"),
              "bronnen": f.get("bronnen", "eigen"), "overgang": f.get("overgang", "tweede rondgang"), "waarborg": (f.get("waarborg") or "12")[:3],
              "aanwezigen": aanwezigen, "opmerking": (f.get("opmerking") or "")[:2000], "door": gebruiker(), "ts": nu()}
    conn.execute("UPDATE werfbezoek SET keuzes=?, ts=? WHERE dossier=? AND volgnr=?", (json.dumps(keuzes, ensure_ascii=False), nu(), dossier, volgnr))
    conn.commit()
    return redirect(url_for("werfbezoek_pagina", dossier=dossier, volgnr=volgnr, tab="keuzes"))


@app.route("/werfverslag/<dossier>/<int:volgnr>/opdracht", methods=["POST"])
def werfbezoek_opdracht(dossier, volgnr):
    """Knop op de bezoekpagina: zet een opdracht klaar voor Werfverslag schrijver (voorbereid | proef).
    Hij voert ze uit in zijn opdrachtenronde (cron elke 5 min) en meldt bewijs in zijn werkverslag."""
    if not mag_beslissen():
        abort(403)
    soort = request.form.get("soort", "")
    if soort not in ("voorbereid", "proef"):
        abort(400)
    conn = db()
    conn.execute("INSERT INTO klaarzet(van, voor, soort, sleutel, titel, inhoud, verwijzing, uniek, ts) VALUES(?,?,?,?,?,?,?,?,?)",
                 (f"bord:{gebruiker()}", "werfverslag-schrijver", "opdracht", f"{dossier}-{volgnr}", f"{soort} {dossier} {volgnr}",
                  json.dumps({"door": gebruiker()}), "", "", nu()))
    conn.commit()
    return redirect(url_for("werfbezoek_pagina", dossier=dossier, volgnr=volgnr, tab="proef"))


# --- commandocentrum: één rij per bezoek ter plaatse dat een verslag vraagt (werfverslag, veiligheidscoördinatie,
#     plaatsbeschrijving, barsten en scheuren). Het Commandocentrum (agent) leest de agenda-bak, herkent de
#     verslagsoort, stuurt de impuls naar de verslagagent en laat de wachten het pakket vullen (foto's, opname,
#     transcript). De verslagagent meet het pakket en schrijft de proef na Mehdi's knop. Alleen beheer ziet de
#     pagina (klant- en dossiernamen zijn inhoud).
VERSLAG_KOLOMMEN = ("dossiermap", "bezoekmap", "pakket", "taken", "stand", "impuls_voorbereiding_ts", "impuls_verslag_ts",
                    "proef_pad", "proef_ts", "verslag_md", "proef_info", "opmerking", "open")
VERSLAG_JSON = {"pakket": {}, "taken": [], "proef_info": {}}
PAKKET_LABELS = (("agenda", "agenda"), ("dossiermap", "dossiermap"), ("bezoekmap", "bezoekmap"), ("fotos", "foto's"),
                 ("opnames", "opname"), ("transcripten", "transcript"), ("documenten", "documenten"))


def _verslagopdracht_tabel(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verslagopdracht (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            uniek     TEXT NOT NULL UNIQUE,   -- agenda:<kalender>:<event-id>, uit de bak van de Agendawacht
            verslagsoort TEXT NOT NULL,       -- sleutel in verslagsoorten.SOORTEN
            agent     TEXT NOT NULL,          -- verslagagent die hem draagt
            afdeling  TEXT DEFAULT '',
            dossier   TEXT DEFAULT '',        -- projectnummer als de titel er een had
            klant     TEXT DEFAULT '',
            adres     TEXT DEFAULT '',
            datum     TEXT NOT NULL,
            start     TEXT DEFAULT '',
            einde     TEXT DEFAULT '',
            titel     TEXT DEFAULT '',
            agenda    TEXT DEFAULT '',
            deal_id   TEXT DEFAULT '',
            dossiermap TEXT DEFAULT '',
            bezoekmap TEXT DEFAULT '',
            pakket    TEXT DEFAULT '{}',      -- json: agenda, dossiermap, bezoekmap, fotos, opnames, transcripten, documenten, gemeten_ts
            taken     TEXT DEFAULT '[]',      -- json: [{voor, uniek, titel}]
            stand     TEXT DEFAULT 'gepland', -- gepland | voorbereid | verzamelen | pakket klaar | proef gevraagd | proef klaar | gesloten
            impuls_voorbereiding_ts TEXT DEFAULT '',
            impuls_verslag_ts TEXT DEFAULT '',
            proef_pad TEXT DEFAULT '',
            proef_ts  TEXT DEFAULT '',
            verslag_md TEXT DEFAULT '',
            proef_info TEXT DEFAULT '{}',
            opmerking TEXT DEFAULT '',        -- van Mehdi, voor de verslagagent
            open      INTEGER DEFAULT 1,
            ts        TEXT NOT NULL
        )""")


def _verslag_dict(r):
    d = dict(r)
    for k, leeg in VERSLAG_JSON.items():
        d[k] = _json(d.get(k), leeg)
    return d


@app.route("/api/verslagopdracht", methods=["POST"])
def api_verslagopdracht():
    """Upsert op uniek. Met `_alleen` worden alleen die kolommen bijgewerkt (de verslagagent meldt pakket,
    dossiermap, bezoekmap, proef; het Commandocentrum meldt impulsen en stand) zonder elkaars werk te overschrijven."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _verslagopdracht_tabel(conn)
    n = 0
    for r in p.get("rijen") or []:
        if not r.get("uniek"):
            continue
        alleen = r.get("_alleen")
        if alleen:
            velden = {}
            for k in alleen:
                if k in VERSLAG_KOLOMMEN:
                    v = r.get(k)
                    velden[k] = v if isinstance(v, (str, int)) or v is None else json.dumps(v, ensure_ascii=False)
            if not velden:
                continue
            velden["ts"] = nu()
            zet = ", ".join(f"{k}=?" for k in velden)
            n += conn.execute(f"UPDATE verslagopdracht SET {zet} WHERE uniek=?", (*velden.values(), r["uniek"][:200])).rowcount
            continue
        if not (r.get("verslagsoort") and r.get("agent") and r.get("datum")):
            continue
        conn.execute(
            "INSERT INTO verslagopdracht(uniek, verslagsoort, agent, afdeling, dossier, klant, adres, datum, start, einde, titel, agenda, deal_id, ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uniek) DO UPDATE SET verslagsoort=excluded.verslagsoort, agent=excluded.agent, "
            "afdeling=excluded.afdeling, dossier=excluded.dossier, klant=excluded.klant, adres=excluded.adres, datum=excluded.datum, "
            "start=excluded.start, einde=excluded.einde, titel=excluded.titel, agenda=excluded.agenda, deal_id=excluded.deal_id, ts=excluded.ts",
            (r["uniek"][:200], r["verslagsoort"][:40], r["agent"][:60], (r.get("afdeling") or "")[:40], str(r.get("dossier") or "")[:20],
             (r.get("klant") or "")[:120], (r.get("adres") or "")[:200], r["datum"][:10], (r.get("start") or "")[:40],
             (r.get("einde") or "")[:40], (r.get("titel") or "")[:200], (r.get("agenda") or "")[:60], str(r.get("deal_id") or "")[:20], nu()))
        n += 1
    conn.commit()
    return jsonify(ok=True, rijen=n)


@app.route("/api/verslagopdracht")
def api_verslagopdracht_lezen():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _verslagopdracht_tabel(conn)
    q, a = "SELECT * FROM verslagopdracht WHERE 1=1", []
    if request.args.get("agent"):
        q += " AND agent=?"; a.append(request.args["agent"])
    if request.args.get("uniek"):
        q += " AND uniek=?"; a.append(request.args["uniek"])
    if request.args.get("id"):
        q += " AND id=?"; a.append(int(request.args["id"]))
    if request.args.get("open", "1") != "alle":
        q += " AND open=1"
    return jsonify(rijen=[_verslag_dict(r) for r in conn.execute(q + " ORDER BY datum, start", a).fetchall()])


def _verslag_rij(d, taak_status):
    """Wat de pagina toont: pakketlampjes (in de tekens van de dossiercontrole), taken met stand, wat nog nodig is."""
    pk = d["pakket"] or {}
    lampjes = []
    for sleutel, label in PAKKET_LABELS:
        v = pk.get(sleutel)
        if sleutel in ("agenda", "dossiermap", "bezoekmap"):
            st = "ok" if v else ("onbekend" if v is None else "fout")
            tekst = (d.get(sleutel) or "").rsplit("/", 1)[-1] if sleutel != "agenda" else ("gevonden" if v else "")
        else:
            st = "ok" if (v or 0) > 0 else ("onbekend" if v is None else "fout")
            tekst = str(v) if v is not None else "?"
        lampjes.append({"sleutel": sleutel, "label": label, "status": st, "tekst": tekst})
    d["lampjes"] = lampjes
    for t in d["taken"]:
        s = taak_status.get(t.get("uniek"))
        t["status"] = s["status"] if s else "niet klaargezet"
        t["door"] = s["opgepakt_door"] if s else ""
    nodig = []
    if not d.get("dossiermap"):
        nodig.append("dossiermap (agent zoekt; anders zet jij het pad)")
    elif not d.get("bezoekmap"):
        nodig.append("bezoekmap (agent maakt hem aan)")
    if d["stand"] not in ("gepland",) and d.get("bezoekmap"):
        if not pk.get("fotos"):
            nodig.append("foto's (iCloud-wacht)")
        if not pk.get("transcripten"):
            nodig.append("transcript (Plaudwacht)")
    if d["stand"] == "pakket klaar" and not d.get("proef_pad"):
        nodig.append("jouw knop: Proef maken")
    if d.get("proef_pad"):
        nodig = ["proef nakijken"] + ([] if not (d["proef_info"] or {}).get("open") else ["open punten in de proef"])
    d["nodig"] = nodig
    d["proef_naam"] = (d.get("proef_pad") or "").rsplit("/", 1)[-1]
    return d


@app.route("/commandocentrum")
def commandocentrum_pagina():
    if not mag_beslissen():
        abort(403)
    conn = db()
    _verslagopdracht_tabel(conn)
    taak_status = {r["uniek"]: dict(r) for r in conn.execute(
        "SELECT uniek, status, opgepakt_door FROM klaarzet WHERE van='commandocentrum' AND uniek<>''").fetchall()}
    rijen = [_verslag_rij(_verslag_dict(r), taak_status) for r in conn.execute(
        "SELECT * FROM verslagopdracht WHERE open=1 ORDER BY datum DESC, start DESC").fetchall()]
    vandaag = nu()[:10]
    werf = [r for r in rijen if r["verslagsoort"] == "werfverslag"]      # eigen keten: pagina Werfverslagen
    eigen = [r for r in rijen if r not in werf]
    komend = [r for r in eigen if r["datum"] >= vandaag and r["stand"] in ("gepland", "voorbereid")]
    lopend = [r for r in eigen if r not in komend and not r.get("proef_pad")]
    proef = [r for r in eigen if r.get("proef_pad")]
    agents_namen = ["commandocentrum", "werfverslag-voorbereider", "werfverslag-schrijver", "veiligheidscoordinatie-verslag",
                    "plaatsbeschrijving-verslag", "barsten-scheuren-verslag", "icloud-wacht", "plaud-wacht", "agenda-wacht"]
    st = {r["naam"]: dict(r) for r in conn.execute(
        f"SELECT * FROM status WHERE naam IN ({','.join('?' * len(agents_namen))})", agents_namen).fetchall()}
    labels = {r["naam"]: r["label"] for r in conn.execute("SELECT naam, label FROM agent").fetchall()}
    noden = [dict(r) for r in conn.execute(
        f"SELECT naam, tekst, wie, ts FROM nood WHERE open=1 AND naam IN ({','.join('?' * len(agents_namen))}) ORDER BY id", agents_namen).fetchall()]
    logboek = [dict(r) for r in conn.execute(
        "SELECT naam, onderwerp, stap, tekst, ts FROM logboek WHERE naam IN ('commandocentrum','veiligheidscoordinatie-verslag',"
        "'plaatsbeschrijving-verslag','barsten-scheuren-verslag') ORDER BY id DESC LIMIT 25").fetchall()]
    gesloten = conn.execute("SELECT COUNT(*) FROM verslagopdracht WHERE open=0").fetchone()[0]
    return render_template("commandocentrum.html", app_naam=APP_NAAM, komend=komend, lopend=lopend, proef=proef, werf=werf, status=st,
                           labels=labels, agents_namen=agents_namen, noden=noden, logboek=logboek, gesloten=gesloten, gebruiker=gebruiker())


@app.route("/commandocentrum/<int:vid>/opdracht", methods=["POST"])
def commandocentrum_opdracht(vid):
    """Knoppen op de pagina. `proef`: opdracht voor de verslagagent (kost tokens, dus alleen op de knop).
    `dossiermap`: Mehdi zet het pad zelf als de agent de map niet vond. `sluiten`: van de pagina."""
    if not mag_beslissen():
        abort(403)
    conn = db()
    _verslagopdracht_tabel(conn)
    r = conn.execute("SELECT * FROM verslagopdracht WHERE id=?", (vid,)).fetchone()
    if not r:
        abort(404)
    soort = request.form.get("soort", "")
    if soort == "proef":
        conn.execute("INSERT INTO klaarzet(van, voor, soort, sleutel, titel, inhoud, verwijzing, uniek, ts) VALUES(?,?,?,?,?,?,?,?,?)",
                     (f"bord:{gebruiker()}", r["agent"], "opdracht", str(vid), f"proef {vid}",
                      json.dumps({"door": gebruiker(), "uniek": r["uniek"], "opmerking": (request.form.get("opmerking") or "")[:2000]}),
                      r["bezoekmap"] or "", "", nu()))
        conn.execute("UPDATE verslagopdracht SET stand='proef gevraagd', opmerking=?, ts=? WHERE id=?",
                     ((request.form.get("opmerking") or "")[:2000], nu(), vid))
    elif soort == "dossiermap":
        pad = (request.form.get("dossiermap") or "").strip()[:500]
        conn.execute("UPDATE verslagopdracht SET dossiermap=?, bezoekmap='', impuls_voorbereiding_ts='', ts=? WHERE id=?", (pad, nu(), vid))
        # de agent maakt de bezoekmap bij zijn volgende impuls; het Commandocentrum zet die opnieuw klaar
        conn.execute("DELETE FROM klaarzet WHERE uniek=?", (f"cc:{r['uniek']}:voorbereiding",))
    elif soort == "sluiten":
        conn.execute("UPDATE verslagopdracht SET open=0, stand='gesloten', ts=? WHERE id=?", (nu(), vid))
    elif soort == "heropen":
        conn.execute("UPDATE verslagopdracht SET open=1, ts=? WHERE id=?", (nu(), vid))
    else:
        abort(400)
    conn.commit()
    return redirect(url_for("commandocentrum_pagina") + f"#v{vid}")


TESTFORMULIER = """<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Testformulier De Bode</title>
<style>body{font-family:system-ui,sans-serif;max-width:520px;margin:40px auto;padding:0 16px;color:#1d1d1f}
label{display:block;margin:14px 0 4px;font-weight:600}input{width:100%;padding:9px;border:1px solid #bbb;border-radius:6px;font-size:15px}
button{margin-top:20px;padding:10px 18px;border:0;border-radius:6px;background:#0b5cad;color:#fff;font-size:15px}
.info{background:#f2f2f5;padding:10px 12px;border-radius:6px;font-size:14px}#uit{margin-top:16px;font-weight:600}</style></head>
<body><h1>Klantgegevens bevestigen</h1>
<p class="info">Testformulier voor de bel-tool van De Bode. Er wordt niets verstuurd en niets bewaard, ook niet als je op Versturen klikt.</p>
<form onsubmit="event.preventDefault();document.getElementById('uit').textContent='Test: niets verstuurd, niets bewaard.';this.reset();">
<label for="naam">Volledige naam</label><input id="naam" name="naam" autocomplete="off">
<label for="mail">E-mailadres</label><input id="mail" name="mail" type="email" autocomplete="off">
<label for="pas">Paspoortnummer</label><input id="pas" name="pas" autocomplete="off">
<label for="iban">IBAN</label><input id="iban" name="iban" autocomplete="off">
<button type="submit">Versturen</button></form><div id="uit"></div></body></html>"""


@app.get("/test/formulier")
def testformulier():
    """Nepformulier om de bel-tool te testen (25-09-2026): vraagt om een paspoortnummer en een IBAN, waar
    Claude niet zelf mag invullen. Alles blijft in de browser: geen POST, geen opslag."""
    return TESTFORMULIER


# MCP voor Mehdi's Claude: "roep Mehdi" als een agent vastzit (mcp_bode.py, 25-09-2026).
import mcp_bode  # noqa: E402
mcp_bode.registreer(app, gebruiker, groepen, db, nu)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 3022)), debug=True)
