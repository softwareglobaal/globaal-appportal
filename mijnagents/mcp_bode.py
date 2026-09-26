"""MCP-endpoint voor Mehdi's Claude: "roep Mehdi" als een agent vastzit.

Mehdi, 25-09-2026: Claude weet wat er moet gebeuren, maar stopt bij een stap die
alleen hij mag doen (paspoort, bankgegevens, een login, een beslissing). Dan
wacht Claude in stilte, Mehdi merkt het pas later, de sessie is verlopen en
alles begint opnieuw. Deze koppeling laat Claude hem op dat moment bellen, van
het vastzit-nummer (TWILIO_VAN_VAST), met een zin: wat en waar. Hetzelfde
bericht komt op Telegram, zodat hij het ook kan nalezen.

Mantel en OAuth zijn die van de Postbus (post/mcp_server.py): claude.ai koppelt
als custom connector op https://mijnagents.<domein>/mcp, de login is de
Authentik-SSO. Stateless HMAC-tokens (env MIJNAGENTS_MCP_SECRET in
mijnagents-data/.env). Zonder dat geheim staat alles uit (404).

Wie mag bellen: de gebruikersnamen in MIJNAGENTS_MCP_GEBRUIKERS (standaard
mehdi) en de groep admin (om te testen). Grenzen in de code: tussen 07:00 en
22:00 Belgische tijd (daarbuiten alleen Telegram), hooguit een oproep per 2
minuten, en dezelfde zin geen twee keer binnen 30 minuten.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from urllib.parse import urlencode, urlparse
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from flask import redirect, request

PROTOCOL_VERSIES = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "mehdi-agents", "title": "Mehdi Agents: Mehdi roepen als je vastzit", "version": "1.0.0"}

AANVRAAG_TTL = 600
AANVRAAG_KOEK = "mijnagents_aanvraag"
CODE_TTL = 120
ACCESS_TTL = 12 * 3600
REFRESH_TTL = 60 * 86400

BE = ZoneInfo("Europe/Brussels")
BEL_UREN = (7, 22)             # alleen bellen tussen 07:00 en 22:00 Belgische tijd
MIN_TUSSEN_OPROEPEN = 120      # seconden
ZELFDE_ZIN_BLOK = 30 * 60      # seconden
VAGE_ZINNEN = ("dringend signaal", "details op het bord", "kijk op het bord", "er is iets", "ik zit vast")

INSTRUCTIES = (
    "Deze server heeft een tool: roep_mehdi. Gebruik hem alleen als je vastzit op een stap die alleen "
    "Mehdi zelf kan doen: gevoelige gegevens invullen (paspoort, bankrekening, wachtwoord), inloggen, "
    "betalen, of een beslissing nemen. Zet eerst ALLES klaar tot die ene stap: formulier ingevuld, mail "
    "als concept met bijlage, venster open. Roep daarna Mehdi. De tool belt hem meteen van het "
    "vastzit-nummer en zet hetzelfde op Telegram. "
    "'wat' is de actie in een korte zin (bv. 'Flying Blue wacht op je paspoortnummer'); 'waar' zegt waar "
    "het klaarstaat (bv. 'het formulier staat open in Chrome'). Nooit vaag ('er is een dringend signaal'), "
    "nooit een statusmelding, en een oproep per blokkade. Geef in 'context' kort mee wat je al deed en welke "
    "keuzes er zijn: Mehdi kan aan de telefoon terugpraten en doorvragen. Controleer daarna met oproep_status "
    "of hij opnam; staat er 'antwoord_van_mehdi', voer dat uit. Wacht anders tot hij de stap gedaan heeft en ga "
    "verder. Laat de sessie open staan."
)


def _basis():
    return "https://mijnagents." + os.environ.get("BASE_DOMAIN", "globaal.be")


def _secret():
    return os.environ.get("MIJNAGENTS_MCP_SECRET", "").strip().encode()


def _toegestaan(naam, groepen):
    namen = {n.strip().lower() for n in os.environ.get("MIJNAGENTS_MCP_GEBRUIKERS", "mehdi").split(",") if n.strip()}
    return (naam or "").lower() in namen or "admin" in {str(g).lower() for g in groepen}


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _teken(payload):
    raw = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return raw + "." + _b64(hmac.new(_secret(), raw.encode(), hashlib.sha256).digest())


def _lees(token, soort):
    if not _secret() or "." not in (token or ""):
        return None
    raw, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _b64(hmac.new(_secret(), raw.encode(), hashlib.sha256).digest())):
        return None
    try:
        p = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:  # noqa: BLE001
        return None
    if p.get("t") != soort or p.get("exp", 0) < time.time():
        return None
    return p


def _redirect_ok(uri):
    try:
        p = urlparse(uri)
    except Exception:  # noqa: BLE001
        return False
    host = (p.hostname or "").lower()
    if p.scheme == "http" and host in ("localhost", "127.0.0.1"):
        return True
    basis = ("claude.ai", "claude.com", "anthropic.com")
    return p.scheme == "https" and (host in basis or host.endswith(tuple("." + b for b in basis)))


def _log(wie, boodschap):
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} mcp-bode {wie}: {boodschap}", file=sys.stdout, flush=True)


# ---------------------------------------------------------------- bellen ---
def _e(n):
    return os.environ.get(n, "").strip()


def _twilio(pad, data=None):
    gebruiker, geheim = (_e("TWILIO_API_KEY_SID"), _e("TWILIO_API_KEY_SECRET")) if _e("TWILIO_API_KEY_SID") \
        else (_e("TWILIO_ACCOUNT_SID"), _e("TWILIO_AUTH_TOKEN"))
    url = f"https://api.twilio.com/2010-04-01/Accounts/{_e('TWILIO_ACCOUNT_SID')}/{pad}"
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode() if data else None,
                                 {"Authorization": "Basic " + base64.b64encode(f"{gebruiker}:{geheim}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _telegram(tekst):
    tok, chat = _e("TELEGRAM_BOT_TOKEN"), _e("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                 json.dumps({"chat_id": chat, "text": tekst[:3900]}).encode(),
                                 {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20):
            return True
    except Exception:  # noqa: BLE001
        return False


def _zin(wat, waar):
    wat = re.sub(r"\s+", " ", str(wat or "")).strip().rstrip(".")
    waar = re.sub(r"\s+", " ", str(waar or "")).strip().rstrip(".")
    if len(wat) < 12:
        raise ValueError("'wat' is te kort: zeg in een zin welke actie Mehdi moet doen, bv. "
                         "'Flying Blue wacht op je paspoortnummer'.")
    if any(v in wat.lower() for v in VAGE_ZINNEN) and len(wat) < 60:
        raise ValueError("'wat' is te vaag. Zeg welke actie, voor wie of wat, bv. "
                         "'Flying Blue wacht op je paspoortnummer'.")
    if not waar:
        raise ValueError("'waar' ontbreekt: zeg waar het klaarstaat, bv. 'het formulier staat open in Chrome'.")
    if wat.split()[0] in ("De", "Het", "Een", "Je", "Jouw"):   # "Mehdi, de bank ..." i.p.v. "Mehdi, De bank ..."
        wat = wat[0].lower() + wat[1:]
    zin = f"Mehdi, {wat}. {waar[0].upper() + waar[1:]}."
    if len(zin) > 260:
        raise ValueError("De zin is te lang om voor te lezen (max ongeveer 250 tekens). Kort hem in.")
    return zin


STEM_URL = os.environ.get("MIJNAGENTS_STEM_URL", "http://app-mijnagents-stem:3040")


def _stem_klaar():
    """De spraakserver draait en heeft een OpenAI-sleutel. Zo niet: voorlezen zoals voorheen."""
    try:
        with urllib.request.urlopen(STEM_URL + "/gezond", timeout=2) as r:
            return bool(json.load(r).get("sleutel"))
    except Exception:  # noqa: BLE001
        return False


def _stem_teken(gid):
    return hmac.new(_secret(), f"stem:{gid}".encode(), hashlib.sha256).hexdigest()[:32]


def _stemgesprek(conn, zin, context, wie):
    conn.execute("""CREATE TABLE IF NOT EXISTS stemgesprek (
        id INTEGER PRIMARY KEY AUTOINCREMENT, zin TEXT NOT NULL, context TEXT DEFAULT '', wie TEXT DEFAULT '',
        twilio_sid TEXT DEFAULT '', status TEXT DEFAULT 'gepland', antwoord TEXT DEFAULT '',
        verslag TEXT DEFAULT '', ts TEXT NOT NULL, ts_eind TEXT DEFAULT '')""")
    cur = conn.execute("INSERT INTO stemgesprek(zin, context, wie, ts) VALUES(?,?,?,?)",
                       (zin, context, wie, datetime.now().astimezone().isoformat()))
    conn.commit()
    return cur.lastrowid


def registreer(app, gebruiker, groepen_van_verzoek, db, nu):
    """Hang /mcp en de OAuth-endpoints aan de Flask-app van mijnagents."""

    tools = [
        dict(name="roep_mehdi",
             description="Belt Mehdi METEEN van het vastzit-nummer en zet hetzelfde op Telegram. Alleen als je "
                         "vastzit op een stap die alleen hij kan doen (gevoelige gegevens, inloggen, betalen, een "
                         "beslissing), NADAT je al het andere hebt klaargezet. De oproep leest voor: "
                         "'Mehdi, <wat>. <waar>.'",
             inputSchema={"type": "object", "properties": {
                 "wat": {"type": "string", "description": "de actie die Mehdi moet doen, in een korte zin"},
                 "waar": {"type": "string", "description": "waar het klaarstaat (venster, mailconcept, map)"},
                 "context": {"type": "string", "description": "optioneel: achtergrond voor de stem als Mehdi "
                             "doorvraagt (wat je al gedaan hebt, welke keuzes er zijn). Geen gevoelige gegevens."}},
                 "required": ["wat", "waar"]}),
        dict(name="oproep_status",
             description="Status van een oproep van roep_mehdi: queued, ringing, in-progress, completed "
                         "(opgenomen), busy/no-answer (niet opgenomen), failed.",
             inputSchema={"type": "object", "properties": {"sid": {"type": "string"}}, "required": ["sid"]}),
    ]

    def _laatste(conn):
        r = conn.execute("SELECT tekst, detail, ts FROM logboek WHERE naam='bode' AND stap='roep' ORDER BY id DESC LIMIT 20").fetchall()
        return r

    def t_roep(wie, args):
        zin = _zin(args.get("wat"), args.get("waar"))
        conn = db()
        nu_ts = time.time()
        for r in _laatste(conn):
            try:
                oud = datetime.fromisoformat(r["ts"]).timestamp()
            except ValueError:
                continue
            if nu_ts - oud < MIN_TUSSEN_OPROEPEN:
                raise ValueError("Er is minder dan 2 minuten geleden al een oproep gedaan. Wacht op Mehdi; "
                                 "controleer met oproep_status of hij opnam.")
            if r["detail"] == zin and nu_ts - oud < ZELFDE_ZIN_BLOK:
                raise ValueError("Deze zin is in het laatste half uur al doorgegeven. Niet opnieuw bellen.")
        uur = datetime.now(BE).hour
        tg = _telegram(f"Een agent zit vast en heeft je nodig:\n\n{zin}\n\n(via Claude, {wie})")
        uit = {"zin": zin, "telegram": "verstuurd" if tg else "niet verstuurd"}
        if not (BEL_UREN[0] <= uur < BEL_UREN[1]):
            uit.update({"gebeld": False, "reden": f"buiten de beluren ({BEL_UREN[0]}:00 tot {BEL_UREN[1]}:00 "
                                                  "Belgische tijd): alleen Telegram"})
        elif not (_e("TWILIO_ACCOUNT_SID") and _e("ALARM_NUMMER") and (_e("TWILIO_VAN_VAST") or _e("TWILIO_VAN"))):
            uit.update({"gebeld": False, "reden": "Twilio staat niet ingesteld op de server"})
        else:
            # Met de stem (mijnagents-stem, OpenAI Realtime) kan Mehdi terugpraten; is die er niet, dan
            # leest Twilio de zin voor zoals voorheen.
            gid = _stemgesprek(conn, zin, str(args.get("context") or "")[:1500], wie) if _stem_klaar() else None
            if gid:
                twiml = ('<Response><Connect><Stream url="' + _basis().replace("https://", "wss://") + '/stem/ws">'
                         f'<Parameter name="g" value="{gid}"/><Parameter name="t" value="{_stem_teken(gid)}"/>'
                         '</Stream></Connect></Response>')
            else:
                t = escape(zin)
                twiml = ('<Response><Pause length="1"/>'
                         f'<Say language="nl-NL" voice="Polly.Lotte">{t}</Say><Pause length="1"/>'
                         f'<Say language="nl-NL" voice="Polly.Lotte">Ik herhaal. {t}</Say>'
                         '<Say language="nl-NL" voice="Polly.Lotte">Het staat ook op Telegram.</Say></Response>')
            try:
                c = _twilio("Calls.json", {"To": _e("ALARM_NUMMER"), "From": _e("TWILIO_VAN_VAST") or _e("TWILIO_VAN"),
                                           "Twiml": twiml, "Timeout": "25"})
                uit.update({"gebeld": True, "sid": c.get("sid", ""), "van": _e("TWILIO_VAN_VAST") or _e("TWILIO_VAN"),
                            "gesprek": "Mehdi kan terugpraten" if gid else "alleen voorgelezen"})
                if gid:
                    conn.execute("UPDATE stemgesprek SET twilio_sid=?, status='gebeld' WHERE id=?", (c.get("sid", ""), gid))
            except urllib.error.HTTPError as e:
                uit.update({"gebeld": False, "reden": f"Twilio weigerde ({e.code})"})
        conn.execute("INSERT INTO logboek(naam, onderwerp, stap, tekst, detail, ts) VALUES(?,?,?,?,?,?)",
                     ("bode", "Mehdi geroepen", "roep",
                      f"{wie} roept Mehdi: {'gebeld' if uit.get('gebeld') else 'niet gebeld'}, "
                      f"Telegram {uit['telegram']}", zin, nu()))
        conn.commit()
        _log(wie, f"ROEP {'gebeld' if uit.get('gebeld') else 'niet gebeld'}: {zin}")
        uit["volgende_stap"] = ("Controleer over een halve minuut met oproep_status of hij opnam. Laat de sessie "
                                "open en wacht tot Mehdi de stap gedaan heeft.")
        return uit

    def t_status(wie, args):
        sid = str(args.get("sid") or "")
        if not re.fullmatch(r"CA[0-9a-f]{32}", sid):
            raise ValueError("Geen geldige oproep-sid (begint met CA).")
        s = _twilio(f"Calls/{sid}.json").get("status", "")
        betekenis = {"completed": "opgenomen", "busy": "weggedrukt of bezet", "no-answer": "niet opgenomen",
                     "failed": "mislukt", "canceled": "geannuleerd"}.get(s, "nog bezig")
        uit = {"status": s, "betekenis": betekenis}
        try:
            r = db().execute("SELECT status, antwoord FROM stemgesprek WHERE twilio_sid=?", (sid,)).fetchone()
        except Exception:  # noqa: BLE001  (tabel bestaat nog niet)
            r = None
        if r:
            uit["gesprek"] = r["status"]
            if r["antwoord"]:
                uit["antwoord_van_mehdi"] = r["antwoord"]
                uit["volgende_stap"] = "Voer dit antwoord uit. Is het onduidelijk, vraag het Mehdi in de chat."
        return uit

    handlers = {"roep_mehdi": t_roep, "oproep_status": t_status}

    # ---- OAuth (zelfde opbouw als de Postbus) ----------------------------
    def _as_metadata():
        b = _basis()
        return {"issuer": b, "authorization_endpoint": b + "/oauth/authorize", "token_endpoint": b + "/mcp/token",
                "registration_endpoint": b + "/mcp/register", "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["none"],
                "scopes_supported": ["mijnagents"]}

    @app.get("/.well-known/oauth-authorization-server")
    @app.get("/.well-known/oauth-authorization-server/mcp")
    @app.get("/.well-known/openid-configuration")
    def mcp_as_metadata():
        if not _secret():
            return {"fout": "OAuth staat uit"}, 404
        return _as_metadata()

    @app.get("/.well-known/oauth-protected-resource")
    @app.get("/.well-known/oauth-protected-resource/mcp")
    def mcp_pr_metadata():
        if not _secret():
            return {"fout": "OAuth staat uit"}, 404
        b = _basis()
        return {"resource": b + "/mcp", "authorization_servers": [b], "bearer_methods_supported": ["header"],
                "scopes_supported": ["mijnagents"]}

    @app.post("/mcp/register")
    def mcp_register():
        if not _secret():
            return {"fout": "OAuth staat uit"}, 404
        body = request.get_json(silent=True) or {}
        uris = body.get("redirect_uris") or []
        if not uris or not all(_redirect_ok(u) for u in uris):
            return {"error": "invalid_redirect_uri", "error_description": "Alleen redirects naar Claude of localhost"}, 400
        return {"client_id": "mijnagents-claude", "client_name": body.get("client_name", "Claude"),
                "redirect_uris": uris, "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}, 201

    @app.get("/oauth/authorize")
    def mcp_oauth_authorize():
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
        bon = _teken({"t": "aanvraag", "ch": challenge, "r": redirect_uri, "s": request.args.get("state", ""),
                      "exp": int(time.time()) + AANVRAAG_TTL})
        antwoord = redirect("/oauth/inloggen")
        antwoord.set_cookie(AANVRAAG_KOEK, bon, max_age=AANVRAAG_TTL, secure=True, httponly=True,
                            samesite="Lax", path="/oauth")
        return antwoord

    @app.get("/oauth/inloggen")
    def mcp_oauth_inloggen():
        if not _secret():
            return {"fout": "OAuth staat uit"}, 404
        p = _lees(request.cookies.get(AANVRAAG_KOEK, ""), "aanvraag")
        if not p:
            return "De koppeling is verlopen of het venster stond te lang open. Begin opnieuw vanuit Claude.", 400
        naam = gebruiker()
        groepen = sorted(groepen_van_verzoek())
        if not naam or naam == "?":
            return f"Geen Authentik-identiteit gevonden. Log eerst in op {_basis()} en probeer opnieuw.", 403
        if not _toegestaan(naam, groepen):
            return "Deze koppeling is alleen voor Mehdi.", 403
        code = _teken({"t": "code", "u": naam, "g": groepen, "ch": p["ch"], "r": p["r"],
                       "exp": int(time.time()) + CODE_TTL})
        _log(naam, "koppelt een connector")
        sep = "&" if "?" in p["r"] else "?"
        antwoord = redirect(p["r"] + sep + urlencode({"code": code, "state": p.get("s", "")}))
        antwoord.delete_cookie(AANVRAAG_KOEK, path="/oauth")
        return antwoord

    def _tokens_voor(p):
        n = int(time.time())
        return {"access_token": _teken({"t": "acc", "u": p["u"], "g": p["g"], "exp": n + ACCESS_TTL}),
                "token_type": "Bearer", "expires_in": ACCESS_TTL,
                "refresh_token": _teken({"t": "ref", "u": p["u"], "g": p["g"], "exp": n + REFRESH_TTL}),
                "scope": "mijnagents"}

    @app.post("/mcp/token")
    def mcp_token():
        if not _secret():
            return {"fout": "OAuth staat uit"}, 404
        soort = request.form.get("grant_type", "")
        if soort == "authorization_code":
            p = _lees(request.form.get("code", ""), "code")
            if not p:
                return {"error": "invalid_grant", "error_description": "Code ongeldig of verlopen"}, 400
            digest = hashlib.sha256(request.form.get("code_verifier", "").encode()).digest()
            if not hmac.compare_digest(_b64(digest), p["ch"]):
                return {"error": "invalid_grant", "error_description": "PKCE-verificatie faalt"}, 400
            terug = request.form.get("redirect_uri", "")
            if terug and terug != p["r"]:
                return {"error": "invalid_grant", "error_description": "redirect_uri wijkt af"}, 400
            return _tokens_voor(p)
        if soort == "refresh_token":
            p = _lees(request.form.get("refresh_token", ""), "ref")
            if not p:
                return {"error": "invalid_grant", "error_description": "Refresh token ongeldig of verlopen"}, 400
            return _tokens_voor(p)
        return {"error": "unsupported_grant_type"}, 400

    # ---- MCP: JSON-RPC over HTTP ------------------------------------------
    def _auth():
        kop = request.headers.get("Authorization", "")
        if not kop.startswith("Bearer "):
            return None
        p = _lees(kop[7:].strip(), "acc")
        if p and _toegestaan(p["u"], p.get("g") or []):
            return p["u"]
        return None

    @app.get("/mcp")
    def mcp_get():
        return "", 405

    @app.post("/mcp")
    def mcp_post():
        if not _secret():
            return {"fout": "MCP staat uit"}, 404
        wie = _auth()
        if wie is None:
            return {"fout": "Ongeldig of ontbrekend token"}, 401, \
                {"WWW-Authenticate": f'Bearer resource_metadata="{_basis()}/.well-known/oauth-protected-resource/mcp"'}
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Geen geldige JSON-RPC-request"}}
        methode, rid, params = body.get("method", ""), body.get("id"), body.get("params") or {}
        if methode.startswith("notifications/"):
            return "", 202
        if methode == "initialize":
            pv = params.get("protocolVersion")
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": pv if pv in PROTOCOL_VERSIES else PROTOCOL_VERSIES[0],
                "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO, "instructions": INSTRUCTIES}}
        if methode == "ping":
            return {"jsonrpc": "2.0", "id": rid, "result": {}}
        if methode == "tools/list":
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}
        if methode == "tools/call":
            naam = params.get("name", "")
            handler = handlers.get(naam)
            if not handler:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"Onbekende tool: {naam}"}}
            try:
                uit = handler(wie, params.get("arguments") or {})
                return {"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": json.dumps(uit, ensure_ascii=False, default=str)}], "isError": False}}
            except ValueError as e:
                return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": str(e)}], "isError": True}}
            except Exception as e:  # noqa: BLE001
                _log(wie, f"FOUT in {naam}: {type(e).__name__}: {e}")
                return {"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": f"Fout: {type(e).__name__}"}], "isError": True}}
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Onbekende methode: {methode}"}}
