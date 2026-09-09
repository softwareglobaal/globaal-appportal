#!/usr/bin/env python3
"""Uitvoerder van Mehdi's agent-omgeving: voert GOEDGEKEURDE voorstellen met
parameters uit en meldt bewijs terug. Deterministisch, geen AI.

De poort:
  agent stelt een actie voor (runbook + parameters)  ->  voorstel 'open'
  Mehdi keurt goed op mijnagents.globaal.be           ->  status 'goedgekeurd'
  DEZE uitvoerder haalt het op, voert het uit, meldt  ->  'uitgevoerd' / 'mislukt'

Alleen runbooks uit de allowlist in runbooks/__init__.py worden uitgevoerd.
Een onbekend runbook of een voorstel zonder parameters wordt nooit uitgevoerd.
Draait op de host via cron (elke minuut), praat met de app over localhost.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runbooks import RUNBOEKEN  # noqa: E402


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/appportal/mijnagents-data/.env")
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3022")
TOKEN = os.environ.get("AGENTS_TOKEN", "")


def api(pad, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(PLATFORM + pad, data=data, method=method)
    req.add_header("X-Agents-Token", TOKEN)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def meld(vid, uitvoering, detail, bewijs=""):
    api("/uitvoer-resultaat", "POST",
        {"id": vid, "uitvoering": uitvoering, "detail": detail[:400], "bewijs": bewijs[:4000]})


def main():
    if not TOKEN:
        print("FOUT: geen AGENTS_TOKEN", file=sys.stderr)
        return
    wacht = api("/api/uitvoer-wacht").get("wacht") or []
    for a in wacht:
        vid, rb = a.get("id"), (a.get("runbook") or "").strip()
        try:
            p = json.loads(a.get("parameters") or "")
        except (ValueError, TypeError):
            meld(vid, "mislukt", f"parameters niet leesbaar (runbook '{rb}')")
            continue
        if not isinstance(p, dict) or not p:
            meld(vid, "overgeslagen", "geen parameters: alleen een signaal")
            continue
        runbook = RUNBOEKEN.get(rb)
        if runbook is None:
            meld(vid, "mislukt", f"runbook '{rb}' staat niet in de allowlist "
                                 f"(wel: {', '.join(sorted(RUNBOEKEN))})")
            continue
        try:
            detail, bewijs = runbook(p)
            uitvoering = "gelukt"
        except Exception as e:  # noqa: BLE001 - deterministische uitvoerder, alles afvangen
            uitvoering, detail, bewijs = "mislukt", f"{type(e).__name__}: {e}", ""
        meld(vid, uitvoering, detail, bewijs)
        print(f"voorstel {vid} ({rb}): {uitvoering} — {detail}")


if __name__ == "__main__":
    main()
