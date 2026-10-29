"""Grendel op de pagina /tijdlijn (Mehdi, 29-10-2026: verleden en agenda samen, zodat AI hem beter helpt).

De pagina leest alleen wat er al is: de afspraken van De Agendawacht (klaarzet) en de gesprekken (gesprek_log).
Deze test legt vast:

- T01: zonder beheer 403;
- T02: een afspraak van morgen en een gesprek van gisteren staan op hun dag, met wie en hoe lang;
- T03: een privégesprek toont geen namen; een dubbel en een chat tellen niet;
- T04: een vervallen afspraak staat er niet; een afspraak buiten het venster ook niet;
- T05: de tekst voor een AI noemt beide dagen; geen gedachtestreepje; het bord linkt naar de pagina.

Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "start.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "proef"}
ANDER = {"X-authentik-groups": "agents", "X-authentik-username": "iemand"}
C = A.app.test_client()
A._locatie = lambda pad, standaard=None: standaard
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


A.DB_PAD = os.path.join(MAP, "t.db")
A.init_db()
vandaag = datetime.now(A.BRUSSEL).date()
morgen, gisteren, ver = (vandaag + timedelta(days=1)).isoformat(), (vandaag - timedelta(days=1)).isoformat(), \
    (vandaag + timedelta(days=40)).isoformat()


def afspraak(uniek, dag, titel, status=None):
    C.post("/api/klaarzet", headers=K, json={"items": [{
        "van": "agenda-wacht", "voor": "mehdi", "soort": "afspraak", "titel": f"{dag} {titel}", "uniek": uniek,
        "inhoud": {"datum": dag, "start": dag + "T10:00:00+01:00", "einde": dag + "T11:00:00+01:00", "titel": titel,
                   "locatie": "Genk"}}]})
    if status:
        with A.app.app_context():
            c = A.db()
            c.execute("UPDATE klaarzet SET status=? WHERE uniek=?", (status, uniek))
            c.commit()


afspraak("agenda:a:1", morgen, "[HA-KB] WB 2310 werfbezoek")
afspraak("agenda:a:2", morgen, "Afgelaste afspraak", "vervallen")
afspraak("agenda:a:3", ver, "Te ver vooruit")
C.post("/api/gesprekken", headers=K, json={"rijen": [
    {"uniek": "zoom:1", "bron": "zoom", "datum": gisteren, "start": gisteren + " 09:15", "minuten": 32, "personen": "Thomas Berg"},
    {"uniek": "telefoon:2", "bron": "telefoon", "datum": gisteren, "start": gisteren + " 12:00", "minuten": 5,
     "personen": "Geheime Naam", "prive": 1},
    {"uniek": "fathom:3", "bron": "fathom", "datum": gisteren, "start": gisteren + " 09:15", "minuten": 32,
     "personen": "Dubbel Persoon", "dubbel_van": "zoom:1"},
    {"uniek": "whatsapp:4", "bron": "whatsapp", "datum": gisteren, "start": gisteren + " 14:00", "minuten": 0,
     "personen": "Chat Persoon"},
]})

r = C.get("/tijdlijn", headers=ANDER)
check("T01 zonder beheer 403", r.status_code == 403, r.status_code)
r = C.get("/tijdlijn", headers=BEHEER)
html = r.get_data(as_text=True)
check("T02 pagina laadt", r.status_code == 200, r.status_code)
check("T02 afspraak van morgen staat erop", "WB 2310 werfbezoek" in html)
check("T02 gesprek van gisteren met wie en hoe lang", "Thomas Berg" in html and "32 min" in html)
check("T03 privégesprek zonder namen", "Geheime Naam" not in html and "privé" in html)
check("T03 dubbel en chat tellen niet", "Dubbel Persoon" not in html and "Chat Persoon" not in html)
check("T04 vervallen afspraak niet", "Afgelaste afspraak" not in html)
check("T04 buiten het venster niet", "Te ver vooruit" not in html)
with A.app.app_context():
    tekst = A.tijdlijn_tekst(A.tijdlijn_gegevens(A.db(), vandaag))
check("T05 tekst voor AI noemt verleden en toekomst", f"{gisteren} (verleden)" in tekst and f"{morgen} (toekomst)" in tekst, tekst)
check("T05 geen gedachtestreepje", "—" not in html and "–" not in html)
bord = C.get("/", headers=BEHEER).get_data(as_text=True)
check("T05 bord linkt naar de tijdlijn", "/tijdlijn" in bord)

print("tijdlijn:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
