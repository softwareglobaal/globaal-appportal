"""Grendel op De Plaudwacht in /api/wachten/dag (T-0120, groep plaud). Apart van test_wachten_dag.py, zodat de groepen
elkaar daar niet in de weg zitten; het draait in dezelfde Docker-build.

- P01 (PLAUD-8): 'regels' is het aantal regels in het werkverslag; 'rondes' telt alleen de slotregels 'ronde:' van De
  Plaudwacht (29-10: 408 regels, 24 rondes). Een wacht zonder zo'n slotregel heeft geen meetbare rondes: None, nooit 0.

Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import os
import sqlite3
import sys
import tempfile

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "w.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
C = A.app.test_client()
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("ok   " if voorwaarde else "FOUT ") + naam + (f" ({extra})" if extra else ""))
    fout += 0 if voorwaarde else 1


def wachten(dag):
    return {x["naam"]: x for v in C.get(f"/api/wachten/dag?dag={dag}", headers=K).get_json()["vakken"] for x in v["wachten"]}


C.get("/api/wachten/dag?dag=2026-10-29", headers=K)  # maakt de tabellen
con = sqlite3.connect(os.environ["AGENTS_DB"])
for uur in range(3):
    con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('plaud-wacht','Plaud','bron',?,?)",
                ("ronde: gedaan 0, ongewijzigd 2", f"2026-10-29T{8 + uur:02d}:20:00+00:00"))
    for taak in (11, 12):
        con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('plaud-wacht',?,'bevinding',?,?)",
                    (f"taak {taak}", "niet_gevonden: geen opname op de bezoekdag", f"2026-10-29T{8 + uur:02d}:19:00+00:00"))
con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('belwacht','','bron','0 oproepen',"
            "'2026-10-29T11:00:00+00:00')")
con.commit()
con.close()

w = wachten("2026-10-29")
pl = w["plaud-wacht"]
check("P01 plaud: regels is het aantal regels in het werkverslag", pl["regels"] == 9 and len(pl["log"]) == 9, pl["regels"])
check("P01 plaud: rondes telt de slotregels 'ronde:'", pl["rondes"] == 3, pl["rondes"])
be = w["belwacht"]
check("P01 een wacht zonder slotregel: rondes onbekend, niet 0", be["rondes"] is None and be["regels"] == 1, be)
check("P01 een wacht zonder werkverslag: 0 regels, rondes onbekend", w["zoom-wacht"]["regels"] == 0
      and w["zoom-wacht"]["rondes"] is None, w["zoom-wacht"])

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
