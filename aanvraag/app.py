"""Aanvraag-inname: vangt formulierinzendingen van unabo.be op.

Deze dienst doet met opzet bijna niets. Ze controleert het gedeelde geheim,
schrijft de inzending onveranderd in een wachtrij en antwoordt meteen. De
bezoeker op de site wacht dus nooit op Pipedrive of Google.

Het echte werk — Google-contact aanmaken, wachten tot de sync hem in Pipedrive
heeft gezet, de deal aanmaken en koppelen — gebeurt daarna door
`aanvraag_verwerk.py` op de host. Die leest deze wachtrij.

Waarom gescheiden: als Pipedrive of Google er even uit ligt, mag een aanvraag
niet verloren gaan en mag de bezoeker daar niets van merken. Alles wat
binnenkomt staat op schijf voordat er iets anders gebeurt.
"""

import json
import os
import sqlite3
import time
from flask import Flask, request, jsonify

DB = os.environ.get("AANVRAAG_DB", "/data/aanvragen.db")
TOKEN = os.environ.get("AANVRAAG_TOKEN", "")

app = Flask(__name__)


def db():
    conn = sqlite3.connect(DB, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS aanvraag (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ontvangen    TEXT NOT NULL,
        bron         TEXT NOT NULL DEFAULT 'wpforms',
        payload      TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'wacht',
        pogingen     INTEGER NOT NULL DEFAULT 0,
        laatste_fout TEXT DEFAULT '',
        google_id    TEXT DEFAULT '',
        persoon_id   INTEGER,
        deal_id      INTEGER,
        verwerkt     TEXT DEFAULT '')""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON aanvraag(status)")
    conn.commit()
    conn.close()


init()


@app.post("/wpforms")
def inname():
    if not TOKEN or request.headers.get("X-Aanvraag-Token", "") != TOKEN:
        # Geen detail in het antwoord: wie het geheim niet heeft, hoort niets te leren.
        return jsonify({"ok": False}), 403

    ruw = request.get_data(as_text=True) or ""
    if len(ruw) > 64_000:
        return jsonify({"ok": False, "fout": "te groot"}), 413
    try:
        data = json.loads(ruw)
    except ValueError:
        return jsonify({"ok": False, "fout": "geen geldige json"}), 400
    if not isinstance(data, dict):
        return jsonify({"ok": False, "fout": "geen object"}), 400

    conn = db()
    cur = conn.execute(
        "INSERT INTO aanvraag (ontvangen, bron, payload) VALUES (?,?,?)",
        (time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
         str(data.get("bron") or "wpforms")[:40],
         json.dumps(data, ensure_ascii=False)))
    conn.commit()
    nr = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "aanvraag": nr})


@app.get("/health")
def health():
    conn = db()
    r = conn.execute(
        "SELECT status, COUNT(*) n FROM aanvraag GROUP BY status").fetchall()
    laatste = conn.execute(
        "SELECT ontvangen FROM aanvraag ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return jsonify({
        "ok": True,
        "per_status": {x["status"]: x["n"] for x in r},
        "laatste_ontvangen": laatste["ontvangen"] if laatste else None,
    })
