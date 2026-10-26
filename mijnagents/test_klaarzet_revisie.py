"""Grendel op revisies van klaargezette items (nacontrole Plaud-agent v1.1, 12-10-2026, P1-5).

Een al opgepakt item dat om revisie vraagt (revisie: true) en een nieuwe beoordeling krijgt, wordt niet
stil genegeerd: de oude versie gaat naar klaarzet_revisie (met wie ze oppakte en een herstelstatus), de
nieuwe inhoud wordt zichtbaar met status klaar. Zonder revisie-vlag blijft het oude gedrag: een
opgepakt item verandert niet (andere agents zetten soms elke ronde licht gewijzigde inhoud klaar).
Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import json
import os
import sys
import tempfile

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "test.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
C = A.app.test_client()
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


def zet(voor, prive, revisie=True, uniek="plaud:of_proef"):
    it = {"van": "plaud-wacht", "voor": voor, "soort": "transcript", "sleutel": "2531", "titel": "Plaud: proef",
          "uniek": uniek, "inhoud": {"firma": "HARC", "projectnummer": "2531", "prive": prive}}
    if revisie:
        it["revisie"] = True
    return C.post("/api/klaarzet", json={"items": [it]}, headers=K).get_json()


def lees(uniek="plaud:of_proef"):
    return C.get("/api/klaarzet?status=alle&uniek=" + uniek, headers=K).get_json()["items"][0]


zet("h-architects", False)
kid = lees()["id"]
C.post(f"/api/klaarzet/{kid}/opgepakt", json={"door": "werfverslag-voorbereider"}, headers=K)
r = zet("mehdi", True)
it = lees()
check("herzien gemeld", r.get("herzien") == 1, r)
check("nieuwe beoordeling zichtbaar", it["voor"] == "mehdi" and json.loads(it["inhoud"])["prive"] is True and it["status"] == "klaar", it)
rev = C.get("/api/klaarzet/revisies?uniek=plaud:of_proef", headers=K).get_json()["revisies"]
check("revisie met oude versie en herstel", len(rev) == 1 and rev[0]["oud_voor"] == "h-architects" and rev[0]["oud_status"] == "opgepakt"
      and rev[0]["opgepakt_door"] == "werfverslag-voorbereider" and rev[0]["herstel"], rev)
r = zet("mehdi", True)
check("zelfde inhoud: geen nieuwe revisie", r.get("herzien") == 0 and r.get("bestaand") == 1, r)
zet("h-architects", False, revisie=False, uniek="agenda:proef")
kid = lees("agenda:proef")["id"]
C.post(f"/api/klaarzet/{kid}/opgepakt", json={"door": "x"}, headers=K)
r = zet("mehdi", True, revisie=False, uniek="agenda:proef")
it = lees("agenda:proef")
check("zonder revisie-vlag blijft een opgepakt item ongewijzigd", it["status"] == "opgepakt" and it["voor"] == "h-architects" and r.get("herzien") == 0, (r, it))
# vervang (De Communicatiebundelaar, Codex CB04 en CB12): ook een opgepakt item volgt de bron, zonder revisiekopie
def dagitem(inhoud):
    return C.post("/api/klaarzet", json={"items": [{"van": "communicatie-bundelaar", "voor": "mehdi", "soort": "communicatie",
                  "sleutel": "2026-10-25", "titel": "Communicatie proef", "uniek": "communicatie:dag:proef", "vervang": True,
                  "inhoud": inhoud}]}, headers=K).get_json()


dagitem({"personen": [{"naam": "Proefpersoon Zeta"}]})
kid = lees("communicatie:dag:proef")["id"]
C.post(f"/api/klaarzet/{kid}/opgepakt", json={"door": "x"}, headers=K)
r = dagitem({"personen": []})
it = lees("communicatie:dag:proef")
check("vervang: opgepakt item volgt de bron en staat weer op klaar", it["status"] == "klaar" and "Zeta" not in it["inhoud"]
      and r.get("bijgewerkt") == 1, (r, it))
rev = C.get("/api/klaarzet/revisies?uniek=communicatie:dag:proef", headers=K).get_json()["revisies"]
check("vervang: geen kopie van de oude inhoud", rev == [], rev)
zet("h-architects", False, revisie=False, uniek="agenda:vervang")
kid = lees("agenda:vervang")["id"]
C.post(f"/api/klaarzet/{kid}/opgepakt", json={"door": "x"}, headers=K)
it = {"van": "plaud-wacht", "voor": "mehdi", "soort": "transcript", "sleutel": "2531", "titel": "anders", "uniek": "agenda:vervang",
      "vervang": True, "inhoud": {"x": 1}}
C.post("/api/klaarzet", json={"items": [it]}, headers=K)
check("vervang geldt alleen voor de dagitems van De Communicatiebundelaar", lees("agenda:vervang")["status"] == "opgepakt")
print(f"{fout} fout")
sys.exit(1 if fout else 0)
