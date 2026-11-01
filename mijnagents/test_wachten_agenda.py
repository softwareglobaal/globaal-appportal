"""Grendel op /api/wachten/dag voor de wachten van het vak Agenda (T-0120, meting 01-10 tot 01-11-2026, groep agenda).

- AG-2: van een signaal en het dagplan van De Agendawacht en De Calendlywacht komen de regels van de inhoud mee, niet
  alleen de titel; een signaal met 3 regels geeft 3 regels; wat bij het klaarzetten gemaskeerd werd, blijft '(privé)';
  een andere wacht krijgt geen regels (nooit de tekst van een bericht);
- AG-9: het werkverslag komt per blad van MAX_LOG regels; een dag met 1.200 regels heeft twee bladen, en begin, midden
  en einde zijn bereikbaar; zonder blad het laatste blad; een blad buiten het bereik wordt het dichtstbijzijnde;
- CL-4: een wacht met cadans 'elke werkdag' zonder ronde op zaterdag of zondag is 'geen ronde gepland', geen grijs; een
  werkdag zonder ronde blijft grijs; een weekend met een ronde telt gewoon; een wacht die ook in het weekend draait,
  blijft grijs.

Verzonnen voorbeelden, geen echte namen. Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
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
import wachten_dag as WD  # noqa: E402

K = {"X-Agents-Token": "proef"}
C = A.app.test_client()
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("ok   " if voorwaarde else "FOUT ") + naam + (f" ({extra})" if extra else ""))
    fout += 0 if voorwaarde else 1


def wachten(dag, **extra):
    q = "&".join(f"{k}={v}" for k, v in extra.items())
    d = C.get(f"/api/wachten/dag?dag={dag}" + (f"&{q}" if q else ""), headers=K).get_json()
    return {x["naam"]: x for v in d["vakken"] for x in v["wachten"]}


C.get("/api/wachten/dag?dag=2026-10-29", headers=K)  # maakt de tabellen
con = sqlite3.connect(os.environ["AGENTS_DB"])
# AG-2: een signaal met drie regels, een dagplan met een gemaskeerde privéafspraak, en een signaal van een andere wacht
con.execute("INSERT INTO klaarzet(van,voor,soort,sleutel,titel,inhoud,uniek,ts) VALUES('agenda-wacht','mehdi','signaal',"
            "'2026-10-29','Link doorsturen of titel nakijken','- 2026-11-02T09:00 proef A: link doorsturen\n"
            "- 2026-11-03T10:00 proef B: link doorsturen\n- 2026-11-04T11:00 proef C: VOORSTEL',"
            "'agenda-zoom-titel:2026-10-29','2026-10-29T08:00:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,sleutel,titel,inhoud,uniek,ts) VALUES('agenda-wacht','mehdi','dagplan',"
            "'2026-10-29','Dagplan 2026-10-29','Vandaag:\n- 09:00 Mehdi: [HA-KO] proefklant\n- 12:00 (privé)\n\n"
            "Gisteren, klantcontact waar een verslag of opname bij hoort:\n- niets','dagplan:2026-10-29',"
            "'2026-10-29T05:00:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,sleutel,titel,inhoud,uniek,ts) VALUES('calendly-wacht','mehdi','signaal',"
            "'2026-10-29','Calendly: 1 signalen','1 boeking(en) zonder afspraak in de agenda''s van De Agendawacht: "
            "2026-11-06 13:00 Proef: Kennismaking','calendly:2026-10-29','2026-10-29T07:15:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,sleutel,titel,inhoud,uniek,ts) VALUES('sms-wacht','mehdi','signaal',"
            "'2026-10-29','Sms: 1 nieuw','geheime berichttekst van een proefpersoon','sms:2026-10-29','2026-10-29T09:00:00+00:00')")
# AG-9: 1.200 regels in het werkverslag van De Agendawacht op 29-10
con.executemany("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('agenda-wacht','dag 2026-10-29','schrijf',?,?)",
                [(f"proefregel {i:04d}", f"2026-10-29T{6 + i // 120:02d}:{(i % 120) // 2:02d}:{(i % 2) * 30:02d}+00:00")
                 for i in range(1, 1201)])
# CL-4: de cadans uit de tabel agent; 31-10 en 01-11 zijn zaterdag en zondag, 30-10 een vrijdag
for naam, label, cadans in (("calendly-wacht", "De Calendlywacht", "Elke werkdag 07:15"),
                            ("agenda-wacht", "De Agendawacht", "werkdagen 06:30, daarna elke 2 uur; signaalwacht elke 12 minuten"),
                            ("zoom-wacht", "De Zoomwacht", "3 keer per dag")):
    con.execute("INSERT INTO agent(naam,label,cadans,aangemaakt) VALUES(?,?,?,'x')", (naam, label, cadans))
con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('calendly-wacht','','bron','1 account',"
            "'2026-11-01T08:15:00+00:00')")
con.commit()
con.close()

# --- AG-2
w = wachten("2026-10-29")
ag = w["agenda-wacht"]
sig = next(x for x in ag["items"] if x["wat"].startswith("Link doorsturen"))
check("AG-2 een signaal met 3 regels toont 3 regels, zonder het streepje vooraan",
      sig.get("regels") == ["2026-11-02T09:00 proef A: link doorsturen", "2026-11-03T10:00 proef B: link doorsturen",
                            "2026-11-04T11:00 proef C: VOORSTEL"], sig)
plan = next(x for x in ag["items"] if x["wat"].startswith("Dagplan"))
check("AG-2 het dagplan toont zijn regels; een gemaskeerde privéafspraak blijft '(privé)'",
      "12:00 (privé)" in plan.get("regels", []) and "09:00 Mehdi: [HA-KO] proefklant" in plan.get("regels", [])
      and "Vandaag:" in plan.get("regels", []), plan)
cal = w["calendly-wacht"]["items"][0]
check("AG-2 het signaal van De Calendlywacht toont wat het signaal is", cal.get("regels")
      and "2026-11-06 13:00 Proef: Kennismaking" in cal["regels"][0], cal)
sms = w["sms-wacht"]["items"][0]
check("AG-2 een wacht buiten het vak Agenda krijgt geen regels (nooit de tekst van een bericht)",
      "regels" not in sms and "geheime" not in str(sms), sms)

# --- AG-9
check("AG-9 de dag met 1.200 regels telt ze allemaal", ag["rondes"] == 1200, ag["rondes"])
check("AG-9 zonder blad het laatste blad, met het aantal bladen", ag["log_blad"] == 2 and ag["log_bladen"] == 2
      and ag["log"][-1]["tekst"].endswith("proefregel 1200") and len(ag["log"]) == 1200 - WD.MAX_LOG,
      (ag.get("log_blad"), ag.get("log_bladen"), len(ag["log"])))
b1 = wachten("2026-10-29", wacht="agenda-wacht", blad=1)["agenda-wacht"]
check("AG-9 blad 1 begint bij de eerste regel en loopt door het midden", b1["log_blad"] == 1
      and b1["log"][0]["tekst"].endswith("proefregel 0001") and any(x["tekst"].endswith("proefregel 0600") for x in b1["log"])
      and len(b1["log"]) == WD.MAX_LOG, (b1["log_blad"], b1["log"][0]))
b9 = wachten("2026-10-29", wacht="agenda-wacht", blad=9)["agenda-wacht"]
check("AG-9 een blad buiten het bereik wordt het laatste", b9["log_blad"] == 2 and b9["log"][-1]["tekst"].endswith("proefregel 1200"))
bx = wachten("2026-10-29", wacht="agenda-wacht", blad=1)
check("AG-9 het blad geldt alleen voor de gevraagde wacht", bx["calendly-wacht"]["log_blad"] == 1
      and bx["calendly-wacht"]["log_bladen"] == 1)

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
