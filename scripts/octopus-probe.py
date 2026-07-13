"""Read-only probe voor de Octopus REST API (stap 3 uit PLAN.md).

Draaien op de VM (secrets staan in ~/appportal/.env, nooit in git/chat):
    cd ~/appportal
    set -a; . ./.env; set +a
    python3 scripts/octopus-probe.py

Doet uitsluitend: inloggen, dossiers oplijsten en (optioneel, met
OCTOPUS_PROBE_DOSSIER=<id>) een relations-telling van een dossier.
Schrijft niets, print geen secrets.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASIS = "https://service.inaras.be/octopus-rest-api/v1"


def vraag(pad, headers=None, body=None, methode=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASIS + pad, data=data, method=methode or ("POST" if data else "GET"),
        headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return e.code, {"fout": detail}


uuid = os.environ.get("OCTOPUS_SOFTWAREHOUSE_UUID", "").strip()
gebruiker = os.environ.get("OCTOPUS_USER", "").strip()
wachtwoord = os.environ.get("OCTOPUS_PASSWORD", "").strip()
if not uuid or uuid.startswith("VUL-HIER"):
    print("OCTOPUS_SOFTWAREHOUSE_UUID moet in de omgeving staan.")
    sys.exit(1)

if not (gebruiker and wachtwoord):
    # ID-check zonder API-gebruiker: log in met bewust foute credentials.
    # Een geldige Software House ID geeft dan een credentials-fout terug;
    # een ongeldige ID geeft een softwarehouse-fout. Zo testen we de ID
    # zonder dat er een gebruiker bestaat.
    status, antwoord = vraag("/authentication",
                             headers={"softwareHouseUuid": uuid},
                             body={"user": "id-check", "password": "id-check"})
    print(f"ID-check (zonder API-gebruiker): HTTP {status}")
    print(f"antwoord: {json.dumps(antwoord)[:300]}")
    if status == 200:
        print("onverwacht: login lukte met dummy-credentials?!")
    print("Interpretatie: wijst de fout naar user/wachtwoord, dan is de "
          "Software House ID geaccepteerd; wijst hij naar de softwarehouse "
          "zelf, dan klopt de ID niet. Vul OCTOPUS_USER en OCTOPUS_PASSWORD "
          "in voor de volledige probe.")
    sys.exit(0)

status, antwoord = vraag("/authentication",
                         headers={"softwareHouseUuid": uuid},
                         body={"user": gebruiker, "password": wachtwoord})
if status != 200 or "token" not in antwoord:
    print(f"authenticatie FAALT (HTTP {status}): {antwoord}")
    sys.exit(1)
token = antwoord["token"]
print("authenticatie OK (token 10 min geldig)")

status, dossiers = vraag("/dossiers", headers={"Token": token})
if status != 200:
    print(f"dossiers ophalen FAALT (HTTP {status}): {dossiers}")
    sys.exit(1)
lijst = dossiers if isinstance(dossiers, list) else dossiers.get("dossiers", dossiers)
print(f"dossiers: {len(lijst)}")
for d in lijst if isinstance(lijst, list) else []:
    if isinstance(d, dict):
        naam = d.get("name") or d.get("naam") or d.get("description") or "?"
        print(f"  - {d.get('id') or d.get('dossierId') or '?'}: {naam}")
    else:
        print(f"  - {d}")

probe_dossier = os.environ.get("OCTOPUS_PROBE_DOSSIER", "").strip()
if probe_dossier:
    status, dt = vraag(f"/dossiers?dossierId={probe_dossier}&localeId=1",
                       headers={"Token": token}, body={})
    sleutel = dt.get("Dossiertoken") if isinstance(dt, dict) else None
    if status != 200 or not sleutel:
        print(f"dossiertoken FAALT (HTTP {status}): {dt}")
        sys.exit(1)
    status, rel = vraag(f"/dossiers/{probe_dossier}/relations",
                        headers={"Token": sleutel})
    aantal = len(rel) if isinstance(rel, list) else "?"
    print(f"relations dossier {probe_dossier}: HTTP {status}, {aantal} rijen")
print("PROBE KLAAR - alleen gelezen, niets geschreven")
