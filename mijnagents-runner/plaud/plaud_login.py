#!/usr/bin/env python3
"""Eenmalige aanmelding bij Plaud (OAuth met PKCE), zoals de officiele Plaud-CLI.

Mehdi opent de link, logt in bij Plaud en geeft toestemming. Het token komt in
~/.config/plaud/token.json (alleen leesbaar voor hem). Er gaat geen wachtwoord
door dit script; wij zien alleen de code die Plaud terugstuurt.

Gebruik:  python3 plaud_login.py        toont de link en wacht op de terugkeer
"""
import base64
import hashlib
import http.server
import json
import os
import secrets
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).parent))
import tokenbestand  # noqa: E402
from pathlib import Path

CLIENT_ID = "client_f9e0b214-c11f-434b-8b95-c4497d1feb81"   # publieke CLI-client van Plaud
AUTORISATIE = "https://web.plaud.ai/platform/oauth"
TOKEN_URL = "https://platform.plaud.ai/developer/api/oauth/third-party/access-token"
REDIRECT = "http://localhost:8199/auth/callback"
DOEL = Path.home() / ".config" / "plaud" / "token.json"

verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
state = secrets.token_urlsafe(16)
gereed = threading.Event()
uitkomst = {}


class Callback(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        if p.path != "/auth/callback":
            self.send_response(404); self.end_headers(); return
        if q.get("state", [""])[0] != state:
            uitkomst["fout"] = "state klopt niet"
        elif "code" not in q:
            uitkomst["fout"] = f"geen code: {q.get('error', ['onbekend'])[0]}"
        else:
            uitkomst["code"] = q["code"][0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        boodschap = "Aanmelding gelukt. Je kunt dit venster sluiten." if "code" in uitkomst else f"Mislukt: {uitkomst.get('fout')}"
        self.wfile.write(f"<html><body style='font-family:system-ui;padding:3em'><h2>{boodschap}</h2></body></html>".encode())
        gereed.set()


def wissel(code: str) -> dict:
    basis = base64.b64encode(f"{CLIENT_ID}:".encode()).decode()
    body = urllib.parse.urlencode({"code": code, "redirect_uri": REDIRECT,
                                   "code_verifier": verifier, "state": state})
    r = subprocess.run(["curl", "-sS", "--fail-with-body", "-X", "POST", TOKEN_URL,
                        "-H", "Content-Type: application/x-www-form-urlencoded",
                        "-H", "Accept: application/json",
                        "-H", f"Authorization: Basic {basis}",
                        "-A", "plaud-cli/0.3.14",
                        "--data", body], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"tokenruil mislukt: {r.stdout.decode()[:300]} {r.stderr.decode()[:200]}")
    return json.loads(r.stdout.decode())


def main():
    params = urllib.parse.urlencode({"client_id": CLIENT_ID, "redirect_uri": REDIRECT,
                                     "response_type": "code", "code_challenge": challenge,
                                     "code_challenge_method": "S256", "state": state})
    print("OPEN DEZE LINK EN MELD JE AAN BIJ PLAUD:\n")
    print(f"{AUTORISATIE}?{params}\n")
    srv = http.server.HTTPServer(("127.0.0.1", 8199), Callback)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("Ik wacht tot 24 uur op de terugkeer...")
    if not gereed.wait(86400):
        print("Niets ontvangen binnen 24 uur."); return 1
    srv.shutdown()
    if "code" not in uitkomst:
        print("Mislukt:", uitkomst.get("fout")); return 1
    tok = wissel(uitkomst["code"])
    if isinstance(tok.get("data"), dict):
        tok = tok["data"]
    # vervaltijd vastleggen, zodat plaud_haal_alles.py op tijd ververst (verbeteropdracht v1.0, §2)
    if tok.get("expires_in") and not tok.get("expires_at"):
        tok["expires_at"] = int(time.time() * 1000 + float(tok["expires_in"]) * 1000)
    tokenbestand.schrijf(DOEL, tok)          # 0600 vanaf het eerste moment, map 0700 (nacontrole v1.1, P2-11)
    print("Aangemeld. Token bewaard in", DOEL)
    print("velden:", ", ".join(tok.keys()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
