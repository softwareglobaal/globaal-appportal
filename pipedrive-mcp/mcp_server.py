"""MCP-server voor de vijf Pipedrive-accounts van de groep.

H-Architects, UNABO, TKN-Buro, Energie Efficiënt en HarmonieBOUW hebben elk een
eigen Pipedrive met een eigen token. Deze server maakt ze alle vijf bereikbaar
vanuit Claude, met een harde regel: **elke handeling hoort bij precies een
firma**. Elk stuk gereedschap heeft `firma` als verplichte parameter; ontbreekt
die, dan gebeurt er niets en komt er een weigering terug die de vijf keuzes
noemt, zodat de vraag bij de gebruiker terechtkomt. Er is geen standaardfirma,
en een firma uit een eerdere vraag telt niet door: dat is precies de fout die
een deal in de verkeerde administratie zou zetten.

Koppelen kan op twee manieren, allebei via OAuth en dus met de eigen SSO-login:
als aangepaste connector in claude.ai, of lokaal met
`claude mcp add --transport http pipedrive https://pipedrive-mcp.globaal.be/mcp`.
De OAuth-laag (dynamic client registration + PKCE, RFC 7591/8414/9728) is
overgenomen van renovision-mcp en het Vermogens-dashboard; de loginstap
/oauth/authorize staat ACHTER de Authentik forward-auth, dus SSO is de
authenticatie. De groepen van de ingelogde gebruiker gaan mee in het token en
bepalen of er ook geschreven mag worden (pipedrive-editors of admin); lezen mag
iedereen die door de forward-auth komt.

Draait als losse systemd-dienst op de host (172.17.0.1:8112), niet in een
container: er hoort geen app bij, alleen deze koppeling. De tokens komen uit
`~/appportal/.env` (dezelfde vijf die het sales-dashboard gebruikt), zodat een
rotatie maar op een plek hoeft.
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
from gereedschap import FIRMAS, Geweigerd, PipedriveFout

PROTOCOL_VERSIES = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "pipedrive", "title": "Pipedrive (vijf firma's)",
               "version": "1.0.0"}

CODE_TTL = 120            # autorisatiecode: 2 minuten
ACCESS_TTL = 12 * 3600    # access token: 12 uur
REFRESH_TTL = 60 * 86400  # refresh token: 60 dagen

SCHRIJFGROEPEN = ("pipedrive-editors", "admin")

app = Flask(__name__)


def _basis() -> str:
    return os.environ.get("MCP_BASIS") or "https://pipedrive-mcp.globaal.be"


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
    """Waar mag de autorisatiecode naartoe: Claude zelf, of de eigen machine.

    claude.ai in de browser stuurt terug naar een adres van Claude; Claude Code
    op een werkplek luistert op een willekeurige poort op localhost (RFC 8252).
    Die loopback-adressen komen het netwerk niet op, en PKCE plus de SSO-login
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
            "scopes_supported": ["pipedrive"]}


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
            "scopes_supported": ["pipedrive"]}


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
    return {"client_id": "pipedrive-claude",
            "client_name": body.get("client_name", "Claude"),
            "redirect_uris": uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"]}, 201


def _mag_schrijven(groepen: list[str]) -> bool:
    return any(g.strip().lower() in SCHRIJFGROEPEN for g in groepen)


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

    # Wie hier komt is al door Authentik heen; naam en groepen komen uit de
    # proxy-headers en worden in het token gebakken. Dit is het enige punt waar
    # 'wie ben je' en 'mag je schrijven' worden vastgesteld.
    wie = (request.headers.get("X-authentik-username") or "").strip()
    if not wie:
        return "Geen ingelogde gebruiker; log opnieuw in via het portaal.", 403
    groepen = [g for g in (request.headers.get("X-authentik-groups") or "").split("|") if g]

    code = _teken({"t": "code", "u": wie, "w": _mag_schrijven(groepen),
                   "ch": challenge, "r": redirect_uri,
                   "exp": int(time.time()) + CODE_TTL})
    sep = "&" if "?" in redirect_uri else "?"
    return redirect(redirect_uri + sep + urlencode(
        {"code": code, "state": request.args.get("state", "")}))


def _tokens_voor(payload: dict) -> dict:
    nu = int(time.time())
    kern = {"u": payload["u"], "w": bool(payload.get("w"))}
    return {"access_token": _teken({"t": "acc", **kern, "exp": nu + ACCESS_TTL}),
            "token_type": "Bearer", "expires_in": ACCESS_TTL,
            "refresh_token": _teken({"t": "ref", **kern, "exp": nu + REFRESH_TTL}),
            "scope": "pipedrive"}


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
# Elke beschrijving zegt het opnieuw: eerst de firma, en die wordt gevraagd,
# niet geraden. Claude leest deze teksten; het is de enige plek waar het
# gedrag "vraag het na" wordt afgesproken, naast de harde weigering in
# gereedschap.firma_kiezen.
KEUZES = ", ".join(f"{s} = {n}" for s, n in FIRMAS.items())
FIRMA_VELD = {
    "type": "string",
    "enum": list(FIRMAS),
    "description": ("VERPLICHT. In welke firma-administratie moet dit gebeuren: "
                    + KEUZES + ". Staat de firma niet in de opdracht van de "
                    "gebruiker, vraag het dan eerst; raad nooit en neem de "
                    "firma van een eerdere vraag niet automatisch over."),
}
LET_OP = (" Vraag de gebruiker eerst voor welke firma dit is als dat niet "
          "expliciet gezegd is.")
SCHRIJFT = (" Dit wijzigt gegevens in de Pipedrive van die firma; noem de firma "
            "in je bevestiging zodat de gebruiker ziet waar het geland is.")


def _schema(props: dict | None = None, verplicht: list | None = None) -> dict:
    p = {"firma": FIRMA_VELD, **(props or {})}
    return {"type": "object", "properties": p,
            "required": ["firma"] + (verplicht or [])}


_ID = {"type": "integer"}
_TXT = {"type": "string"}
_VELDEN = {"type": "object",
           "description": "Eigen velden als {veldnaam: waarde}; keuzevelden "
                          "accepteren het label. Zie het gereedschap 'velden'."}

TOOLS = [
    dict(name="firmas",
         description="De vijf firma's met hun sleutel, plus of het token werkt. "
                     "Begin hier als je niet zeker weet welke namen er zijn, of "
                     "als de gebruiker vraagt wat er beschikbaar is. Dit is het "
                     "enige gereedschap zonder firma-parameter.",
         inputSchema={"type": "object", "properties": {}}),
    dict(name="overzicht",
         description="De opzet van een firma: pijplijnen met hun fases, actieve "
                     "gebruikers, activiteittypes en het aantal open deals met "
                     "waarde. Handig als eerste stap voor je gaat filteren." + LET_OP,
         inputSchema=_schema()),
    dict(name="velden",
         description="De eigen (maatwerk-)velden van een firma voor deals, "
                     "personen of organisaties, met hun keuzes. Nodig om te "
                     "weten welke namen je in 'velden' kunt gebruiken." + LET_OP,
         inputSchema=_schema({"soort": {"type": "string",
                                        "enum": ["deal", "person", "organization"],
                                        "description": "standaard deal"}})),
    dict(name="zoeken",
         description="Zoeken door deals, personen, organisaties en leads van een "
                     "firma tegelijk. De snelste manier om iets terug te vinden "
                     "op naam, e-mailadres of telefoonnummer." + LET_OP,
         inputSchema=_schema({"term": _TXT,
                              "soorten": {"type": "string",
                                          "description": "beperken, bv. 'deal,person'"},
                              "exact": {"type": "boolean"},
                              "limiet": {"type": "integer"}}, ["term"])),
    dict(name="deals",
         description="Deals van een firma opsommen. Filter op status (open, won, "
                     "lost, alle), pijplijn, fase of eigenaar, of geef een "
                     "zoekterm. Standaard de open deals, laatst gewijzigd eerst." + LET_OP,
         inputSchema=_schema({"status": {"type": "string",
                                         "enum": ["open", "won", "lost", "alle"]},
                              "term": _TXT, "pijplijn_id": _ID, "fase_id": _ID,
                              "eigenaar_id": _ID,
                              "sorteer": {"type": "string",
                                          "description": "bv. update_time, value, expected_close_date"},
                              "oplopend": {"type": "boolean"},
                              "limiet": {"type": "integer"}})),
    dict(name="deal",
         description="Alles van een deal: waarde, fase, contact, producten, "
                     "eigen velden, de laatste notities en de openstaande "
                     "activiteiten, met een link naar Pipedrive." + LET_OP,
         inputSchema=_schema({"id": _ID}, ["id"])),
    dict(name="deal_geschiedenis",
         description="Het verloop van een deal: fasewissels, gewijzigde velden, "
                     "notities, activiteiten en mails, in tijdsvolgorde. "
                     "Hiermee beantwoord je 'wat is hier gebeurd'." + LET_OP,
         inputSchema=_schema({"id": _ID, "limiet": {"type": "integer"}}, ["id"])),
    dict(name="deal_aanmaken",
         description="Een nieuwe deal aanmaken." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"titel": _TXT, "waarde": {"type": "number"},
                              "valuta": _TXT, "persoon_id": _ID, "organisatie_id": _ID,
                              "pijplijn_id": _ID, "fase_id": _ID, "eigenaar_id": _ID,
                              "verwachte_sluiting": {"type": "string",
                                                     "description": "JJJJ-MM-DD"},
                              "velden": _VELDEN}, ["titel"])),
    dict(name="deal_bijwerken",
         description="Een bestaande deal wijzigen: waarde, fase, eigenaar, of "
                     "sluiten met status won/lost (bij lost hoort een "
                     "verliesreden)." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"id": _ID, "titel": _TXT, "waarde": {"type": "number"},
                              "valuta": _TXT, "fase_id": _ID, "pijplijn_id": _ID,
                              "eigenaar_id": _ID, "persoon_id": _ID, "organisatie_id": _ID,
                              "status": {"type": "string", "enum": ["open", "won", "lost"]},
                              "verliesreden": _TXT, "kans_pct": {"type": "integer"},
                              "verwachte_sluiting": _TXT, "velden": _VELDEN}, ["id"])),
    dict(name="personen",
         description="Contactpersonen van een firma zoeken of opsommen (met "
                     "'term' zoeken op naam, e-mail of telefoon)." + LET_OP,
         inputSchema=_schema({"term": _TXT, "organisatie_id": _ID,
                              "eigenaar_id": _ID, "limiet": {"type": "integer"}})),
    dict(name="persoon",
         description="Alles van een contactpersoon: contactgegevens, "
                     "organisatie, eigen velden, deals en laatste notities." + LET_OP,
         inputSchema=_schema({"id": _ID}, ["id"])),
    dict(name="persoon_aanmaken",
         description="Een nieuwe contactpersoon aanmaken." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"naam": _TXT,
                              "email": {"type": "string", "description": "een adres of een lijst"},
                              "telefoon": {"type": "string"},
                              "organisatie_id": _ID, "eigenaar_id": _ID,
                              "velden": _VELDEN}, ["naam"])),
    dict(name="persoon_bijwerken",
         description="Een contactpersoon wijzigen. E-mail en telefoon vervangen "
                     "de bestaande lijst." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"id": _ID, "naam": _TXT, "email": _TXT,
                              "telefoon": _TXT, "organisatie_id": _ID,
                              "eigenaar_id": _ID, "velden": _VELDEN}, ["id"])),
    dict(name="organisaties",
         description="Organisaties (bedrijven) van een firma zoeken of "
                     "opsommen." + LET_OP,
         inputSchema=_schema({"term": _TXT, "eigenaar_id": _ID,
                              "limiet": {"type": "integer"}})),
    dict(name="organisatie",
         description="Alles van een organisatie: adres, eigen velden, de "
                     "contactpersonen, de deals en de laatste notities." + LET_OP,
         inputSchema=_schema({"id": _ID}, ["id"])),
    dict(name="organisatie_aanmaken",
         description="Een nieuwe organisatie aanmaken." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"naam": _TXT, "adres": _TXT, "eigenaar_id": _ID,
                              "velden": _VELDEN}, ["naam"])),
    dict(name="organisatie_bijwerken",
         description="Een organisatie wijzigen." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"id": _ID, "naam": _TXT, "adres": _TXT,
                              "eigenaar_id": _ID, "velden": _VELDEN}, ["id"])),
    dict(name="activiteiten",
         description="Activiteiten (bellen, mailen, vergadering, taak) van een "
                     "firma. Zonder filter de openstaande van iedereen; filter "
                     "op deal, persoon, organisatie, eigenaar of periode." + LET_OP,
         inputSchema=_schema({"deal_id": _ID, "persoon_id": _ID, "organisatie_id": _ID,
                              "eigenaar_id": _ID,
                              "gedaan": {"type": "boolean",
                                         "description": "true = afgevinkt, false = open"},
                              "type": {"type": "string", "description": "bv. call, meeting, task"},
                              "van": {"type": "string", "description": "JJJJ-MM-DD"},
                              "tot": {"type": "string", "description": "JJJJ-MM-DD"},
                              "limiet": {"type": "integer"}})),
    dict(name="activiteit_aanmaken",
         description="Een activiteit inplannen bij een deal, persoon of "
                     "organisatie." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"onderwerp": _TXT,
                              "datum": {"type": "string", "description": "JJJJ-MM-DD"},
                              "tijd_utc": {"type": "string",
                                           "description": "UU:MM in UTC; leeg = hele dag"},
                              "duur": {"type": "string", "description": "UU:MM"},
                              "type": {"type": "string", "description": "bv. call, meeting, task"},
                              "deal_id": _ID, "persoon_id": _ID, "organisatie_id": _ID,
                              "eigenaar_id": _ID, "notitie": _TXT, "locatie": _TXT},
                             ["onderwerp", "datum"])),
    dict(name="activiteit_bijwerken",
         description="Een activiteit wijzigen of afvinken (gedaan=true)." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"id": _ID, "gedaan": {"type": "boolean"},
                              "onderwerp": _TXT, "datum": _TXT, "tijd_utc": _TXT,
                              "duur": _TXT, "eigenaar_id": _ID, "notitie": _TXT}, ["id"])),
    dict(name="notities",
         description="De notities bij een deal, persoon, organisatie of lead, "
                     "nieuwste eerst." + LET_OP,
         inputSchema=_schema({"deal_id": _ID, "persoon_id": _ID,
                              "organisatie_id": _ID, "lead_id": _TXT,
                              "limiet": {"type": "integer"}})),
    dict(name="notitie_aanmaken",
         description="Een notitie toevoegen aan een deal, persoon, organisatie "
                     "of lead." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"tekst": _TXT, "deal_id": _ID, "persoon_id": _ID,
                              "organisatie_id": _ID, "lead_id": _TXT,
                              "vastpinnen": {"type": "boolean"}}, ["tekst"])),
    dict(name="leads",
         description="De leads (nog geen deal) van een firma opsommen of "
                     "doorzoeken." + LET_OP,
         inputSchema=_schema({"term": _TXT, "eigenaar_id": _ID,
                              "gearchiveerd": {"type": "boolean"},
                              "limiet": {"type": "integer"}})),
    dict(name="lead_aanmaken",
         description="Een lead aanmaken bij een bestaande persoon of "
                     "organisatie." + LET_OP + SCHRIJFT,
         inputSchema=_schema({"titel": _TXT, "persoon_id": _ID, "organisatie_id": _ID,
                              "waarde": {"type": "number"}, "valuta": _TXT,
                              "eigenaar_id": _ID, "verwachte_sluiting": _TXT},
                             ["titel"])),
]


# ---- MCP: JSON-RPC over HTTP ---------------------------------------------
def _wie():
    """(gebruikersnaam, mag_schrijven) uit het bearer-token, of None."""
    kop = request.headers.get("Authorization", "")
    if not kop.startswith("Bearer "):
        return None
    token = kop[7:].strip()
    statisch = _statisch_token()
    if statisch and hmac.compare_digest(token, statisch):
        # Vaste sleutel voor beheer en voor Claude Code; volle rechten.
        return "akadmin", True
    p = _lees_token(token, "acc")
    return (p["u"], bool(p.get("w"))) if p else None


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
    beschikbaar = sorted(gs.tokens())
    return {"firmas": list(FIRMAS),
            "tokens_aanwezig": beschikbaar,
            "tokens_ontbreken": sorted(set(FIRMAS) - set(beschikbaar))}


@app.post("/mcp")
def mcp():
    if not _statisch_token() and not _secret():
        return {"fout": "MCP staat uit"}, 404
    wie = _wie()
    if wie is None:
        kop = ('Bearer resource_metadata='
               f'"{_basis()}/.well-known/oauth-protected-resource/mcp"')
        return {"fout": "Ongeldig of ontbrekend token"}, 401, \
               {"WWW-Authenticate": kop}
    gebruiker, mag_schrijven = wie

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
            "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO,
            "instructions":
                "Vijf gescheiden Pipedrive-administraties: "
                + KEUZES + ". Elke opdracht hoort bij precies een firma en elk "
                "stuk gereedschap heeft daarvoor de verplichte parameter "
                "'firma'. Zegt de gebruiker niet welke firma bedoeld is, vraag "
                "het dan expliciet voordat je iets ophaalt of wijzigt; kies "
                "nooit zelf en houd de firma uit een vorige vraag niet vast. "
                "Noem in je antwoord altijd om welke firma het ging."})
    if methode == "ping":
        return _resultaat(rid, {})
    if methode == "tools/list":
        return _resultaat(rid, {"tools": TOOLS})
    if methode != "tools/call":
        return _fout(rid, -32601, f"Onbekende methode: {methode}")

    naam = params.get("name", "")
    try:
        uit = gs.voer_uit(naam, params.get("arguments") or {}, mag_schrijven)
        return _resultaat(rid, {
            "content": [{"type": "text",
                         "text": json.dumps(uit, ensure_ascii=False, default=str)}],
            "isError": False})
    except Geweigerd as e:
        return _tekst(rid, str(e), True)
    except PipedriveFout as e:
        return _tekst(rid, f"Pipedrive weigerde dit ({e.status}): {e}"
                           + (f" [{e.info}]" if e.info else ""), True)
    except Exception as e:  # noqa: BLE001 - Claude moet de fout kunnen lezen
        app.logger.exception("gereedschap %s faalde (gebruiker %s)", naam, gebruiker)
        return _tekst(rid, f"Fout: {type(e).__name__}: {e}", True)


if __name__ == "__main__":
    # Binden op de docker-brug, niet op 0.0.0.0: alleen nginx (in een
    # container) hoeft erbij, en zo staat het niet open op het internet.
    # Zelfde keuze als renovision-mcp (8110) en de Schuldentracker (5050).
    app.run(host=os.environ.get("PIPEDRIVE_MCP_ADRES", "172.17.0.1"),
            port=int(os.environ.get("PIPEDRIVE_MCP_POORT", "8112")),
            threaded=True)
