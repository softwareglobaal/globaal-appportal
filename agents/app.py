"""Agents: het besturingscentrum van het Globaal-agentplatform.

Toont het agent-team in een oogopslag: elk lid als figuurtje met een status
(rust / actief / klaar / fout). Bewust zelfstandig gehouden: een eigen kleine
SQLite in het datavolume, geen database-credential nodig. Agents melden hun
status via de token-route /agent-status (nginx laat die ene route langs de
SSO); de rest van de app zit achter Authentik forward-auth.

v1 is read-only: kijken, niet besturen. Knoppen om agents te starten of te
stoppen komen later.
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


def _nu():
    return datetime.now(timezone.utc)


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
    return conn


def roster():
    """Het team met live status. 'actief' zonder afronding vervalt na een uur
    naar rust (vrijwel zeker een afgebroken sessie); klaar en fout doven na
    een dag uit naar rust."""
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


@app.route("/")
def index():
    return render_template(
        "agents.html",
        agents=roster(),
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"),
    )


@app.route("/api/status")
def api_status():
    """Voor de zelfverversing van de tegel."""
    return jsonify({"agents": roster()})


@app.route("/agent-status", methods=["POST"])
def agent_status():
    """Een agent meldt zijn huidige toestand. Token-auth (gedeeld geheim),
    net als de ontwikkel-hooks; nginx laat alleen deze POST langs de SSO."""
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
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/healthz")
def healthz():
    return {"status": "ok"}
