"""MCP-server voor het boek: zoeken en lezen vanuit een MCP-client.

Model Context Protocol over streamable HTTP, in de stateless JSON-variant: de
client POST een JSON-RPC-bericht naar /mcp en krijgt het antwoord als gewone
JSON terug. Geen SSE-stroom en geen sessies; voor een read-only zoekdienst is
dat de hele behoefte, en elke gangbare client (Claude Code, Claude Desktop)
kan ermee overweg.

Toegang. De rest van de vitrine zit achter de forward-auth van de portal, maar
een MCP-client kan niet door een browserlogin heen. Daarom passeert /mcp de
SSO in nginx (hetzelfde patroon als /agent-status op de agents-tegel) en
controleert deze module zelf een Bearer-token uit de omgeving. Staat er geen
token ingesteld, dan staat de hele route uit; een vergeten variabele mag nooit
een open deur zijn.

Alles hier is lezen: zoeken, een fragment ophalen, een bladzijde ophalen en de
metingen opvragen. Er bestaat geen schrijvend gereedschap, dus het ergste dat
een gelekt token kan doen is het boek doorzoeken.
"""
from __future__ import annotations

import base64
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

from flask import Blueprint, Response, request

PROTOCOLVERSIES = {"2024-11-05", "2025-03-26", "2025-06-18"}
NIEUWSTE = "2025-06-18"

mcp = Blueprint("mcp", __name__)


def _token() -> str:
    return (os.environ.get("MCP_TOKEN") or "").strip()


# ---------------------------------------------------------------- OAuth
# De volwaardige route: claude.ai (of elke MCP-client) doorloopt de gewone
# Authentik-login en -autorisatie, en biedt hier het verkregen access-token
# aan. Wij vragen Authentik via introspectie of het token echt leeft en bij
# onze client hoort. Zo bepaalt Authentik wie toegang heeft (de bindings op de
# applicatie boek-mcp: mehdi en akadmin), niet een gedeeld geheim.

RESOURCE = os.environ.get("RESOURCE_URL", "https://boek.globaal.be")
ISSUER = os.environ.get("OAUTH_ISSUER",
                        "https://auth.globaal.be/application/o/boek-mcp/")
INTROSPECT = os.environ.get(
    "OAUTH_INTROSPECT_URL",
    "http://authentik-server:9000/application/o/introspect/")
CLIENT_ID = (os.environ.get("OAUTH_CLIENT_ID") or "").strip()
CLIENT_SECRET = (os.environ.get("OAUTH_CLIENT_SECRET") or "").strip()

# Kort cachen zodat niet elk gereedschapsgebruik een introspectie-rondgang
# kost. Kort genoeg dat een ingetrokken token binnen een minuut echt dood is.
_introspectie_cache: dict[str, float] = {}
_CACHE_SECONDEN = 60


def _oauth_geldig(token: str) -> bool:
    if not (CLIENT_ID and CLIENT_SECRET and token):
        return False
    nu = time.time()
    tot = _introspectie_cache.get(token)
    if tot and tot > nu:
        return True
    try:
        req = urllib.request.Request(
            INTROSPECT,
            data=urllib.parse.urlencode({"token": token}).encode(),
            method="POST")
        basis = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        req.add_header("Authorization", f"Basic {basis}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
    except Exception:                                          # noqa: BLE001
        return False
    if not d.get("active"):
        _introspectie_cache.pop(token, None)
        return False
    verloop = min(nu + _CACHE_SECONDEN, float(d.get("exp") or nu + _CACHE_SECONDEN))
    _introspectie_cache[token] = verloop
    if len(_introspectie_cache) > 500:
        for k in [k for k, v in _introspectie_cache.items() if v <= nu]:
            _introspectie_cache.pop(k, None)
    return True


def _toegestaan() -> bool:
    """Bearer uit de Authorization-header: het vaste ops-token, of een
    OAuth-token van Authentik (geverifieerd via introspectie).

    Er is bewust GEEN token-in-de-URL-variant: toegang hoort via de
    Authentik-login te lopen, zodat de bindings op de applicatie bepalen wie
    erin kan. Vergelijking in vaste tijd; een gewone == lekt via de
    responstijd hoeveel tekens er al goed waren.
    """
    verwacht = _token()
    kop = request.headers.get("Authorization", "")
    if not kop.startswith("Bearer "):
        return False
    aangeboden = kop[7:].strip()
    if verwacht and hmac.compare_digest(aangeboden, verwacht):
        return True
    return _oauth_geldig(aangeboden)


def _rpc_fout(id_, code: int, boodschap: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_,
            "error": {"code": code, "message": boodschap}}


def _tekst(inhoud: str) -> dict:
    return {"content": [{"type": "text", "text": inhoud}], "isError": False}


# ---------------------------------------------------------------- gereedschap

GEREEDSCHAP = [
    {
        "name": "zoek_in_boek",
        "description": (
            "Doorzoek het boek 'Niet-vergunde constructies, tussen gedogen en "
            "regulariseren' (Vlaams omgevingsrecht, 383 blz). Hybride zoeken: "
            "woordelijke treffers en betekenis samen. Elke treffer draagt zijn "
            "gedrukte bladzijde, hoofdstuk en sectie, plus een fragment_id om "
            "het hele fragment op te halen."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vraag": {"type": "string",
                          "description": "De vraag of zoektermen, in gewone taal."},
                "aantal": {"type": "integer", "minimum": 1, "maximum": 20,
                           "description": "Hoeveel treffers (standaard 5)."},
            },
            "required": ["vraag"],
        },
    },
    {
        "name": "lees_fragment",
        "description": ("Haal één fragment volledig op, met bladzijde, "
                        "hoofdstuk en sectie. Het fragment_id komt uit "
                        "zoek_in_boek of lees_bladzijde."),
        "inputSchema": {
            "type": "object",
            "properties": {"fragment_id": {"type": "integer"}},
            "required": ["fragment_id"],
        },
    },
    {
        "name": "lees_bladzijde",
        "description": ("Alle fragmenten van één gedrukte bladzijde, in "
                        "leesvolgorde. Handig om een passage in zijn context "
                        "te lezen of een voetnoot bij de hoofdtekst te vinden."),
        "inputSchema": {
            "type": "object",
            "properties": {"bladzijde": {"type": "integer",
                                         "description": "Het gedrukte paginanummer."}},
            "required": ["bladzijde"],
        },
    },
    {
        "name": "wat_ontbreekt",
        "description": (
            "De bekende gaten en voorbehouden van deze kennisbank: welke "
            "inhoudsopgave-titels niet op hun verwachte bladzijde zijn "
            "teruggevonden, welke gedrukte bladzijden geen fragmenten hebben "
            "(met de duiding of dat een blanco pagina is of een echt gat), "
            "wat er bewust is uitgesloten, en de vaste kanttekening over de "
            "OCR. Gebruik dit als iemand vraagt of de verwerking volledig is."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "boek_info",
        "description": ("Titel, omvang en de kwaliteitsmetingen van deze "
                        "kennisbank (inhoudsopgave-verificatie, dekking, "
                        "rookproef), plus hoe de resultaten tot stand kwamen."),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _treffer_naar_tekst(t) -> str:
    plek = f"blz {t.gedrukt}" if t.gedrukt else f"scan {t.fysiek}"
    if getattr(t, "randnummer", None):
        plek = f"nr {t.randnummer}, {plek}"
    kop = " › ".join(x for x in (t.hoofdstuk, t.sectie) if x)
    via = []
    if t.woord_rang:
        via.append(f"woorden #{t.woord_rang}")
    if t.vector_rang:
        via.append(f"betekenis #{t.vector_rang}")
    tekst = t.tekst if len(t.tekst) <= 1400 else t.tekst[:1400] + " …[afgekapt]"
    return (f"[{plek} | {t.soort} | fragment {t.fragment_id} | {' + '.join(via)}]\n"
            f"{kop}\n{tekst}")


def _doe_zoek(bank, args: dict) -> dict:
    vraag = (args.get("vraag") or "").strip()
    if not vraag:
        return _tekst("Geen vraag opgegeven.")
    k = max(1, min(int(args.get("aantal") or 5), 20))
    treffers = bank.zoek(vraag, k=k)
    if not treffers:
        return _tekst("Niets gevonden.")
    delen = [f"{len(treffers)} treffers voor: {vraag}\n"]
    delen += [_treffer_naar_tekst(t) for t in treffers]
    return _tekst("\n\n---\n\n".join(delen))


def _doe_fragment(bank, args: dict) -> dict:
    f = bank.fragment(int(args.get("fragment_id") or 0))
    if not f:
        return _tekst("Dit fragment bestaat niet.")
    plek = f"blz {f['gedrukt']}" if f.get("gedrukt") else f"scan {f['fysiek']}"
    if f.get("randnummer"):
        plek = f"nr {f['randnummer']}, {plek}"
    kop = " › ".join(x for x in (f.get("hoofdstuk"), f.get("sectie")) if x)
    return _tekst(f"[{plek} | {f['soort']} | fragment {f['id']}]\n{kop}\n\n{f['tekst']}")


def _doe_bladzijde(bank, args: dict) -> dict:
    nr = int(args.get("bladzijde") or 0)
    rijen = [dict(r) for r in bank.db.execute(
        "SELECT * FROM fragment WHERE gedrukt=? ORDER BY volgnummer", (nr,))]
    if not rijen:
        return _tekst(f"Geen fragmenten met gedrukt paginanummer {nr}. "
                      "Het voorwerk (romeinse nummering) heeft geen gedrukt "
                      "nummer; de arabische telling begint bij 1.")
    delen = [f"Bladzijde {nr}: {len(rijen)} fragmenten\n"]
    for f in rijen:
        delen.append(f"[{f['soort']} | fragment {f['id']}] "
                     f"{f.get('sectie') or ''}\n{f['tekst']}")
    return _tekst("\n\n---\n\n".join(delen))


ONTBREEKT_PAD = os.environ.get("ONTBREEKT_PAD", "/data/ontbreekt.json")


def _doe_ontbreekt() -> dict:
    from pathlib import Path as _P
    pad = _P(ONTBREEKT_PAD)
    if not pad.exists():
        return _tekst("Er is geen gaten-overzicht beschikbaar voor dit boek.")
    d = json.loads(pad.read_text(encoding="utf-8"))
    regels = [
        "BEKENDE GATEN EN VOORBEHOUDEN",
        "",
        f"Inhoudsopgave-verificatie: {round(d['trefkans'] * 100)}% — "
        f"{len(d['niet_geverifieerde_ingangen'])} van de {d['ingangen_totaal']} "
        "ingangen zijn NIET op hun geijkte bladzijde teruggevonden. Vaak zijn "
        "dat korte titels (zoals '§ 1. Algemeen') die alleen tegen de "
        "titelblokken zijn getoetst; de inhoud kan er alsnog staan. De lijst:",
        "",
    ]
    for m in d["niet_geverifieerde_ingangen"]:
        regels.append(f"  - blz {m['gedrukt']:>3}: {m['titel']}")
    if "randnummer_gaten" in d:
        g = d["randnummer_gaten"]
        regels += ["", f"Randnummer-reeks: {len(g)} gaten"
                   + (": " + ", ".join(
                       f"na nr {x['na']} (blz {x['bladzijde']})"
                       for x in g[:10]) if g else
                       " — de reeks is compleet, elke eenheid volgt op "
                       "de vorige")]
    regels += ["", "Gedrukte bladzijden zonder fragmenten:"]
    if d["bladzijden_zonder_fragmenten"]:
        for z in d["bladzijden_zonder_fragmenten"]:
            regels.append(f"  - blz {z['bladzijde']}: {z['duiding']}")
    else:
        regels.append("  - geen")
    u = d.get("uitgesloten", {})
    regels += [
        "",
        f"Bewust uitgesloten: {u.get('voorwerk', '')}. De inhoudsopgave zelf "
        f"(scans {', '.join(map(str, u.get('inhoudsopgave_scans', [])))}) is "
        "niet doorzoekbaar gemaakt, want navigatie is geen antwoord.",
        "",
        "KANTTEKENING: " + d.get("kanttekening", ""),
    ]
    return _tekst("\n".join(regels))


def _doe_info(bank, rapport: dict) -> dict:
    info = bank.info() or {}
    rp = rapport.get("rookproef") or {}
    dek = rapport.get("dekking") or {}
    regels = [
        f"Titel: {info.get('titel')}",
        f"Bron: {info.get('bestandsnaam')} — gescand, {info.get('bladzijden')} "
        "bladzijden, geen tekstlaag",
        f"Verwerking: v{info.get('verwerking') or 1} "
        f"({info.get('strategie') or 'bladzijde-blokken'}); citeer met "
        "randnummer en bladzijde.",
        f"Fragmenten: {rapport.get('fragmenten')} "
        f"({', '.join(f'{v} {k}' for k, v in (rapport.get('per_soort') or {}).items())})",
        "",
        "Kwaliteitsmetingen:",
        f"- inhoudsopgave geverifieerd: {round((info.get('trefkans') or 0) * 100)}% "
        "van de titels uit de inhoudsopgave is op de geijkte bladzijde teruggevonden",
        f"- dekking brontekst: {round((dek.get('aandeel') or 0) * 100)}%",
        f"- rookproef: {rp.get('geslaagd')}/{rp.get('gevraagd')} fragmenten vinden "
        "zichzelf terug in de top 5",
        "",
        "Proces: OCR per bladzijde met bloktypering (titel/kop/voet/tekst/tabel), "
        "structuur uit de inhoudsopgave geijkt op de gedrukte paginanummers in de "
        f"voetteksten (verschuiving +{info.get('verschuiving')}: gedrukt 1 = scan "
        f"{(info.get('verschuiving') or 0) + 1}), fragmenten blijven binnen één "
        "bladzijde, voetnoten behouden als eigen soort, hybride zoeken "
        "(FTS + vectoren, RRF).",
        "",
        "De volledige verantwoording staat op https://boek.globaal.be/proces "
        "(achter de SSO). De bekende gaten: zie het gereedschap "
        "wat_ontbreekt.",
    ]
    return _tekst("\n".join(regels))


# ---------------------------------------------------------------- de route

@mcp.route("/mcp", methods=["POST", "GET", "DELETE"])
def endpoint():
    if not _toegestaan():
        return Response(status=401, headers={
            "WWW-Authenticate":
            f'Bearer resource_metadata="{RESOURCE}'
            '/.well-known/oauth-protected-resource"'})

    if request.method != "POST":
        # Geen SSE-stroom en geen sessies in deze stateless variant.
        return Response(status=405, headers={"Allow": "POST"})

    try:
        bericht = request.get_json(force=True)
    except Exception:                                          # noqa: BLE001
        return Response(json.dumps(_rpc_fout(None, -32700, "geen geldige JSON")),
                        mimetype="application/json", status=400)

    # Een notificatie (geen id) vraagt geen antwoord.
    if isinstance(bericht, dict) and "id" not in bericht:
        return Response(status=202)

    id_ = bericht.get("id")
    methode = bericht.get("method")
    params = bericht.get("params") or {}

    if methode == "initialize":
        gevraagd = params.get("protocolVersion")
        versie = gevraagd if gevraagd in PROTOCOLVERSIES else NIEUWSTE
        resultaat = {
            "protocolVersion": versie,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "boek-kennisbank", "version": "1.0.0"},
            "instructions": (
                "Doorzoekbare kennisbank van het boek 'Niet-vergunde "
                "constructies, tussen gedogen en regulariseren'. Begin met "
                "zoek_in_boek; elke treffer noemt zijn bladzijde en "
                "fragment_id. Citeer altijd met de bladzijde erbij. Bij vragen "
                "over volledigheid of betrouwbaarheid: gebruik wat_ontbreekt "
                "voor de bekende gaten en voorbehouden."),
        }
    elif methode == "ping":
        resultaat = {}
    elif methode == "tools/list":
        resultaat = {"tools": GEREEDSCHAP}
    elif methode == "tools/call":
        naam = params.get("name")
        args = params.get("arguments") or {}
        from vitrine import KB_PAD, rapport
        from kennisbank.opslag import Kennisbank
        if not KB_PAD.exists():
            return Response(json.dumps(_rpc_fout(id_, -32603,
                                                 "kennisbank niet beschikbaar")),
                            mimetype="application/json")
        bank = Kennisbank(KB_PAD)
        try:
            if naam == "zoek_in_boek":
                resultaat = _doe_zoek(bank, args)
            elif naam == "lees_fragment":
                resultaat = _doe_fragment(bank, args)
            elif naam == "lees_bladzijde":
                resultaat = _doe_bladzijde(bank, args)
            elif naam == "wat_ontbreekt":
                resultaat = _doe_ontbreekt()
            elif naam == "boek_info":
                resultaat = _doe_info(bank, rapport())
            else:
                return Response(json.dumps(_rpc_fout(
                    id_, -32602, f"onbekend gereedschap: {naam}")),
                    mimetype="application/json")
        except Exception as e:                                 # noqa: BLE001
            resultaat = {"content": [{"type": "text",
                                      "text": f"Fout bij uitvoeren: {e}"}],
                         "isError": True}
        finally:
            bank.sluit()
    else:
        return Response(json.dumps(_rpc_fout(id_, -32601,
                                             f"onbekende methode: {methode}")),
                        mimetype="application/json")

    return Response(json.dumps({"jsonrpc": "2.0", "id": id_, "result": resultaat},
                               ensure_ascii=False),
                    mimetype="application/json")


# ---------------------------------------------------------------- discovery

_as_metadata_cache: dict | None = None


def _as_metadata() -> dict:
    """De metadata van de OAuth-server, opgehaald bij Authentik en gecachet.

    We serveren hem ook zelf (op /.well-known/oauth-authorization-server),
    omdat sommige clients de metadata op de resource-host zoeken in plaats van
    de verwijzing in oauth-protected-resource te volgen.
    """
    global _as_metadata_cache
    if _as_metadata_cache is None:
        bron = ISSUER.rstrip("/") + "/.well-known/openid-configuration"
        intern = bron.replace("https://auth.globaal.be",
                              "http://authentik-server:9000")
        req = urllib.request.Request(intern)
        req.add_header("Host", "auth.globaal.be")
        with urllib.request.urlopen(req, timeout=10) as r:
            _as_metadata_cache = json.loads(r.read().decode())
    return _as_metadata_cache


@mcp.route("/.well-known/oauth-protected-resource")
@mcp.route("/.well-known/oauth-protected-resource/mcp")
def beschermde_resource():
    return Response(json.dumps({
        "resource": RESOURCE,
        "authorization_servers": [ISSUER],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["openid", "profile", "email", "offline_access"],
    }), mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"})


@mcp.route("/.well-known/oauth-authorization-server")
@mcp.route("/.well-known/oauth-authorization-server/mcp")
@mcp.route("/.well-known/openid-configuration")
def as_metadata_route():
    try:
        d = _as_metadata()
    except Exception as e:                                     # noqa: BLE001
        return Response(json.dumps({"fout": f"metadata onbereikbaar: {e}"}),
                        status=502, mimetype="application/json")
    return Response(json.dumps(d), mimetype="application/json",
                    headers={"Access-Control-Allow-Origin": "*"})
