"""Agents: het besturingscentrum van het Globaal-agentplatform.

Toont het agent-team in een oogopslag: elk lid als kaart met een status. Een
gewired-en-levende agent staat op "waakt" (op wacht) of "actief" (bezig); valt
hij stil dan wordt dat "stil" (geen recente hartslag). Een nog niet gekoppelde
rol staat op "niet gekoppeld". Bewust zelfstandig gehouden: een eigen kleine
SQLite in het datavolume, geen database-credential nodig. Agents melden hun
status via de token-route /agent-status (nginx laat die ene route langs de
SSO); de rest van de app zit achter Authentik forward-auth.

Voorstellen (mens-in-de-lus): een agent kan bij een probleem een benoemde
runbook VOORSTELLEN. De gebruiker keurt goed of weigert op de tegel. Een
goedgekeurd voorstel wordt NIET hier uitgevoerd: een aparte host-uitvoerder
(runner/uitvoerder.py) pikt goedgekeurde voorstellen op, valideert ze tegen een
korte allowlist en voert alleen dan de veilige actie uit, met verificatie
achteraf. Deze app legt alleen de beslissing en de uitkomst vast.
"""
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, abort

app = Flask(__name__)

DB = os.environ.get("AGENTS_DB", "/data/agents.db")
TOKEN = os.environ.get("AGENTS_TOKEN", "").strip()
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")

STATUSSEN = ("rust", "waakt", "actief", "klaar", "fout")

TEAM = [
    {"naam": "onderhoud", "label": "Onderhoudsagent", "type": "onderhoud",
     "rol": "waakt over de VM en de apps"},
    {"naam": "architect", "label": "Architect", "type": "bouw",
     "rol": "ontwerpt de aanpak"},
    {"naam": "bouwer", "label": "Bouwer", "type": "bouw",
     "rol": "schrijft de code"},
    {"naam": "reviewer", "label": "Reviewer", "type": "bouw",
     "rol": "beoordeelt het werk"},
    {"naam": "verifier", "label": "Verifier", "type": "bouw",
     "rol": "test en verifieert"},
]
LABELS = {a["naam"]: a["label"] for a in TEAM}

# Mandaat per agent: wat hij doet, wat hij mag, en zijn grenzen. Voor de
# detailweergave als je op een kaart klikt.
DETAILS = {
    "onderhoud": {
        "mandaat": ("Waakt over de VM en de AppPortal-apps. Meet elk uur, "
                    "oordeelt over de gezondheid, en herstelt binnen een "
                    "veilige grens."),
        "mag": ["Een container herstarten die down of unhealthy is"],
        "grenzen": [
            "Nooit de kern: postgres, authentik of nginx",
            "Alleen als de container echt stuk is (niet als hij gezond is)",
            "Maximaal 3 herstarts per container per dag, daarna escaleren",
            "Verifieert achteraf; lukt het niet, dan naar een mens",
        ],
        "cadans": "Sonde elk uur; duiding dagelijks en direct bij een storing.",
    },
}
DETAIL_STANDAARD = {
    "mandaat": ("Onderdeel van het bouw-team (fase 1). Nog niet aan deze tegel "
                "gekoppeld; verschijnt hier zodra hij meldt."),
    "mag": [],
    "grenzen": [],
    "cadans": "Op afroep.",
}


def _nu():
    return datetime.now(timezone.utc)


def _fmt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d-%m %H:%M")
    except Exception:
        return ""


def _kolom(conn, tabel, kolom, definitie):
    """Voegt een kolom toe als die nog niet bestaat (SQLite-migratie)."""
    try:
        conn.execute(f"ALTER TABLE {tabel} ADD COLUMN {kolom} {definitie}")
    except sqlite3.OperationalError:
        pass


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS status (
        naam   TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        taak   TEXT DEFAULT '',
        detail TEXT DEFAULT '',
        tokens INTEGER,
        ts     TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS voorstel (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        naam         TEXT NOT NULL,
        actie        TEXT NOT NULL,
        reden        TEXT DEFAULT '',
        aangemaakt   TEXT NOT NULL,
        besluit      TEXT NOT NULL DEFAULT 'open',
        besluit_door TEXT DEFAULT '',
        besluit_ts   TEXT DEFAULT '')""")
    # Migraties voor de uitvoer-lus.
    _kolom(conn, "voorstel", "runbook", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "doel", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "uitvoering", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "uitvoer_detail", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "uitvoer_ts", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "bewijs", "TEXT DEFAULT ''")
    # Handelingen herleid uit de systemd-journal (bron van waarheid); de
    # uitvoerder synct deze elke minuut. Alleen een weergave-spiegel.
    conn.execute("""CREATE TABLE IF NOT EXISTS handeling (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        agent     TEXT, tijd TEXT, modus TEXT, container TEXT, actie TEXT,
        waarom    TEXT, uitkomst TEXT, detail TEXT, bewijs TEXT)""")
    return conn


def roster():
    conn = db()
    rows = {r["naam"]: r for r in conn.execute("SELECT * FROM status")}
    conn.close()
    uit = []
    for a in TEAM:
        kaart = {**a, "status": "niet gekoppeld", "taak": "", "detail": "",
                 "sinds": None, "minuten": None, "tokens": None}
        r = rows.get(a["naam"])
        if r:
            try:
                ts = datetime.fromisoformat(r["ts"])
                minuten = int((_nu() - ts).total_seconds() // 60)
            except Exception:
                ts, minuten = None, None
            status = r["status"]
            # Verval: geen recente melding -> "stil" (mogelijk down), zodat een
            # gestopte agent niet vals als levend blijft tonen. De hartslag komt
            # uurlijks; ruim twee gemiste beats maakt "waakt" stil.
            if status == "actief" and minuten is not None and minuten >= 60:
                status = "stil"
            elif status == "waakt" and minuten is not None and minuten >= 150:
                status = "stil"
            elif status in ("klaar", "fout") and minuten is not None and minuten >= 24 * 60:
                status = "stil"
            kaart.update(status=status, taak=r["taak"] or "", detail=r["detail"] or "",
                         tokens=r["tokens"], minuten=minuten,
                         sinds=ts.strftime("%d-%m %H:%M") if ts else None)
        uit.append(kaart)
    return uit


def open_voorstellen():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM voorstel WHERE besluit='open' ORDER BY aangemaakt DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "naam": r["naam"], "label": LABELS.get(r["naam"], r["naam"]),
             "actie": r["actie"], "reden": r["reden"], "doel": r["doel"] or "",
             "wanneer": _fmt(r["aangemaakt"])}
            for r in rows]


def recente_besluiten(limit=8):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM voorstel WHERE besluit!='open' ORDER BY besluit_ts DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [{"id": r["id"], "label": LABELS.get(r["naam"], r["naam"]),
             "actie": r["actie"], "besluit": r["besluit"], "doel": r["doel"] or "",
             "door": r["besluit_door"], "wanneer": _fmt(r["besluit_ts"]),
             "uitvoering": r["uitvoering"] or "", "uitvoer_detail": r["uitvoer_detail"] or ""}
            for r in rows]


@app.route("/")
def index():
    return render_template(
        "agents.html",
        agents=roster(),
        voorstellen=open_voorstellen(),
        besluiten=recente_besluiten(),
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"),
    )


@app.route("/api/status")
def api_status():
    return jsonify({"agents": roster(), "voorstellen": open_voorstellen(),
                    "besluiten": recente_besluiten()})


@app.route("/agent-status", methods=["POST"])
def agent_status():
    if not TOKEN:
        abort(404)
    if request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    data = request.get_json(silent=True) or {}
    naam = str(data.get("naam", "")).strip().lower()[:40]
    status = str(data.get("status", "")).strip()
    if not naam or status not in STATUSSEN:
        abort(400)
    try:
        tokens = int(data["tokens"])
    except (KeyError, TypeError, ValueError):
        tokens = None
    conn = db()
    conn.execute(
        """INSERT INTO status (naam, status, taak, detail, tokens, ts)
           VALUES (:naam, :s, :taak, :detail, :t, :ts)
           ON CONFLICT(naam) DO UPDATE SET
             status=excluded.status, taak=excluded.taak,
             detail=excluded.detail, tokens=excluded.tokens, ts=excluded.ts""",
        {"naam": naam, "s": status,
         "taak": str(data.get("taak", "")).strip()[:200],
         "detail": str(data.get("detail", "")).strip()[:400],
         "t": tokens, "ts": _nu().isoformat()})

    v = data.get("voorstel")
    if isinstance(v, dict):
        actie = str(v.get("actie", "")).strip()[:200]
        runbook = str(v.get("runbook", "")).strip()[:60]
        doel = str(v.get("doel", "")).strip()[:120]
        reden = str(v.get("reden", "")).strip()[:400]
        autonoom = bool(v.get("autonoom"))
        if actie and runbook and runbook.lower() != "geen":
            # Dedup: geen tweede openstaand of nog-uit-te-voeren voorstel voor
            # dezelfde container.
            bestaat = conn.execute(
                """SELECT 1 FROM voorstel WHERE naam=? AND runbook=? AND doel=?
                   AND (besluit='open' OR uitvoering IN ('wacht', 'bezig'))""",
                (naam, runbook, doel)).fetchone()
            if not bestaat and autonoom:
                # Veilige klasse: de agent handelt zelf. Meteen goedgekeurd door
                # de agent, klaar voor de uitvoerder (die opnieuw valideert).
                now = _nu().isoformat()
                conn.execute(
                    """INSERT INTO voorstel (naam, actie, reden, runbook, doel, aangemaakt,
                       besluit, besluit_door, besluit_ts, uitvoering)
                       VALUES (?,?,?,?,?,?, 'goedgekeurd', 'agent (autonoom)', ?, 'wacht')""",
                    (naam, actie, reden, runbook, doel, now, now))
            elif not bestaat:
                conn.execute(
                    """INSERT INTO voorstel (naam, actie, reden, runbook, doel, aangemaakt, besluit)
                       VALUES (?, ?, ?, ?, ?, ?, 'open')""",
                    (naam, actie, reden, runbook, doel, _nu().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/voorstel/<int:vid>/besluit", methods=["POST"])
def voorstel_besluit(vid):
    """De gebruiker keurt goed of weigert (achter forward-auth). Bij goedkeuren
    wordt de uitvoering op 'wacht' gezet; de host-uitvoerder pikt dat op. Deze
    app voert zelf niets uit."""
    besluit = str((request.get_json(silent=True) or {}).get("besluit", "")).strip()
    if besluit not in ("goedgekeurd", "geweigerd"):
        abort(400)
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    uitvoering = "wacht" if besluit == "goedgekeurd" else ""
    conn = db()
    conn.execute(
        """UPDATE voorstel SET besluit=?, besluit_door=?, besluit_ts=?, uitvoering=?
           WHERE id=? AND besluit='open'""",
        (besluit, wie, _nu().isoformat(), uitvoering, vid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/uitvoer-wacht")
def uitvoer_wacht():
    """De host-uitvoerder haalt goedgekeurde, nog niet uitgevoerde acties op.
    Token-auth; alleen bereikbaar op localhost of via de SSO. Claimt elke rij
    atomair (wacht -> bezig) zodat twee uitvoer-runs elkaar niet dubbel doen."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    conn = db()
    rows = conn.execute(
        """SELECT id, runbook, doel, reden, besluit_door FROM voorstel
           WHERE besluit='goedgekeurd' AND uitvoering='wacht'"""
    ).fetchall()
    geclaimd = []
    for r in rows:
        cur = conn.execute(
            "UPDATE voorstel SET uitvoering='bezig', uitvoer_ts=? WHERE id=? AND uitvoering='wacht'",
            (_nu().isoformat(), r["id"]))
        if cur.rowcount:
            geclaimd.append({"id": r["id"], "runbook": r["runbook"] or "",
                             "doel": r["doel"] or "", "reden": r["reden"] or "",
                             "door": r["besluit_door"] or ""})
    conn.commit()
    conn.close()
    return jsonify({"wacht": geclaimd})


@app.route("/uitvoer-resultaat", methods=["POST"])
def uitvoer_resultaat():
    """De host-uitvoerder meldt de uitkomst van een actie terug."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    try:
        vid = int(d.get("id"))
    except (TypeError, ValueError):
        abort(400)
    uitvoering = str(d.get("uitvoering", "")).strip()
    if uitvoering not in ("gelukt", "mislukt", "overgeslagen"):
        abort(400)
    conn = db()
    conn.execute(
        """UPDATE voorstel SET uitvoering=?, uitvoer_detail=?, uitvoer_ts=?, bewijs=?
           WHERE id=?""",
        (uitvoering, str(d.get("detail", ""))[:400], _nu().isoformat(),
         str(d.get("bewijs", ""))[:4000], vid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


def handelingen(naam):
    """De handelingen van de agent, herleid uit de systemd-journal (via de sync)."""
    conn = db()
    rows = conn.execute(
        "SELECT * FROM handeling WHERE agent=? ORDER BY id DESC LIMIT 30", (naam,)).fetchall()
    conn.close()
    uit = []
    for r in rows:
        actie = r["actie"] or ""
        container = r["container"] or ""
        if actie == "herstart_container" and container:
            actie_txt = "Herstart container " + container
        elif actie == "escaleren":
            actie_txt = "Escalatie" + (" · " + container if container else "")
        elif container:
            actie_txt = (actie + " " + container).strip()
        else:
            actie_txt = actie
        uit.append({
            "actie": actie_txt, "modus": r["modus"] or "",
            "uitvoering": r["uitkomst"] or "", "waarom": r["waarom"] or "",
            "detail": r["detail"] or "", "bewijs": r["bewijs"] or "",
            "wanneer": _fmt(r["tijd"]),
        })
    return uit


@app.route("/api/agent/<naam>")
def api_agent(naam):
    naam = naam.strip().lower()[:40]
    kaart = next((a for a in roster() if a["naam"] == naam), None)
    if not kaart:
        abort(404)
    detail = DETAILS.get(naam, DETAIL_STANDAARD)
    return jsonify({
        "naam": naam, "label": kaart["label"], "rol": kaart["rol"],
        "status": kaart["status"], "taak": kaart["taak"], "detail": kaart["detail"],
        "sinds": kaart["sinds"], "tokens": kaart["tokens"],
        "mandaat": detail["mandaat"], "mag": detail["mag"],
        "grenzen": detail["grenzen"], "cadans": detail["cadans"],
        "handelingen": handelingen(naam),
    })


@app.route("/handelingen-sync", methods=["POST"])
def handelingen_sync():
    """De host-uitvoerder herleidt de handelingen uit de journal en zet ze hier;
    de tegel spiegelt zo de journal. Token-auth, over localhost."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    agent = str(d.get("agent", "")).strip().lower()[:40]
    lijst = d.get("handelingen")
    if not agent or not isinstance(lijst, list):
        abort(400)
    conn = db()
    conn.execute("DELETE FROM handeling WHERE agent=?", (agent,))
    for e in lijst[-50:]:
        if not isinstance(e, dict):
            continue
        conn.execute(
            """INSERT INTO handeling (agent, tijd, modus, container, actie, waarom,
               uitkomst, detail, bewijs) VALUES (?,?,?,?,?,?,?,?,?)""",
            (agent, str(e.get("tijd", ""))[:40], str(e.get("modus", ""))[:80],
             str(e.get("container", ""))[:120], str(e.get("actie", ""))[:80],
             str(e.get("waarom", ""))[:400], str(e.get("uitkomst", ""))[:40],
             str(e.get("detail", ""))[:400], str(e.get("bewijs", ""))[:4000]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/healthz")
def healthz():
    return {"status": "ok"}
