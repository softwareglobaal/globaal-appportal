"""Grendel op de pagina /bronnen (Mehdi, 28-10-2026: "een dashboard om te zien wat gewerkt heeft en wat niet").

De pagina leest alleen wat er al is: de hartslag en de noden van de wachten, en de dagtellingen uit de weekoverzichten.
Deze test legt vast:

- B01: zonder beheer 403;
- B02: een wacht zonder hartslag staat op rood en zegt "nooit"; een wacht met hartslag en zonder nood op groen;
- B03: een open nood maakt de wacht rood en staat in de rij;
- B04: een vastgestelde dag kleurt per bron: volledig groen, voorlopig oranje, "niet aangesloten" rood;
- B05: een dag zonder telling zegt "niet vastgesteld"; een weekoverzicht dat geen json is, laat de pagina niet vallen;
- B06: geen gedachtestreepje; het bord linkt naar de pagina.

Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import json
import os
import re
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


def verse_db(naam):
    A.DB_PAD = os.path.join(MAP, naam + ".db")
    A.init_db()


def pagina(kop=BEHEER):
    r = C.get("/bronnen", headers=kop)
    return r, r.get_data(as_text=True)


def rij(html, begin):
    m = re.search(r"<tr>\s*<td[^>]*>(?:<span[^>]*></span>|<a[^>]*>)?" + re.escape(begin) + r".*?</tr>", html, re.S)
    return m.group(0) if m else ""


def gisteren():
    return (datetime.now(A.BRUSSEL).date() - timedelta(days=1))


def b01_alleen_beheer():
    verse_db("b01")
    r, _ = pagina(ANDER)
    check("B01 zonder beheer 403", r.status_code == 403, r.status_code)


def b02_hartslag():
    verse_db("b02")
    C.post("/agent-status", headers=K, json={"naam": "agenda-wacht", "status": "waakt"})
    r, html = pagina()
    check("B02 pagina laadt", r.status_code == 200, r.status_code)
    check("B02 agenda met hartslag is groen", 'stip groen"></span>Agenda<' in html, rij(html, "Agenda"))
    wa = rij(html, "WhatsApp")
    check("B02 WhatsApp zonder hartslag is rood en zegt nooit", "stip rood" in wa and "nooit" in wa, wa)


def b03_nood():
    verse_db("b03")
    C.post("/agent-status", headers=K, json={"naam": "belwacht", "status": "waakt"})
    conn = A.sqlite3.connect(A.DB_PAD)
    conn.execute("INSERT INTO nood(naam, tekst, open, ts) VALUES(?,?,1,?)", ("belwacht", "geen toegang tot de oproepen", A.nu()))
    conn.commit()
    conn.close()
    _, html = pagina()
    t = rij(html, "Telefoon iPhone")
    check("B03 een open nood maakt de wacht rood", "stip rood" in t and "geen toegang tot de oproepen" in t, t)


def b04_dagkleuren():
    verse_db("b04")
    d = gisteren()
    e = {"dag": d.isoformat(), "vastgesteld": True,
         "whatsapp": {"stand": "niet aangesloten"}, "telefoon": {"stand": "aangesloten"},
         "mail": {"binnen": 1, "verzonden": 0, "onvolledig": True},
         "standen": {"agenda": "volledig", "zoom": "voorlopig", "locatie": "afgesloten"}}
    wk = A.week_naam(d)
    C.post("/api/klaarzet", headers=K, json={"items": [{
        "van": "weekoverzicht", "voor": "mehdi", "soort": "weekoverzicht", "sleutel": wk, "titel": wk,
        "inhoud": json.dumps({"dagen": [e]}), "uniek": f"weekoverzicht:{wk}"}]})
    _, html = pagina()
    r = rij(html, f"{A.WEEKDAGEN[d.weekday()]} {d:%d-%m}")
    cellen = re.findall(r'stip (\w+)"></span>([^<]*)', r)
    check("B04 kleuren per bron", cellen == [("groen", "volledig"), ("groen", "afgesloten"), ("oranje", "voorlopig"),
                                             ("oranje", "onvolledig"), ("rood", "niet aangesloten"),
                                             ("groen", "aangesloten")], cellen)


def b05_geen_telling():
    verse_db("b05")
    wk = A.week_naam(gisteren())
    C.post("/api/klaarzet", headers=K, json={"items": [{
        "van": "weekoverzicht", "voor": "mehdi", "soort": "weekoverzicht", "sleutel": wk, "titel": wk,
        "inhoud": "geen json", "uniek": f"weekoverzicht:{wk}"}]})
    r, html = pagina()
    check("B05 een kapot weekoverzicht laat de pagina staan", r.status_code == 200, r.status_code)
    check("B05 een dag zonder telling zegt niet vastgesteld", "niet vastgesteld" in html)


def b06_stijl():
    verse_db("b06")
    _, html = pagina()
    check("B06 geen gedachtestreepje", "—" not in html and "–" not in html)
    r = C.get("/", headers=BEHEER)
    check("B06 het bord linkt naar bronnen", 'href="/bronnen"' in r.get_data(as_text=True))


if __name__ == "__main__":
    b01_alleen_beheer()
    b02_hartslag()
    b03_nood()
    b04_dagkleuren()
    b05_geen_telling()
    b06_stijl()
    print(f"{fout} fout")
    sys.exit(1 if fout else 0)
