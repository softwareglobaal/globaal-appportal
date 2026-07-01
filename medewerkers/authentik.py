"""Read-only Authentik-lookups voor het Toegang-panel op het profiel.

Bevraagt de Authentik-API met een read-only service-account-token om de groepen
van een persoon op te halen; de app-toegang wordt daaruit lokaal afgeleid via
apps.yaml (groep ∩ app.roles). Alles is best-effort: ontbreekt het token of de
API, dan komt er lege data terug en toont het profiel "n.v.t." — de app blijft
werken zonder deze feature.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import yaml

API_URL = os.environ.get("AUTHENTIK_API_URL", "").rstrip("/")
API_TOKEN = os.environ.get("AUTHENTIK_API_TOKEN", "").strip()
APPS_FILE = os.environ.get("APPS_FILE", "/app/apps.yaml")
TIMEOUT = 4

# Feature staat aan zodra er een API-URL én token zijn.
enabled = bool(API_URL and API_TOKEN)


def groepen_van(username):
    """Gesorteerde groepsnamen van de Authentik-gebruiker; [] bij fout/onbekend."""
    if not (enabled and username):
        return []
    url = f"{API_URL}/core/users/?username=" + urllib.parse.quote(username)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return []
    results = data.get("results") or []
    if not results:
        return []
    groups = results[0].get("groups_obj") or []
    return sorted(g["name"] for g in groups if g.get("name"))


def apps_voor(groepen):
    """Apps die iemand met deze groepen kan openen, o.b.v. apps.yaml (roles)."""
    groepen = set(groepen)
    if not groepen:
        return []
    try:
        with open(APPS_FILE, encoding="utf-8") as fh:
            apps = (yaml.safe_load(fh) or {}).get("apps", [])
    except (OSError, ValueError):
        return []
    namen = [a.get("name") or a.get("id") for a in apps
             if groepen & set(a.get("roles", []))]
    return sorted(n for n in namen if n)
