"""Client voor de MCP-koppeling van het contract-dashboard (contracten.globaal.be/mcp).

Statisch servertoken CONTRACTEN_MCP_TOKEN uit ~/appportal/.env (nooit in git).
Dat token heeft schrijfrecht (contracten-bewerken), dus alles wat de
Werkinstructie AI toelaat kan hierlangs: voorbereiding_starten, gegeven_invullen,
keuze_maken, proef_maken. Nooit een definitief contract: dat is Mehdi's klik.
"""
import json
import os
import urllib.request

URL = os.environ.get("CONTRACTEN_MCP_URL", "https://contracten.globaal.be/mcp")


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/.env")
TOKEN = os.environ.get("CONTRACTEN_MCP_TOKEN", "")


class ToolFout(Exception):
    """De tool zelf gaf een fout terug (isError); de tekst zegt wat er mist."""


def _rpc(methode, params=None, rid=1):
    req = urllib.request.Request(
        URL, data=json.dumps({"jsonrpc": "2.0", "id": rid, "method": methode,
                              "params": params or {}}).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": f"Bearer {TOKEN}"}, method="POST")
    raw = urllib.request.urlopen(req, timeout=240).read().decode()
    for regel in raw.splitlines():
        if regel.startswith("data:"):
            raw = regel[5:].strip()
    uit = json.loads(raw)
    if "error" in uit:
        raise RuntimeError(f"MCP {methode}: {uit['error']}")
    return uit["result"]


def tools():
    return [t["name"] for t in _rpc("tools/list")["tools"]]


def call(naam, **args):
    """Roept een tool aan en geeft het antwoord als dict/list (of tekst) terug."""
    r = _rpc("tools/call", {"name": naam, "arguments": args}, rid=2)
    tekst = "".join(c.get("text", "") for c in r.get("content", []))
    if r.get("isError"):
        raise ToolFout(tekst)
    try:
        return json.loads(tekst)
    except ValueError:
        return tekst
