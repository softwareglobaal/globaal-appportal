"""Inbox van de agent-bewaker op de Mac van Siyan.

De bewaker (~/Claude/bin/agent-bewaker.py) leest de Claude Code-transcripten
en ziet welke agents draaien of net klaar zijn. Hij zet dat als JSON-bestand
in ~/appportal/siyanagents-data/inbox/ (via scp, geen token op de Mac). Deze
module, aangeroepen door de uitvoerder-cron (elke minuut), post de inhoud op
het bord met de token die hier al staat, en ruimt het bestand op.

Bestandsvorm:
  {"statussen": [{"naam": "...", "status": "actief|klaar", "taak": "...", "detail": "..."}],
   "opdrachten": [ ... zoals /api/opdracht/import ... ]}
"""
import glob
import json
import os


INBOX = os.path.expanduser("~/appportal/siyanagents-data/inbox")


def verwerk(api):
    """api(path, method, payload) komt uit de uitvoerder (kent token en URL)."""
    paden = sorted(glob.glob(os.path.join(INBOX, "*.json")))
    for pad in paden:
        try:
            with open(pad, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError) as e:
            print(f"inbox: {os.path.basename(pad)} niet leesbaar ({e}), opzij gezet")
            os.replace(pad, pad + ".kapot")
            continue
        fouten = 0
        for s in d.get("statussen") or []:
            try:
                api("/agent-status", "POST", {"naam": s.get("naam", ""), "status": s.get("status", ""),
                                              "taak": s.get("taak", ""), "detail": s.get("detail", "")})
            except Exception as e:  # noqa: BLE001
                fouten += 1
                print(f"inbox: status {s.get('naam')} mislukt: {e}")
        opdrachten = d.get("opdrachten") or []
        if opdrachten:
            try:
                r = api("/api/opdracht/import", "POST", {"opdrachten": opdrachten})
                print(f"inbox: {r.get('nieuw', 0)} opdrachten nieuw, {r.get('overgeslagen', 0)} al bekend")
            except Exception as e:  # noqa: BLE001
                fouten += 1
                print(f"inbox: import mislukt: {e}")
        if fouten:
            # Laat het bestand staan voor een volgende ronde; de import is
            # idempotent en een dubbele statusmelding is onschuldig.
            continue
        os.remove(pad)
