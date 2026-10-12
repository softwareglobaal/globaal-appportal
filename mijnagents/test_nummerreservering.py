"""Grendel op de nummerreservering van het bord (WP2b, 12-10-2026; draait in de Docker-build: faalt dit, dan
blijft de vorige container staan).

Aanleiding: 2617 stond tegelijk in drie open voorstellen voor drie deals (25, 26 en 27, 05 tot 10-10-2026).
Een open of goedgekeurd dealtitel-voorstel houdt nu zijn nummer vast; twee gelijktijdige aanvragen kunnen niet
hetzelfde nummer reserveren; akkoord controleert opnieuw; een voorstel van vóór WP2b zonder reservering telt mee
als bezet. Fictieve deals en een tijdelijke databank; geen netwerk, geen Pipedrive.
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "test.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "mehdi"}
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def leeg():
    with A.app.app_context():
        A.db().execute("DELETE FROM nummerreservering")
        A.db().execute("DELETE FROM voorstel")
        A.db().commit()


def voorstel(c, deal, nummer, firma=None, naam="contracten-agent"):
    params = {"deal_id": deal, "titel": f"{nummer} Testklant {deal}", "nummer": nummer}
    if firma:
        params["firma"] = firma
    r = c.post("/agent-status", headers=K, json={
        "naam": naam, "status": "waakt", "voorstel": {
            "actie": f"Projectnummer {nummer} toekennen aan deal {deal}", "runbook": "pipedrive-dealtitel",
            "parameters": params}})
    return r.get_json().get("voorstel") or {}


def rijen(sql, *args):
    with A.app.app_context():
        return [dict(r) for r in A.db().execute(sql, args).fetchall()]


def oud_voorstel(deal, nummer, status="open"):
    """Een voorstel zoals vóór WP2b: alleen deal_id en titel, geen reservering."""
    with A.app.app_context():
        vid = A.db().execute(
            "INSERT INTO voorstel(naam,actie,parameters,runbook,status,ts) VALUES(?,?,?,?,?,?)",
            ("contracten-agent", f"Projectnummer {nummer} toekennen aan deal {deal}",
             json.dumps({"deal_id": deal, "titel": f"{nummer} Testklant {deal}"}), "pipedrive-dealtitel", status, A.nu())).lastrowid
        A.db().commit()
    return vid


def besluit(c, vid, keuze):
    return c.post(f"/voorstel/{vid}/besluit", data={"keuze": keuze}, headers=BEHEER)


c = A.app.test_client()

# 1. twee opeenvolgende aanvragen voor verschillende deals: de tweede krijgt het nummer niet
leeg()
a, b = voorstel(c, 900101, "2901"), voorstel(c, 900102, "2901")
check("eerste aanvraag reserveert", a.get("uitkomst") == "gereserveerd" and a.get("bewaard"), a)
check("tweede aanvraag voor andere deal is bezet", b.get("uitkomst") == "bezet" and not b.get("bewaard"), b)
check("er staat maar één voorstel en één reservering",
      len(rijen("SELECT * FROM voorstel")) == 1 and len(rijen("SELECT * FROM nummerreservering WHERE actief=1")) == 1)

# 2. dezelfde deal opnieuw: idempotent, geen tweede voorstel
herhaal = voorstel(c, 900101, "2901")
check("herhalen voor dezelfde deal is idempotent", herhaal.get("uitkomst") == "bestaat"
      and herhaal.get("voorstel_id") == a.get("voorstel_id") and len(rijen("SELECT * FROM voorstel")) == 1, herhaal)

# 3. gelijktijdige aanvragen (eigen verbinding per draad): precies één reservering
leeg()
uitkomsten, slot = [], threading.Lock()


def gelijktijdig(deal):
    uit = voorstel(A.app.test_client(), deal, "2902")
    with slot:
        uitkomsten.append(uit.get("uitkomst"))


draden = [threading.Thread(target=gelijktijdig, args=(900200 + i,)) for i in range(8)]
for d in draden:
    d.start()
for d in draden:
    d.join()
check("van 8 gelijktijdige aanvragen reserveert er precies één", uitkomsten.count("gereserveerd") == 1
      and uitkomsten.count("bezet") == 7, uitkomsten)
check("en er staat precies één reservering voor 2902",
      len(rijen("SELECT * FROM nummerreservering WHERE nummer='2902' AND actief=1")) == 1)

# 4. de databank zelf weigert een tweede actieve reservering (de grendel, los van de code)
try:
    with A.app.app_context():
        A.db().execute("INSERT INTO nummerreservering(firma,reeks,nummer,deal_id,voorstel_id,actief,ts) "
                       "VALUES('harchitects','29','2902','999',999,1,'nu')")
        A.db().commit()
    check("unieke index weigert dubbele actieve reservering", False)
except sqlite3.IntegrityError:
    check("unieke index weigert dubbele actieve reservering", True)

# 5. een goedgekeurd voorstel van een andere deal houdt het nummer vast
leeg()
g = voorstel(c, 900301, "2903")
r = besluit(c, g["voorstel_id"], "goedgekeurd")
check("akkoord zonder conflict lukt", r.status_code == 302
      and rijen("SELECT status FROM voorstel WHERE id=?", g["voorstel_id"])[0]["status"] == "goedgekeurd")
check("goedgekeurd voorstel houdt het nummer bezet", voorstel(c, 900302, "2903").get("uitkomst") == "bezet")
anders = voorstel(c, 900301, "2904")
check("goedgekeurd voorstel verandert niet stilzwijgend van nummer", anders.get("uitkomst") == "geweigerd"
      and "goedgekeurd" in anders.get("reden", ""), anders)

# 6. herstart: de reserveringen staan in de databank, niet in het geheugen
A.init_db()
c = A.app.test_client()
check("na herstart blijft het nummer bezet", voorstel(c, 900303, "2903").get("uitkomst") == "bezet")
check("na herstart blijft dezelfde deal idempotent", voorstel(c, 900301, "2903").get("uitkomst") == "bestaat")

# 7. verkeerde firma en ongeldig nummer: geen voorstel, geen reservering
leeg()
w = voorstel(c, 900401, "2905", firma="unabo")
check("andere firma wordt geweigerd", w.get("uitkomst") == "geweigerd" and not rijen("SELECT * FROM voorstel"), w)
check("ongeldig nummer wordt geweigerd", voorstel(c, 900402, "29x5").get("uitkomst") == "geweigerd")

# 8. weigeren geeft het nummer vrij; daarna kan een andere deal het krijgen
leeg()
e = voorstel(c, 900501, "2906")
besluit(c, e["voorstel_id"], "geweigerd")
check("weigeren geeft de reservering vrij", not rijen("SELECT * FROM nummerreservering WHERE actief=1"))
check("een andere deal kan het nummer daarna reserveren", voorstel(c, 900502, "2906").get("uitkomst") == "gereserveerd")
check("hetzelfde geweigerde voorstel komt niet terug", voorstel(c, 900501, "2906").get("uitkomst") in ("bezet", "eerder_geweigerd"))

# 9. een nieuw nummer voor dezelfde deal laat het open voorstel vervallen en geeft het oude nummer vrij
leeg()
o = voorstel(c, 900601, "2907")
n = voorstel(c, 900601, "2908")
check("nieuw nummer voor dezelfde deal: oud voorstel vervalt", n.get("uitkomst") == "gereserveerd"
      and rijen("SELECT status FROM voorstel WHERE id=?", o["voorstel_id"])[0]["status"] == "vervallen")
check("en het oude nummer is weer vrij", voorstel(c, 900602, "2907").get("uitkomst") == "gereserveerd")

# 10. voorstellen van vóór WP2b (zoals 2617 voor drie deals): tellen mee als bezet, akkoord blokkeert
leeg()
v25, v26, v27 = oud_voorstel(14543, "2617"), oud_voorstel(14566, "2617"), oud_voorstel(14518, "2617")
check("oude voorstellen tellen mee als bezet", voorstel(c, 900701, "2617").get("uitkomst") == "bezet")
r = besluit(c, v26, "goedgekeurd")
check("akkoord op een betwist nummer wordt geweigerd (409)", r.status_code == 409
      and rijen("SELECT status FROM voorstel WHERE id=?", v26)[0]["status"] == "open", r.status_code)
check("de weigering noemt de andere voorstellen", str(v25).encode() in r.data and str(v27).encode() in r.data)
html = c.get("/", headers=BEHEER).data.decode()
check("het bord toont het conflict en schakelt Goedkeuren uit", "nummerconflict" in html and "disabled" in html)
with A.app.app_context():
    check("bordweergave van het conflict per voorstel", A.nummerconflicten_op_bord(A.db()).get(v25, {}).get("anderen") == [v26, v27])
besluit(c, v25, "geweigerd")
besluit(c, v27, "geweigerd")
r = besluit(c, v26, "goedgekeurd")
check("na weigeren van de andere twee lukt akkoord", r.status_code == 302
      and rijen("SELECT status FROM voorstel WHERE id=?", v26)[0]["status"] == "goedgekeurd")
check("akkoord legt de reservering voor het oude voorstel vast",
      rijen("SELECT deal_id FROM nummerreservering WHERE voorstel_id=? AND actief=1", v26) == [{"deal_id": "14566"}])

# 11. de controle vlak vóór uitvoering
leeg()
x = voorstel(c, 900801, "2909")
nc = c.get(f"/api/nummercontrole?voorstel_id={x['voorstel_id']}", headers=K).get_json()
check("controle vóór uitvoering weigert een niet goedgekeurd voorstel", nc["ok"] is False and "open" in nc["reden"], nc)
besluit(c, x["voorstel_id"], "goedgekeurd")
nc = c.get(f"/api/nummercontrole?voorstel_id={x['voorstel_id']}", headers=K).get_json()
check("controle vóór uitvoering geeft groen voor het goedgekeurde voorstel", nc["ok"] is True
      and nc["nummer"] == "2909" and nc["deal_id"] == "900801", nc)
oud_voorstel(900802, "2909")      # een tweede (oud) voorstel met hetzelfde nummer duikt op
nc = c.get(f"/api/nummercontrole?voorstel_id={x['voorstel_id']}", headers=K).get_json()
check("controle vóór uitvoering blokkeert bij een ander voorstel met hetzelfde nummer", nc["ok"] is False, nc)
check("controle vereist het token", c.get(f"/api/nummercontrole?voorstel_id={x['voorstel_id']}").status_code == 403)

# 12. mislukte uitvoering geeft de reservering vrij; de lijst voor de agent is volledig en token-gated
leeg()
y = voorstel(c, 900901, "2910")
besluit(c, y["voorstel_id"], "goedgekeurd")
c.post("/uitvoer-resultaat", headers=K, json={"id": y["voorstel_id"], "uitvoering": "mislukt", "detail": "conflict"})
check("mislukte uitvoering geeft de reservering vrij", not rijen("SELECT * FROM nummerreservering WHERE actief=1"))
voorstel(c, 900902, "2911")
lijst = c.get("/api/nummerreserveringen", headers=K).get_json()
check("lijst voor de agent is volledig", lijst["volledig"] is True and lijst["aantal"] == 1
      and lijst["bezet"][0]["nummer"] == "2911", lijst)
check("lijst vereist het token", c.get("/api/nummerreserveringen").status_code == 403)
check("lijst weigert een andere firma", c.get("/api/nummerreserveringen?firma=unabo", headers=K).status_code == 400)

print(f"\n{ok} geslaagd, {fout} mislukt")
sys.exit(1 if fout else 0)
