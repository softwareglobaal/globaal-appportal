"""Grendel op /api/wachten/dag (Mehdi, 01-11-2026: per wacht zien wat er binnenkwam, om te controleren dat het werkt).

- W01: zonder token geen antwoord; een dag die geen datum is, geeft 400;
- W02: elke wacht van de groep Dagbundelaar staat erin, precies een keer, in zijn vak;
- W03: gesprekken (WhatsApp) komen per wacht binnen, met tijd in Brussel en wie; de dekkingsrij telt niet als item;
- W04: mail komt per postvak binnen met afzender en onderwerp;
- W05: een fout in het werkverslag van die dag maakt de wacht rood;
- W06: een wacht die draaide maar niets kreeg is oranje; een wacht zonder ronde is grijs, nooit groen;
- W07: een klaargezet item over die dag (Wispr) komt erbij met zijn telling van die dag;
- W08: wat op een andere dag binnenkwam, telt niet mee;
- W11: een gesprek met afdeling prive (RZ3-01) toont alleen 'privégesprek, N min', zonder naam of onderwerp;
  prive=1 zonder afdeling (WhatsApp van de Mac) houdt naam en aantal;
- W09: een fototitel met een tijdsbereik krijgt de eerste tijd als tijd en de rest als wat, zonder losse streep; '20:25pizza' en '99:99' zijn geen tijd.
- W12 (FATHOM-3, T-0120): een klaarzet-item van een gesprekswacht met de uniek van een gesprek in de tabel staat er niet
  nog eens bij, ook niet op de dag waarop het klaargezet werd; ontdubbeld op uniek, voor de privémaskering. Een ander
  item van dezelfde wacht blijft.
- W13 (FATHOM-4, T-0120): een rij dekking:fathom:<dag> van De Fathomwacht maakt die dag gedekt, en telt niet als item.

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


C.get("/api/wachten/dag?dag=2026-10-31", headers=K)  # maakt de tabellen
con = sqlite3.connect(os.environ["AGENTS_DB"])
A._mail_tabellen(con)
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,prive,bron,ts) "
            "VALUES('whatsapp:1','2026-10-31','09:15',0,'Sara','3 berichten',1,'whatsapp','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,prive,bron,ts) "
            "VALUES('dekking:whatsapp:2026-10-31','2026-10-31','',0,'',1,'dekking','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,prive,bron,ts) "
            "VALUES('whatsapp:2','2026-10-30','10:00',0,'Oud',1,'whatsapp','x')")
con.execute("INSERT INTO mailbericht(uniek,wacht,postvak,datum,dag,van,van_naam,onderwerp,soort,ts) VALUES"
            "('m1','mail-mch','mch@h-architects.be','2026-10-31T08:02:00+00:00','2026-10-31','a@b.be','Klant A',"
            "'Offerte dak','klant','x')")
con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('sms-wacht','','fout','kopie niet leesbaar',"
            "'2026-10-31T10:00:00+00:00')")
con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('belwacht','','bron','0 oproepen',"
            "'2026-10-31T11:00:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('wispr-wacht','mehdi','telling',"
            "'Wispr Flow','{\"per_dag\":{\"2026-10-31\":{\"dictaten\":12,\"woorden\":840}}}','wispr:Mehdi:2026-10-31',"
            "'2026-10-31T20:30:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('icloud-wacht','mehdi','foto',"
            "'2026-10-31 20:25-20:56: 22 foto''s bij 50.88906,4.7214','','fotos:2026-10-31:21:PROEF','2026-10-31T20:15:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('icloud-wacht','mehdi','foto',"
            "'2026-10-31 18:56-18:56: 1 foto''s zonder plaats','','fotos:2026-10-31:19:PROEF','2026-10-31T20:15:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('icloud-wacht','mehdi','foto',"
            "'2026-10-31 20:25pizza bij de bakker','','fotos:2026-10-31:22:PROEF','2026-10-31T20:16:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('icloud-wacht','mehdi','foto',"
            "'2026-10-31 99:99: geen tijd','','fotos:2026-10-31:23:PROEF','2026-10-31T20:17:00+00:00')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
            "VALUES('fathom:9','2026-10-31','19:40',10,'Geheim Persoon','Geheim onderwerp','prive',1,'fathom','x')")
con.commit()
con.close()

check("W01 zonder token", C.get("/api/wachten/dag?dag=2026-10-31").status_code == 403)
check("W01 geen datum", C.get("/api/wachten/dag?dag=gisteren", headers=K).status_code == 400)
r = C.get("/api/wachten/dag?dag=2026-10-31", headers=K)
d = r.get_json()
w = {x["naam"]: x for v in d["vakken"] for x in v["wachten"]}
namen = [x["naam"] for v in d["vakken"] for x in v["wachten"]]
check("W02 alle wachten", set(namen) == set(A.DAGBUNDELAAR_AGENTS), set(A.DAGBUNDELAAR_AGENTS) ^ set(namen))
check("W02 elk een keer", len(namen) == len(set(namen)))
wa = w["whatsapp-wacht"]
check("W03 whatsapp een item", wa["aantal"] == 1 and wa["items"][0]["wie"] == "Sara" and wa["items"][0]["tijd"] == "09:15",
      wa["items"])
check("W03 dag gedekt", wa["gedekt"] is True)
check("W03 groen", wa["kleur"] == "groen")
m = w["mail-mch"]
check("W04 mail", m["aantal"] == 1 and m["items"][0]["wie"] == "Klant A" and "Offerte dak" in m["items"][0]["wat"]
      and m["items"][0]["tijd"] == "09:02", m["items"])
check("W05 fout is rood", w["sms-wacht"]["kleur"] == "rood" and w["sms-wacht"]["fouten"])
check("W06 draaide zonder items oranje", w["belwacht"]["kleur"] == "oranje", w["belwacht"]["kleur"])
check("W06 geen ronde grijs", w["zoom-wacht"]["kleur"] == "grijs", w["zoom-wacht"]["kleur"])
wi = w["wispr-wacht"]
check("W07 wispr telling", wi["aantal"] == 1 and "dictaten 12" in wi["items"][0]["wat"], wi["items"])
d30 = C.get("/api/wachten/dag?dag=2026-11-01", headers=K).get_json()
w30 = {x["naam"]: x for v in d30["vakken"] for x in v["wachten"]}
check("W08 andere dag telt niet", w30["whatsapp-wacht"]["aantal"] == 0 and w30["mail-mch"]["aantal"] == 0)

fo = w["icloud-wacht"]
check("W09 fototitel: tijd en wat", fo["aantal"] == 4 and fo["items"][0]["tijd"] == "18:56"
      and fo["items"][0]["wat"] == "1 foto's zonder plaats" and fo["items"][1]["tijd"] == "20:25"
      and fo["items"][1]["wat"] == "22 foto's bij 50.88906,4.7214 (20:25 tot 20:56)", fo["items"])
check("W09 geen tijd: titel blijft heel", fo["items"][2]["wat"] == "20:25pizza bij de bakker" and fo["items"][2]["tijd"] == "21:16"
      and fo["items"][3]["wat"] == "99:99: geen tijd" and fo["items"][3]["tijd"] == "21:17", fo["items"][2:])

fa = w["fathom-wacht"]
check("W11 privégesprek zonder naam of onderwerp", fa["aantal"] == 1 and fa["items"][0]["wie"] == "privégesprek"
      and fa["items"][0]["wat"] == "10 min" and "Geheim" not in str(fa["items"]), fa["items"])
check("W11 whatsapp prive=1 zonder afdeling houdt de naam", wa["items"][0]["wie"] == "Sara")
check("W10 leesfout en logfout apart in het antwoord", wa.get("logfout") == "" and wa.get("leesfout") == "")

con = sqlite3.connect(os.environ["AGENTS_DB"])
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
            "VALUES('fathom:8','2026-10-30','14:00',25,'Jan Proef','Proefdak','regie',0,'fathom','x')")
for uniek, titel in (("fathom:8", "2026-10-30T14:00 Fathom: Jan Proef · Proefdak"),
                     ("fathom:9", "2026-10-31T19:40 Fathom: privégesprek, 10 min · PRIVÉ"),
                     ("fathom-proef:2026-10-31", "2026-10-31 07:03: Fathom-overzicht")):
    con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('fathom-wacht','regisseur','transcript',"
                "?,'{}',?,'2026-10-31T07:02:00+00:00')", (titel, uniek))
con.commit()
con.close()
w31 = {x["naam"]: x for v in C.get("/api/wachten/dag?dag=2026-10-31", headers=K).get_json()["vakken"] for x in v["wachten"]}
fa31 = w31["fathom-wacht"]
check("W12 geen dubbele regel voor een gesprek in de tabel", fa31["aantal"] == 2 and "Jan Proef" not in str(fa31["items"])
      and sum("privégesprek" in str(x) for x in fa31["items"]) == 1, fa31["items"])
check("W12 een ander item van de wacht blijft", any("Fathom-overzicht" in x["wat"] for x in fa31["items"]), fa31["items"])
w30 = {x["naam"]: x for v in C.get("/api/wachten/dag?dag=2026-10-30", headers=K).get_json()["vakken"] for x in v["wachten"]}
check("W12 het gesprek staat op zijn eigen dag een keer", w30["fathom-wacht"]["aantal"] == 1
      and w30["fathom-wacht"]["items"][0]["wie"] == "Jan Proef", w30["fathom-wacht"]["items"])
check("W13 Fathom zonder dekkingsrij is niet gedekt", w30["fathom-wacht"]["gedekt"] is False)
con = sqlite3.connect(os.environ["AGENTS_DB"])
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,prive,bron,dubbel_van,ts) "
            "VALUES('dekking:fathom:2026-10-30','2026-10-30','',0,'','gelezen',1,'dekking','buiten:dekking','x')")
con.commit()
con.close()
w30 = {x["naam"]: x for v in C.get("/api/wachten/dag?dag=2026-10-30", headers=K).get_json()["vakken"] for x in v["wachten"]}
check("W13 de dekkingsrij van Fathom maakt de dag gedekt, zonder extra item",
      w30["fathom-wacht"]["gedekt"] is True and w30["fathom-wacht"]["aantal"] == 1, w30["fathom-wacht"])

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
