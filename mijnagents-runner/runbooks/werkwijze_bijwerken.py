"""Runbook 'werkwijze-bijwerken': zet een nieuwe werkwijze op het bord van een agent,
na goedkeuring door Mehdi. De vorige versie blijft bewaard (werkwijze_versie).
Parameters: {"agent": "contracten-agent", "werkwijze": "<volledige nieuwe tekst>"}"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3022")
# Agents waarvan de regels in code, JSON en tests staan: een nieuwe tekst op het bord verandert daar niets, en de
# agent zou anders tekst tonen die hij niet uitvoert. Zo'n wijziging wordt een regelwijziging voor de ontwikkelaar
# (regel, code, test en PDF samen, met versienummer), niet alleen tekst op het bord (audit 02-10-2026, A11; FR-98).
CODE_GEDREVEN = {"agenda-wacht"}
REGELWIJZIGINGEN = os.path.expanduser("~/appportal/mijnagents-data/regelwijzigingen")


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
    if agent in CODE_GEDREVEN:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "koppelingen"))
        import taken  # noqa: PLC0415
        os.makedirs(REGELWIJZIGINGEN, exist_ok=True)
        pad = os.path.join(REGELWIJZIGINGEN, f"{agent}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.md")
        with open(pad, "w", encoding="utf-8") as f:
            f.write(tekst)
        t = taken.plannen("regelwijziging", agent, {"tekst": pad}, datetime.now(timezone.utc), eigenaar="claude",
                          reden="nieuwe werkwijze goedgekeurd op het bord: als pakket doorvoeren (regel, code, test, PDF)",
                          toestemming="voorstel goedgekeurd door Mehdi", bron="runbook werkwijze-bijwerken")
        return (f"niet rechtstreeks op het bord: de regels van {agent} staan in code en JSON. Regelwijziging taak {t['id']} "
                f"staat klaar voor de ontwikkelaar", pad)
    req = urllib.request.Request(f"{PLATFORM}/api/agent/{agent}/werkwijze",
                                 data=json.dumps({"werkwijze": tekst, "overschrijf": True}).encode(),
                                 headers={"Content-Type": "application/json", "X-Agents-Token": _token()},
                                 method="POST")
    uit = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    if not uit.get("ok"):
        raise RuntimeError(uit.get("reden") or "niet gezet")
    return f"werkwijze van {agent} bijgewerkt ({len(tekst)} tekens)", ""
