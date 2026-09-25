"""Grendel op het maildashboard van het bord (draait in de Docker-build: faalt dit, dan blijft de vorige container staan).

Mehdi, 25-09-2026: "een dashboard dat we de belangrijke zaken van daar kunnen volgen". Deze toetsen falen zodra de
pagina open staat voor wie geen beheer is (afzenders en onderwerpen zijn inhoud), zodra belangrijke mail niet meer
bovenaan staat, of zodra een punt dat Mehdi afhandelde bij de volgende ronde van de wacht terugkomt.
"""
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
ANDER = {"X-authentik-groups": "agents", "X-authentik-username": "siyan"}
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def punt(uniek, soort, onderwerp, datum, van="mail-mch"):
    return {"van": van, "voor": "mail-regisseur", "soort": "mail", "sleutel": "MCH", "titel": f"MCH: {onderwerp}",
            "uniek": uniek, "inhoud": {"postvak": "mch@h-architects.be", "van": "x@kbc.be", "van_naam": "KBC",
                                       "onderwerp": onderwerp, "datum": datum, "soort": soort, "waarom": "rol bank",
                                       "werkdagen_zonder_antwoord": 3, "voorstel": "beantwoorden"}}


c = A.app.test_client()
for naam, label in (("mail-mch", "De Mailwacht mch@"), ("mail-hinv", "De Mailwacht info@ H-Invest"),
                    ("mail-regisseur", "De Mailregisseur")):
    c.post("/api/agent", json={"naam": naam, "label": label, "type": "mail", "rol": "bewaakt mch@h-architects.be"}, headers=K)
c.post("/api/klaarzet", json={"items": [
    punt("opvolgen:mail-mch:<a>", "midden", "Gewone vraag van een klant", "2026-09-01T09:00:00+02:00"),
    punt("opvolgen:mail-mch:<b>", "hoog", "Herinnering premiebetaling", "2026-09-24T09:00:00+02:00"),
]}, headers=K)

check("wie geen beheer is, ziet de pagina niet", c.get("/mail", headers=ANDER).status_code == 403)
r = c.get("/mail", headers=BEHEER)
html = r.get_data(as_text=True)
check("beheer ziet de pagina", r.status_code == 200, r.status_code)
check("elke actieve wacht heeft een blok, ook zonder punten", 'id="mail-hinv"' in html and "Niets open." in html)
check("De Mailregisseur is geen postvak", 'id="mail-regisseur"' not in html)
check("belangrijk staat boven gewone mail, ook als die langer wacht",
      html.find("Herinnering premiebetaling") < html.find("Gewone vraag van een klant"))

with A.app.app_context():
    kid = A.db().execute("SELECT id FROM klaarzet WHERE uniek='opvolgen:mail-mch:<b>'").fetchone()["id"]
c.post(f"/mail/{kid}/afgehandeld", headers=BEHEER)
check("wie geen beheer is, kan niets afhandelen", c.post(f"/mail/{kid}/terug", headers=ANDER).status_code == 403)
c.post("/api/klaarzet", json={"items": [punt("opvolgen:mail-mch:<b>", "hoog", "Herinnering premiebetaling",
                                              "2026-09-24T09:00:00+02:00")]}, headers=K)
with A.app.app_context():
    st = A.db().execute("SELECT status, opgepakt_door FROM klaarzet WHERE id=?", (kid,)).fetchone()
check("afgehandeld blijft afgehandeld als de wacht hetzelfde bericht opnieuw klaarzet", st["status"] == "opgepakt", dict(st))
check("wie afhandelde, staat erbij", "mehdi" in (st["opgepakt_door"] or ""))
html = c.get("/mail", headers=BEHEER).get_data(as_text=True)
open_deel = html.split('class="klaar"')[0]
check("afgehandeld staat niet meer bij de open punten", "Herinnering premiebetaling" not in open_deel)
check("afgehandeld staat bij de laatste zeven dagen", "Herinnering premiebetaling" in html.split('class="klaar"')[1])
c.post(f"/mail/{kid}/terug", headers=BEHEER)
with A.app.app_context():
    check("terugzetten maakt het weer open",
          A.db().execute("SELECT status FROM klaarzet WHERE id=?", (kid,)).fetchone()["status"] == "klaar")
check("De Mailregisseur leest alleen wat open is",
      [i["uniek"] for i in c.get("/api/klaarzet?voor=mail-regisseur", headers=K).get_json()["items"]].count("opvolgen:mail-mch:<b>") == 1)
check("het bord heeft een knop Mail voor beheer", "/mail" in c.get("/", headers=BEHEER).get_data(as_text=True))
check("het bord toont die knop niet aan anderen", 'href="/mail"' not in c.get("/", headers=ANDER).get_data(as_text=True))
from datetime import date  # noqa: E402
check("werkdagen tellen het weekend niet (vrijdag tot maandag is een werkdag)",
      A._werkdagen_sinds("2026-09-25T10:00:00+02:00", date(2026, 9, 28)) == 1)
check("een onleesbare datum geeft geen fout", A._werkdagen_sinds("", date(2026, 9, 28)) is None)

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
