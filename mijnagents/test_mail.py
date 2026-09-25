"""Grendel op het maildashboard van het bord (draait in de Docker-build: faalt dit, dan blijft de vorige container staan).

Mehdi, 25-09-2026: "een dashboard dat we de belangrijke zaken van daar kunnen volgen"; 26-09-2026: "ik wil zien hoeveel
mails zijn binnengekomen, hoeveel belangrijk, hoeveel spam, hoeveel reclame, en ik wil de mails opschonen". Deze toetsen
falen zodra de pagina open staat voor wie geen beheer is (afzenders en onderwerpen zijn inhoud), zodra de cijfers niet
kloppen met wat de wachten doorgaven, zodra opruimen kan in een postvak dat alleen gelezen mag worden, zodra een regel op
een heel gratis domein (gmail.com) kan, of zodra een punt dat Mehdi afhandelde bij de volgende ronde terugkomt.
"""
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

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


VANDAAG = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)


def bericht(uniek, soort, van, postvak="mch@h-architects.be", dagen_terug=0, onderwerp="x"):
    return {"uniek": f"{postvak}:{uniek}", "postvak": postvak, "datum": (VANDAAG - timedelta(days=dagen_terug)).isoformat(),
            "van": van, "van_naam": van.split("@")[0], "onderwerp": onderwerp, "soort": soort, "waarom": "proef"}


def punt(uniek, soort, onderwerp, datum, van="mail-mch"):
    return {"van": van, "voor": "mail-regisseur", "soort": "mail", "sleutel": "MCH", "titel": f"MCH: {onderwerp}",
            "uniek": uniek, "inhoud": {"postvak": "mch@h-architects.be", "van": "x@kbc.be", "van_naam": "KBC",
                                       "onderwerp": onderwerp, "datum": datum, "soort": soort, "waarom": "rol bank",
                                       "werkdagen_zonder_antwoord": 3, "voorstel": "beantwoorden"}}


c = A.app.test_client()
for naam, label in (("mail-mch", "De Mailwacht mch@"), ("mail-melo", "De Mailwacht Melodie"),
                    ("mail-regisseur", "De Mailregisseur")):
    c.post("/api/agent", json={"naam": naam, "label": label, "type": "mail", "rol": "bewaakt een postvak"}, headers=K)
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "postvakken": [{"postvak": "mch@h-architects.be", "wacht": "mail-mch", "schrijven": 1}],
                                     "rijen": [bericht("a", "hoog", "x@kbc.be"), bericht("b", "rommel", "promo@winkel.be"),
                                               bericht("c", "rommel", "promo@winkel.be", dagen_terug=1),
                                               bericht("d", "melding", "noreply@bpost.be"), bericht("e", "verdacht", "fake@gmail.com"),
                                               bericht("oud", "rommel", "promo@winkel.be", dagen_terug=40)]})
c.post("/api/mail", headers=K, json={"wacht": "mail-melo", "postvakken": [{"postvak": "melodiebvba@gmail.com", "wacht": "mail-melo", "schrijven": 0}],
                                     "rijen": [bericht("f", "rommel", "news@syndicus.be", postvak="melodiebvba@gmail.com")]})
c.post("/api/klaarzet", json={"items": [
    punt("opvolgen:mail-mch:<a>", "midden", "Gewone vraag van een klant", "2026-09-01T09:00:00+02:00"),
    punt("opvolgen:mail-mch:<b>", "hoog", "Herinnering premiebetaling", "2026-09-24T09:00:00+02:00"),
]}, headers=K)

check("wie geen beheer is, ziet de pagina niet", c.get("/mail", headers=ANDER).status_code == 403)
check("wie geen token heeft, kan geen mail doorgeven", c.post("/api/mail", json={"rijen": []}).status_code == 403)
r = c.get("/mail?periode=7", headers=BEHEER)
html = r.get_data(as_text=True)
check("beheer ziet de pagina", r.status_code == 200, r.status_code)
kpi = html.split('class="kpirij"')[1].split("</section>")[0]
check("binnengekomen telt de periode, niet wat ouder is (6 van 7)", ">6</div>" in kpi, kpi[:300])
check("ruis is melding, onbekend, reclame en verdacht samen (5 van 6 = 83%)", ">83<small>%" in kpi)
check("verdacht staat apart", "Verdacht (phishing)" in kpi)
check("de grafiek staat erop", "<svg" in html and "Mails per dag" in html)
check("belangrijk staat boven gewone mail, ook als die langer wacht",
      html.find("Herinnering premiebetaling") < html.find("Gewone vraag van een klant"))
opschonen = html.split('id="opschonen"')[1].split("</section>")[0]
check("de afzender met de meeste ruis staat bovenaan", opschonen.find("promo@winkel.be") < opschonen.find("noreply@bpost.be"))
melo = next(rij for rij in opschonen.split("<tr") if "news@syndicus.be" in rij)
check("opruimen kan niet in een postvak dat alleen gelezen mag worden", "Opruimen</button>" not in melo)
check("maar ruis of belangrijk zetten kan daar wel", "Ruis</button>" in melo)
check("heel gmail.com opruimen staat niet als knop", "alle mail van gmail.com" not in opschonen)

c.post("/mail/regel", headers=BEHEER, data={"postvak": "mch@h-architects.be", "wie": "promo@winkel.be", "actie": "opruimen"})
regels = c.get("/api/mailregels", headers=K).get_json()["regels"]
check("een regel van Mehdi komt bij de wachten", [(x["wie"], x["actie"]) for x in regels] == [("promo@winkel.be", "opruimen")], regels)
check("een regel op heel gmail.com wordt geweigerd",
      c.post("/mail/regel", headers=BEHEER, data={"postvak": "mch@h-architects.be", "wie": "@gmail.com", "actie": "opruimen"}).status_code == 400)
check("een eigen domein ook", c.post("/mail/regel", headers=BEHEER, data={"postvak": "*", "wie": "@h-architects.be", "actie": "ruis"}).status_code == 400)
check("wie geen beheer is, kan geen regel zetten",
      c.post("/mail/regel", headers=ANDER, data={"postvak": "*", "wie": "x@y.be", "actie": "ruis"}).status_code == 403)
c.post("/mail/regel", headers=BEHEER, data={"postvak": "mch@h-architects.be", "wie": "promo@winkel.be", "actie": "weg"})
check("ongedaan maken haalt de regel weg", c.get("/api/mailregels", headers=K).get_json()["regels"] == [])

c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [], "opgeruimd": ["mch@h-architects.be:b"]})
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [], "verplaatst": [{"uniek": "mch@h-architects.be:d", "naar": "INBOX.Bestellingen"}]})
with A.app.app_context():
    check("wat de wacht sorteerde, krijgt zijn map",
          A.db().execute("SELECT naar, opgeruimd FROM mailbericht WHERE uniek='mch@h-architects.be:d'").fetchone()[:] == ("INBOX.Bestellingen", 0))
check("de tegel telt wat uit de inbox gesorteerd is", "Uit de inbox gesorteerd" in c.get("/mail?periode=7", headers=BEHEER).get_data(as_text=True))
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [bericht("b", "rommel", "promo@winkel.be")]})
with A.app.app_context():
    check("opgeruimd blijft staan als de wacht het bericht later nog eens doorgeeft",
          A.db().execute("SELECT opgeruimd FROM mailbericht WHERE uniek='mch@h-architects.be:b'").fetchone()[0] == 1)
    kid = A.db().execute("SELECT id FROM klaarzet WHERE uniek='opvolgen:mail-mch:<b>'").fetchone()["id"]
    kid_a = A.db().execute("SELECT id FROM klaarzet WHERE uniek='opvolgen:mail-mch:<a>'").fetchone()["id"]

c.post(f"/mail/{kid}/afgehandeld", headers=BEHEER)
check("wie geen beheer is, kan niets afhandelen", c.post(f"/mail/{kid}/terug", headers=ANDER).status_code == 403)
c.post("/api/klaarzet", json={"items": [punt("opvolgen:mail-mch:<b>", "hoog", "Herinnering premiebetaling",
                                              "2026-09-24T09:00:00+02:00")]}, headers=K)
with A.app.app_context():
    st = A.db().execute("SELECT status, opgepakt_door FROM klaarzet WHERE id=?", (kid,)).fetchone()
check("afgehandeld blijft afgehandeld als de wacht hetzelfde bericht opnieuw klaarzet", st["status"] == "opgepakt", dict(st))
check("wie afhandelde, staat erbij", "mehdi" in (st["opgepakt_door"] or ""))
html = c.get("/mail", headers=BEHEER).get_data(as_text=True)
open_deel = html.split('id="opvolgen"')[1].split("</section>")[0]
check("afgehandeld staat niet meer bij de open punten", "Herinnering premiebetaling" not in open_deel)
check("afgehandeld staat bij de laatste zeven dagen", "Herinnering premiebetaling" in html.split("<details")[1])
c.post(f"/mail/{kid}/terug", headers=BEHEER)
with A.app.app_context():
    check("terugzetten maakt het weer open",
          A.db().execute("SELECT status FROM klaarzet WHERE id=?", (kid,)).fetchone()["status"] == "klaar")
c.post(f"/mail/{kid_a}/ruis", headers=BEHEER)
check("Ruis op een open punt handelt het af en zet de afzender op ruis in dat postvak",
      [(x["postvak"], x["wie"], x["actie"]) for x in c.get("/api/mailregels", headers=K).get_json()["regels"]]
      == [("mch@h-architects.be", "x@kbc.be", "ruis")])
check("De Mailregisseur leest alleen wat open is",
      [i["uniek"] for i in c.get("/api/klaarzet?voor=mail-regisseur", headers=K).get_json()["items"]] == ["opvolgen:mail-mch:<b>"])
check("het bord heeft een knop Mail voor beheer", "/mail" in c.get("/", headers=BEHEER).get_data(as_text=True))
check("het bord toont die knop niet aan anderen", 'href="/mail"' not in c.get("/", headers=ANDER).get_data(as_text=True))
check("werkdagen tellen het weekend niet (vrijdag tot maandag is een werkdag)",
      A._werkdagen_sinds("2026-09-25T10:00:00+02:00", date(2026, 9, 28)) == 1)
check("een onleesbare datum geeft geen fout", A._werkdagen_sinds("", date(2026, 9, 28)) is None)

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
