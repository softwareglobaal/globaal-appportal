"""Grendel op het Dagboek (dagboek.globaal.be). Leest proef/2026/2026-10-22.md en .json: een dagbestand en telling zoals
De Dagbundelaar ze schrijft (gemaakt met mijnagents-runner/koppelingen/dagvaststelling.py, verzonnen namen).

- D01: zonder de groep 403, met de groep 200; Authentik scheidt groepen met "|";
- D02: de dagpagina toont de afspraken met hun uitkomst in gewone woorden, zonder "Mehdi:" vooraan;
- D03: een privéafspraak toont geen titel; een privéoproep geen naam;
- D04: niet gepland toont met wie, via welk kanaal en hoe lang;
- D05: het overzicht toont de tegels van een vastgestelde dag, en "Nog niet vastgesteld" voor een dag zonder bestand;
- D06: een onbekend getal wordt een vraagteken; een kapotte telling laat de pagina niet vallen;
- D07: geen gedachtestreepje.
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
MAP = tempfile.mkdtemp()
os.environ["DAGBOEK_MAP"] = MAP
os.environ["DAGBOEK_GROUPS"] = "dagboek"
sys.path.insert(0, HIER)
import app as A  # noqa: E402

C = A.app.test_client()
MET = {"X-authentik-groups": "medewerkers|dagboek"}
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


PROEF = os.path.join(HIER, "proef", "2026")
os.makedirs(os.path.join(MAP, "2026"))
for ext in ("md", "json"):
    shutil.copy(os.path.join(PROEF, f"2026-10-22.{ext}"), os.path.join(MAP, "2026", f"2026-10-22.{ext}"))
gisteren = (A.vandaag() - timedelta(days=1)).isoformat()
os.makedirs(os.path.join(MAP, gisteren[:4]), exist_ok=True)
for ext in ("md", "json"):
    shutil.copy(os.path.join(PROEF, f"2026-10-22.{ext}"), os.path.join(MAP, gisteren[:4], f"{gisteren}.{ext}"))

check("D01 zonder groep 403", C.get("/", headers={"X-authentik-groups": "medewerkers"}).status_code == 403)
r = C.get("/dag/2026-10-22", headers=MET)
html = r.get_data(as_text=True)
check("D01 met groep 200", r.status_code == 200, r.status_code)
check("D02 afspraak met uitkomst", "[UB-KB] PL 9001" in html and "waarschijnlijk" in html and "geen spoor" in html, html[:400])
check("D02 zonder Mehdi: vooraan", "Mehdi: [UB-KB]" not in html)
check("D03 privéafspraak zonder titel", "Proefafspraak Zeta" not in html)
check("D03 privéoproep zonder naam", "Geheim" not in html)
check("D04 niet gepland: wie, kanaal, minuten", "Sara Proef" in html and "Zoom, 16 min" in html and "project HARC 9004" in html)
r = C.get("/", headers=MET)
html = r.get_data(as_text=True)
check("D05 overzicht laadt", r.status_code == 200, r.status_code)
check("D05 tegels van gisteren", "Gesprekken" in html and "41 min" in html, html[:300])
check("D05 dag zonder bestand", "Nog niet vastgesteld" in html)
t = json.load(open(os.path.join(MAP, "2026", "2026-10-22.json")))
t["gesprekken"] = {"aantal": None, "minuten": None}
t["mail"] = None
json.dump(t, open(os.path.join(MAP, gisteren[:4], f"{gisteren}.json"), "w"))
html = C.get("/", headers=MET).get_data(as_text=True)
check("D06 onbekend is een vraagteken", '<div class="groot">?</div>' in html and "niet gelezen" in html)
open(os.path.join(MAP, gisteren[:4], f"{gisteren}.json"), "w").write("{kapot")
check("D06 kapotte telling valt niet", C.get("/", headers=MET).status_code == 200)
alles = html + C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D07 geen gedachtestreepje", "—" not in alles and "–" not in alles)
check("healthz", C.get("/healthz").get_json().get("ok") is True)

print("dagboek:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
