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
- W12 (T-0120 DB-8): een Zoom- of Plaud-rij met prive=1 en afdeling onbekend of leeg is ook privé (privegrens.py):
  alleen 'privégesprek, N min'. Tot 01-11-2026 toonde de pagina daar naam en onderwerp;
- W12 (T-0120 WACHT-2): De Zoomwacht is helemaal gelezen als haar dagregel volledig, definitief en met elke bron ok is;
  vandaag toont niets;
- W12 (TEL-4, WA-7): een gemiste oproep (buiten:gemist) heet 'telt niet als gesprek', nooit 'dubbel'; een vervallen
  rij 'niet meer in de bron'; alleen een echte dubbel blijft 'dubbel, telt niet';
- W13 (TEL-8): een gesprekswacht met een dekkingsrij voor die dag en geen enkel item is groen 'gelezen, niets gebeurd',
  niet grijs of oranje: de dag is gelezen en er was niets;
- W09: een fototitel met een tijdsbereik krijgt de eerste tijd als tijd en de rest als wat, zonder losse streep; '20:25pizza' en '99:99' zijn geen tijd;
- W20 (WISPR-3): een fout-hartslag van gisteren maakt vandaag niet rood (de stand van nu blijft zichtbaar); een
  fout-hartslag van vandaag wel.
- W12 (MAIL-6, T-0120): een mail toont of ze opgevolgd is en waar ze heen ging (Opgeruimd, een sorteermap, de map
  waarin ze gelezen werd); een mailwacht die rondes deed zonder leesprobleem en 0 mails kreeg, zegt 'postvak
  gelezen, 0 nieuwe mails'; met een leesprobleem in het werkverslag blijft het 'draaide, niets binnen'.
- W12 (FATHOM-3, T-0120): een klaarzet-item van een gesprekswacht met de uniek van een gesprek in de tabel staat er niet
  nog eens bij, ook niet op de dag waarop het klaargezet werd; ontdubbeld op uniek, voor de privémaskering. Een ander
  item van dezelfde wacht blijft.
- W13 (FATHOM-4, T-0120): een rij dekking:fathom:<dag> van De Fathomwacht maakt die dag gedekt, en telt niet als item.
- W14 (T-0120, Codex bij FATHOM-3): bij Fathom, Plaud en Zoom is prive=1 ook met een andere afdeling een privégesprek:
  'privégesprek, N min', zonder naam of onderwerp. Bij WhatsApp blijft prive=1 de naam tonen (W11).

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
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
            "VALUES('zoom:meeting:w12','2026-10-29','16:00',25,'Verborgen Persoon','Verborgen onderwerp','onbekend',1,"
            "'zoom','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,prive,bron,ts) "
            "VALUES('plaud:w12','2026-10-29','17:00',8,'Verborgen Persoon','Verborgen onderwerp',1,'plaud','x')")
for uniek, wacht, soort, opv, besluit, mp, naar, opg in (
        ("m2", "mail-hinv", "hoog", "open", "", "INBOX", "INBOX.Opgeruimd", 1),
        ("m3", "mail-hinv", "melding", "geen", "", "INBOX.Zoom", "", 0),
        ("m4", "mail-hinv", "midden", "open", "afgehandeld", "INBOX", "INBOX.Bank en verzekering", 0),
        ("m5", "mail-hinv", "midden", "beantwoord", "", "INBOX", "", 0)):
    con.execute("INSERT INTO mailbericht(uniek,wacht,postvak,map,datum,dag,van,van_naam,onderwerp,soort,ts,opvolging,besluit,"
                "naar,opgeruimd) VALUES(?,?,'proef@h-invest.be',?,'2026-10-31T09:00:00+00:00','2026-10-31','p@voorbeeld.test',"
                "'Proef',?,?,'x',?,?,?,?)", (uniek, wacht, mp, f"Onderwerp {uniek}", soort, opv, besluit, naar, opg))
for wacht, stap in (("mail-melo", "ronde"), ("mail-info-harc", "ronde"), ("mail-info-harc", "bron")):
    con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES(?,'dag 2026-10-31',?,'laatste 24 u: hoog 0',"
                "'2026-10-31T12:00:00+00:00')", (wacht, stap))
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
      and fo["items"][1]["wat"] == "22 foto's bij een plek (plaats niet getoond) (20:25 tot 20:56)", fo["items"])
check("W09 (T-0120 FOTO-8, groep pagina) een oud foto-item toont geen coördinaten", "50.88906" not in str(fo["items"]))
check("W09 geen tijd: titel blijft heel", fo["items"][2]["wat"] == "20:25pizza bij de bakker" and fo["items"][2]["tijd"] == "21:16"
      and fo["items"][3]["wat"] == "99:99: geen tijd" and fo["items"][3]["tijd"] == "21:17", fo["items"][2:])

fa = w["fathom-wacht"]
check("W11 privégesprek zonder naam of onderwerp", fa["aantal"] == 1 and fa["items"][0]["wie"] == "privégesprek"
      and fa["items"][0]["wat"] == "10 min" and "Geheim" not in str(fa["items"]), fa["items"])
check("W11 whatsapp prive=1 zonder afdeling houdt de naam", wa["items"][0]["wie"] == "Sara")
d29 = C.get("/api/wachten/dag?dag=2026-10-29", headers=K).get_json()
w29 = {x["naam"]: x for v in d29["vakken"] for x in v["wachten"]}
for wacht in ("zoom-wacht", "plaud-wacht"):
    it = w29[wacht]["items"]
    check(f"W12 {wacht}: prive=1 zonder afdeling privé is een privégesprek",
          len(it) == 1 and it[0]["wie"] == "privégesprek" and it[0]["wat"].endswith(" min")
          and "Verborgen" not in str(it), it)
check("W10 leesfout en logfout apart in het antwoord", wa.get("logfout") == "" and wa.get("leesfout") == "")

hi = {x["wat"].split(" · ")[0]: x["wat"] for x in w["mail-hinv"]["items"]}
check("W12 opgevolgd en waarheen", "op te volgen" in hi["Onderwerp m2"] and "naar Opgeruimd" in hi["Onderwerp m2"], hi)
check("W12 gelezen in een andere map", hi["Onderwerp m3"].endswith("in Zoom") and "op te volgen" not in hi["Onderwerp m3"], hi)
check("W12 besluit van Mehdi gaat voor", "afgehandeld" in hi["Onderwerp m4"] and "op te volgen" not in hi["Onderwerp m4"]
      and "naar Bank en verzekering" in hi["Onderwerp m4"], hi)
check("W12 beantwoord", "beantwoord" in hi["Onderwerp m5"], hi)
check("W12 postvak gelezen, 0 nieuwe", w["mail-melo"]["oordeel"] == "postvak gelezen, 0 nieuwe mails"
      and w["mail-melo"]["kleur"] == "oranje", w["mail-melo"]["oordeel"])
check("W12 leesprobleem: geen bewering", w["mail-info-harc"]["oordeel"] == "draaide, niets binnen", w["mail-info-harc"]["oordeel"])
check("W12 andere wachten ongewijzigd", w["belwacht"]["oordeel"] == "draaide, niets binnen")
# W20 (WISPR-3): 01-11-2026 stond de Wispr-wacht rood door de fout-hartslag van de serverwacht van 31-10 22:45.
from datetime import datetime, timedelta, timezone  # noqa: E402
nu_utc = datetime.now(timezone.utc)
vandaag = nu_utc.astimezone(A.BRUSSEL).date()
con = sqlite3.connect(os.environ["AGENTS_DB"])
gisteren_ts = datetime.combine(vandaag - timedelta(days=1), datetime.min.time(), timezone.utc).replace(hour=12).isoformat()
con.execute("INSERT OR REPLACE INTO status(naam,status,taak,detail,ts) VALUES('wispr-wacht','fout','portaal','oud',?)",
            (gisteren_ts,))
con.execute("INSERT OR REPLACE INTO status(naam,status,taak,detail,ts) VALUES('youtube-wacht','fout','lezen','nu',?)",
            (nu_utc.isoformat(),))
con.commit()
con.close()
dv = C.get(f"/api/wachten/dag?dag={vandaag.isoformat()}", headers=K).get_json()
wv = {x["naam"]: x for v in dv["vakken"] for x in v["wachten"]}
check("W20 fout-hartslag van gisteren: vandaag niet rood", wv["wispr-wacht"]["kleur"] != "rood"
      and wv["wispr-wacht"]["status"]["status"] == "fout", wv["wispr-wacht"])
check("W20 fout-hartslag van vandaag: rood", wv["youtube-wacht"]["kleur"] == "rood", wv["youtube-wacht"])
# W12 (T-0120 WACHT-2): De Zoomwacht schrijft geen dekkingsrij; haar dekking staat in de dagregel zoom:dag:<dag>.
import json as _json  # noqa: E402
from datetime import datetime as _dt  # noqa: E402
from zoneinfo import ZoneInfo as _Zone  # noqa: E402


def _dagregel(dag, telling, stand, bronnen):
    return ("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('zoom-wacht','mehdi','zoom',?,?,?,?)",
            (f"Zoom {dag}", _json.dumps({"datum": dag, "telling": telling, "stand": stand, "bronnen": bronnen,
                                          "gesprekken": 3}), f"zoom:dag:{dag}", f"{dag}T22:00:00+00:00"))

ok = {b: "ok" for b in ("rapport", "vaste vergaderruimte", "gepland", "opnames", "laatste sessie", "fathom-archief",
                        "fathom-api", "chat")}
vandaag = _dt.now(_Zone("Europe/Brussels")).date().isoformat()
con = sqlite3.connect(os.environ["AGENTS_DB"])
for sql, args in (_dagregel("2026-10-27", "volledig", "definitief", ok),
                  _dagregel("2026-10-28", "volledig", "voorlopig: Fathom levert nog", ok),
                  _dagregel("2026-10-29", "volledig", "definitief", dict(ok, chat="fout: HTTP 500")),
                  _dagregel("2026-10-25", "volledig", "definitief", {"rapport": "ok"}),
                  _dagregel(vandaag, "volledig", "definitief", ok)):
    con.execute(sql, args)
con.commit()
con.close()


def _zoom(dag):
    d = C.get(f"/api/wachten/dag?dag={dag}", headers=K).get_json()
    return {x["naam"]: x for v in d["vakken"] for x in v["wachten"]}["zoom-wacht"]


check("W12 zoom: dagregel volledig, definitief, elke bron ok geeft helemaal gelezen", _zoom("2026-10-27")["gedekt"] is True)
check("W12 zoom: een voorlopige dagregel geeft nog niet helemaal gelezen", _zoom("2026-10-28")["gedekt"] is False)
check("W12 zoom: een bron niet ok geeft nog niet helemaal gelezen", _zoom("2026-10-29")["gedekt"] is False)
check("W12 zoom: een ontbrekende bron is niet gelezen", _zoom("2026-10-25")["gedekt"] is False)
check("W12 zoom: een dag zonder dagregel is nog niet helemaal gelezen", _zoom("2026-10-26")["gedekt"] is False)
check("W12 zoom: vandaag toont niets", _zoom(vandaag)["gedekt"] is None)
check("W12 whatsapp houdt zijn dekkingsrij", w["whatsapp-wacht"]["gedekt"] is True)
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
con = sqlite3.connect(os.environ["AGENTS_DB"])
for uniek, bron in (("fathom:14", "fathom"), ("plaud:14", "plaud"), ("zoom:meeting:14", "zoom")):
    con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
                "VALUES(?,'2026-10-22','11:00',12,'Verborgen Persoon','Verborgen onderwerp','regie',1,?,'x')", (uniek, bron))
con.commit()
con.close()
w22 = {x["naam"]: x for v in C.get("/api/wachten/dag?dag=2026-10-22", headers=K).get_json()["vakken"] for x in v["wachten"]}
for wacht in ("fathom-wacht", "plaud-wacht", "zoom-wacht"):
    it = w22[wacht]["items"]
    check(f"W14 {wacht}: prive=1 met afdeling regie is een privégesprek", len(it) == 1 and it[0]["wie"] == "privégesprek"
          and it[0]["wat"] == "12 min" and "Verborgen" not in str(it), it)
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
# Codex 01-11: een vervallen dekkingsrij (de bron toont de dag niet meer) is geen bewijs dat de dag gelezen is
con = sqlite3.connect(os.environ["AGENTS_DB"])
con.execute("UPDATE gesprek_log SET dubbel_van='buiten:vervallen' WHERE uniek='dekking:xelion:2026-10-30'")
con.commit()
con.close()
w30 = {x["naam"]: x for v in C.get("/api/wachten/dag?dag=2026-10-30", headers=K).get_json()["vakken"] for x in v["wachten"]}
check("W13 vervallen dekking is niet gelezen", w30["xelion-wacht"]["kleur"] == "grijs"
      and w30["xelion-wacht"]["gedekt"] is False, (w30["xelion-wacht"]["oordeel"], w30["xelion-wacht"]["gedekt"]))

# --- T-0120 groep pagina: VOL-19/DB-5 (links via een route achter Authentik), VOL-9 (bijlagen), VOL-13 (gelezen tot),
# ARCH-2 (De Zoomarchivaris), ANGEL-6 (de taken van Ai Angel). Verzonnen voorbeelden op 27-10 (dinsdag) en 24-10 (zaterdag).
import json  # noqa: E402

import wachten_dag as WD  # noqa: E402

INV = tempfile.mkdtemp()                        # /data/plaud-invoer
WD.PLAUD_INVOER = INV
for mapnaam in ("2026-10-27 1000 Proefopname", "2026-10-27 1100 Prive proef"):
    os.makedirs(os.path.join(INV, mapnaam))
    with open(os.path.join(INV, mapnaam, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump([{"start_time": 0, "speaker": "Spreker Proef", "content": "Goedemorgen, dit is een proefzin."},
                   {"start_time": 65000, "speaker": "Spreker Twee", "content": "Tweede proefzin."}], f)
with open(os.path.join(INV, "00 manifest.json"), "w", encoding="utf-8") as f:
    json.dump({"meta": {"gemaakt": "2026-10-28T08:00:00+00:00"}, "opnames": [
        {"plaud_id": "pw1", "start_brussel": "2026-10-27T10:00", "duur_minuten": 12, "toestand": "compleet",
         "audio": {"staat": "ok"}, "archief": {"map": "2026-10-27 1000 Proefopname"}},
        {"plaud_id": "pw2", "start_brussel": "2026-10-27T11:00", "duur_minuten": 5, "toestand": "compleet",
         "audio": {"staat": "ontbreekt"}, "archief": {"map": "2026-10-27 1100 Prive proef"}}]}, f)
ZA = tempfile.mkdtemp()                         # /data/zoom-archief
WD.ZOOM_ARCHIEF = os.path.join(ZA, "wachten.json")
with open(WD.ZOOM_ARCHIEF, "w", encoding="utf-8") as f:
    json.dump({"ts": "2026-10-28T06:00:00+00:00", "dagen": {"2026-10-27": {
        "gekopieerd": [{"uur": "10:05", "soort": "scherm en spreker", "mb": 512.34, "map": "Zoom/2026-10-27 1005"},
                       {"uur": "14:00", "soort": "chat", "mb": 0.1, "map": "Zoom/2026-10-27 1400 Geheim onderwerp"}],
        "verdwenen": [{"uur": "16:00", "mb": 20.0}]}}}, f)
WD.ANGEL_STAAT = os.path.join(ZA, "staat.json")
with open(WD.ANGEL_STAAT, "w", encoding="utf-8") as f:
    json.dump({"taken": {"t3": {"id": "t3", "tekst": "Bel de proefaannemer over de offerte", "prive": True}},
               "afgerond": []}, f)
TAKEN = ["Bijgewerkt 27-10-2026 10:20. Bijsturen kan op het bord.", "", "## Voor jou", ""]
for i in range(1, 15):
    tekst = {3: "Bel de proefaannemer over de offerte"}.get(i, f"Proeftaak nummer {i}")
    TAKEN += [f"{i}. {tekst} (normaal)", "   Waarom: omdat het in de proef staat",
              f"   Bron: 2026-10-27, {'privégesprek, 12 min' if i == 2 else 'proefregel'}"]
TAKEN += ["", "## Afgerond vandaag", "", "- Oude proeftaak (gedaan)"]
con = sqlite3.connect(os.environ["AGENTS_DB"])
for uniek, prive, afd, link, archief in (
        ("fathom:f1", 0, "regie", "https://fathom.video/share/PROEF1", ""),
        ("fathom:f2", 1, "regie", "https://fathom.video/calls/2", ""),
        ("fathom:f3", 0, "regie", "https://elders.example/x", ""),
        ("plaud:pw1", 0, "regie", "Data uit Mehdi/Plaud/2026-10-27 1000 Proefopname/transcript.md",
         "Data uit Mehdi/Plaud/2026-10-27 1000 Proefopname/transcript.md"),
        ("plaud:pw2", 1, "", "Data uit Mehdi/Plaud/2026-10-27 1100 Prive proef/transcript.md",
         "Data uit Mehdi/Plaud/2026-10-27 1100 Prive proef/transcript.md"),
        ("plaud:pw3", 0, "regie", "", "Data uit Mehdi/Plaud/../transcript.md"),
        ("whatsapp:w30", 1, "", "https://fathom.video/share/NIET", "")):
    con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,link,archief,ts) "
                "VALUES(?,'2026-10-27','10:00',12,'Proef Persoon','Proefonderwerp',?,?,?,?,?,'x')",
                (uniek, afd, prive, uniek.split(":")[0], link, archief))
for uniek, n, info in (("m30", 2, '[{"soort":"pdf","bytes":120000},{"soort":"dwg","bytes":1300000}]'),
                       ("m31", 0, "[]"), ("m32", None, None), ("m33", 1, '[{"soort":"pdf","bytes":500}]'),
                       ("m34", 3, '[{"soort":"pdf","bytes":10},{"soort":"pdf","bytes":10},{"soort":"eml","bytes":0}]')):
    con.execute("INSERT INTO mailbericht(uniek,wacht,postvak,map,datum,dag,van,van_naam,onderwerp,soort,ts,bijlagen,"
                "bijlagen_info) VALUES(?,'mail-mch','proef@voorbeeld.test','INBOX','2026-10-27T09:00:00+00:00',"
                "'2026-10-27','p@voorbeeld.test','Proef',?,'klant','x',?,?)", (uniek, f"Onderwerp {uniek}", n, info))
for van, soort, uniek, sleutel, titel, inhoud in (
        ("dagbundelaar", "dagvaststelling", "vaststelling:2026-10-27", "2026-10-27", "Dagvaststelling 2026-10-27", ""),
        ("communicatie-bundelaar", "communicatie", "communicatie:dag:2026-10-27", "2026-10-27", "Communicatie 27-10", ""),
        ("icloud-wacht", "foto", "fotos:2026-10-27:w1", "2026-10-27",
         "2026-10-27 10:00-10:30: HA 9001 Proefproject: 3 werkfoto's, bij afspraak '[HA] 9001 proef' 10:00-11:00",
         json.dumps({"datum": "2026-10-27", "soort": "zeker", "firma": "HA", "nummer": "9001", "aantal": 3})),
        ("icloud-wacht", "foto", "fotos:2026-10-27:telling", "2026-10-27",
         "2026-10-27: geen werk: privé 4, met mensen 1, scherm of app 0, onbeslist 0 (alleen geteld, geen plaats)",
         json.dumps({"datum": "2026-10-27", "aantal": 5, "prive": 4, "mensen": 1})),
        ("mehdi-agent", "taken", "mehdi-agent:taken:2026-10-27", "2026-10-27", "Te doen 27-10: 14 open", "\n".join(TAKEN)),
        ("mehdi-agent", "verslag", "mehdi-agent:avond:2026-10-27", "2026-10-27", "Avondoverzicht 27-10", "Proefoverzicht")):
    con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,sleutel,ts) VALUES(?,'mehdi',?,?,?,?,?,"
                "'2026-10-27T20:00:00+00:00')", (van, soort, titel, inhoud, uniek, sleutel))
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,prive,bron,dubbel_van,ts) "
            "VALUES('dekking:whatsapp:2026-10-24','2026-10-24','',0,'',1,'dekking','buiten:dekking','x')")
for naam, uur_ in (("belwacht", "09:00"), ("belwacht", "15:30"), ("zoom-archief", "06:00"), ("plaud-wacht", "08:00"),
                   ("mail-mch", "09:05")):
    con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES(?,'','bron','proefronde',?)",
                (naam, f"2026-10-27T{uur_}:00+00:00"))
con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('zoom-archief','','bron','proefronde',"
            "'2026-10-26T06:00:00+00:00')")
con.execute("INSERT INTO agent(naam,label,rol,cadans,aangemaakt) VALUES('agenda-wacht','De Agendawacht',"
            "'Leest de agenda''s en zet de afspraken klaar','Elke werkdag 07:15','x')")
con.commit()
tel_voor = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("gesprek_log", "klaarzet", "logboek")]
con.close()


def wachten(dag):
    return {x["naam"]: x for v in C.get(f"/api/wachten/dag?dag={dag}", headers=K).get_json()["vakken"] for x in v["wachten"]}


w27, w26, w24 = wachten("2026-10-27"), wachten("2026-10-26"), wachten("2026-10-24")
f1 = [x for x in w27["fathom-wacht"]["items"] if x.get("link")]
check("P30 (FATHOM-3) een werkgesprek van Fathom heeft 'open in Fathom', als soort en zonder url",
      len(f1) == 1 and f1[0]["link"] == {"soort": "fathom", "uniek": "fathom:f1", "tekst": "open in Fathom"},
      w27["fathom-wacht"]["items"])
check("P30 een privégesprek van Fathom heeft geen link en geen naam",
      any(x["wie"] == "privégesprek" and "link" not in x for x in w27["fathom-wacht"]["items"]), w27["fathom-wacht"]["items"])
pl = w27["plaud-wacht"]["items"]
check("P31 (PLAUD-7) een werkopname van Plaud heeft 'transcript lezen'; privé en een map met '..' niet",
      [x["link"]["uniek"] for x in pl if x.get("link")] == ["plaud:pw1"]
      and any(x["wie"] == "privégesprek" and "link" not in x for x in pl), pl)
alle_links = [(n, x) for n, w in w27.items() for x in w["items"] if x.get("link")]
check("P32 (VOL-19) geen enkele link bij WhatsApp, sms, telefoon of Xelion, of bij een privé-item",
      alle_links and not any(n in WD.GEEN_LINK or x["wie"] == "privégesprek" for n, x in alle_links), alle_links)
check("P32 een link draagt nooit een url of een pad naar Dropbox",
      "http" not in json.dumps([x["link"] for _, x in alle_links]) and "Data uit Mehdi" not in json.dumps(alle_links))
check("P33 (DB-5) dagvaststelling en communicatie naar /dag/<dag>",
      [x["link"] for x in w27["dagbundelaar"]["items"]] == [{"soort": "dag", "dag": "2026-10-27", "tekst": "de dag openen"}]
      and w27["communicatie-bundelaar"]["items"][0]["link"]["soort"] == "dag", w27["communicatie-bundelaar"]["items"])
check("P34 (FOTO-5) een werfgroep linkt naar de foto's per project; de telling van privé en mensen niet",
      [x["link"]["soort"] for x in w27["icloud-wacht"]["items"] if x.get("link")] == ["fotos"]
      and any("alleen geteld, geen plaats" in x["wat"] and "link" not in x for x in w27["icloud-wacht"]["items"]),
      w27["icloud-wacht"]["items"])
bij = {x["wat"].split(" · ")[0]: x["wat"] for x in w27["mail-mch"]["items"]}
check("P35 (VOL-9) een mail met een pdf en een dwg toont '2 bijlagen (pdf, dwg)' met de grootte",
      bij.get("Onderwerp m30") == "Onderwerp m30 · 2 bijlagen (pdf, dwg), 1,4 MB · klant", bij)
check("P35 bij 0 of onbekend nooit '0 bijlagen'", "bijlage" not in bij["Onderwerp m31"] and "bijlage" not in bij["Onderwerp m32"],
      bij)
check("P35 een bijlage enkelvoud, en dezelfde soort een keer met haar aantal",
      "1 bijlage (pdf), 1 kB" in bij["Onderwerp m33"] and "3 bijlagen (2 pdf, eml)" in bij["Onderwerp m34"], bij)
za = w27["zoom-archief"]
check("P36 (ARCH-2) De Zoomarchivaris toont elk gekopieerd bestand met uur, soort, MB en de map, en verdwenen apart",
      [(x["tijd"], x["wie"], x["wat"]) for x in za["items"]] == [
          ("10:05", "scherm en spreker", "512,3 MB, bewezen in je Dropbox, map Zoom/2026-10-27 1005"),
          ("14:00", "chat", "0,1 MB, bewezen in je Dropbox, map Zoom"),
          ("16:00", "verdwenen in Zoom", "20,0 MB, niet gekopieerd")] and za["items"][2]["fout"] and za["kleur"] == "groen",
      za["items"])
check("P36 nooit een onderwerp uit de map", "Geheim" not in json.dumps(za), za["items"])
check("P36 een dag zonder kopie blijft oranje", w26["zoom-archief"]["kleur"] == "oranje" and w26["zoom-archief"]["aantal"] == 0,
      w26["zoom-archief"]["oordeel"])
check("P36 de telling van die dag", za["archief"] == {"gekopieerd": 2, "verdwenen": 1, "overzicht_van": "2026-10-28T06:00:00+00:00",
                                                      "na_de_dag": True}, za["archief"])
an = {x["wie"]: x for x in w27["mehdi-agent"]["items"]}
regels = an["taken"].get("regels") or []
check("P37 (ANGEL-6) de genummerde taken van Ai Angel, hoogstens 12, met de rest geteld en de link naar het bord",
      regels[:1] == ["1. Proeftaak nummer 1 (normaal)"] and len(regels) == 13 and regels[-1] == "en nog 2 op het bord"
      and an["taken"]["link"] == {"soort": "bord", "pad": "/agent/mehdi-agent", "tekst": "de volledige lijst op het bord"},
      regels)
check("P37 een privétaak toont alleen 'privé', ook als alleen de staat haar privé noemt",
      regels[1:3] == ["2. privé", "3. privé"] and "proefaannemer" not in json.dumps(w27["mehdi-agent"]), regels)
check("P37 het verslag van Ai Angel linkt naar het bord, zonder regels", an["verslag"]["link"]["soort"] == "bord"
      and "regels" not in an["verslag"])
check("P37 een andere wacht ziet niets veranderen: geen regels bij De Dagbundelaar",
      all("regels" not in x for x in w27["dagbundelaar"]["items"]))
g = {n: w["gelezen"] for n, w in w27.items()}
check("P38 (VOL-13) rondes op die dag zonder dekkingsrij: nog niet helemaal, met de laatste ronde (Brussel)",
      g["belwacht"]["stand"] == "deels" and g["belwacht"]["tekst"] == "nog niet helemaal gelezen, laatste ronde 16:30",
      g["belwacht"])
check("P38 een mailwacht met een ronde: gelezen tot die ronde", g["mail-mch"]["stand"] == "tot"
      and g["mail-mch"]["tekst"] == "gelezen tot 10:05", g["mail-mch"])
check("P38 het manifest van na de dag: alle opnames bekend; het overzicht van na de dag: alle kopieën bekend",
      g["plaud-wacht"]["stand"] == "gelezen" and g["zoom-archief"]["stand"] == "gelezen"
      and g["zoom-archief"]["tekst"] == "alle kopieën van deze dag bekend", (g["plaud-wacht"], g["zoom-archief"]))
check("P38 de dagvaststelling van die dag: dag vastgesteld", g["dagbundelaar"]["stand"] == "gelezen"
      and g["dagbundelaar"]["tekst"] == "dag vastgesteld", g["dagbundelaar"])
check("P38 een wacht zonder ronde, dekking of item: niet gelezen, nooit 0",
      g["gezondheid-wacht"] == {"stand": "niet", "tekst": "niet gelezen",
                                "bewijs": "geen ronde, geen dekking en geen item van deze dag"}, g["gezondheid-wacht"])
g24 = {n: w["gelezen"] for n, w in w24.items()}
check("P38 een dekkingsrij zonder item: helemaal gelezen, niets gebeurd", g24["whatsapp-wacht"]["stand"] == "gelezen"
      and g24["whatsapp-wacht"]["tekst"] == "helemaal gelezen, niets gebeurd", g24["whatsapp-wacht"])
check("P38 zaterdag bij een werkdagwacht: geen ronde gepland (cadans uit de agenttabel)",
      g24["agenda-wacht"]["stand"] == "rust" and "Elke werkdag 07:15" in g24["agenda-wacht"]["bewijs"], g24["agenda-wacht"])
check("P38 een wacht die het bord niet kon lezen: onbekend",
      WD.gelezen_tot(None, "x", "2026-10-27", [], [], None, "niet gelezen (X)", "")["stand"] == "onbekend")
check("P39 (DB-5) de uitleg van een wacht komt uit agent.rol en agent.cadans",
      w24["agenda-wacht"]["uitleg"] == {"rol": "Leest de agenda's en zet de afspraken klaar", "cadans": "Elke werkdag 07:15"}
      and w24["gezondheid-wacht"]["uitleg"] is None, w24["agenda-wacht"]["uitleg"])
con = sqlite3.connect(os.environ["AGENTS_DB"])
tel_na = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("gesprek_log", "klaarzet", "logboek")]
con.close()
check("P38 de pagina schrijft niets: geen dekkingsrij, geen item, geen regel", tel_voor == tel_na, (tel_voor, tel_na))


def open_(uniek, wat, h=K):
    return C.get(f"/api/wachten/gesprek?uniek={uniek}&wat={wat}", headers=h)


check("P40 (VOL-19) zonder token geen gesprek", open_("fathom:f1", "fathom", {}).status_code == 403)
check("P40 Fathom: de link van een werkgesprek", open_("fathom:f1", "fathom").get_json() == {
    "uniek": "fathom:f1", "link": "https://fathom.video/share/PROEF1"})
check("P40 Fathom privé, een link buiten fathom.video, WhatsApp of een onbekend gesprek: 404",
      [open_(u, "fathom").status_code for u in ("fathom:f2", "fathom:f3", "whatsapp:w30", "fathom:geen")] == [404] * 4)
tr = open_("plaud:pw1", "transcript").get_json() or {}
check("P41 (PLAUD-7) het transcript van een werkopname, met tijd en spreker", (tr.get("regels") or [None, None])[1] == {
    "tijd": "00:01:05", "wie": "Spreker Twee", "tekst": "Tweede proefzin."} and tr.get("dag") == "2026-10-27"
      and tr.get("meer") == 0, tr)
check("P41 Plaud privé, een map met '..', Fathom als transcript of Plaud als Fathom-link: 404",
      [open_("plaud:pw2", "transcript").status_code, open_("plaud:pw3", "transcript").status_code,
       open_("fathom:f1", "transcript").status_code, open_("plaud:pw1", "fathom").status_code] == [404] * 4)

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
