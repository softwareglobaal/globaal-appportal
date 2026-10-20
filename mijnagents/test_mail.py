"""Grendel op het maildashboard van het bord (draait in de Docker-build: faalt dit, dan blijft de vorige container staan).

Mehdi, 25-09-2026: "een dashboard dat we de belangrijke zaken van daar kunnen volgen"; 26-09-2026: "ik wil zien hoeveel
mails zijn binnengekomen, hoeveel belangrijk, hoeveel spam, hoeveel reclame, en ik wil de mails opschonen". Deze toetsen
falen zodra de pagina open staat voor wie geen beheer is (afzenders en onderwerpen zijn inhoud), zodra de cijfers niet
kloppen met wat de wachten doorgaven, zodra opruimen kan in een postvak dat alleen gelezen mag worden, zodra een regel op
een heel gratis domein (gmail.com) kan, of zodra een punt dat Mehdi afhandelde bij de volgende ronde terugkomt.

Sinds 19-10-2026 (driehoeksoverleg, 3-0): een bron voor wat openstaat. Ze falen zodra de wacht (antwoord op /api/mail), De
Mailregisseur (/api/mail/open), de tegel Op te volgen en de kolom Open per postvak een ander getal geven; zodra een besluit
van Mehdi of een gevonden antwoord door een volgende ronde verdwijnt; zodra /mail per bericht geen ontvangst, afzender,
postvak, onderwerp, status, wachttijd en volgende stap toont; of zodra terugzetten uit Opgeruimd niet rondgaat.
"""
import os
import sqlite3
import sys
import tempfile
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

A_BRUSSEL = ZoneInfo("Europe/Brussels")

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "test.db")
os.environ["AGENTS_TOKEN"] = "proef"
# De tabel zoals ze voor 19-10-2026 was: met de kolom 'lijst'. De nieuwe code hernoemt ze naar 'mailinglijst'.
_oud = sqlite3.connect(os.environ["AGENTS_DB"])
_oud.executescript("""
    CREATE TABLE mailbericht (uniek TEXT PRIMARY KEY, wacht TEXT, postvak TEXT, map TEXT DEFAULT '', datum TEXT, dag TEXT,
        van TEXT, van_naam TEXT DEFAULT '', domein TEXT DEFAULT '', onderwerp TEXT DEFAULT '', soort TEXT,
        waarom TEXT DEFAULT '', lijst INTEGER DEFAULT 0, beantwoord INTEGER DEFAULT 0, opgeruimd INTEGER DEFAULT 0, ts TEXT);
    INSERT INTO mailbericht(uniek, wacht, postvak, datum, dag, van, soort, lijst)
        VALUES('mch@h-architects.be:<nieuwsbrief>', 'mail-mch', 'mch@h-architects.be', '2026-08-01T10:00:00+02:00',
               '2026-08-01', 'news@lijst.be', 'melding', 1);
""")
_oud.commit()
_oud.close()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402
import eenmalig_mail_een_bron as OVERGANG  # noqa: E402

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


# Middag in Brussel: rond middernacht viel 'vandaag' in UTC op een andere dag dan op de pagina (gezien 20-10-2026 00:05).
VANDAAG = datetime.now(A_BRUSSEL).replace(hour=12, minute=0, second=0, microsecond=0)


def bericht(uniek, soort, van, postvak="mch@h-architects.be", dagen_terug=0, onderwerp="x", **extra):
    r = {"uniek": f"{postvak}:{uniek}", "postvak": postvak, "datum": (VANDAAG - timedelta(days=dagen_terug)).isoformat(),
         "van": van, "van_naam": van.split("@")[0], "onderwerp": onderwerp, "soort": soort, "waarom": "proef",
         "message_id": uniek if uniek.startswith("<") else "", "map": "INBOX",
         "opvolging": {"hoog": "open", "midden": "open", "actie": "open"}.get(soort, "geen")}
    r.update(extra)
    return r


def db():
    with A.app.app_context():
        return A.db()


def rij(uniek):
    with A.app.app_context():
        return dict(A.db().execute("SELECT * FROM mailbericht WHERE uniek=?", (uniek,)).fetchone())


def tellingen(html):
    """De vier tellingen: tegel Op te volgen, som van de kolom Open, /api/mail/open, en het antwoord aan de wacht."""
    tegel = int(html.split('id="tegel-open"')[1].split('class="groot">')[1].split("<")[0])
    kolom = sum(int(x.split(">", 1)[1].split("<")[0]) for x in html.split('class="num open-per"')[1:])
    api = c.get("/api/mail/open", headers=K).get_json()["aantal"]
    return tegel, kolom, api


c = A.app.test_client()
for naam, label in (("mail-mch", "De Mailwacht mch@"), ("mail-melo", "De Mailwacht Melodie"),
                    ("mail-regisseur", "De Mailregisseur")):
    c.post("/api/agent", json={"naam": naam, "label": label, "type": "mail", "rol": "bewaakt een postvak"}, headers=K)

MCH = [bericht("<a@kbc>", "hoog", "x@kbc.be", onderwerp="Herinnering premiebetaling"),
       bericht("<klant@x>", "midden", "klant@bouwheer.be", dagen_terug=6, onderwerp="Gewone vraag van een klant"),
       bericht("<twijfel@x>", "midden", "jan@aannemer.be", dagen_terug=2, onderwerp="Planning werf",
               opvolging="onzeker", antwoord_door="mch@h-architects.be", antwoord_ts=(VANDAAG - timedelta(days=1)).isoformat(),
               stap="nakijken: zelfde onderwerp zonder draad"),
       bericht("<antw@x>", "hoog", "notaris@notaris.be", dagen_terug=1, onderwerp="Akte verkoop",
               opvolging="beantwoord", antwoord_door="info@h-invest.be", antwoord_ts=VANDAAG.isoformat()),
       bericht("<nieuw@x>", "midden", "piet@partner.be", onderwerp="Vraag van vandaag", opvolging="wacht"),
       bericht("<oudactie@x>", "actie", "noreply@bank.be", dagen_terug=9, onderwerp="Betaling mislukt", opvolging="verlopen"),
       bericht("b", "rommel", "promo@winkel.be"), bericht("c", "rommel", "promo@winkel.be", dagen_terug=1),
       bericht("d", "melding", "noreply@bpost.be"), bericht("e", "verdacht", "fake@gmail.com"),
       bericht("oud", "rommel", "promo@winkel.be", dagen_terug=40),
       bericht("<r1@winkel>", "rommel", "deals@shop.be", auto_opruimen="droog"),
       bericht("<r2@winkel>", "rommel", "deals@shop.be", dagen_terug=1, auto_opruimen="verplaatst"),
       bericht("<nl@x>", "melding", "nieuws@krant.be", lijst=1)]
antw_mch = c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": MCH, "opgeruimd": ["mch@h-architects.be:<r2@winkel>"],
                                                 "postvakken": [{"postvak": "mch@h-architects.be", "wacht": "mail-mch", "schrijven": 1}]}).get_json()
antw_melo = c.post("/api/mail", headers=K, json={"wacht": "mail-melo", "postvakken": [{"postvak": "melodiebvba@gmail.com", "wacht": "mail-melo", "schrijven": 0}],
                                                  "rijen": [bericht("f", "rommel", "news@syndicus.be", postvak="melodiebvba@gmail.com"),
                                                            bericht("<m@x>", "hoog", "info@fod.be", postvak="melodiebvba@gmail.com",
                                                                    onderwerp="Aanslag vennootschapsbelasting", dringend=1)]}).get_json()

check("wie geen beheer is, ziet de pagina niet", c.get("/mail", headers=ANDER).status_code == 403)
check("wie geen token heeft, kan geen mail doorgeven", c.post("/api/mail", json={"rijen": []}).status_code == 403)
check("wie geen token heeft, leest de open lijst niet", c.get("/api/mail/open").status_code == 403)
r = c.get("/mail?periode=7", headers=BEHEER)
html = r.get_data(as_text=True)
check("beheer ziet de pagina", r.status_code == 200, r.status_code)
kpi = html.split('class="kpirij"')[1].split("</section>")[0]
check("binnengekomen telt de periode, niet wat ouder is (14: zonder die van 9 en 40 dagen en de oude rij)", ">14</div>" in kpi, kpi[:300])
check("verdacht staat apart", "Verdacht (phishing)" in kpi)
check("de grafiek staat erop", "<svg" in html and "Mails per dag" in html)

# --- een bron: vier tellingen, een getal
tegel, kolom, api = tellingen(html)
check("open is: hoog, gewoon, onzeker en een verlopen automatisch bericht zonder besluit (5); niet beantwoord of nog geen werkdag",
      api == 5, api)
check("de wacht, De Mailregisseur, de tegel en de kolom Open geven hetzelfde getal",
      (antw_mch["open"] + antw_melo["open"], tegel, kolom, api) == (5, 5, 5, 5), (antw_mch, antw_melo, tegel, kolom, api))
opv = html.split('id="opvolgen"')[1].split("</section>")[0]
for kop in ("Ontvangen", "Afzender", "Postvak", "Onderwerp", "Status", "Wacht", "Volgende stap"):
    check(f"de lijst Op te volgen toont per bericht: {kop}", f"<th>{kop}</th>" in opv or f">{kop}</th>" in opv)
check("belangrijk staat boven gewone mail, ook als die langer wacht",
      opv.find("Herinnering premiebetaling") < opv.find("Gewone vraag van een klant"))
check("mogelijk beantwoord staat erbij, met wie", "mogelijk beantwoord (mch@h-architects.be" in opv)
check("een gewoon bericht van vandaag staat er nog niet", "Vraag van vandaag" not in opv)
check("de wachttijd staat in werkdagen", "werkdagen</span>" in opv or "werkdag</span>" in opv)
# --- opgevolgd tot opgelost (Mehdi, 20-10-2026: "dat ik weet dat een mail opgevolgd wordt tot het volledig gedaan/opgelost
# is"; gekozen: pas weg na Opgelost). Een antwoord sluit niets: het punt loopt, met wie en sinds wanneer.
dicht = html.split('id="afgesloten"')[1].split("</section>")[0]
loopt = html.split('id="loopt"')[1].split("</section>")[0]
check("beantwoord staat bij Loopt, door wie, niet bij afgesloten",
      "Akte verkoop" in loopt and "info@h-invest.be" in loopt and "Akte verkoop" not in dicht, loopt[:400])
check("een verlopen automatisch bericht blijft open, niet stil weg", "Betaling mislukt" in opv and "Betaling mislukt" not in dicht)
check("Loopt heeft de knoppen Opgelost en Toch open", ">Opgelost</button>" in loopt and ">Toch open</button>" in loopt)
check("de tegel Loopt telt de lijst Loopt", int(html.split('id="tegel-loopt"')[1].split('class="groot">')[1].split("<")[0])
      == loopt.count("<tr class=") , loopt.count("<tr class="))
check("de kolom heet mailinglijst; een oude wacht met 'lijst' werkt nog",
      rij("mch@h-architects.be:<nl@x>")["mailinglijst"] == 1 and "lijst" not in rij("mch@h-architects.be:<nl@x>"))
check("wat al in de tabel stond, houdt zijn mailinglijst", rij("mch@h-architects.be:<nieuwsbrief>")["mailinglijst"] == 1)

# --- besluiten van Mehdi
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<a@kbc>", "actie": "afgehandeld"})
check("wie geen beheer is, kan niets beslissen",
      c.post("/mail/besluit", headers=ANDER, data={"uniek": "mch@h-architects.be:<a@kbc>", "actie": "terug"}).status_code == 403)
antw = c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [MCH[0]]}).get_json()
st = rij("mch@h-architects.be:<a@kbc>")
check("afgehandeld blijft afgehandeld als de wacht het bericht opnieuw als open doorgeeft", st["besluit"] == "afgehandeld", st)
check("wie afhandelde, staat erbij", st["besluit_door"] == "mehdi")
html = c.get("/mail", headers=BEHEER).get_data(as_text=True)
tegel, kolom, api = tellingen(html)
check("na een besluit zakken alle tellingen samen", (antw["open"] + antw_melo["open"], tegel, kolom, api) == (4, 4, 4, 4),
      (antw, tegel, kolom, api))
check("Opgelost staat bij afgesloten met wie", "opgelost (aangeduid door mehdi op" in html.split('id="afgesloten"')[1].split("</section>")[0])
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<a@kbc>", "actie": "terug"})
check("terugzetten maakt het weer open", c.get("/api/mail/open", headers=K).get_json()["aantal"] == 5)
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<antw@x>", "actie": "open"})
check("Toch open zet een punt dat loopt weer op de lijst, ook als de wacht het beantwoord blijft noemen",
      c.get("/api/mail/open", headers=K).get_json()["aantal"] == 6
      and "weer opengezet door mehdi" in c.get("/mail", headers=BEHEER).get_data(as_text=True)
      and "Akte verkoop" not in c.get("/mail", headers=BEHEER).get_data(as_text=True).split('id="loopt"')[1].split("</section>")[0])
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<antw@x>", "actie": "afgehandeld"})
_html = c.get("/mail", headers=BEHEER).get_data(as_text=True)
check("pas na Opgelost is een beantwoord punt weg uit Loopt en staat het bij afgesloten",
      "Akte verkoop" not in _html.split('id="loopt"')[1].split("</section>")[0]
      and "Akte verkoop" in _html.split('id="afgesloten"')[1].split("</section>")[0])
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<antw@x>", "actie": "terug"})
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<klant@x>", "actie": "ruis"})
check("Ruis op een open punt sluit het en zet de afzender op ruis in dat postvak",
      [(x["postvak"], x["wie"], x["actie"]) for x in c.get("/api/mailregels", headers=K).get_json()["regels"]]
      == [("mch@h-architects.be", "klant@bouwheer.be", "ruis")] and rij("mch@h-architects.be:<klant@x>")["besluit"] == "ruis")
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<twijfel@x>", "actie": "doorgezet"})
_loopt = c.get("/mail", headers=BEHEER).get_data(as_text=True).split('id="loopt"')[1].split("</section>")[0]
check("Doorgezet haalt het van Op te volgen en zet het op Loopt, met wie", rij("mch@h-architects.be:<twijfel@x>")["besluit"] == "doorgezet"
      and "Planning werf" in _loopt and "mehdi (doorgezet)" in _loopt, _loopt[:300])
c.post("/mail/regel", headers=BEHEER, data={"postvak": "mch@h-architects.be", "wie": "klant@bouwheer.be", "actie": "weg"})

# --- een onvolledige ronde zegt een gevonden antwoord niet af
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "verzonden_volledig": False,
                                     "rijen": [dict(MCH[3], opvolging="open", antwoord_door="", antwoord_ts="")]})
check("las de wacht zijn verzonden post niet volledig, dan blijft beantwoord beantwoord",
      rij("mch@h-architects.be:<antw@x>")["opvolging"] == "beantwoord" and rij("mch@h-architects.be:<antw@x>")["antwoord_door"] == "info@h-invest.be")
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [dict(MCH[3], opvolging="open", antwoord_door="", antwoord_ts="")]})
check("met een volledige lezing volgt de wacht de draad", rij("mch@h-architects.be:<antw@x>")["opvolging"] == "open")
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [MCH[3]]})

# --- eenmaal begonnen opvolging blijft (Codex-toets f750f0c, 5): een punt dat loopt of open staat, verdwijnt niet als de
# wacht het later anders indeelt; alleen een besluit of 'verdwenen' haalt het weg
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [dict(MCH[3], soort="rommel", opvolging="geen", antwoord_door="",
                                                                          antwoord_ts="")]})
_r = rij("mch@h-architects.be:<antw@x>")
check("een punt dat loopt, blijft lopen als de wacht het later als rommel ziet",
      (_r["soort"], _r["opvolging"], _r["antwoord_door"]) == ("hoog", "beantwoord", "info@h-invest.be"), _r)
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [dict(MCH[0], soort="midden", opvolging="wacht")]})
check("een open punt blijft open als de wacht het weer 'wacht' noemt", rij("mch@h-architects.be:<a@kbc>")["opvolging"] == "open")
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [MCH[0], MCH[3]]})

# --- De Mailregisseur leest hetzelfde, met de sleutel voor een oproep
punten = c.get("/api/mail/open", headers=K).get_json()["punten"]
check("De Mailregisseur krijgt per punt wacht, soort, stap en dringend", all(
    {"uniek", "wacht", "postvak", "van", "onderwerp", "datum_iso", "soort", "werkdagen", "stap", "dringend", "klaarzet_id",
     "opvolging", "message_id"} <= set(p) for p in punten), punten[:1])
check("de wacht kan zijn eigen open punten vragen (ook ouder dan zijn venster)",
      {p["wacht"] for p in c.get("/api/mail/open?wacht=mail-melo", headers=K).get_json()["punten"]} == {"mail-melo"})

# --- veilig: nooit automatisch opruimen
veilig = c.get("/api/mail/veilig", headers=K).get_json()["domeinen"]
check("wie iets belangrijks stuurde of beantwoord werd, is veilig", {"kbc.be", "notaris.be", "fod.be"} <= set(veilig), veilig)
check("een domein met alleen reclame is niet veilig", "winkel.be" not in veilig and "shop.be" not in veilig)

# --- reclame naar Opgeruimd: proefweek, Niet opruimen, Terugzetten
html = c.get("/mail", headers=BEHEER).get_data(as_text=True)
rec = html.split('id="reclame"')[1].split("</section>")[0]
check("de proefweek toont wat verplaatst zou worden, met Niet opruimen", "zou verplaatst worden (proefweek)" in rec and "Niet opruimen</button>" in rec)
check("wat verplaatst is, krijgt Terugzetten", "in Opgeruimd" in rec and "Terugzetten</button>" in rec)
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<r1@winkel>", "actie": "houden"})
check("Niet opruimen zet een regel houden op die afzender",
      ("deals@shop.be", "houden") in [(x["wie"], x["actie"]) for x in c.get("/api/mailregels", headers=K).get_json()["regels"]])
check("en haalt het uit de proeflijst", rij("mch@h-architects.be:<r1@winkel>")["auto_opruimen"] == "")
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<r2@winkel>", "actie": "houden"})
terug = c.get("/api/mail/terug?wacht=mail-mch", headers=K).get_json()["berichten"]
check("Terugzetten vraagt de wacht het bericht terug te zetten, op Message-ID",
      terug == [{"uniek": "mch@h-architects.be:<r2@winkel>", "postvak": "mch@h-architects.be", "message_id": "<r2@winkel>"}], terug)
check("een andere wacht krijgt die vraag niet", c.get("/api/mail/terug?wacht=mail-melo", headers=K).get_json()["berichten"] == [])
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [], "teruggezet": ["mch@h-architects.be:<r2@winkel>"]})
st = rij("mch@h-architects.be:<r2@winkel>")
check("na de bevestiging is het teruggezet en niet meer opgeruimd", (st["auto_opruimen"], st["opgeruimd"], st["terug"]) == ("teruggezet", 0, 0), st)
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [dict(MCH[12], auto_opruimen="")]})
check("een latere ronde verandert teruggezet niet", rij("mch@h-architects.be:<r2@winkel>")["auto_opruimen"] == "teruggezet")

# --- de oude afspraken: opschonen, regels, sorteren
opschonen = html.split('id="opschonen"')[1].split("</section>")[0]
check("de afzender met de meeste ruis staat bovenaan", opschonen.find("promo@winkel.be") < opschonen.find("noreply@bpost.be"))
melo = next(rij_ for rij_ in opschonen.split("<tr") if "news@syndicus.be" in rij_)
check("opruimen kan niet in een postvak dat alleen gelezen mag worden", "Opruimen</button>" not in melo)
check("maar ruis of belangrijk zetten kan daar wel", "Ruis</button>" in melo)
check("heel gmail.com opruimen staat niet als knop", "alle mail van gmail.com" not in opschonen)
c.post("/mail/regel", headers=BEHEER, data={"postvak": "mch@h-architects.be", "wie": "promo@winkel.be", "actie": "opruimen"})
regels = c.get("/api/mailregels", headers=K).get_json()["regels"]
check("een regel van Mehdi komt bij de wachten", ("promo@winkel.be", "opruimen") in [(x["wie"], x["actie"]) for x in regels], regels)
check("een regel op heel gmail.com wordt geweigerd",
      c.post("/mail/regel", headers=BEHEER, data={"postvak": "mch@h-architects.be", "wie": "@gmail.com", "actie": "opruimen"}).status_code == 400)
check("een eigen domein ook", c.post("/mail/regel", headers=BEHEER, data={"postvak": "*", "wie": "@h-architects.be", "actie": "ruis"}).status_code == 400)
check("wie geen beheer is, kan geen regel zetten",
      c.post("/mail/regel", headers=ANDER, data={"postvak": "*", "wie": "x@y.be", "actie": "ruis"}).status_code == 403)
c.post("/mail/regel", headers=BEHEER, data={"postvak": "mch@h-architects.be", "wie": "promo@winkel.be", "actie": "weg"})
check("ongedaan maken haalt de regel weg",
      "promo@winkel.be" not in [x["wie"] for x in c.get("/api/mailregels", headers=K).get_json()["regels"]])
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [], "opgeruimd": ["mch@h-architects.be:b"]})
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [], "verplaatst": [{"uniek": "mch@h-architects.be:d", "naar": "INBOX.Bestellingen"}]})
check("wat de wacht sorteerde, krijgt zijn map",
      (rij("mch@h-architects.be:d")["naar"], rij("mch@h-architects.be:d")["opgeruimd"]) == ("INBOX.Bestellingen", 0))
c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [MCH[6]]})
check("opgeruimd blijft staan als de wacht het bericht later nog eens doorgeeft", rij("mch@h-architects.be:b")["opgeruimd"] == 1)

# --- de overgang van de klaarzet-items (eenmalig, 19-10-2026)
OUD = (VANDAAG - timedelta(days=40)).isoformat()


def punt(uniek, soort, onderwerp, datum, van="x@kbc.be", postvak="mch@h-architects.be", dringend=False):
    return {"van": "mail-mch", "voor": "mail-regisseur", "soort": "mail", "sleutel": "MCH", "titel": f"MCH: {onderwerp}",
            "uniek": uniek, "inhoud": {"postvak": postvak, "van": van, "van_naam": "X", "onderwerp": onderwerp, "datum": datum,
                                       "soort": soort, "waarom": "rol bank", "werkdagen_zonder_antwoord": 3,
                                       "voorstel": "beantwoorden", "dringend": dringend}}


c.post("/api/mail", headers=K, json={"wacht": "mail-mch", "rijen": [
    {k: v for k, v in bericht("<gezien@x>", "hoog", "y@kbc.be", onderwerp="Al gezien").items() if k != "opvolging"},
    {k: v for k, v in bericht("<mehdi@x>", "hoog", "z@kbc.be", onderwerp="Door Mehdi afgehandeld").items() if k != "opvolging"}]})
c.post("/api/klaarzet", headers=K, json={"items": [
    punt("opvolgen:mail-mch:<oud@x>", "hoog", "Oud open punt", OUD, dringend=True),
    punt("opvolgen:mail-mch:<gezien@x>", "hoog", "Al gezien", VANDAAG.isoformat()),
    punt("opvolgen:mail-mch:<mehdi@x>", "hoog", "Door Mehdi afgehandeld", VANDAAG.isoformat()),
    punt("opvolgen:mail-mch:mch@h-architects.be:77", "midden", "Zonder Message-ID", OUD),
    dict(punt("opvolgen:mail-mch:<kapot@x>", "hoog", "Kapot", OUD), inhoud="geen json")]})
with A.app.app_context():
    con = A.db()
    kid_oud = con.execute("SELECT id FROM klaarzet WHERE uniek='opvolgen:mail-mch:<oud@x>'").fetchone()[0]
    kid_mehdi = con.execute("SELECT id FROM klaarzet WHERE uniek='opvolgen:mail-mch:<mehdi@x>'").fetchone()[0]
    kid_kapot = con.execute("SELECT id FROM klaarzet WHERE uniek='opvolgen:mail-mch:<kapot@x>'").fetchone()[0]
    con.execute("UPDATE klaarzet SET status='opgepakt', opgepakt_door='mehdi: afgehandeld op het bord', opgepakt_ts=? WHERE id=?",
                (A.nu(), kid_mehdi))
    con.commit()
check("voor de overgang telt een klaarzet-item niet als open (geen tweede bron)",
      "Oud open punt" not in [p["onderwerp"] for p in c.get("/api/mail/open", headers=K).get_json()["punten"]])
voor, na, vorige, _ = OVERGANG.overzetten(droog=True)
with A.app.app_context():
    _kol = {r[1] for r in A.db().execute("PRAGMA table_info(mailmeta)").fetchall()}
check("een droge overgang bewaart niets, ook geen merker", not _kol and vorige is None and
      c.get("/api/mail/open", headers=K).get_json()["aantal"] == voor["open in mailbericht (_mail_open)"])
voor, na, vorige, onplaatsbaar = OVERGANG.overzetten()
punten = {p["onderwerp"]: p for p in c.get("/api/mail/open", headers=K).get_json()["punten"]}
check("de overgang zet elk open klaarzet-item open in mailbericht, ook ouder dan het venster",
      {"Oud open punt", "Al gezien", "Zonder Message-ID"} <= set(punten), list(punten))
check("en alleen het kapotte klaarzet-item blijft klaar", na["klaarzet klaar voor mail-regisseur"] == 1, na)
check("een al gebeld bericht houdt zijn sleutel voor een oproep", punten["Oud open punt"]["klaarzet_id"] == kid_oud)
check("wat Mehdi op het oude bord afhandelde, blijft afgehandeld",
      "Door Mehdi afgehandeld" not in punten and rij("mch@h-architects.be:<mehdi@x>")["besluit"] == "afgehandeld")
voor2, na2, vorige2, _ = OVERGANG.overzetten()
check("de overgang opnieuw draaien verandert niets", na2 == na and vorige2, (na, na2))
check("een kapot klaarzet-item blokkeert de overgang niet en wordt gemeld", onplaatsbaar == [kid_kapot], onplaatsbaar)
check("een uniek zonder Message-ID wordt het juiste bericht",
      rij("mch@h-architects.be:77")["onderwerp"] == "Zonder Message-ID")

# --- logboek uitschrijven (Mehdi, 20-10-2026): op /mail, nooit de URL van de knop, nooit dubbel
U = {"gebeurtenis": "g1", "ts": VANDAAG.isoformat(), "postvak": "melodiebvba@gmail.com", "van": "news@brand.be",
     "onderwerp": "Najaarsactie", "map": "Opgeruimd", "message_id": "<n1@brand.be>", "knop_domein": "brand.be",
     "uitslag": "aanvaard", "code": 200}
check("zonder token geen logboek", c.post("/api/mail/uitschrijving", json={"regels": [U]}).status_code == 403)
c.post("/api/mail/uitschrijving", headers=K, json={"wacht": "mail-melo", "regels": [
    U, U, dict(U, gebeurtenis="g2", knop_domein="brand.be/u?t=GEHEIM"), dict(U, gebeurtenis="g3", uitslag="weet niet"),
    dict(U, gebeurtenis="g4", van="info@shop.be", postvak="mch@h-architects.be", map="INBOX.Opgeruimd", uitslag="geweigerd", code=410)]})
log = c.get("/api/mail/uitschrijvingen?n=50", headers=K).get_json()["uitschrijvingen"]
check("dezelfde gebeurtenis twee keer gestuurd telt een keer", sorted(x["gebeurtenis"] for x in log) == ["g1", "g4"], log)
check("een knop met een pad of sleutel wordt geweigerd: alleen het domein", "GEHEIM" not in str(log))
check("de wachten en De Mailregisseur lezen het logboek alleen met token", c.get("/api/mail/uitschrijvingen").status_code == 403)
html = c.get("/mail?periode=7", headers=BEHEER).get_data(as_text=True)
blok = html.split('id="uitgeschreven"')[1].split("</section>")[0]
check("het blok Uitgeschreven toont afzender, onderwerp, knop en uitslag",
      all(x in blok for x in ("news@brand.be", "Najaarsactie", "brand.be", "aanvaard (200)", "geweigerd (410)")))
check("bij Gmail een link naar het bericht", "mail.google.com/mail/u/0/#search/rfc822msgid%3An1%40brand.be" in blok)
check("bij one.com de map", "map INBOX.Opgeruimd" in blok)

# --- focus (Mehdi, 20-10-2026: "we focusen nu op mch, mehdichegini@hotmail.com, melodie"): /mail toont standaard die drie,
# ?postvak=alle alles; en de stand voor de update van 08:00 en 17:00 telt hetzelfde open als /mail
c.post("/api/agent", json={"naam": "mail-hinv", "label": "De Mailwacht info@ H-Invest", "type": "mail", "rol": "x"}, headers=K)
c.post("/api/mail", headers=K, json={"wacht": "mail-hinv", "postvakken": [{"postvak": "info@h-invest.be", "wacht": "mail-hinv", "schrijven": 1}],
                                      "rijen": [bericht("<h@x>", "hoog", "boekhouder@octopus.be", postvak="info@h-invest.be",
                                                        onderwerp="Vraag van de boekhouder")]})
alle_api = c.get("/api/mail/open", headers=K).get_json()["aantal"]
hinv_open = len([p for p in c.get("/api/mail/open", headers=K).get_json()["punten"] if p["postvak"] == "info@h-invest.be"])
focus_html = c.get("/mail", headers=BEHEER).get_data(as_text=True)
alle_html = c.get("/mail?postvak=alle", headers=BEHEER).get_data(as_text=True)
t_focus, k_focus, _ = tellingen(focus_html)
t_alle, k_alle, _ = tellingen(alle_html)
check("standaard toont /mail de focus: info@h-invest telt niet mee in de tegel en de kolom Open",
      hinv_open == 1 and (t_focus, k_focus) == (alle_api - 1, alle_api - 1), (t_focus, k_focus, alle_api))
check("de focus toont het bericht van info@h-invest niet", "Vraag van de boekhouder" not in focus_html)
check("Alle postvakken toont alles, hetzelfde getal als /api/mail/open", (t_alle, k_alle) == (alle_api, alle_api)
      and "Vraag van de boekhouder" in alle_html, (t_alle, k_alle, alle_api))
check("de knop Focus staat aan als standaard", 'class="actief" href="/mail?periode=7"' in focus_html or
      'class="actief" href="/mail"' in focus_html.replace("?periode=7", ""))
r = c.post("/mail/besluit", headers=BEHEER, data={"uniek": "info@h-invest.be:<h@x>", "actie": "afgehandeld", "periode": "7", "filter": "alle"})
check("na een besluit blijft de keuze Alle postvakken", "postvak=alle" in r.headers.get("Location", ""), r.headers.get("Location"))
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "info@h-invest.be:<h@x>", "actie": "terug"})
check("zonder token geen stand", c.get("/api/mail/stand").status_code == 403)
stand = c.get("/api/mail/stand?sinds=" + urllib.parse.quote((VANDAAG - timedelta(days=3)).isoformat()), headers=K).get_json()
check("de stand noemt dezelfde focus als /mail", stand["focus"] == list(A.MAIL_FOCUS) == ["mch@h-architects.be",
      "mehdichegini@hotmail.com", "melodiebvba@gmail.com"], stand["focus"])
check("de stand telt open per postvak zoals /api/mail/open",
      sum(x["open"] for x in stand["postvakken"].values()) == alle_api and stand["postvakken"]["info@h-invest.be"]["open"] == 1,
      {k: v["open"] for k, v in stand["postvakken"].items()})
with A.app.app_context():
    _rijen = A.db().execute("SELECT uniek, datum, gezien FROM mailbericht WHERE postvak='mch@h-architects.be'").fetchall()
_grens = VANDAAG - timedelta(days=3)
_verwacht = sum(1 for r in _rijen if datetime.fromisoformat(r["gezien"] or r["datum"]) >= _grens)
check("binnen telt wanneer het bord een bericht voor het eerst zag (zonder dat: de maildatum), niet de maildatum",
      stand["postvakken"]["mch@h-architects.be"]["binnen"] == _verwacht and 0 < _verwacht < len(_rijen),
      (stand["postvakken"]["mch@h-architects.be"], _verwacht, len(_rijen)))
check("een mail met een oude datum die het bord nu pas ziet, telt mee (hotmail als de Mac sliep)",
      rij("mch@h-architects.be:oud")["gezien"] >= _grens.astimezone(timezone.utc).isoformat()[:10]
      and not rij("mch@h-architects.be:<nieuwsbrief>")["gezien"])
check("een postvak zonder mail staat er toch, met nul (hotmail)", stand["postvakken"]["mehdichegini@hotmail.com"]["binnen"] == 0)
check("uitgeschreven telt alleen wat aanvaard werd", stand["postvakken"]["melodiebvba@gmail.com"]["uitgeschreven"] == 1
      and stand["postvakken"]["mch@h-architects.be"]["uitgeschreven"] == 0, stand["postvakken"]["melodiebvba@gmail.com"])
_alle = c.get("/mail?postvak=alle", headers=BEHEER).get_data(as_text=True)
check("de stand telt Loopt zoals de tegel Loopt op Alle postvakken",
      sum(x["loopt"] for x in stand["postvakken"].values())
      == int(_alle.split('id="tegel-loopt"')[1].split('class="groot">')[1].split("<")[0]) > 0)
_leeg = c.get("/api/mail/stand?" + urllib.parse.urlencode({"sinds": (VANDAAG - timedelta(days=3)).isoformat(),
                                                             "tot": (VANDAAG - timedelta(days=2)).isoformat()}), headers=K).get_json()
check("tot is de bovengrens: wat het bord daarna zag, telt pas in de volgende update (Codex-toets f750f0c, 7)",
      sum(x["binnen"] for x in _leeg["postvakken"].values()) == 0, {k: x["binnen"] for k, x in _leeg["postvakken"].items()})
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<oudactie@x>", "actie": "afgehandeld"})
check("wie vandaag een mail van 9 dagen oud op Opgelost zet, ziet hem bij Afgesloten van 7 dagen (Codex-toets f750f0c, 11)",
      "Betaling mislukt" in c.get("/mail?periode=7", headers=BEHEER).get_data(as_text=True).split('id="afgesloten"')[1].split("</section>")[0])
c.post("/mail/besluit", headers=BEHEER, data={"uniek": "mch@h-architects.be:<oudactie@x>", "actie": "terug"})
check("de stand geeft per wacht de laatste ronde en de open noden", "mail-mch" in stand["wachten"]
      and "noden" in stand["wachten"]["mail-mch"])

check("het bord heeft een knop Mail voor beheer", "/mail" in c.get("/", headers=BEHEER).get_data(as_text=True))
check("het bord toont die knop niet aan anderen", 'href="/mail"' not in c.get("/", headers=ANDER).get_data(as_text=True))
check("werkdagen tellen het weekend niet (vrijdag tot maandag is een werkdag)",
      A._werkdagen_sinds("2026-09-25T10:00:00+02:00", date(2026, 9, 28)) == 1)
check("een onleesbare datum geeft geen fout", A._werkdagen_sinds("", date(2026, 9, 28)) is None)

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
