"""Grendel op correcties na het oppakken (nacontrole Plaud-agent v1.1, 12-10-2026, P1-5).

De echte klaarzet-API werkte een item alleen bij zolang het nog niet opgepakt was. Werd een zakelijk
gepubliceerd transcript later als privé of conflict beoordeeld, dan antwoordde de API ok, bestaand=1,
bijgewerkt=0, bleef het item bij h-architects staan, en noemde De Plaudwacht dat een geslaagde publicatie.

Deze proef gebruikt de echte API-functie van het bord (mijnagents/app.py) op een tijdelijke SQLite en
De Plaudwacht met nagebootste Dropbox en model. Verwacht: een zichtbare revisie met herstelstatus, het
item opnieuw zichtbaar met de nieuwe beoordeling, en geen schijnsucces.

Vereist Flask (CI en de Docker-build van het bord). Draaien: python3 mijnagents-runner/tests/test_plaud_revisie.py
"""
import json
import os
import sqlite3
import sys
import tempfile

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(HIER)
DB = os.path.join(tempfile.mkdtemp(prefix="bord-proef-"), "mijnagents.db")
os.environ["AGENTS_DB"] = DB
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.join(REPO, "mijnagents"))
sys.path.insert(0, os.path.join(HIER, "tests"))
import app as A  # noqa: E402
import test_plaud_wacht as T  # noqa: E402

K = {"X-Agents-Token": "proef"}
C = A.app.test_client()


class BordWereld(T.Wereld):
    """De Wereld uit test_plaud_wacht, maar klaarzet en oppakken gaan door de echte API."""

    def __init__(self):
        T.Wereld.__init__(self)
        T.P.ag.klaarzet = self.klaarzet
        T.P.bord.opgepakt = self.pak

    def klaarzet(self, items):
        r = C.post("/api/klaarzet", json={"items": [dict(it, van="plaud-wacht") for it in items]}, headers=K)
        self.klaar += items
        return r.get_json()

    def call(self, pad, payload=None, method=None):
        if pad.startswith("/api/klaarzet?") and "uniek=" in pad:
            return C.get(pad, headers=K).get_json()
        return T.Wereld.call(self, pad, payload, method)

    def pak(self, kid, door):
        C.post(f"/api/klaarzet/{kid}/opgepakt", json={"door": door}, headers=K)
        T.Wereld.pak(self, kid, door)


def rij(uniek):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    r = con.execute("SELECT * FROM klaarzet WHERE uniek=?", (uniek,)).fetchone()
    rev = [dict(x) for x in con.execute("SELECT * FROM klaarzet_revisie WHERE uniek=? ORDER BY id", (uniek,)).fetchall()] \
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='klaarzet_revisie'").fetchone() else []
    return dict(r), rev


def test_privecorrectie_na_oppakken_is_een_zichtbare_revisie():
    w = BordWereld()
    w.deals = [{"id": 777, "titel": "2531 Spleesters", "nummer": "2531"}]
    w.opname(T.ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
    w.push()
    w.ronde()
    uniek = f"plaud:{T.ID1}"
    item, _ = rij(uniek)
    assert item["voor"] == "h-architects", item
    C.post(f"/api/klaarzet/{item['id']}/opgepakt", json={"door": "werfverslag-voorbereider"}, headers=K)
    # nieuwe beoordeling: privé (andere titel = andere modelinput)
    w.opname(T.ID1, "10-08 PRIVE Angela en Mehdi", "2026-10-08T09:05:00")
    w.push()
    w.herkenning[T.ID1] = {"personen": ["Angela"], "hoofdpersoon": "Angela", "bedrijf": "", "afdeling": "prive", "thema": "weekend",
                           "project": "", "prive": True, "zekerheid": "hoog", "waarom": ""}
    code, tel, noden = w.ronde()
    item, rev = rij(uniek)
    assert item["voor"] == "mehdi" and json.loads(item["inhoud"])["prive"] is True, item
    assert item["status"] == "klaar", "de nieuwe beoordeling is opnieuw zichtbaar"
    assert rev and rev[-1]["oud_voor"] == "h-architects" and rev[-1]["oud_status"] == "opgepakt" \
        and rev[-1]["opgepakt_door"] == "werfverslag-voorbereider" and rev[-1]["herstel"], rev
    st = json.loads((w.staat / f"{T.ID1}.json").read_text())
    k = [o for o in st["opdrachten"] if o["sleutel"] == "klaarzet" and o.get("gedaan")]
    assert k and k[-1].get("bevestigd"), "gedaan pas na bevestiging van de opgeslagen versie"
    assert any("eerder verspreid" in n.lower() for n in noden), noden


def test_uitvoerder_bevestigt_de_opgeslagen_versie():
    """Een API die 'bestaand' zegt zonder de nieuwe inhoud op te slaan, is geen geslaagde publicatie."""
    w = BordWereld()
    w.opname(T.ID2, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
    w.push()
    echt = w.klaarzet
    w.klaarzet = lambda items: {"ok": True, "nieuw": 0, "bestaand": 1}          # zegt ok, slaat niets op
    T.P.ag.klaarzet = w.klaarzet
    code, tel, _ = w.ronde()
    assert code == T.P.DEELS and tel["fouten"] >= 1, (code, tel)
    T.P.ag.klaarzet = echt


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except Exception as e:  # noqa: BLE001
                fouten += 1
                import traceback
                traceback.print_exc()
                print("   GEFAALD   %s: %s" % (naam, e))
    print("%d gefaald" % fouten if fouten else "alles geslaagd")
    sys.exit(1 if fouten else 0)
