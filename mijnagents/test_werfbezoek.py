"""Grendel op de werfbezoek-rijen van het bord (draait in de Docker-build: faalt dit, dan blijft de vorige container staan).

Gebeurd op 24-09-2026: de projectmap van 2145 verhuisde van '4. STAN Execution waiting to start' naar
'5. STAN Execution ONGOING'. Het bord maakte voor dezelfde vijf bezoeken nieuwe, lege rijen (145-149) naast de oude
met de gegevens van de schrijver (19-23); de bezoekpagina toonde de lege, de schrijver las de oude map die niet meer
bestond. Deze toetsen falen zodra de herkoppeling, de keuze van de levende rij of de veiligheid van de opruiming
wegvalt, en ook als hetzelfde voorstel weer elke ronde opnieuw op het bord komt.
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
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "mehdi"}
OUD = "/Work All/01. H-A WORK/0 H-A Standaard projects/4. STAN Execution waiting to start/2145 Vertommensberg 9"
NIEUW = "/Work All/01. H-A WORK/0 H-A Standaard projects/5. STAN Execution ONGOING/2145 Vertommensberg 9"
BEZOEK = "/_00. Communication/2026-06-06 bezoek klant - plaatsbezoek werf"
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def rij(pm, datum="2026-06-06", volgnr=1, rel=BEZOEK, **extra):
    return {"dossier": "2145", "datum": datum, "volgnr": volgnr, "projectmap": pm, "bezoekmap": pm + rel,
            "bronnen": {"nr_label": "PB1", "soort_bezoek": "plaatsbezoek"}, "controles": [], "taken": [], "stand": "te verzamelen", **extra}


def rijen_db():
    with A.app.app_context():
        return [dict(r) for r in A.db().execute("SELECT * FROM werfbezoek ORDER BY id").fetchall()]


def leeg_db():
    with A.app.app_context():
        A._werfbezoek_tabel(A.db())
        A.db().execute("DELETE FROM werfbezoek")
        A.db().execute("DELETE FROM voorstel")
        A.db().commit()


c = A.app.test_client()

# 1. verhuis zonder rij op het nieuwe pad: de oude rij gaat mee, met haar gegevens, en er komt geen tweede rij
leeg_db()
c.post("/api/werfbezoek", json={"rijen": [rij(OUD)]}, headers=K)
c.post("/api/werfbezoek", json={"rijen": [{"dossier": "2145", "datum": "2026-06-06", "bezoekmap": OUD + BEZOEK, "_alleen": ["gegevens", "bijlagen"],
                                           "gegevens": {"gegevens": [{"veld": "bouwheer", "waarde": "x"}]},
                                           "bijlagen": [{"naam": "a.docx", "pad": OUD + BEZOEK + "/a.docx"}]}]}, headers=K)
oud_id = rijen_db()[0]["id"]
uit = c.post("/api/werfbezoek", json={"rijen": [rij(NIEUW, vorige_bezoekmappen=[OUD + BEZOEK])]}, headers=K).get_json()
r = rijen_db()
check("verhuis maakt geen nieuwe rij", len(r) == 1, f"{len(r)} rijen")
check("de oude rij (zelfde id) staat nu op het nieuwe pad", r[0]["id"] == oud_id and r[0]["bezoekmap"] == NIEUW + BEZOEK and r[0]["projectmap"] == NIEUW)
check("de gegevens van de schrijver gaan mee", json.loads(r[0]["gegevens"]).get("gegevens"))
check("de paden in de bijlagen wijzen naar het nieuwe pad", json.loads(r[0]["bijlagen"])[0]["pad"] == NIEUW + BEZOEK + "/a.docx", r[0]["bijlagen"])
check("het antwoord meldt de herkoppeling", uit["herkoppeld"] and uit["herkoppeld"][0]["wat"] == "herkoppeld", uit)

# 2. de toestand van 2145: oude rij met gegevens én al een lege rij op het nieuwe pad
leeg_db()
c.post("/api/werfbezoek", json={"rijen": [rij(OUD)]}, headers=K)
c.post("/api/werfbezoek", json={"rijen": [{"dossier": "2145", "datum": "2026-06-06", "bezoekmap": OUD + BEZOEK, "_alleen": ["gegevens"],
                                           "gegevens": {"gegevens": [{"veld": "bouwheer", "waarde": "x"}]}}]}, headers=K)
c.post("/api/werfbezoek", json={"rijen": [rij(NIEUW)]}, headers=K)
oud_id, nieuw_id = [x["id"] for x in rijen_db()]
uit = c.post("/api/werfbezoek", json={"rijen": [rij(NIEUW, vorige_bezoekmappen=[OUD + BEZOEK])]}, headers=K).get_json()
r = {x["id"]: x for x in rijen_db()}
check("de rij van het nieuwe pad krijgt de gegevens van de oude", json.loads(r[nieuw_id]["gegevens"]).get("gegevens"))
check("de oude rij blijft staan (niets wissen zonder ja)", oud_id in r)
check("de oude rij is gemarkeerd als dubbel", r[oud_id]["stand"] == A.WERF_DUBBEL, r[oud_id]["stand"])
check("het antwoord geeft het paar voor het opruimvoorstel",
      uit["herkoppeld"] and uit["herkoppeld"][0].get("dubbel") == oud_id and uit["herkoppeld"][0]["id"] == nieuw_id, uit)
lees = c.get("/api/werfbezoek?dossier=2145&volgnr=1", headers=K).get_json()["rijen"]
check("de schrijver leest de levende rij, niet de dubbel", lees[0]["id"] == nieuw_id, [x["id"] for x in lees])
with A.app.app_context():
    A.db().execute("UPDATE werfbezoek SET gegevens='' WHERE id=?", (nieuw_id,))
    A.db().commit()
bl = c.get("/werfverslag/2145/1", headers=BEHEER).get_data(as_text=True)
check("de bezoekpagina toont de levende rij", "5. STAN Execution ONGOING" in bl and "4. STAN Execution waiting" not in bl)
ov = c.get("/werfverslagen", headers=BEHEER).get_data(as_text=True)
check("het overzicht toont de dubbel apart", "oude rij(en) van vóór de verhuis" in ov)

# 3. opruimen: weigert zolang de rij die blijft iets mist, wist daarna met een kopie
leeg = c.post("/api/werfbezoek/opruimen", json={"paren": [[oud_id, nieuw_id]]}, headers=K).get_json()
check("opruimen weigert als de rij die blijft de gegevens nog mist", not leeg["gewist"] and oud_id in {x["id"] for x in rijen_db()}, leeg)
c.post("/api/werfbezoek", json={"rijen": [rij(NIEUW, vorige_bezoekmappen=[OUD + BEZOEK])]}, headers=K)
vreemd = c.post("/api/werfbezoek/opruimen", json={"paren": [[nieuw_id, nieuw_id]]}, headers=K).get_json()
check("opruimen weigert een rij die geen verhuisde dubbel is", not vreemd["gewist"], vreemd)
check("opruimen zonder token kan niet", c.post("/api/werfbezoek/opruimen", json={"paren": [[oud_id, nieuw_id]]}).status_code == 403)
weg = c.post("/api/werfbezoek/opruimen", json={"paren": [[oud_id, nieuw_id]]}, headers=K).get_json()
check("opruimen wist de dubbel", weg["gewist"] == [oud_id] and oud_id not in {x["id"] for x in rijen_db()}, weg)
kopie = [json.loads(x) for x in open(A.WERF_GEWIST)] if os.path.exists(A.WERF_GEWIST) else []
check("de gewiste rij staat volledig in de kopie", kopie and kopie[-1]["rij"]["id"] == oud_id and kopie[-1]["rij"]["gegevens"])

# 4. een voorstel dat elke ronde terugkomt, staat maar één keer op het bord
leeg_db()
v = {"actie": "Dubbele werfbezoek-rijen opruimen", "runbook": "werfbezoek-dubbels", "parameters": {"sleutel": "werfbezoek-dubbels", "paren": [[1, 2]]}}
for _ in range(3):
    c.post("/agent-status", json={"naam": "werfverslag-voorbereider", "status": "klaar", "voorstel": v}, headers=K)
with A.app.app_context():
    vs = [dict(x) for x in A.db().execute("SELECT * FROM voorstel ORDER BY id").fetchall()]
check("hetzelfde voorstel komt maar één keer", len(vs) == 1, f"{len(vs)} voorstellen")
with A.app.app_context():
    A.db().execute("UPDATE voorstel SET status='geweigerd'")
    A.db().commit()
c.post("/agent-status", json={"naam": "werfverslag-voorbereider", "status": "klaar", "voorstel": v}, headers=K)
with A.app.app_context():
    n = A.db().execute("SELECT COUNT(*) FROM voorstel").fetchone()[0]
check("wat Mehdi weigerde, komt niet elke ronde terug", n == 1, f"{n} voorstellen")
v2 = dict(v, actie="Dubbele werfbezoek-rijen opruimen (meer)", parameters={"sleutel": "werfbezoek-dubbels", "paren": [[1, 2], [3, 4]]})
with A.app.app_context():
    A.db().execute("UPDATE voorstel SET status='open'")
    A.db().commit()
c.post("/agent-status", json={"naam": "werfverslag-voorbereider", "status": "klaar", "voorstel": v2}, headers=K)
with A.app.app_context():
    st = [x["status"] for x in A.db().execute("SELECT status FROM voorstel ORDER BY id").fetchall()]
check("een ruimer voorstel met dezelfde sleutel vervangt het open voorstel", st == ["vervallen", "open"], st)
for _ in range(2):
    c.post("/agent-status", json={"naam": "ontwikkelaar", "status": "klaar", "voorstel": {"actie": "Lees het ontwikkelverslag"}}, headers=K)
with A.app.app_context():
    n = A.db().execute("SELECT COUNT(*) FROM voorstel WHERE naam='ontwikkelaar'").fetchone()[0]
check("een voorstel zonder parameters (alleen een signaal) blijft zoals vroeger", n == 2, f"{n}")

print(f"\n{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
