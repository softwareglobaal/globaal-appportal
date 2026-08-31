"""MCP-server voor RenoVision: collega's passen de code aan via Claude.

Iedereen met een eigen kopie van RenoVision (`renovision-<naam>.globaal.be`)
kan die kopie hiermee vanuit Claude aanpassen: code lezen en doorzoeken,
wijzigen, vastleggen in git en opnieuw uitrollen. Wie je bent bepaalt in welke
kopie je terechtkomt -- dat is niet in te stellen en niet te omzeilen.

Koppelen in claude.ai: aangepaste connector op
https://renovision-mcp.globaal.be/mcp. Dat gaat via OAuth; deze module is
daarvoor zelf een kleine OAuth-server (dynamic client registration + PKCE, RFC
7591/8414/9728), overgenomen van angela.sr en het Vermogens-dashboard. De
loginstap (/oauth/authorize) staat ACHTER de Authentik forward-auth in de
vhost: wie koppelt logt in via SSO, en alleen de renovision-groepen komen
erdoor (scripts/add-renovision-mcp.py). Tokens zijn stateless (HMAC-getekend
met MCP_SECRET), dus geen tabel en geen sessie-opslag.

De vhost laat /mcp, /mcp/token, /mcp/register en de OAuth-metadata vrij; de
tokencontrole gebeurt hier.

Waarom een aparte dienst op de host en niet in de app-container: het
gereedschap moet bij de mappen van alle kopieen en bij docker kunnen. Draait
als een enkel proces (geen workers), zodat de uitrolstand van een bouw in het
geheugen klopt.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode, urlparse

from flask import Flask, redirect, request

import gereedschap as gs
import werkruimte as wr
from werkruimte import Geweigerd

PROTOCOL_VERSIES = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "renovision", "title": "RenoVision", "version": "1.0.0"}

CODE_TTL = 120            # autorisatiecode: 2 minuten
ACCESS_TTL = 12 * 3600    # access token: 12 uur
REFRESH_TTL = 60 * 86400  # refresh token: 60 dagen

app = Flask(__name__)


def _basis() -> str:
    return os.environ.get("MCP_BASIS") or "https://renovision-mcp.globaal.be"


def _statisch_token() -> str:
    return os.environ.get("MCP_TOKEN", "").strip()


def _secret() -> bytes:
    return os.environ.get("MCP_SECRET", "").strip().encode()


# ---- Stateless tokens (HMAC-getekend) -------------------------------------
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _teken(payload: dict) -> str:
    ruw = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), ruw.encode(), hashlib.sha256).digest())
    return ruw + "." + sig


def _lees_token(token: str, soort: str):
    """Getekend token terug naar payload; None bij fout/verlopen/ander soort."""
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
    """Alleen terugsturen naar Claude zelf."""
    try:
        p = urlparse(uri)
    except Exception:
        return False
    host = (p.hostname or "").lower()
    basis = ("claude.ai", "claude.com", "anthropic.com")
    return (p.scheme == "https"
            and (host in basis or host.endswith(tuple("." + b for b in basis))))


# ---- OAuth: metadata (RFC 8414 / 9728) ------------------------------------
def _as_metadata() -> dict:
    b = _basis()
    return {"issuer": b,
            "authorization_endpoint": b + "/oauth/authorize",
            "token_endpoint": b + "/mcp/token",
            "registration_endpoint": b + "/mcp/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": ["renovision"]}


@app.get("/.well-known/oauth-authorization-server")
@app.get("/.well-known/oauth-authorization-server/mcp")
@app.get("/.well-known/openid-configuration")
def oauth_as_metadata():
    if not _secret():
        return {"fout": "OAuth staat uit"}, 404
    return _as_metadata()


@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/mcp")
def oauth_pr_metadata():
    if not _secret():
        return {"fout": "OAuth staat uit"}, 404
    b = _basis()
    return {"resource": b + "/mcp", "authorization_servers": [b],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["renovision"]}


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
    return {"client_id": "renovision-claude",
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

    # Wie hier komt is al door Authentik heen; de identiteit komt uit de
    # proxy-headers en wordt in het token gebakken. Dat token bepaalt later de
    # werkruimte, dus dit is het enige punt waar 'wie ben je' wordt vastgesteld.
    wie = (request.headers.get("X-authentik-username") or "").strip()
    if not wie:
        return "Geen ingelogde gebruiker; log opnieuw in via het portaal.", 403
    if wr.voor_gebruiker(wie) is None:
        return (f"Voor '{wie}' staat er geen eigen RenoVision-kopie klaar. "
                "Vraag de beheerder er een aan te maken."), 403

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
            "scope": "renovision"}


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
WIJZIG = ("Werkt alleen in jouw eigen kopie van RenoVision; de kopieen van "
          "collega's en de gedeelde versie blijven ongemoeid.")

TOOLS = [
    dict(name="werkruimte",
         description="Begin hier. Vertelt in welke kopie van RenoVision je "
                     "werkt, op welke tak, hoeveel er openstaat, welke "
                     "containers draaien, hoe een lopende uitrol ervoor staat "
                     "en hoe zwaar de VM belast is.",
         inputSchema={"type": "object", "properties": {}}),
    dict(name="bestanden",
         description="De bestanden van de app opsommen (alleen wat in git "
                     "staat). Geef eventueel een deel van een pad als filter, "
                     "bijvoorbeeld 'backend' of 'frontend/src'.",
         inputSchema={"type": "object",
                      "properties": {"patroon": {"type": "string"}}}),
    dict(name="lees",
         description="Een bestand lezen, met regelnummers. Grote bestanden "
                     "lees je in stukken met vanaf/aantal. Doe dit altijd "
                     "voordat je iets wijzigt.",
         inputSchema={"type": "object",
                      "properties": {
                          "pad": {"type": "string",
                                  "description": "relatief, bv. backend/routes.py"},
                          "vanaf": {"type": "integer",
                                    "description": "eerste regel (standaard 1)"},
                          "aantal": {"type": "integer",
                                     "description": "aantal regels"}},
                      "required": ["pad"]}),
    dict(name="zoek",
         description="Door de hele code zoeken met een reguliere expressie. "
                     "De snelste manier om te vinden waar iets geregeld "
                     "wordt. Beperk desgewenst tot een map met 'bestanden', "
                     "bijvoorbeeld 'backend/*.py'.",
         inputSchema={"type": "object",
                      "properties": {
                          "patroon": {"type": "string"},
                          "bestanden": {"type": "string",
                                        "description": "padfilter, bv. frontend/src"},
                          "hoofdletters": {"type": "boolean",
                                           "description": "hoofdlettergevoelig zoeken"}},
                      "required": ["patroon"]}),
    dict(name="vervang",
         description="Een exact stuk tekst in een bestand vervangen. Dit is "
                     "de gewone manier om code te wijzigen. De tekst in 'oud' "
                     "moet letterlijk kloppen (inspringing meegerekend) en "
                     "uniek zijn in het bestand. " + WIJZIG,
         inputSchema={"type": "object",
                      "properties": {
                          "pad": {"type": "string"},
                          "oud": {"type": "string",
                                  "description": "de bestaande tekst, letterlijk"},
                          "nieuw": {"type": "string",
                                    "description": "wat ervoor in de plaats komt"},
                          "alles": {"type": "boolean",
                                    "description": "alle voorkomens vervangen"}},
                      "required": ["pad", "oud", "nieuw"]}),
    dict(name="schrijf",
         description="Een bestand volledig schrijven: voor nieuwe bestanden, "
                     "of als er zo veel verandert dat vervangen onhandig is. "
                     "Vervangt de hele inhoud. " + WIJZIG,
         inputSchema={"type": "object",
                      "properties": {"pad": {"type": "string"},
                                     "inhoud": {"type": "string"}},
                      "required": ["pad", "inhoud"]}),
    dict(name="verwijder",
         description="Een bestand verwijderen. " + WIJZIG,
         inputSchema={"type": "object",
                      "properties": {"pad": {"type": "string"}},
                      "required": ["pad"]}),
    dict(name="wijzigingen",
         description="Laat zien wat er veranderd is: wat nog niet is "
                     "vastgelegd, welke bestanden nieuw zijn, en hoe jouw tak "
                     "verschilt van de gedeelde versie. Doe dit voor je "
                     "vastlegt.",
         inputSchema={"type": "object",
                      "properties": {"pad": {"type": "string"}}}),
    dict(name="vastleggen",
         description="De wijzigingen vastleggen in git, op jouw eigen tak. "
                     "Geef een korte omschrijving van wat je veranderd hebt. "
                     "Vastleggen zet nog niets live; dat doet 'uitrollen'.",
         inputSchema={"type": "object",
                      "properties": {"bericht": {"type": "string"}},
                      "required": ["bericht"]}),
    dict(name="geschiedenis",
         description="De laatste commits op jouw tak, met kenmerk en datum.",
         inputSchema={"type": "object",
                      "properties": {"aantal": {"type": "integer"}}}),
    dict(name="terugdraaien",
         description="Iets ongedaan maken. Met 'pad' gooi je de nog niet "
                     "vastgelegde wijzigingen in dat bestand weg; met "
                     "'commit' maak je een tegen-commit voor iets dat al "
                     "vastligt. Er wordt nooit geschiedenis gewist.",
         inputSchema={"type": "object",
                      "properties": {"pad": {"type": "string"},
                                     "commit": {"type": "string"}}}),
    dict(name="uitrollen",
         description="Jouw kopie opnieuw bouwen en herstarten, zodat de "
                     "wijzigingen live staan op jouw eigen adres. Duurt "
                     "enkele minuten en loopt op de achtergrond; vraag daarna "
                     "'werkruimte' voor de stand. Er kan er maar een tegelijk "
                     "bouwen op de VM.",
         inputSchema={"type": "object", "properties": {}}),
    dict(name="logboek",
         description="De laatste regels uit een containerlog: backend, web of "
                     "mongo. Hiermee zie je of een wijziging een fout geeft.",
         inputSchema={"type": "object",
                      "properties": {
                          "dienst": {"type": "string",
                                     "description": "backend, web of mongo"},
                          "regels": {"type": "integer"}}}),
]


def _voer_uit(naam: str, a: dict, ws, gebruiker: str):
    if naam == "werkruimte":
        return gs.werkruimte_info(ws)
    if naam == "bestanden":
        return gs.bestanden(ws, a.get("patroon", ""))
    if naam == "lees":
        return gs.lees(ws, a.get("pad", ""), a.get("vanaf", 1), a.get("aantal", 0))
    if naam == "zoek":
        return gs.zoek(ws, a.get("patroon", ""), a.get("bestanden", ""),
                       bool(a.get("hoofdletters")))
    if naam == "vervang":
        return gs.vervang(ws, a.get("pad", ""), a.get("oud", ""),
                          a.get("nieuw", ""), bool(a.get("alles")))
    if naam == "schrijf":
        return gs.schrijf(ws, a.get("pad", ""), a.get("inhoud", ""))
    if naam == "verwijder":
        return gs.verwijder(ws, a.get("pad", ""))
    if naam == "wijzigingen":
        return gs.wijzigingen(ws, a.get("pad", ""))
    if naam == "vastleggen":
        return gs.vastleggen(ws, a.get("bericht", ""), gebruiker)
    if naam == "geschiedenis":
        return gs.geschiedenis(ws, a.get("aantal", 15))
    if naam == "terugdraaien":
        return gs.terugdraaien(ws, a.get("pad", "") or "", a.get("commit", "") or "")
    if naam == "uitrollen":
        return gs.uitrollen(ws)
    if naam == "logboek":
        return gs.logboek(ws, a.get("dienst", "backend"), a.get("regels", 60))
    raise Geweigerd(f"Onbekend gereedschap: {naam}")


# ---- MCP: JSON-RPC over HTTP ---------------------------------------------
def _wie() -> str | None:
    """De gebruikersnaam uit het bearer-token, of None."""
    kop = request.headers.get("Authorization", "")
    if not kop.startswith("Bearer "):
        return None
    token = kop[7:].strip()
    statisch = _statisch_token()
    if statisch and hmac.compare_digest(token, statisch):
        # Vaste sleutel voor beheer en voor Claude Code; komt op de admin-kopie
        # uit, net als een ingelogde beheerder.
        return "akadmin"
    p = _lees_token(token, "acc")
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
    ruimtes = wr.ontdek()
    return {"werkruimtes": sorted(ruimtes), "schijf": gs.schijfruimte()}


@app.post("/mcp")
def mcp():
    if not _statisch_token() and not _secret():
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

    # De werkruimte wordt hier bepaald, uit de identiteit in het token. Er is
    # geen parameter waarmee een gebruiker een andere kopie kan kiezen.
    ws = wr.voor_gebruiker(gebruiker)
    if ws is None:
        return _tekst(rid, f"Voor '{gebruiker}' staat er geen eigen kopie van "
                           "RenoVision klaar. Vraag de beheerder er een aan "
                           "te maken.", True)
    naam = params.get("name", "")
    try:
        uit = _voer_uit(naam, params.get("arguments") or {}, ws, gebruiker)
        return _resultaat(rid, {
            "content": [{"type": "text",
                         "text": json.dumps(uit, ensure_ascii=False, default=str)}],
            "isError": False})
    except Geweigerd as e:
        return _tekst(rid, str(e), True)
    except Exception as e:  # noqa: BLE001 - Claude moet de fout kunnen lezen
        app.logger.exception("gereedschap %s faalde", naam)
        return _tekst(rid, f"Fout: {type(e).__name__}: {e}", True)


if __name__ == "__main__":
    # Binden op de docker-brug, niet op 0.0.0.0: alleen nginx (in een
    # container) hoeft erbij, en zo staat het niet open op het internet.
    # Zelfde keuze als de Schuldentracker op 172.17.0.1:5050.
    app.run(host=os.environ.get("RENOVISION_MCP_ADRES", "172.17.0.1"),
            port=int(os.environ.get("RENOVISION_MCP_POORT", "8110")),
            threaded=True)
