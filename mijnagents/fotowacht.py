"""De Fotowacht op het bord (T-0120 FOTO-4 en FOTO-5): twee routes, alleen met het token van het bord.

Mehdi, 01-11-2026: "voor de fotos zijn de projecten van de bedrijven belangrijk niet de fotos van de mensen" en "ik wil
elke foto en elke file van wachter kunnen zien en begrijpen".

- POST /api/fotometadata: per dag de metadata van de foto's van de Mac (tijd, GPS, soort en de vlaggen van Photos; nooit
  een beeld of bestandsnaam) voor de indeling op de VM (mijnagents-runner/koppelingen/fotoindeling.py). Ze komt in
  <data>/fotometadata/<dag>.json: niet in de databank van het bord (Codex 1: daar las elke agent de privé-GPS mee), niet
  in de export naar Data uit Mehdi en niet in Dropbox. Alleen de gebruiker van de VM kan het bestand lezen (0600).
- POST /api/fotovoorbeeld: een kleine JPEG van een werkfoto, in <data>/fotovoorbeeld/<dag>/<id>.jpg; het Dagboek toont
  hem achter Authentik (dagboek/fotos.py). Alleen een foto die de indeling van die dag als werf zeker met GPS en zonder
  mensen aanwijst ("voorbeeld": true in <data>/fotoindeling/<jaar>/<dag>.json): een vergissing op de Mac zet zo nooit
  een privéfoto of een foto van mensen op de VM.
De bestanden krijgen de eigenaar van de datamap (de VM-gebruiker), want de container schrijft als root.
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
MAX_FOTOS = 5000
ID = re.compile(r"^[0-9A-Za-z-]{1,64}$")


def _dag(p):
    try:
        d = date.fromisoformat(str(p.get("dag") or ""))
    except ValueError:
        return None
    morgen = datetime.now(ZoneInfo("Europe/Brussels")).date() + timedelta(days=1)
    return d.isoformat() if date.fromisoformat(VANAF) <= d <= morgen else None


def _schrijf(data, pad, inhoud):
    """Atomair, 0600, met de eigenaar van de datamap (de mappen ertussen ook)."""
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    tijdelijk = f"{pad}.{os.getpid()}.tmp"
    with open(tijdelijk, "wb") as f:
        f.write(inhoud)
    os.chmod(tijdelijk, 0o600)
    st = os.stat(data)
    try:
        map_ = os.path.dirname(pad)
        while os.path.commonpath([map_, data]) == data and map_ != data:
            os.chown(map_, st.st_uid, st.st_gid)
            map_ = os.path.dirname(map_)
        os.chown(tijdelijk, st.st_uid, st.st_gid)
    except PermissionError:
        pass                    # buiten de container (proef): de eigenaar is al de gebruiker
    os.replace(tijdelijk, pad)
    return pad


def _vlag(x):
    return x if x is True or x is False else None    # alleen echt ja of nee; al de rest is onbekend


def schone_fotos(lijst):
    """Alleen de velden die de indeling gebruikt, met hun soort; None bij een ongeldige lijst."""
    if not isinstance(lijst, list) or len(lijst) > MAX_FOTOS:
        return None
    uit = []
    for f in lijst:
        if not isinstance(f, dict) or not ID.fullmatch(str(f.get("id") or "")) or not isinstance(f.get("utc"), str):
            return None
        lat, lon = f.get("lat"), f.get("lon")
        gps = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lat, lon))
        uit.append({"id": f["id"], "utc": f["utc"][:40], "lat": float(lat) if gps else None, "lon": float(lon) if gps else None,
                    "video": f.get("video") is True, "scherm": _vlag(f.get("scherm")), "app": _vlag(f.get("app")),
                    "mensen": _vlag(f.get("mensen"))})
    return uit


def toegestaan(data, dag, fid):
    """Staat deze foto in de indeling van die dag als werkfoto met voorvertoning?"""
    try:
        with open(os.path.join(data, "fotoindeling", dag[:4], f"{dag}.json"), encoding="utf-8") as f:
            ind = json.load(f)
    except (OSError, ValueError):
        return False
    return any(x.get("id") == fid and x.get("voorbeeld") is True
               for g in ind.get("werf") or [] for x in g.get("fotos") or [])


def registreer(app, token, data):
    """token: het AGENTS_TOKEN van het bord; data: de datamap (naast de databank)."""

    def toets():
        if not token or request.headers.get("X-Agents-Token") != token:
            abort(403)
        return request.get_json(silent=True) or {}

    @app.route("/api/fotometadata", methods=["POST"])
    def api_fotometadata():
        p = toets()
        dag = _dag(p)
        fotos = schone_fotos(p.get("fotos"))
        if not dag or fotos is None or p.get("aantal") != len(fotos):
            return jsonify(ok=False, fout="dag, aantal of foto's ongeldig"), 400
        inhoud = {"datum": dag, "versie": 1, "aantal": len(fotos), "fotos": fotos,
                  "ontvangen": datetime.now(ZoneInfo("Europe/Brussels")).isoformat(timespec="seconds")}
        _schrijf(data, os.path.join(data, "fotometadata", f"{dag}.json"), json.dumps(inhoud, ensure_ascii=False).encode("utf-8"))
        return jsonify(ok=True, aantal=len(fotos))

    @app.route("/api/fotovoorbeeld", methods=["POST"])
    def api_fotovoorbeeld():
        p = toets()
        dag, fid = _dag(p), str(p.get("id") or "")
        if not dag or not ID.fullmatch(fid):
            return jsonify(ok=False, fout="dag of id ongeldig"), 400
        try:
            inhoud = base64.b64decode(str(p.get("jpeg") or ""), validate=True)
        except (binascii.Error, ValueError):
            return jsonify(ok=False, fout="geen base64"), 400
        if not inhoud.startswith(b"\xff\xd8\xff") or not inhoud.rstrip(b"\x00").endswith(b"\xff\xd9") or len(inhoud) > MAX_BYTES:
            return jsonify(ok=False, fout="geen kleine JPEG"), 400
        if not toegestaan(data, dag, fid):
            return jsonify(ok=False, fout="geen werkfoto met voorvertoning in de indeling van die dag"), 409
        _schrijf(data, os.path.join(data, "fotovoorbeeld", dag, f"{fid}.jpg"), inhoud)
        return jsonify(ok=True, bytes=len(inhoud))
