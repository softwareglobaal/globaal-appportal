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
      and fo["items"][1]["wat"] == "22 foto's bij 50.88906,4.7214 (20:25 tot 20:56)", fo["items"])
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

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
