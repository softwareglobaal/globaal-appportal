"""Grendel op het blok "Laatst klaargezet" op de pagina van een agent (/agent/<naam>, De Mehdi-agent, 31-10-2026).

De Mehdi-agent zet zijn takenlijst (soort taken) en zijn ochtend- en avondverslag (soort verslag) klaar voor Mehdi. Zijn
pagina op het bord toont de laatste van elk. Deze test legt vast:

- K01: zonder beheer geen blok, ook niet bij een agent die wel iets klaarzette;
- K02: beheer ziet de nieuwste takenlijst en het nieuwste verslag, niet een oudere versie en niet die van een andere agent;
- K03: ruwe HTML uit de tekst komt er als tekst door, en een link in markdown wordt geen link (geen javascript:);
- K04: elke regel blijft een regel, de lijst blijft een lijst;
- K05: een agent die niets klaarzette, heeft geen leeg blok;
- K06: geen gedachtestreepje in het blok.

Verzonnen voorbeelden, geen echte namen. Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import os
import re
import sys
import tempfile

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "start.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "proef"}
ANDER = {"X-authentik-groups": "agents", "X-authentik-username": "iemand"}
C = A.app.test_client()
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


def verse_db(naam):
    A.DB_PAD = os.path.join(MAP, naam + ".db")
    A.init_db()


def agent(naam, prive=False):
    r = C.post("/api/agent", headers=K, json={"naam": naam, "label": f"De {naam}", "rol": "proef", "prive": prive})
    assert r.status_code == 200, r.get_data(as_text=True)


def zet(van, soort, uniek, titel, inhoud):
    r = C.post("/api/klaarzet", headers=K, json={"items": [{
        "van": van, "voor": "mehdi", "soort": soort, "sleutel": "2026-10-31", "uniek": uniek,
        "titel": titel, "inhoud": inhoud}]})
    assert r.status_code == 200, r.get_data(as_text=True)


def blok(html):
    m = re.search(r'<div class="blok" id="klaargezet">(.*?)\n  </div>', html, re.S)
    return m.group(1) if m else ""


LIJST = ("Bijgewerkt 31-10-2026 21:40.\n\n## Voor jou\n\n"
         "1. Bel Proefpersoon Zeta terug over de offerte (hoog)\n"
         "   Waarom: wacht sinds gisteren\n"
         "   Bron: 2026-10-30, gemiste oproep van Proefpersoon Zeta\n"
         "2. Bevestig de afspraak met Klant Omega (normaal)\n"
         "   Bron: 2026-10-30, afspraak met Klant Omega\n")


def k01_alleen_beheer():
    verse_db("k01")
    agent("proefagent")
    zet("proefagent", "taken", "proefagent:taken:2026-10-31", "Te doen 31-10: 2 open, 1 hoog", LIJST)
    r = C.get("/agent/proefagent", headers=ANDER)
    html = r.get_data(as_text=True)
    check("K01 zonder beheer: pagina wel, blok niet", r.status_code == 200 and 'id="klaargezet"' not in html
          and "Proefpersoon Zeta" not in html)
    agent("geheim", prive=True)
    zet("geheim", "taken", "geheim:taken:2026-10-31", "Te doen 31-10: 1 open", LIJST)
    check("K01 privé-agent zonder beheer: 404", C.get("/agent/geheim", headers=ANDER).status_code == 404)


def k02_nieuwste():
    verse_db("k02")
    agent("proefagent")
    agent("andere")
    zet("proefagent", "taken", "proefagent:taken:2026-10-30", "Te doen 30-10: 5 open", "OUDE LIJST")
    zet("proefagent", "taken", "proefagent:taken:2026-10-31", "Te doen 31-10: 2 open, 1 hoog", LIJST)
    zet("proefagent", "verslag", "proefagent:ochtend:2026-10-31", "Te doen vandaag 31-10", "OUD VERSLAG")
    zet("proefagent", "verslag", "proefagent:avond:2026-10-31", "Avondoverzicht 31-10",
        "Twee dingen bleven liggen.\n\nTip: plan het terugbellen voor tien uur.")
    zet("andere", "taken", "andere:taken:2026-10-31", "Te doen van een ander", "LIJST VAN EEN ANDER")
    r = C.get("/agent/proefagent", headers=BEHEER)
    b = blok(r.get_data(as_text=True))
    check("K02 nieuwste takenlijst met titel", r.status_code == 200 and "Te doen 31-10: 2 open, 1 hoog" in b
          and "Proefpersoon Zeta" in b, b[:300])
    check("K02 nieuwste verslag", "Avondoverzicht 31-10" in b and "Tip: plan het terugbellen" in b)
    check("K02 geen oudere versie, niet die van een ander",
          "OUDE LIJST" not in b and "OUD VERSLAG" not in b and "LIJST VAN EEN ANDER" not in b)
    zet("proefagent", "taken", "proefagent:taken:2026-10-31", "Te doen 31-10: 1 open", "BIJGEWERKTE LIJST")
    b = blok(C.get("/agent/proefagent", headers=BEHEER).get_data(as_text=True))
    check("K02 een bijgewerkte lijst toont de nieuwe inhoud", "BIJGEWERKTE LIJST" in b and "Te doen 31-10: 1 open" in b)


def k03_geen_html():
    verse_db("k03")
    agent("proefagent")
    zet("proefagent", "taken", "proefagent:taken:2026-10-31", "Te doen 31-10: <b>1</b> open",
        "1. Lees <script>alert(1)</script> en [klik hier](javascript:alert(2)) en <img src=x onerror=alert(3)>\n")
    b = blok(C.get("/agent/proefagent", headers=BEHEER).get_data(as_text=True))
    check("K03 geen script of img uit de tekst", "<script>" not in b and "<img" not in b, b[:400])
    check("K03 de tekst staat er als tekst", "&lt;script&gt;" in b and "&lt;img" in b)
    check("K03 een markdown-link wordt geen link", "<a " not in b and 'href="javascript' not in b)
    check("K03 de titel is ontsnapt", "&lt;b&gt;1&lt;/b&gt;" in b)


def k04_regels():
    verse_db("k04")
    agent("proefagent")
    zet("proefagent", "taken", "proefagent:taken:2026-10-31", "Te doen 31-10: 2 open, 1 hoog", LIJST)
    b = blok(C.get("/agent/proefagent", headers=BEHEER).get_data(as_text=True))
    check("K04 de lijst is een genummerde lijst met kop", "<ol>" in b and "<h2>Voor jou</h2>" in b, b[:400])
    check("K04 waarom en bron op een eigen regel", re.search(r"<br\s*/?>\s*Waarom: wacht", b) is not None
          and re.search(r"<br\s*/?>\s*Bron: 2026-10-30", b) is not None)


def k05_geen_leeg_blok():
    verse_db("k05")
    agent("stil")
    r = C.get("/agent/stil", headers=BEHEER)
    check("K05 geen blok zonder klaargezet item", r.status_code == 200 and 'id="klaargezet"' not in r.get_data(as_text=True))


def k06_stijl():
    verse_db("k06")
    agent("proefagent")
    zet("proefagent", "taken", "proefagent:taken:2026-10-31", "Te doen 31-10: 2 open, 1 hoog", LIJST)
    zet("proefagent", "verslag", "proefagent:avond:2026-10-31", "Avondoverzicht 31-10", "Tip: een ding per keer.")
    b = blok(C.get("/agent/proefagent", headers=BEHEER).get_data(as_text=True))
    check("K06 geen gedachtestreepje in het blok", b and "—" not in b and "–" not in b)


if __name__ == "__main__":
    k01_alleen_beheer()
    k02_nieuwste()
    k03_geen_html()
    k04_regels()
    k05_geen_leeg_blok()
    k06_stijl()
    print(f"{fout} fout")
    sys.exit(1 if fout else 0)
