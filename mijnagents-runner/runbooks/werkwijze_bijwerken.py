"""Runbook 'werkwijze-bijwerken': zet een nieuwe werkwijze op het bord van een agent,
na goedkeuring door Mehdi. De vorige versie blijft bewaard (werkwijze_versie).
Parameters: {"agent": "contracten-agent", "werkwijze": "<volledige nieuwe tekst>"}"""
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
    agent = str(p.get("agent", "")).strip()
    tekst = str(p.get("werkwijze", "")).strip()
    if not agent or len(tekst) < 200:
        raise ValueError("agent en een volledige werkwijze (minstens 200 tekens) zijn verplicht")
    req = urllib.request.Request(f"{PLATFORM}/api/agent/{agent}/werkwijze",
                                 data=json.dumps({"werkwijze": tekst, "overschrijf": True}).encode(),
                                 headers={"Content-Type": "application/json", "X-Agents-Token": _token()},
                                 method="POST")
    uit = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    if not uit.get("ok"):
        raise RuntimeError(uit.get("reden") or "niet gezet")
    return f"werkwijze van {agent} bijgewerkt ({len(tekst)} tekens)", ""
