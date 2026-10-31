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
# Locatie: zonder dashboard (zoals hierboven) een vraagteken, met dashboard de echte dagindeling.
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D10 locatie onbereikbaar: zin", "Locatie-dashboard is nu niet bereikbaar" in html)
check("D10 locatie onbereikbaar: tegel ?", "locatie niet bereikbaar" in html)
LOC = json.load(open(os.path.join(PROEF, "locatie-2026-10-22.json")))


def nep_locatie(pad):
    if pad.startswith("/api/dagboek/2026-10-22"):
        return LOC
    if pad.startswith("/api/dagcijfers"):
        return {"dagen": {gisteren: {"punten": 80, "km": 72.3, "verblijven": 3, "onderweg_min": 86}}}
    return None


A.haal_locatie = nep_locatie
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D08 plek met project", "project HARC 9004, Proefstraat 1" in html, html[-2500:])
check("D08 thuis en rit met km", "<b>Thuis</b>" in html and "rit auto, 36,2 km" in html)
check("D08 tracker in de auto", "waar de auto stond" in html)
check("D08 tegel Onderweg op de dag", "72,3 km" in html and "3 plekken" in html)
for ext in ("md", "json"):
    shutil.copy(os.path.join(PROEF, f"2026-10-22.{ext}"), os.path.join(MAP, gisteren[:4], f"{gisteren}.{ext}"))
html = C.get("/", headers=MET).get_data(as_text=True)
check("D09 overzicht tegel Onderweg", "Onderweg" in html and "72,3 km" in html and "1u26 rijden" in html)
check("D07 geen gedachtestreepje (locatie)", "—" not in html and "–" not in html)
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D11 blok gesprekken in Zoom, Fathom en Plaud", "Gesprekken in Zoom, Fathom en Plaud" in html
      and "<b>Ruben (H-AI &amp; ICT)</b> <span class=\"zacht\">Zoom, 25 min</span>" in html, html[:200])
check("D11 tegel noemt de bron", "2 Zoom; 41 min" in html)
check("healthz", C.get("/healthz").get_json().get("ok") is True)

print("dagboek:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
