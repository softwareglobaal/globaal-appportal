#!/usr/bin/env python3
"""gezondheid-wacht — runner voor mijnagents.globaal.be.

Gegenereerd door nieuwe-agent.py. Draait op de host via cron (buiten de
container), praat met de mijnagents-app over localhost en meldt zijn status
via het hartslag-contract.

Vul WERK() in met wat deze agent echt doet. Houd je aan de grenzen die op
het bord staan en aan de zichtbaarheidsregel: in `taak`/`detail` alleen
neutrale werkstatus, nooit inhoud (geen klantnamen, geen bedragen).

Muteren mag NIET rechtstreeks: doe een voorstel (stel_voor) dat je op het
bord goedkeurt. Pas na goedkeuring voert de uitvoerder het uit.
"""
import json
import os
import urllib.request

NAAM = "gezondheid-wacht"
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3022")


def _env(pad):
    """Laadt KEY=VALUE-regels uit een .env in os.environ (secrets nooit in git)."""
    pad = os.path.expanduser(pad)
    if not os.path.exists(pad):
        return
    for regel in open(pad):
        regel = regel.strip()
        if regel and not regel.startswith("#") and "=" in regel:
            k, v = regel.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_env("~/appportal/mijnagents-data/.env")   # AGENTS_TOKEN
TOKEN = os.environ.get("AGENTS_TOKEN", "")


def hartslag(status, taak="", detail="", tokens=None, voorstel=None):
    """Meldt status aan het bord. status in rust|waakt|actief|klaar|fout."""
    payload = {"naam": NAAM, "status": status, "taak": taak, "detail": detail}
    if tokens is not None:
        payload["tokens"] = tokens
    if voorstel is not None:
        payload["voorstel"] = voorstel
    req = urllib.request.Request(
        f"{PLATFORM}/agent-status",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Agents-Token": TOKEN},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print("hartslag mislukt:", e)
        return False


def stel_voor(actie, doel="", reden="", parameters=None, runbook=""):
    """Zet een voorstel op het bord. Zonder parameters is het een louter
    signaal (nooit autonoom uitvoerbaar); met parameters wordt het, na jouw
    goedkeuring, door de uitvoerder uitgevoerd."""
    return hartslag("waakt", taak=actie, detail=reden, voorstel={
        "actie": actie, "doel": doel, "reden": reden,
        "parameters": parameters, "runbook": runbook,
    })


def werk():
    """VUL DIT IN. Doe hier het echte werk van de agent en meld neutrale status.

    Voorbeeld:
        gedaan = 0
        # ... doe het werk ...
        hartslag("klaar", taak="ronde afgerond",
                 detail=f"laatste ronde: {gedaan} items bekeken")
    """
    hartslag("waakt", taak="beschikbaar", detail="skelet — werk() nog in te vullen")


if __name__ == "__main__":
    hartslag("actief", taak="ronde gestart")
    try:
        werk()
    except Exception as e:
        hartslag("fout", taak="ronde mislukt", detail=str(e)[:200])
        raise
