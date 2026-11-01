"""Voorvertoningen van werkfoto's op de VM (T-0120 FOTO-5): POST /api/fotovoorbeeld, alleen met het token van het bord.

Mehdi, 01-11-2026: "ik wil elke foto en elke file van wachter kunnen zien en begrijpen". De Fotowacht op de Mac maakt
een kleine JPEG van een werkfoto en stuurt hem hierheen; het Dagboek toont hem achter Authentik (dagboek/fotos.py). Hij
staat in <data>/fotovoorbeeld/<dag>/<id>.jpg, nooit in Dropbox (de Mac-sync haalt die map niet op).

Alleen een foto die de indeling op de VM (mijnagents-runner/koppelingen/fotoindeling.py) als werf zeker met GPS en zonder
mensen aanwees ("voorbeeld": true in <data>/fotoindeling/<jaar>/<dag>.json), wordt aanvaard: een vergissing op de Mac
zet zo nooit een privéfoto of een foto van mensen op de VM. Alleen een echte, kleine JPEG.
"""
import base64
import binascii
import json
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import abort, jsonify, request

VANAF = "2026-10-01"           # zoals het Dagboek: terugkijken vanaf 01-10 (X4)
MAX_BYTES = 150_000
ID = re.compile(r"^[0-9A-Za-z-]{1,64}$")


def toegestaan(data, dag, fid):
    """Staat deze foto in de indeling van die dag als werkfoto met voorvertoning?"""
    try:
        with open(os.path.join(data, "fotoindeling", dag[:4], f"{dag}.json"), encoding="utf-8") as f:
            ind = json.load(f)
    except (OSError, ValueError):
        return False
    return any(x.get("id") == fid and x.get("voorbeeld") is True
               for g in ind.get("werf") or [] for x in g.get("fotos") or [])


def bewaar(data, dag, fid, inhoud):
    map_ = os.path.join(data, "fotovoorbeeld", dag)
    os.makedirs(map_, exist_ok=True)
    pad = os.path.join(map_, f"{fid}.jpg")
    tijdelijk = f"{pad}.{os.getpid()}.tmp"
    with open(tijdelijk, "wb") as f:
        f.write(inhoud)
    os.chmod(tijdelijk, 0o644)
    os.replace(tijdelijk, pad)
    return pad


def registreer(app, token, data):
    """token: het AGENTS_TOKEN van het bord; data: de datamap (naast de databank)."""

    @app.route("/api/fotovoorbeeld", methods=["POST"])
    def api_fotovoorbeeld():
        if not token or request.headers.get("X-Agents-Token") != token:
            abort(403)
        p = request.get_json(silent=True) or {}
        dag, fid = str(p.get("dag") or ""), str(p.get("id") or "")
        try:
            d = date.fromisoformat(dag)
        except ValueError:
            return jsonify(ok=False, fout="dag ongeldig"), 400
        morgen = datetime.now(ZoneInfo("Europe/Brussels")).date() + timedelta(days=1)
        if not (date.fromisoformat(VANAF) <= d <= morgen) or not ID.fullmatch(fid):
            return jsonify(ok=False, fout="dag of id ongeldig"), 400
        try:
            inhoud = base64.b64decode(str(p.get("jpeg") or ""), validate=True)
        except (binascii.Error, ValueError):
            return jsonify(ok=False, fout="geen base64"), 400
        if not inhoud.startswith(b"\xff\xd8\xff") or not inhoud.rstrip(b"\x00").endswith(b"\xff\xd9") or len(inhoud) > MAX_BYTES:
            return jsonify(ok=False, fout="geen kleine JPEG"), 400
        if not toegestaan(data, dag, fid):
            return jsonify(ok=False, fout="geen werkfoto met voorvertoning in de indeling van die dag"), 409
        bewaar(data, dag, fid, inhoud)
        return jsonify(ok=True, bytes=len(inhoud))
