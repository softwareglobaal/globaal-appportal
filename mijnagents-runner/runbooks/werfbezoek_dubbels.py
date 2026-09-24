"""Runbook 'werfbezoek-dubbels': wist de oude werfbezoek-rijen die na de verhuis van een projectmap
(ander fasepad, zelfde bezoekmap) dubbel staan, na goedkeuring door Mehdi. Voorgesteld door
Werfverslag voorbereider. Het bord wist een rij alleen als ze echt een dubbel is en alles wat ze
droeg (gegevens, keuzes, bijlagen, proef) ook op de rij staat die blijft; elke gewiste rij komt
eerst volledig in mijnagents-data/werfbezoek_gewist.jsonl.
Parameters: {"sleutel": "werfbezoek-dubbels", "paren": [[oud_id, blijft_id], ...]}"""
import json
import os
import urllib.request

PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3022")


def _token():
    for regel in open(os.path.expanduser("~/appportal/mijnagents-data/.env")):
        if regel.startswith("AGENTS_TOKEN="):
            return regel.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def voer_uit(p):
    paren = p.get("paren")
    if not isinstance(paren, list) or not paren or not all(isinstance(x, list) and len(x) == 2 for x in paren):
        raise ValueError("parameter 'paren' ontbreekt: [[oud_id, blijft_id], ...]")
    req = urllib.request.Request(f"{PLATFORM}/api/werfbezoek/opruimen",
                                 data=json.dumps({"paren": paren}).encode(),
                                 headers={"Content-Type": "application/json", "X-Agents-Token": _token()},
                                 method="POST")
    uit = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    gewist, over = uit.get("gewist") or [], uit.get("overgeslagen") or []
    if over and not gewist:
        raise RuntimeError("niets gewist: " + "; ".join(f"rij {o.get('id')}: {o.get('reden')}" for o in over)[:300])
    detail = f"{len(gewist)} dubbele rij(en) gewist (kopie in werfbezoek_gewist.jsonl)"
    if over:
        detail += f", {len(over)} overgeslagen"
    return detail, json.dumps(uit, ensure_ascii=False)
