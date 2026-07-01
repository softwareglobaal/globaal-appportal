"""Read-only lookup naar het Telefoonregister voor het 360°-profiel.

Roept de interne API van de telefoonregister-app aan (op het docker-netwerk,
buiten nginx om, dus zonder forward-auth) om de nummers van een persoon op te
halen. Best-effort: ontbreekt de URL of de app, dan lege lijst en toont het
profiel netjes "geen nummers" — de app blijft werken zonder deze feature.
De API levert nooit secrets (PIN/PUK) terug; alleen de voorkant-velden.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_URL = os.environ.get("TELEFOON_API_URL", "").rstrip("/")
TIMEOUT = 4

enabled = bool(API_URL)


def nummers_van(persoon_id):
    """Nummers (telefoon/functie/status) van een persoon; [] bij fout/onbekend."""
    if not (enabled and persoon_id):
        return []
    url = f"{API_URL}/api/numbers?persoon_id=" + urllib.parse.quote(str(persoon_id))
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    nummers = [
        {
            "phone": r.get("phone", ""),
            "functie": r.get("function", ""),
            "status": r.get("status", ""),
        }
        for r in data
    ]
    # Actieve nummers eerst, daarbinnen op telefoonnummer.
    nummers.sort(key=lambda x: (x["status"] != "Actief", x["phone"]))
    return nummers
