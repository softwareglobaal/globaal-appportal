"""MCP-server voor het portaal: alle applicaties leesbaar vanuit Claude.

Een vaste link voor iedereen. Wie hem koppelt logt in via SSO, en vanaf dat
moment ziet hij precies de applicaties waarvan hij op het portaal ook de tegel
ziet. Niet meer, en niet minder.

Koppelen kan op twee manieren, allebei via OAuth en dus allebei met de eigen
Authentik-login: als aangepaste connector in claude.ai, of lokaal met
`claude mcp add --transport http portaal https://portal-mcp.globaal.be/mcp`.
Deze module is daarvoor zelf een kleine OAuth-server (dynamic client
registration + PKCE, RFC 7591/8414/9728), overgenomen van het Vermogens-dashboard
en RenoVision. De loginstap (/oauth/authorize) staat ACHTER de Authentik
forward-auth in de vhost; dat is het enige punt waar wordt vastgesteld wie je
bent. Tokens zijn stateless (HMAC-getekend met MCP_SECRET), dus geen tabel en
geen sessie-opslag.

**Geen vaste sleutel.** Vermogen en RenoVision kennen een `MCP_TOKEN` waarmee je
buiten de SSO om binnenkomt, uitkomend op een vaste gebruiker. Die zit hier
bewust niet in. Deze server ontsluit alle applicaties van het platform; een
sleutel in een `.env` die als beheerder binnenkomt zou de hele belofte
onderuithalen dat Authentik bepaalt wie wat ziet. Ook beheer gaat door de
voordeur.

Wat de server zelf niet beslist: de rechten. Die komen bij elke aanroep opnieuw
uit Authentik (`catalogus.py`) en worden tijdens de query afgedwongen door
Postgres (`gereedschap.py`). Deze module vertaalt alleen HTTP naar die twee.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode, urlparse

import psycopg
from flask import Flask, redirect, request

import bronnen
from catalogus import Cataloog, Onbereikbaar
from gereedschap import Geweigerd, Gereedschap

PROTOCOL_VERSIES = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "portaal", "title": "Globaal portaal", "version": "1.0.0"}

CODE_TTL = 120            # autorisatiecode: 2 minuten
ACCESS_TTL = 12 * 3600    # access token: 12 uur
REFRESH_TTL = 60 * 86400  # refresh token: 60 dagen

app = Flask(__name__)


def _basis() -> str:
    return os.environ.get("MCP_BASIS") or "https://portal-mcp.globaal.be"


def _secret() -> bytes:
    return os.environ.get("MCP_SECRET", "").strip().encode()


# ---- Database -------------------------------------------------------------
def _dsn(database: str) -> str:
    return " ".join([
        f"host={os.environ.get('PG_HOST', '127.0.0.1')}",
        f"port={os.environ.get('PG_PORT', '5433')}",
        f"dbname={database}",
        "user=mcp_lezer",
        f"password={os.environ.get('MCP_LEZER_WACHTWOORD', '')}",
        "connect_timeout=10",
    ])


def _cataloog_uitvoerder(sql, params):
    """Leest de cataloog. Een verbinding per aanroep; het zijn er weinig en
    `Cataloog` buffert zelf een minuut."""
    try:
        with psycopg.connect(_dsn("authentik")) as verbinding:
            with verbinding.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
    except psycopg.Error as e:
        raise Onbereikbaar(f"Cataloog niet te lezen: {e}") from e


def _appportal():
    return psycopg.connect(_dsn("appportal"))


cataloog = Cataloog(_cataloog_uitvoerder)
gereedschap = Gereedschap(cataloog, _appportal)


# ---- Stateless tokens (HMAC-getekend) -------------------------------------
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _teken(payload: dict) -> str:
    ruw = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), ruw.encode(), hashlib.sha256).digest())
    return ruw + "." + sig


def _lees_token(token: str, soort: str):
    """Getekend token terug naar payload; None bij fout, verlopen of ander soort."""
    if not _secret() or "." not in (token or ""):
        return None
    ruw, sig = token.rsplit(".", 1)
    goed = _b64(hmac.new(_secret(), ruw.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, goed):
        return None
    try:
        p = json.loads(base64.urlsafe_b64decode(ruw + "=" * (-len(ruw) % 4)))
    except Exception:
        return None
    if p.get("t") != soort or p.get("exp", 0) < time.time():
        return None
    return p


def _redirect_ok(uri: str) -> bool:
    """Waar de autorisatiecode heen mag: Claude zelf, of de eigen machine.

    claude.ai stuurt terug naar een adres van Claude; Claude Code op een
    werkplek luistert op een willekeurige poort op localhost (RFC 8252). Die
    loopback-adressen komen het netwerk niet op, en PKCE plus de SSO-login
    blijven ook daar gelden.
    """
    try:
        p = urlparse(uri)
    except Exception:
        return False
    host = (p.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return p.scheme in ("http", "https")
    basis = ("claude.ai", "claude.com", "anthropic.com")
    return (p.scheme == "https"
            and (host in basis or host.endswith(tuple("." + b for b in basis))))


# ---- OAuth: metadata (RFC 8414 / 9728) ------------------------------------
@app.get("/.well-known/oauth-authorization-server")
@app.get("/.well-known/oauth-authorization-server/mcp")
@app.get("/.well-known/openid-configuration")
def oauth_as_metadata():
    if not _secret():
        return {"fout": "OAuth staat uit"}, 404
    b = _basis()
    return {"issuer": b,
            "authorization_endpoint": b + "/oauth/authorize",
            "token_endpoint": b + "/mcp/token",
            "registration_endpoint": b + "/mcp/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": ["portaal"]}


@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/mcp")
def oauth_pr_metadata():
    if not _secret():
        return {"fout": "OAuth staat uit"}, 404
    b = _basis()
    return {"resource": b + "/mcp", "authorization_servers": [b],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["portaal"]}


@app.post("/mcp/register")
def oauth_register():
    if not _secret():
        return {"fout": "OAuth staat uit"}, 404
    body = request.get_json(silent=True) or {}
    uris = body.get("redirect_uris") or []
    if not uris or not all(_redirect_ok(u) for u in uris):
        return {"error": "invalid_redirect_uri",
                "error_description": "Alleen redirects naar Claude zijn "
                                     "toegestaan"}, 400
    return {"client_id": "portaal-claude",
            "client_name": body.get("client_name", "Claude"),
            "redirect_uris": uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"]}, 201


@app.get("/oauth/authorize")
def oauth_authorize():
    """De loginstap. Staat achter de Authentik forward-auth in de vhost."""
    if not _secret():
        return {"fout": "OAuth staat uit"}, 404
    redirect_uri = request.args.get("redirect_uri", "")
    if not _redirect_ok(redirect_uri):
        return "Ongeldige redirect_uri", 400
    if request.args.get("response_type") != "code":
        return "Alleen response_type=code wordt ondersteund", 400
    challenge = request.args.get("code_challenge", "")
    if not challenge or request.args.get("code_challenge_method") != "S256":
        return "PKCE (S256) is verplicht", 400

    # Wie hier komt is al door Authentik heen. Dit is het enige punt waar 'wie
    # ben je' wordt vastgesteld; wat je daarna mag, wordt bij elke aanroep
    # opnieuw opgezocht. In het token zit alleen de naam, geen rechten: een
    # ingetrokken groep werkt binnen een minuut, niet pas na twaalf uur.
    wie = (request.headers.get("X-authentik-username") or "").strip()
    if not wie:
        return "Geen ingelogde gebruiker; log opnieuw in via het portaal.", 403

    code = _teken({"t": "code", "u": wie, "ch": challenge, "r": redirect_uri,
                   "exp": int(time.time()) + CODE_TTL})
    sep = "&" if "?" in redirect_uri else "?"
    return redirect(redirect_uri + sep + urlencode(
        {"code": code, "state": request.args.get("state", "")}))


def _tokens_voor(payload: dict) -> dict:
    nu = int(time.time())
    return {"access_token": _teken({"t": "acc", "u": payload["u"],
                                    "exp": nu + ACCESS_TTL}),
            "token_type": "Bearer", "expires_in": ACCESS_TTL,
            "refresh_token": _teken({"t": "ref", "u": payload["u"],
                                     "exp": nu + REFRESH_TTL}),
            "scope": "portaal"}


@app.post("/mcp/token")
def oauth_token():
    if not _secret():
        return {"fout": "OAuth staat uit"}, 404
    soort = request.form.get("grant_type", "")
    if soort == "authorization_code":
        p = _lees_token(request.form.get("code", ""), "code")
        if not p:
            return {"error": "invalid_grant",
                    "error_description": "Code ongeldig of verlopen"}, 400
        digest = hashlib.sha256(
            request.form.get("code_verifier", "").encode()).digest()
        if not hmac.compare_digest(_b64(digest), p["ch"]):
            return {"error": "invalid_grant",
                    "error_description": "PKCE-verificatie faalt"}, 400
        terug = request.form.get("redirect_uri", "")
        if terug and terug != p["r"]:
            return {"error": "invalid_grant",
                    "error_description": "redirect_uri wijkt af"}, 400
        return _tokens_voor(p)
    if soort == "refresh_token":
        p = _lees_token(request.form.get("refresh_token", ""), "ref")
        if not p:
            return {"error": "invalid_grant",
                    "error_description": "Refresh token ongeldig of verlopen"}, 400
        return _tokens_voor(p)
    return {"error": "unsupported_grant_type"}, 400


# ---- De gereedschapskist --------------------------------------------------
TOOLS = [
    {"name": "apps",
     "title": "Welke applicaties",
     "description":
         "De applicaties van het platform die jij mag lezen, gelijk aan de "
         "tegels die je op het portaal ziet. Per app staat erbij of de data nu "
         "leesbaar is, ergens anders staat, of nog niet is uitgezocht. Begin "
         "hiermee: de andere twee stukken gereedschap willen een appnaam uit "
         "deze lijst.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "schema",
     "title": "Tabellen van een applicatie",
     "description":
         "De tabellen en kolommen van een applicatie, zodat je een query kunt "
         "schrijven. Ziet een applicatie er leeg uit, kijk dan naar het veld "
         "niet_zichtbaar: sommige tabellen vragen een extra groep.",
     "inputSchema": {
         "type": "object",
         "properties": {"app": {"type": "string",
                                "description": "De appnaam uit `apps`"}},
         "required": ["app"]}},
    {"name": "query",
     "title": "Lezen uit een applicatie",
     "description":
         "Voert een SELECT uit op de data van een applicatie. Alleen lezen: de "
         "query draait in een read-only transactie onder een databaserol die "
         "uitsluitend de schema's van die ene applicatie mag zien. Schrijven "
         "kan niet, en een query die een andere applicatie probeert te lezen "
         "wordt door de database geweigerd.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "app": {"type": "string", "description": "De appnaam uit `apps`"},
             "sql": {"type": "string",
                     "description": "Een enkele SELECT, eventueel met WITH"},
             "rijen": {"type": "integer",
                       "description": "Maximaal aantal rijen (standaard 200, "
                                      "hoogstens 1000)"}},
         "required": ["app", "sql"]}},
]


def _voer_uit(naam: str, a: dict, gebruiker: str):
    if naam == "apps":
        return gereedschap.apps(gebruiker)
    if naam == "schema":
        return gereedschap.schema(gebruiker, a.get("app", ""))
    if naam == "query":
        return gereedschap.query(gebruiker, a.get("app", ""), a.get("sql", ""),
                                 a.get("rijen"))
    raise Geweigerd(f"Onbekend gereedschap: {naam}")


# ---- MCP: JSON-RPC over HTTP ---------------------------------------------
def _wie() -> str | None:
    """De gebruikersnaam uit het bearer-token, of None."""
    kop = request.headers.get("Authorization", "")
    if not kop.startswith("Bearer "):
        return None
    p = _lees_token(kop[7:].strip(), "acc")
    return p["u"] if p else None


def _resultaat(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _fout(rid, code, boodschap):
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": code, "message": boodschap}}


def _tekst(rid, tekst, mislukt=False):
    return _resultaat(rid, {"content": [{"type": "text", "text": tekst}],
                            "isError": mislukt})


@app.get("/mcp")
def mcp_get():
    return "", 405


@app.get("/gezond")
def gezond():
    """Kort rondje langs de twee databases, zonder iets prijs te geven."""
    try:
        apps = cataloog.applicaties()
    except Onbereikbaar as e:
        return {"gezond": False, "cataloog": str(e)}, 503
    telling = bronnen.overzicht(a.slug for a in apps)
    return {"gezond": True,
            "applicaties": len(apps),
            "rechten_onzeker": sum(1 for a in apps if a.onzeker),
            "bronnen": telling}


@app.post("/mcp")
def mcp():
    if not _secret():
        return {"fout": "MCP staat uit"}, 404
    gebruiker = _wie()
    if gebruiker is None:
        kop = ('Bearer resource_metadata='
               f'"{_basis()}/.well-known/oauth-protected-resource/mcp"')
        return {"fout": "Ongeldig of ontbrekend token"}, 401, \
               {"WWW-Authenticate": kop}

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _fout(None, -32700, "Geen geldige JSON-RPC-request")
    methode, rid = body.get("method", ""), body.get("id")
    params = body.get("params") or {}

    if methode.startswith("notifications/"):
        return "", 202
    if methode == "initialize":
        pv = params.get("protocolVersion")
        return _resultaat(rid, {
            "protocolVersion": pv if pv in PROTOCOL_VERSIES else PROTOCOL_VERSIES[0],
            "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO})
    if methode == "ping":
        return _resultaat(rid, {})
    if methode == "tools/list":
        return _resultaat(rid, {"tools": TOOLS})
    if methode != "tools/call":
        return _fout(rid, -32601, f"Onbekende methode: {methode}")

    naam = params.get("name", "")
    try:
        uit = _voer_uit(naam, params.get("arguments") or {}, gebruiker)
        return _resultaat(rid, {
            "content": [{"type": "text",
                         "text": json.dumps(uit, ensure_ascii=False, default=str)}],
            "isError": False})
    except Geweigerd as e:
        return _tekst(rid, str(e), True)
    except Onbereikbaar as e:
        # Kan de cataloog niet gelezen worden, dan weten we niet wat iemand mag.
        # Dan geven we niets, en zeggen we waarom.
        return _tekst(rid, f"De rechten zijn nu niet vast te stellen, dus er "
                           f"gaat niets open. {e}", True)
    except Exception as e:  # noqa: BLE001 - Claude moet de fout kunnen lezen
        app.logger.exception("gereedschap %s faalde", naam)
        return _tekst(rid, f"Fout: {type(e).__name__}: {e}", True)


if __name__ == "__main__":
    # Binden op de docker-brug, niet op 0.0.0.0: alleen nginx (in een
    # container) hoeft erbij, en zo staat het niet open op het internet.
    app.run(host=os.environ.get("PORTAL_MCP_ADRES", "172.17.0.1"),
            port=int(os.environ.get("PORTAL_MCP_POORT", "8113")),
            threaded=True)
