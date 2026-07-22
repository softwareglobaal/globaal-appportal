"""Agents: het besturingscentrum van het Globaal-agentplatform.

Toont het agent-team in een oogopslag: elk lid als figuurtje met een status
(rust / actief / klaar / fout). Bewust zelfstandig gehouden: een eigen kleine
SQLite in het datavolume, geen database-credential nodig. Agents melden hun
status via de token-route /agent-status (nginx laat die ene route langs de
SSO); de rest van de app zit achter Authentik forward-auth.

Voorstellen (mens-in-de-lus): een agent kan bij een probleem een actie
VOORSTELLEN. De gebruiker keurt goed of weigert op de tegel. In deze fase wordt
er nog NIETS uitgevoerd: alleen de beslissing wordt vastgelegd (wie, wanneer).
Zo zie je eerst welke voorstellen komen voordat de agent iets mag doen.
"""
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, abort

app = Flask(__name__)

DB = os.environ.get("AGENTS_DB", "/data/agents.db")
TOKEN = os.environ.get("AGENTS_TOKEN", "").strip()
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")

STATUSSEN = ("rust", "actief", "klaar", "fout")

# Het vaste team. Wie nog niet gemeld heeft, staat op 'rust'. Agents zijn
# oproepkrachten: rust is hun normale toestand, geen wachtende dienst.
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


def _nu():
    return datetime.now(timezone.utc)


def _fmt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d-%m %H:%M")
    except Exception:
        return ""


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
    return conn


def roster():
    """Het team met live status. 'actief' zonder afronding vervalt na een uur
    naar rust; klaar en fout doven na een dag uit naar rust."""
    conn = db()
    rows = {r["naam"]: r for r in conn.execute("SELECT * FROM status")}
    conn.close()
    uit = []
    for a in TEAM:
        kaart = {**a, "status": "rust", "taak": "", "detail": "",
                 "sinds": None, "minuten": None, "tokens": None}
        r = rows.get(a["naam"])
        if r:
            try:
                ts = datetime.fromisoformat(r["ts"])
                minuten = int((_nu() - ts).total_seconds() // 60)
            except Exception:
                ts, minuten = None, None
            status = r["status"]
            if status == "actief" and minuten is not None and minuten >= 60:
                status = "rust"
            elif status in ("klaar", "fout") and minuten is not None and minuten >= 24 * 60:
                status = "rust"
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
             "actie": r["actie"], "reden": r["reden"], "wanneer": _fmt(r["aangemaakt"])}
            for r in rows]


def recente_besluiten(limit=6):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM voorstel WHERE besluit!='open' ORDER BY besluit_ts DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [{"id": r["id"], "label": LABELS.get(r["naam"], r["naam"]),
             "actie": r["actie"], "besluit": r["besluit"],
             "door": r["besluit_door"], "wanneer": _fmt(r["besluit_ts"])}
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
    """Voor de zelfverversing van de tegel."""
    return jsonify({"agents": roster(), "voorstellen": open_voorstellen()})


@app.route("/agent-status", methods=["POST"])
def agent_status():
    """Een agent meldt zijn toestand en kan een actie voorstellen. Token-auth
    (gedeeld geheim); nginx laat alleen deze POST langs de SSO."""
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

    # Optioneel voorstel. Dedup: geen tweede open voorstel met dezelfde actie.
    v = data.get("voorstel")
    if isinstance(v, dict):
        actie = str(v.get("actie", "")).strip()[:200]
        reden = str(v.get("reden", "")).strip()[:400]
        if actie and actie.lower() != "geen":
            bestaat = conn.execute(
                "SELECT 1 FROM voorstel WHERE naam=? AND actie=? AND besluit='open'",
                (naam, actie)).fetchone()
            if not bestaat:
                conn.execute(
                    """INSERT INTO voorstel (naam, actie, reden, aangemaakt, besluit)
                       VALUES (?, ?, ?, ?, 'open')""",
                    (naam, actie, reden, _nu().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/voorstel/<int:vid>/besluit", methods=["POST"])
def voorstel_besluit(vid):
    """De gebruiker keurt goed of weigert. Zit achter forward-auth, dus de
    identiteit komt uit de X-authentik-header. In deze fase wordt er niets
    uitgevoerd: alleen de beslissing wordt vastgelegd."""
    besluit = str((request.get_json(silent=True) or {}).get("besluit", "")).strip()
    if besluit not in ("goedgekeurd", "geweigerd"):
        abort(400)
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    conn = db()
    conn.execute(
        "UPDATE voorstel SET besluit=?, besluit_door=?, besluit_ts=? WHERE id=? AND besluit='open'",
        (besluit, wie, _nu().isoformat(), vid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/healthz")
def healthz():
    return {"status": "ok"}
