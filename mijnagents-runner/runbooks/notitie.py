"""Runbook 'notitie': schrijft een regel in het logboek ~/agents/mijnagents-notities.log.
Onschadelijk; bewijst de keten agent -> voorstel -> goedkeuring -> uitvoering.
Parameters: {"tekst": "..."}"""
import os
from datetime import datetime, timezone

LOG = os.path.expanduser("~/agents/mijnagents-notities.log")


def voer_uit(p):
    tekst = str(p.get("tekst", "")).strip()
    if not tekst:
        raise ValueError("parameter 'tekst' ontbreekt")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    regel = f"{datetime.now(timezone.utc).isoformat()} {tekst}"
    with open(LOG, "a") as f:
        f.write(regel + "\n")
    return "notitie vastgelegd", regel
