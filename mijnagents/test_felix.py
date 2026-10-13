"""Grendel op de FelixArchief-pagina (draait in de Docker-build: faalt dit, dan blijft de vorige container staan).

Shaniel, 13-10-2026: Shelton krijgt toegang tot de FelixArchief-agent, zonder goedkeuring van Mehdi; resultaten op de
pagina en in een logboek; opslaan in de projectmap pas op een klik. Deze toetsen falen zodra felix.<domein> meer toont
dan de Felix-pagina (Mehdi's bord, mail of agenda), zodra iemand zonder de groep felix of beheer erbij kan, zodra een
dubbele klik twee zoektochten geeft, zodra opslaan kan voor een zoektocht die niet klaar is of geen projectnummer
heeft, zodra een bestandslink buiten de map van de zoektocht kan lezen, of zodra een formulier van een andere site
iets kan aanvragen.
"""
import json
import os
import sys
import tempfile

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "test.db")
os.environ["AGENTS_TOKEN"] = "proef"
os.environ["FELIX_DATA"] = os.path.join(MAP, "felix")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402
import felix_pagina as F  # noqa: E402

SHELTON = {"X-authentik-groups": "sales|felix", "X-authentik-username": "shelton"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "mehdi"}
ANDER = {"X-authentik-groups": "agents|sales", "X-authentik-username": "siyan"}
FELIX = "felix.globaal.be"
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


c = A.app.test_client()

# 1. felix.<domein> toont alleen de Felix-pagina
r = c.get("/", headers=SHELTON, base_url=f"https://{FELIX}")
check("felix-domein: / gaat naar /felix", r.status_code in (301, 302) and r.headers["Location"].endswith("/felix"))
for pad in ("/mail", "/werfverslagen", "/gesprekken", "/api/nood", "/agent/bode"):
    r = c.get(pad, headers=BEHEER, base_url=f"https://{FELIX}")
    check(f"felix-domein: {pad} bestaat niet, ook niet voor beheer", r.status_code == 404, r.status_code)
check("felix-domein: Shelton ziet de pagina", c.get("/felix", headers=SHELTON, base_url=f"https://{FELIX}").status_code == 200)

# 2. toegang: felix of beheer, niemand anders
check("zonder groep felix of beheer: 403", c.get("/felix", headers=ANDER).status_code == 403)
check("zonder groepen: 403", c.get("/felix").status_code == 403)
check("beheer op mijnagents: 200", c.get("/felix", headers=BEHEER).status_code == 200)

# 3. aanvragen, met dubbele klik en controle van de invoer
post = dict(headers=SHELTON, base_url=f"https://{FELIX}")
c.post("/felix/zoek", data={"project": "3810", "adres": "Kerkstraat 12, 2000 Antwerpen"}, **post)
c.post("/felix/zoek", data={"project": "3810", "adres": "Kerkstraat  12, 2000 Antwerpen"}, **post)
c.post("/felix/zoek", data={"project": "38a", "adres": "Lange Nieuwstraat 1, 2000 Antwerpen"}, **post)
c.post("/felix/zoek", data={"project": "", "adres": ""}, **post)
aanvragen = [json.loads(x) for x in open(F.AANVRAGEN)]
check("dubbele klik geeft een aanvraag", len(aanvragen) == 1, len(aanvragen))
check("aanvraag bewaart door wie", aanvragen and aanvragen[0]["door"] == "shelton" and aanvragen[0]["soort"] == "zoek")
r = c.post("/felix/zoek", data={"adres": "X 1, 2000 Antwerpen"}, headers={**SHELTON, "Origin": "https://kwaad.example"},
           base_url=f"https://{FELIX}")
check("formulier van een andere site: 403", r.status_code == 403)
check("andere site zette niets klaar", len(open(F.AANVRAGEN).readlines()) == 1)
zid = aanvragen[0]["id"]
c.post("/felix/zoek", data={"project": "", "adres": "Meir 1, 2000 Antwerpen"}, **post)
zonder_project = json.loads(open(F.AANVRAGEN).readlines()[-1])["id"]

# 4. opslaan alleen na een klaar resultaat en met projectnummer
c.post(f"/felix/{zid}/opslaan", **post)
check("opslaan voor een wachtende zoektocht: niets klaargezet",
      not any(json.loads(x)["soort"] == "opslaan" for x in open(F.AANVRAGEN)))
os.makedirs(os.path.join(F.ZOEKTOCHTEN, "z1", "_gegevens"))
os.makedirs(os.path.join(F.ZOEKTOCHTEN, "z1", "FelixArchief"))
open(os.path.join(F.ZOEKTOCHTEN, "z1", "Controle.md"), "w").write("# Kerkstraat 12\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
open(os.path.join(F.ZOEKTOCHTEN, "z1", "Geopunt.png"), "wb").write(b"\x89PNG")
open(os.path.join(F.ZOEKTOCHTEN, "z1", "_gegevens", "resultaat.json"), "w").write("{}")
open(os.path.join(MAP, "geheim.txt"), "w").write("geheim")
json.dump({"zoek": {zid: {"status": "klaar", "map": "z1", "besluit": "Perceel X: 1 vergunning", "klaar": "2026-10-13T10:00:00+02:00"},
                    zonder_project: {"status": "klaar", "map": "z1", "besluit": "x"}}, "opslaan": {}}, open(F.STAND, "w"))
r = c.get(f"/felix/{zid}", **post)
check("detailpagina toont de controle", r.status_code == 200 and b"Kerkstraat 12" in r.data and b"<table>" in r.data)
check("pagina toont de opslagknop", b"Opslaan in projectmap 3810" in c.get("/felix", **post).data)
c.post(f"/felix/{zid}/opslaan", **post)
c.post(f"/felix/{zid}/opslaan", **post)
opslaan = [json.loads(x) for x in open(F.AANVRAGEN) if json.loads(x)["soort"] == "opslaan"]
check("een klik op opslaan geeft een opdracht, een tweede klik niet", len(opslaan) == 1 and opslaan[0]["zoek_id"] == zid, opslaan)
c.post(f"/felix/{zonder_project}/opslaan", **post)
check("zonder projectnummer: niets klaargezet",
      sum(1 for x in open(F.AANVRAGEN) if json.loads(x)["soort"] == "opslaan") == 1)

# 5. bestanden: alleen binnen de map van de zoektocht, niet de _gegevens
check("printscreen leesbaar", c.get(f"/felix/{zid}/bestand/Geopunt.png", **post).status_code == 200)
check("_gegevens niet leesbaar", c.get(f"/felix/{zid}/bestand/_gegevens/resultaat.json", **post).status_code == 404)
check("buiten de map niet leesbaar", c.get(f"/felix/{zid}/bestand/../../geheim.txt", **post).status_code == 404)
check("onbekende zoektocht: 404", c.get("/felix/onbekend", **post).status_code == 404)

print(f"{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
