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
                             ("kennis_ts", "TEXT DEFAULT ''"), ("kennis_bron", "TEXT DEFAULT ''")):
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
    ruw = request.headers.get("X-authentik-groups", "")
    return {x.strip() for x in ruw.split(",") if x.strip()}


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


def kaarten():
    conn = db()
    rijen = conn.execute("SELECT * FROM agent WHERE actief=1 ORDER BY type, label").fetchall()
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    open_per = {}
    for r in conn.execute(
        "SELECT naam, COUNT(*) n FROM voorstel WHERE status='open' GROUP BY naam"
    ).fetchall():
        open_per[r["naam"]] = r["n"]

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
            }
        )
    return uit


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
    a = db().execute("SELECT * FROM agent WHERE naam=?", (naam,)).fetchone()
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
    # Optioneel voorstel meegestuurd (mens-in-de-lus).
    v = p.get("voorstel")
    if isinstance(v, dict) and v.get("actie"):
        params = v.get("parameters")
        conn.execute(
            "INSERT INTO voorstel(naam,actie,doel,reden,parameters,runbook,ts) "
            "VALUES(?,?,?,?,?,?,?)",
            (naam, v["actie"], v.get("doel", ""), v.get("reden", ""),
             json.dumps(params) if params else "", v.get("runbook", ""), nu()),
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
        "eigenaar,actief,aangemaakt) VALUES(?,?,?,?,?,?,?,?,?,?,1,?) "
        "ON CONFLICT(naam) DO UPDATE SET label=excluded.label, type=excluded.type, "
        "rol=excluded.rol, mandaat=excluded.mandaat, mag=excluded.mag, "
        "grenzen=excluded.grenzen, cadans=excluded.cadans, tools=excluded.tools, "
        "eigenaar=excluded.eigenaar, actief=1",
        (naam, p["label"], p.get("type", ""), p.get("rol", ""), p.get("mandaat", ""),
         json.dumps(p.get("mag", [])), json.dumps(p.get("grenzen", [])),
         p.get("cadans", ""), json.dumps(p.get("tools", [])),
         p.get("eigenaar", "mehdi"), nu()),
    )
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

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 3022)), debug=True)
