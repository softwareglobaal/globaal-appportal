"""Grendel op De Plaudwacht in /api/wachten/dag (T-0120, groep plaud). Apart van test_wachten_dag.py, zodat de groepen
elkaar daar niet in de weg zitten; het draait in dezelfde Docker-build.

- P01 (PLAUD-8): 'rondes' blijft het aantal regels in het werkverslag (zo toont de pagina het); 'rondes_geteld' telt
  alleen de slotregels 'ronde:' van De Plaudwacht (29-10: 408 regels, 24 rondes). Een wacht zonder zo'n slotregel heeft
  geen meetbare rondes: None, nooit 0.
- P02 (PLAUD-7): een opname uit het manifest van de Mac zonder rij in de gesprekkentabel (wacht op transcript, kort,
  onvolledig) staat er als item met tijd, duur en toestand, zonder naam; een opname met een rij staat er niet nog eens bij.
  'plaud' telt per dag de opnames, ook die zonder audio. Nooit een naam uit Plaud, nooit een pad of link.
- P03 (PLAUD-7): zonder leesbaar manifest, of met een manifest van voor die dag, blijven de items uit de tabel en is de
  stand onbekend, nooit 0; een manifest van tijdens de dag zegt dat de telling nog niet af is (na_de_dag).
- P04, P05 (Codex-toets 1): privémaskering en geen dubbele klaarzet-regel bij De Plaudwacht; actief na het samenvoegen
  met FATHOM-3 (t0120-fathom) en DB-8 (t0120-prive), die dat bouwen.

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
check("P01 plaud: rondes blijft het aantal regels in het werkverslag", pl["rondes"] == 9 and len(pl["log"]) == 9,
      pl["rondes"])
check("P01 plaud: rondes_geteld telt de slotregels 'ronde:'", pl["rondes_geteld"] == 3, pl["rondes_geteld"])
be = w["belwacht"]
check("P01 een wacht zonder slotregel: rondes_geteld onbekend, niet 0", be["rondes_geteld"] is None and be["rondes"] == 1, be)
check("P01 een wacht zonder werkverslag: 0 regels, rondes_geteld onbekend", w["zoom-wacht"]["rondes"] == 0
      and w["zoom-wacht"]["rondes_geteld"] is None, w["zoom-wacht"])

# ---------------------------------------------------------------- P02, P03: het manifest van de Mac ---
import json  # noqa: E402
import wachten_dag as WD  # noqa: E402

INVOER = tempfile.mkdtemp()
WD.PLAUD_INVOER = INVOER


def opname(letter, start, minuten, toestand, audio="aanwezig", transcript="aanwezig"):
    return {"plaud_id": "of_" + letter * 32, "start_brussel": start, "duur_minuten": minuten, "toestand": toestand,
            "naam_in_plaud": f"Geheime titel {letter}", "transcript": {"staat": transcript}, "audio": {"staat": audio},
            "archief": {"plaats": "mac-dropbox", "map": f"2026-10-27 Geheime map {letter}"}}


MANIFEST = {"meta": {"gemaakt": "2026-10-28T06:05:00+00:00", "aantal": 5}, "opnames": [
    opname("a", "2026-10-27T09:00:00+01:00", 40.2, "compleet"),
    opname("b", "2026-10-27T11:12:00+01:00", 300.0, "wacht_op_transcript", transcript="wacht"),
    opname("c", "2026-10-27T20:57:00+01:00", 0.1, "wacht_op_transcript", transcript="wacht"),
    opname("d", "2026-10-27T15:48:00+01:00", 14.3, "onvolledig", audio="ontbreekt"),
    opname("e", "2026-10-26T10:00:00+01:00", 5.0, "wacht_op_transcript", transcript="wacht")]}
with open(os.path.join(INVOER, "00 manifest.json"), "w", encoding="utf-8") as f:
    json.dump(MANIFEST, f)
con = sqlite3.connect(os.environ["AGENTS_DB"])
for letter, start, minuten in (("a", "09:00", 40), ("d", "15:48", 14)):
    con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,archief,link,ts) "
                "VALUES(?,'2026-10-27',?,?,'Proef Klant','Proefthema','h-architects',0,'plaud',?,?,'x')",
                (f"plaud:of_{letter * 32}", start, minuten, "Data uit Mehdi/Plaud/proef/transcript.md",
                 "Data uit Mehdi/Plaud/proef/transcript.md"))
con.commit()
con.close()

pl = wachten("2026-10-27")["plaud-wacht"]
tekst = json.dumps(pl, ensure_ascii=False)
check("P02 twee opnames in de tabel en twee zonder rij: vier items, geen dubbel", pl["aantal"] == 4, pl["items"])
check("P02 wachtende opname: tijd, duur en 'wacht op transcript'", any(
    x["tijd"] == "11:12" and x["wie"] == "Plaud-opname" and x["wat"] == "300 min, wacht op transcript" for x in pl["items"]),
    pl["items"])
check("P02 korte wachtende: 'kort, na te kijken'", any(
    x["tijd"] == "20:57" and x["wat"] == "6 s, kort, na te kijken" for x in pl["items"]), pl["items"])
check("P02 nooit een naam uit Plaud, een pad of een link", "Geheime" not in tekst and "Data uit Mehdi" not in tekst
      and not any("link" in x for x in pl["items"]), tekst[:400])
check("P02 stand per dag, ook de audio", pl["plaud"] == {"opnames": 4, "in_tabel": 2, "wacht_op_transcript": 2, "kort": 1,
                                                          "onvolledig": 1, "zonder_audio": 1,
                                                          "manifest_van": "2026-10-28T06:05:00+00:00", "na_de_dag": True},
      pl["plaud"])
check("P02 een andere dag telt alleen zijn eigen opname", wachten("2026-10-26")["plaud-wacht"]["plaud"]["opnames"] == 1)
check("P02 groen: er kwam iets binnen", pl["kleur"] == "groen", pl["kleur"])
check("P03 een manifest van voor die dag kent die dag niet: onbekend, geen nul", wachten("2026-10-29")["plaud-wacht"]["plaud"]
      is None)
MANIFEST["meta"]["gemaakt"] = "2026-10-27T14:00:00+00:00"                      # tijdens de dag gemaakt
with open(os.path.join(INVOER, "00 manifest.json"), "w", encoding="utf-8") as f:
    json.dump(MANIFEST, f)
check("P03 een manifest van tijdens de dag: de telling is nog niet af", wachten("2026-10-27")["plaud-wacht"]["plaud"]["na_de_dag"]
      is False)
MANIFEST["meta"]["gemaakt"] = ""
with open(os.path.join(INVOER, "00 manifest.json"), "w", encoding="utf-8") as f:
    json.dump(MANIFEST, f)
check("P03 een manifest zonder tijdstip: onbekend", wachten("2026-10-27")["plaud-wacht"]["plaud"] is None)
os.remove(os.path.join(INVOER, "00 manifest.json"))
pl = wachten("2026-10-27")["plaud-wacht"]
check("P03 zonder manifest: de rijen blijven, de stand is onbekend", pl["aantal"] == 2 and pl["plaud"] is None
      and pl["leesfout"] == "", pl)

# ------------------------------------------- P04, P05: samen met FATHOM-3 (t0120-fathom) en DB-8 (t0120-prive) ---
# Codex-toets 1: de privémaskering (prive=1 bij Plaud is privé, ook met een andere afdeling) en het weglaten van een
# klaarzet-regel met de uniek van een gesprek zijn van die groepen, en gelden ook voor De Plaudwacht (zelfde uniek
# plaud:<id> in beide tabellen). Deze toetsen worden actief zodra die takken samengevoegd zijn; tot dan staan ze er luid.
import inspect  # noqa: E402

DEDUP = "zonder_gesprekken" in inspect.signature(WD.lees_klaarzet).parameters
PRIVE = hasattr(WD, "PRIVE_VLAG_BRONNEN") or hasattr(WD, "privegrens")
con = sqlite3.connect(os.environ["AGENTS_DB"])
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
            "VALUES('plaud:of_" + "p" * 32 + "','2026-10-25','11:00',12,'Verborgen Persoon','Verborgen onderwerp','regie',1,"
            "'plaud','x')")
for letter, start in (("f", "09:00"), ("g", "14:00")):
    uniek = "plaud:of_" + letter * 32
    con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
                "VALUES(?,'2026-10-24',?,20,'Proef Klant','Proefthema','h-architects',0,'plaud','x')", (uniek, start))
    con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('plaud-wacht','h-architects','transcript',"
                "?,'{}',?,'2026-10-24T15:00:00+00:00')", (f"2026-10-24 {start} Plaud: Proef Klant · Proefthema", uniek))
con.commit()
con.close()
if PRIVE:
    it = wachten("2026-10-25")["plaud-wacht"]["items"]
    check("P04 prive=1 bij Plaud met afdeling regie: alleen 'privégesprek, N min'", len(it) == 1
          and it[0]["wie"] == "privégesprek" and "Verborgen" not in str(it), it)
else:
    print("WACHT P04: actief na het samenvoegen van FATHOM-3 (t0120-fathom) of DB-8 (t0120-prive)")
if DEDUP:
    pl = wachten("2026-10-24")["plaud-wacht"]
    check("P05 een dag met 2 opnames: 2 items, niet 4 (klaarzet met dezelfde uniek valt weg)", pl["aantal"] == 2, pl["items"])
else:
    print("WACHT P05: actief na het samenvoegen van FATHOM-3 (t0120-fathom)")

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
