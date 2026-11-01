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
- W12 (TEL-4, WA-7): een gemiste oproep (buiten:gemist) heet 'telt niet als gesprek', nooit 'dubbel'; een vervallen
  rij 'niet meer in de bron'; alleen een echte dubbel blijft 'dubbel, telt niet';
- W13 (TEL-8): een gesprekswacht met een dekkingsrij voor die dag en geen enkel item is groen 'gelezen, niets gebeurd',
  niet grijs of oranje: de dag is gelezen en er was niets;
- W09: een fototitel met een tijdsbereik krijgt de eerste tijd als tijd en de rest als wat, zonder losse streep; '20:25pizza' en '99:99' zijn geen tijd.

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
for uniek, start, thema, dubbel, afdeling in (
        ("telefoon:A-1", "08:00", "telefoon, inkomend, gemist", "buiten:gemist", ""),
        ("telefoon:B-2", "08:30", "telefoon, uitgaand, niet beantwoord", "buiten:gemist", ""),
        ("telefoon:C-3", "09:00", "telefoon, inkomend", "buiten:vervallen", ""),
        ("telefoon:D-4", "09:30", "telefoon, inkomend", "telefoon:A-1", ""),
        ("telefoon:E-5", "10:00", "telefoon, inkomend, gemist", "buiten:gemist", "prive")):
    con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,dubbel_van,ts) "
                "VALUES(?,'2026-10-29',?,0,'Proef Beller',?,?,1,'telefoon',?,'x')", (uniek, start, thema, afdeling, dubbel))
con.commit()
con.close()
d29 = C.get("/api/wachten/dag?dag=2026-10-29", headers=K).get_json()
bel = {x["naam"]: x for v in d29["vakken"] for x in v["wachten"]}["belwacht"]
wat = [i["wat"] for i in bel["items"]]
check("W12 gemist is geen dubbel", wat[0] == "telefoon, inkomend, gemist, telt niet als gesprek"
      and wat[1] == "telefoon, uitgaand, niet beantwoord, telt niet als gesprek", wat)
check("W12 vervallen en echte dubbel", wat[2] == "telefoon, inkomend, niet meer in de bron"
      and wat[3] == "telefoon, inkomend, dubbel, telt niet", wat)
check("W12 privé gemist zonder naam", bel["items"][4]["wie"] == "privégesprek"
      and wat[4] == "gemist, telt niet als gesprek", bel["items"][4])

con = sqlite3.connect(os.environ["AGENTS_DB"])
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,prive,bron,dubbel_van,ts) "
            "VALUES('dekking:xelion:2026-10-30','2026-10-30','',0,'',1,'dekking','buiten:dekking','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,prive,bron,dubbel_van,ts) "
            "VALUES('dekking:sms:2026-10-30','2026-10-30','',0,'',1,'dekking','buiten:dekking','x')")
con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('sms-wacht','','gelezen','0 berichten',"
            "'2026-10-30T10:00:00+00:00')")
con.commit()
con.close()
d30 = C.get("/api/wachten/dag?dag=2026-10-30", headers=K).get_json()
w30 = {x["naam"]: x for v in d30["vakken"] for x in v["wachten"]}
check("W13 gelezen zonder ronde: niets gebeurd", w30["xelion-wacht"]["oordeel"] == "gelezen, niets gebeurd"
      and w30["xelion-wacht"]["kleur"] == "groen" and w30["xelion-wacht"]["aantal"] == 0, w30["xelion-wacht"]["oordeel"])
check("W13 gelezen met ronde: niets gebeurd", w30["sms-wacht"]["oordeel"] == "gelezen, niets gebeurd"
      and w30["sms-wacht"]["kleur"] == "groen", w30["sms-wacht"]["oordeel"])
check("W13 niet gelezen blijft grijs", w30["belwacht"]["kleur"] == "grijs", w30["belwacht"]["oordeel"])

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
