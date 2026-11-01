"""Grendel op de foto's per project in het Dagboek (dagboek/fotos.py, T-0120 FOTO-5). Verzonnen projecten en plekken.

- F01: zonder de groep 403, met de groep 200 (Authentik scheidt groepen met "|");
- F02: een werfgroep toont firma, nummer, project, de afspraak en haar voorvertoningen; het beeld komt als JPEG;
- F03: privé, mensen, scherm en onbeslist alleen als telling: geen plaats, geen tijd, geen beeld; een beeld dat de
  indeling niet als werkfoto zonder mensen aanwijst, geeft 404, ook als het bestand er staat;
- F04: een dag zonder indeling is "nog niet ingedeeld" (onbekend, niet leeg); voor 01-10 of in de toekomst 404;
- F05: de pagina van De Fotowacht wijst naar de foto's per project;
- F06: geen gedachtestreepje.
Draait in de Docker-build (Dockerfile): faalt dit, dan blijft de vorige container staan.
"""
import json
import os
import sys
import tempfile
from datetime import timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
MAP = tempfile.mkdtemp()
os.environ["DAGBOEK_MAP"] = os.path.join(MAP, "dagboek")
os.environ["DAGBOEK_GROUPS"] = "dagboek"
os.environ["FOTOINDELING_MAP"] = os.path.join(MAP, "fotoindeling")
os.environ["FOTOVOORBEELD_MAP"] = os.path.join(MAP, "fotovoorbeeld")
os.environ["MIJNAGENTS_URL"] = "http://127.0.0.1:9"      # geen bord in de proef: de wachtpagina zegt dat het niet antwoordt
sys.path.insert(0, HIER)
import app as A  # noqa: E402

C = A.app.test_client()
MET = {"X-authentik-groups": "medewerkers|dagboek"}
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


DAG = "2026-10-29"
JPEG = b"\xff\xd8\xff fictieve kleine jpeg \xff\xd9"
INDELING = {
    "datum": DAG, "versie": 1, "totaal": 20,
    "werf": [{"sleutel": "afspraak:HARC:9001:10:00", "soort": "zeker", "firma": "HARC", "nummer": "9001", "naam": "Proefwoning Alfa",
              "anker": {"soort": "afspraak", "titel": "[HA] 9001 proefbezoek", "start": "10:00", "einde": "11:00"},
              "auto_min": 45, "link": "https://ha-projecten.globaal.be/project/9001", "van": "10:15", "tot": "10:25",
              "bezoek": {"pagina": "https://mijnagents.globaal.be/werfverslag/9001/2", "bezoekmap": "/Work All/01. H-A WORK/9001 Proef/bezoek 2"},
              "aantal": 3, "met_mensen": 1, "zonder_plaats": 0, "video": 0,
              "fotos": [{"id": "werk-1", "tijd": "10:15", "voorbeeld": True}, {"id": "werk-mens", "tijd": "10:20", "voorbeeld": False},
                        {"id": "werk-2", "tijd": "10:25", "voorbeeld": True}]}],
    "kandidaat": [{"sleutel": "kandidaat:HARC:9002", "soort": "kandidaat", "firma": "HARC", "nummer": "9002", "naam": "Proefwoning Beta",
                   "anker": None, "auto_min": None, "link": "", "van": "16:00", "tot": "16:04", "aantal": 2, "met_mensen": 0,
                   "zonder_plaats": 0, "video": 0, "fotos": [{"id": "kand-1", "tijd": "16:00", "voorbeeld": False},
                                                             {"id": "kand-2", "tijd": "16:04", "voorbeeld": False}]}],
    "telling": {"prive": 12, "mensen": 1, "overig": 2, "onbeslist": 0},
    "bronnen": {"projectplekken": 2, "afspraken": 1, "afspraken_zonder_plaats": 0, "locatiecontext": "gelezen", "verblijven": 1},
}
os.makedirs(os.path.join(MAP, "fotoindeling", "2026"))
with open(os.path.join(MAP, "fotoindeling", "2026", f"{DAG}.json"), "w", encoding="utf-8") as f:
    json.dump(INDELING, f)
os.makedirs(os.path.join(MAP, "fotovoorbeeld", DAG))
for fid in ("werk-1", "kand-1", "werk-mens"):          # ook bestanden die nooit getoond mogen worden
    with open(os.path.join(MAP, "fotovoorbeeld", DAG, f"{fid}.jpg"), "wb") as f:
        f.write(JPEG)

check("F01 zonder groep 403", C.get(f"/fotos/{DAG}", headers={"X-authentik-groups": "medewerkers"}).status_code == 403)
check("F01 beeld zonder groep 403", C.get(f"/fotos/{DAG}/voorbeeld/werk-1.jpg", headers={"X-authentik-groups": "x"}).status_code == 403)
r = C.get(f"/fotos/{DAG}", headers=MET)
html = r.get_data(as_text=True)
check("F01 met groep 200", r.status_code == 200, r.status_code)
check("F02 project en afspraak", "HARC 9001 Proefwoning Alfa" in html and "[HA] 9001 proefbezoek" in html and "45 min" in html, html[:400])
check("F02 voorvertoning van de werkfoto", f"/fotos/{DAG}/voorbeeld/werk-1.jpg" in html)
check("F02 link naar het werfbezoek en de bezoekmap", "/werfverslag/9001/2" in html and "bezoekmap: /Work All" in html)
check("F02 werkfoto zonder aangekomen beeld", "nog geen voorvertoning" in html)
r = C.get(f"/fotos/{DAG}/voorbeeld/werk-1.jpg", headers=MET)
check("F02 beeld is een JPEG", r.status_code == 200 and r.mimetype == "image/jpeg" and r.data == JPEG, r.status_code)
check("F03 werkfoto met mensen: geen beeld op de pagina", "voorbeeld/werk-mens.jpg" not in html)
check("F03 werkfoto met mensen: 404", C.get(f"/fotos/{DAG}/voorbeeld/werk-mens.jpg", headers=MET).status_code == 404)
check("F03 kandidaat: geen beeld, ook niet als het bestand er staat",
      "voorbeeld/kand-1.jpg" not in html and C.get(f"/fotos/{DAG}/voorbeeld/kand-1.jpg", headers=MET).status_code == 404)
check("F03 onbekende of vreemde id: 404", C.get(f"/fotos/{DAG}/voorbeeld/..%2Fx.jpg", headers=MET).status_code == 404
      and C.get(f"/fotos/{DAG}/voorbeeld/onbekend.jpg", headers=MET).status_code == 404)
check("F03 privé alleen geteld", "Privé 12, met mensen 1, scherm of app 2, onbeslist 0" in html)
check("F03 kandidaat zonder bevestiging", "Kandidaat: HARC 9002 Proefwoning Beta" in html and "nog niet bevestigd" in html)
r = C.get("/fotos/2026-10-28", headers=MET)
check("F04 dag zonder indeling", r.status_code == 200 and "Nog niet ingedeeld" in r.get_data(as_text=True))
check("F04 voor 01-10: 404", C.get("/fotos/2026-09-30", headers=MET).status_code == 404)
check("F04 toekomst: 404", C.get(f"/fotos/{(A.vandaag() + timedelta(days=1)).isoformat()}", headers=MET).status_code == 404)
check("F04 geen datum: 404", C.get("/fotos/morgen", headers=MET).status_code == 404)
check("F04 /fotos gaat naar gisteren", C.get("/fotos", headers=MET).status_code == 302)
r = C.get(f"/wachten/icloud-wacht?dag={A.vandaag().isoformat()}", headers=MET)
check("F05 Fotowacht wijst naar de foto's per project", f"/fotos/{A.vandaag().isoformat()}" in r.get_data(as_text=True), r.status_code)
check("F06 geen gedachtestreepje", "—" not in html and "–" not in html)

print("fout:", fout)
sys.exit(1 if fout else 0)
