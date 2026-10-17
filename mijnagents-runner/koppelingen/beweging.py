"""Alleen-leesbare, ongecachete bewegingstoestand voor de Agendawacht."""
import json
import os
import time
import urllib.request
from datetime import datetime

URL = os.environ.get("LOCATIE_URL", "http://127.0.0.1:3031").rstrip("/") + "/api/beweging"


def _epoch(iso):
    try:
        waarde = datetime.fromisoformat(iso)
        return waarde.timestamp() if waarde.tzinfo else None
    except (TypeError, ValueError):
        return None


def lees(nu=None, opener=None):
    """Haal een vers oordeel op; een fout of oud antwoord wordt altijd onbekend."""
    nu = time.time() if nu is None else nu
    opener = opener or urllib.request.urlopen
    leeg = {"persoon": {"toestand": "onbekend", "reden": "locatiesysteem niet actueel"},
            "auto": {"toestand": "onbekend"}}
    try:
        with opener(URL, timeout=3) as antwoord:
            data = json.load(antwoord)
    except Exception:  # noqa: BLE001
        return leeg
    gemaakt = _epoch(data.get("gemaakt")) if isinstance(data, dict) else None
    if gemaakt is None or gemaakt > nu + 10 or nu - gemaakt > 20:
        return leeg
    persoon = data.get("persoon") or {}
    auto = data.get("auto") or {}
    if persoon.get("toestand") == "onderweg":
        einde = _epoch(persoon.get("geldig_tot"))
        meting = _epoch(persoon.get("meettijd"))
        if persoon.get("rol") != "persoon" or einde is None or einde <= nu \
                or meting is None or meting > nu + 10:
            persoon = {"toestand": "onbekend", "reden": "bewegingsbewijs is verlopen of ongeldig"}
    if auto.get("toestand") == "auto_beweegt":
        einde = _epoch(auto.get("geldig_tot"))
        if auto.get("rol") != "auto" or einde is None or einde <= nu:
            auto = {"toestand": "onbekend"}
    return {"persoon": persoon, "auto": auto}


def kort(oordeel):
    """Neutrale tekst voor de interne agentstatus; nooit een afspraaktitel of plek."""
    persoon = (oordeel.get("persoon") or {}).get("toestand")
    auto = (oordeel.get("auto") or {}).get("toestand")
    if persoon == "onderweg":
        return "volgens gedragen tracker waarschijnlijk onderweg"
    if auto == "auto_beweegt":
        return "auto beweegt; persoon niet vastgesteld"
    if persoon == "niet_aangesloten":
        return "persoonlijke tracker nog niet aangesloten"
    return "onderwegstatus onbekend"
