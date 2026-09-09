"""Fathom (opnames van online gesprekken), alleen lezen, vanaf de host.
Sleutel(s) bij naam uit ~/appportal/.env: FATHOM_API_KEYS (komma-gescheiden).
Zelfde API als het contract-dashboard (webapp/fathom_api.py)."""
import json
import os
import urllib.parse
import urllib.request

BASIS = "https://api.fathom.ai/external/v1"


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


def sleutels():
    return [s.strip() for s in os.environ.get("FATHOM_API_KEYS", "").split(",") if s.strip()]


def beschikbaar():
    return bool(sleutels())


def _haal(sleutel, pad, params=None):
    url = f"{BASIS}{pad}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"X-Api-Key": sleutel, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def gesprekken(sinds_iso, met_transcript=False):
    """Alle gesprekken sinds een ISO-tijdstip, over alle sleutels; met transcript als gevraagd."""
    uit = []
    for s in sleutels():
        cursor = None
        while True:
            params = {"created_after": sinds_iso, "include_transcript": "true" if met_transcript else "false"}
            if cursor:
                params["cursor"] = cursor
            d = _haal(s, "/meetings", params)
            uit += d.get("items") or d.get("meetings") or []
            cursor = d.get("next_cursor")
            if not cursor:
                break
    return uit


def transcript_tekst(g):
    """Het transcript van een gesprek als leesbare tekst (spreker: zin), of ''."""
    t = g.get("transcript")
    if not t:
        return ""
    if isinstance(t, str):
        return t
    regels = []
    for r in t:
        spreker = (r.get("speaker") or {}).get("display_name") if isinstance(r.get("speaker"), dict) else r.get("speaker")
        regels.append(f"[{r.get('timestamp', '')}] {spreker or '?'}: {r.get('text', '')}")
    return "\n".join(regels)
