"""Grendel op /api/wachten/dag (Mehdi, 01-11-2026: per wacht zien wat er binnenkwam, om te controleren dat het werkt).

- W01: zonder token geen antwoord; een dag die geen datum is, geeft 400;
- W02: elke wacht van de groep Dagbundelaar staat erin, precies een keer, in zijn vak;
- W03: gesprekken (WhatsApp) komen per wacht binnen, met tijd in Brussel en wie; de dekkingsrij telt niet als item;
- W04: mail komt per postvak binnen met afzender en onderwerp;
- W05: een fout in het werkverslag van die dag maakt de wacht rood;
- W06: een wacht die draaide maar niets kreeg is oranje; een wacht zonder ronde is grijs, nooit groen;
- W07: een klaargezet item over die dag (Wispr) komt erbij met zijn telling van die dag;
- W08: wat op een andere dag binnenkwam, telt niet mee;
- W11: een gesprek met afdeling prive draagt het label privé en blijft leesbaar (Mehdi 02-11-2026: hij kijkt het
  oordeel na); prive=1 zonder afdeling (WhatsApp van de Mac) heeft geen label;
- W12: elk item draagt het detail: alles wat de wacht weet (wie, firma, afdeling, thema, waarom, link), zonder lege velden;
- W13: de tekst van een gesprek: Zoom uit zoom-data/<map [sha1]>/transcript.json, Fathom uit het archief (transcript.md),
  Plaud uit plaud-invoer; een gesprek zonder tekst zegt dat; het item weet of er tekst is;
- W14: De Mailregisseur en De Levenscoach staan op de dagpagina (organogram bij De Dagbundelaar);
- W09: een fototitel met een tijdsbereik krijgt de eerste tijd als tijd en de rest als wat, zonder losse streep; '20:25pizza' en '99:99' zijn geen tijd;
- W15 (T-0154): De Zoomwacht staat als twee rijen (gesprekken en chat), elk item in precies een rij; een chatitem leest als
  aantallen, niet als een gesprek met een duur; de chatrij heeft geen eigen werkverslag;
- W16 (T-0154): twijfel is geen privé: 'bij twijfel privé', zekerheid laag of middel of afdeling onbekend geeft het label
  twijfel met de reden; privé alleen bij hoge zekerheid of de vaste regel van de telefoon (met die regel als reden);
- W17 (T-0154): een Fathom-gesprek draagt de kern (doel, conclusies, volgende stappen uit de samenvatting van Fathom) en
  de taken (actiepunten, voor jou of voor anderen); zonder samenvatting zegt het item dat; Plaud en Zoom met tekst
  zeggen dat de samenvatting op De Gespreksanalist wacht;
- W18 (T-0154): bovenaan de dag staat wat voor Mehdi is: de taken uit de gesprekken en de signalen per agent;
- W19 (T-0154): elke wacht heeft een telregel (WhatsApp: berichten, gesprekken, groepen; telefoon: oproepen en gemist).

Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import os
import sqlite3
import sys
import tempfile

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "w.db")
os.environ["MIJNAGENTS_DATA"] = MAP
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
con.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,ts) VALUES('communicatie-bundelaar','','bron','0 personen',"
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
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts,sessie) "
            "VALUES('zoom:meeting:ABC==','2026-10-31','18:12',40,'Angela, Mehdi','Zoom-gesprek','it',0,'zoom','x','zoom:meeting:ABC==')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
            "VALUES('zoom:meeting:ZONDER==','2026-10-31','19:00',5,'Tom','Kort','it',0,'zoom','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts,archief) VALUES("
            "'plaud:of_1','2026-10-31','08:16',30,'Werf','Werfvergadering','harmoniebouw',0,'plaud','x',"
            "'Data uit Mehdi/Plaud/2026-10-31 0816 Werfvergadering/transcript.md')")
con.execute("UPDATE gesprek_log SET archief='~/appportal/mijnagents-data/fathom-data/2026-10-31 1940 Geheim' "
            "WHERE uniek='fathom:9'")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts,archief) VALUES("
            "'fathom:10','2026-10-31','20:00',5,'Leeg','Zonder transcript','it',0,'fathom','x',"
            "'~/appportal/mijnagents-data/fathom-data/2026-10-31 2000 Leeg')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,zekerheid,waarom,bron,ts) VALUES("
            "'zoom:chat:abc:2026-10-31','2026-10-31','09:59',0,'Sales_Won','Zoom-chat: 4 bericht(en), 1 van Mehdi, 09:59 tot 15:54',"
            "'onbekend',1,'middel','kanaal; afdeling niet uit de naam af te leiden: bij twijfel privé','zoom','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,zekerheid,waarom,bron,ts) VALUES("
            "'zoom:chat:def:2026-10-31','2026-10-31','11:45',0,'Collega','Zoom-chat: 2 bericht(en), 2 van Mehdi, 11:45 tot 11:45',"
            "'it',0,'hoog','1:1; bekend op e-mailadres uit de personentabel','zoom','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,zekerheid,waarom,bron,ts,archief) VALUES("
            "'plaud:of_2','2026-10-31','13:20',9,'Speaker 1, Speaker 2','Levertermijn ramen','onbekend',0,'laag','geen sprekers herkend',"
            "'plaud','x','Data uit Mehdi/Plaud/2026-10-31 1320 Ramen/transcript.md')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,zekerheid,waarom,bron,ts) VALUES("
            "'telefoon:1','2026-10-31','08:38',0,'Installateur','telefoon, inkomend, gemist','',1,'','','telefoon','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,zekerheid,waarom,bron,ts) VALUES("
            "'telefoon:2','2026-10-31','12:14',3,'Installateur','telefoon, uitgaand','',1,'','','telefoon','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,bron,ts) "
            "VALUES('whatsapp:3','2026-10-31','10:00',0,'groep: Proefgroep','20 berichten (18 in, 2 uit), 10:00 tot 17:35','',1,'whatsapp','x')")
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,zekerheid,waarom,bron,ts,archief) VALUES("
            "'fathom:11','2026-10-31','11:52',9,'Mehdi, Collega','Automatisering','elevait',0,'hoog','intern',"
            "'fathom','x','~/appportal/mijnagents-data/fathom-data/2026-10-31 1152 Overleg')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts,status) VALUES('mail-regisseur','mehdi','oproep',"
            "'Dringende mail van Klant A','','oproep:1','2026-10-31T08:10:00+00:00','klaar')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts,status) VALUES('agenda-wacht','mehdi','signaal',"
            "'3 afspraken zonder code','','signaal:1','2026-10-31T06:10:00+00:00','klaar')")
# Codex 02-11 (T-0154 ronde 1): zonder privévlag telt twijfel ook; dezelfde opname telt één keer; de chatrij heeft geen hartslag.
con.execute("INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,thema,afdeling,prive,zekerheid,waarom,bron,ts) VALUES("
            "'plaud:of_3','2026-10-31','23:05',4,'Mehdi, Klant B','Dak','elevait',0,'middel','bij twijfel: twee firma''s genoemd','plaud','x')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts,status) VALUES('fathom-wacht','regisseur','transcript',"
            "'2026-10-31T11:52 Fathom: Mehdi, Collega','{\"stand\": \"tekst bewaard\"}','fathom:11','2026-10-31T12:30:00+00:00','klaar')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts,status) VALUES('zoom-wacht','regisseur','zoom-tekst',"
            "'2026-10-31 09:00 Zoom-gesprek, 30 min, alleen in Zoom','{\"stand\": \"tekst bewaard\"}','zoom-tekst:ABC==','2026-10-31T10:00:00+00:00','klaar')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts,status) VALUES('zoom-wacht','regisseur','zoom-tekst',"
            "'2026-10-31 16:00 Zoom-gesprek, 5 min, alleen in Zoom','{\"stand\": \"opname zonder tekst\", \"minuten\": 5}','zoom-tekst:LOS==','2026-10-31T16:10:00+00:00','klaar')")
con.execute("INSERT OR REPLACE INTO status(naam,status,detail,ts) VALUES('zoom-wacht','ok','ronde klaar','2026-10-31T20:00:00+00:00')")
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts,status) VALUES('agenda-wacht','mehdi','signaal',"
            "'Oud signaal','','signaal:0','2026-10-31T06:11:00+00:00','opgepakt')")
lang = "regel 1\n" + "x" * 59990
con.execute("INSERT INTO klaarzet(van,voor,soort,titel,inhoud,uniek,ts) VALUES('dagbundelaar','mehdi','dagplan',"
            "'lang','" + lang + "','lang:1','2026-10-31T20:17:00+00:00')")
con.commit()
con.close()
import hashlib, json  # noqa: E402
zm = os.path.join(MAP, "zoom-data", f"2026-10-31 1812 Zoom vaste vergaderruimte [{hashlib.sha1(b'ABC==').hexdigest()[:8]}]")
os.makedirs(zm)
json.dump([{"speaker": {"display_name": "Angela"}, "text": "Hallo Mehdi.", "timestamp": "00:00:05"},
           {"speaker": {"display_name": "Mehdi"}, "text": "Dag Angela.", "timestamp": "00:00:09"}], open(os.path.join(zm, "transcript.json"), "w"))
fm = os.path.join(MAP, "fathom-data", "2026-10-31 1940 Geheim")
os.makedirs(fm)
open(os.path.join(fm, "transcript.md"), "w").write("# Geheim\n\nMehdi: dit is de tekst.\n")
fl = os.path.join(MAP, "fathom-data", "2026-10-31 2000 Leeg")
os.makedirs(fl)
open(os.path.join(fl, "transcript.md"), "w").write("# Leeg\n\nHerkenning: {}\n\n")
open(os.path.join(fl, "transcript.json"), "w").write("[]")
open(os.path.join(fl, "geen-transcript.txt"), "w").write("Fathom heeft voor dit gesprek geen transcript.\n")
fs = os.path.join(MAP, "fathom-data", "2026-10-31 1152 Overleg")
os.makedirs(fs)
open(os.path.join(fs, "transcript.md"), "w").write("# Overleg\n\nMehdi: tekst.\n")
json.dump({"recording_id": 11, "default_summary": {"template_name": "Enhanced", "markdown_formatted":
           "## Doel van de Vergadering\n\n[Afstemmen over de aanpak.](https://fathom.video/share/x?timestamp=0.0)\n\n"
           "## Belangrijkste Conclusies\n\n  - [**Keuze:** eerst de kleinste proef.](https://fathom.video/share/x?timestamp=10.0)\n\n"
           "## Volgende Stappen\n\n  - [Collega stuurt de lijst door.](https://fathom.video/share/x?timestamp=20.0)\n"},
           "action_items": [{"description": "Lijst doorsturen", "assignee": {"name": "Collega (IT)"}, "completed": False,
                             "recording_playback_url": "https://fathom.video/calls/1?timestamp=20"},
                            {"description": "Proef goedkeuren", "assignee": {"name": "Mehdi Chegini"}, "completed": False,
                             "recording_playback_url": "https://fathom.video/calls/1?timestamp=30"}]},
          open(os.path.join(fs, "gesprek.json"), "w"))
pm = os.path.join(MAP, "plaud-invoer", "2026-10-31 0816 Werfvergadering")
os.makedirs(pm)
json.dump([{"start_time": 61000, "content": "Eerste zin.", "speaker": "Speaker 1"}], open(os.path.join(pm, "transcript.json"), "w"))

check("W01 zonder token", C.get("/api/wachten/dag?dag=2026-10-31").status_code == 403)
check("W01 geen datum", C.get("/api/wachten/dag?dag=gisteren", headers=K).status_code == 400)
r = C.get("/api/wachten/dag?dag=2026-10-31", headers=K)
d = r.get_json()
w = {x["naam"]: x for v in d["vakken"] for x in v["wachten"]}
namen = [x["naam"] for v in d["vakken"] for x in v["wachten"]]
check("W02 alle wachten", set(namen) == set(A.DAGBOEK_AGENTS), set(A.DAGBOEK_AGENTS) ^ set(namen))
check("W14 Mailregisseur en Levenscoach erbij", set(namen) - set(A.DAGBUNDELAAR_AGENTS) == {"mail-regisseur", "levenscoach", "zoom-chat"}
      and d["vakken"][0]["wachten"][-1]["label"] == "De Levenscoach" and [x["naam"] for v in d["vakken"] if v["vak"] == "Mail"
      for x in v["wachten"]][0] == "mail-regisseur", namen)
check("W02 elk een keer", len(namen) == len(set(namen)))
wa = w["whatsapp-wacht"]
check("W03 whatsapp twee items", wa["aantal"] == 2 and wa["items"][0]["wie"] == "Sara" and wa["items"][0]["tijd"] == "09:15",
      wa["items"])
check("W03 dag gedekt", wa["gedekt"] is True)
check("W03 groen", wa["kleur"] == "groen")
m = w["mail-mch"]
check("W04 mail", m["aantal"] == 1 and m["items"][0]["wie"] == "Klant A" and "Offerte dak" in m["items"][0]["wat"]
      and m["items"][0]["tijd"] == "09:02", m["items"])
check("W05 fout is rood", w["sms-wacht"]["kleur"] == "rood" and w["sms-wacht"]["fouten"])
check("W06 draaide zonder items oranje", w["communicatie-bundelaar"]["kleur"] == "oranje", w["communicatie-bundelaar"]["kleur"])
check("W06 geen ronde grijs", w["calendly-wacht"]["kleur"] == "grijs", w["calendly-wacht"]["kleur"])
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
fa_items = {x["wie"]: x for x in fa["items"]}
check("W11 privégesprek leesbaar met label privé", fa["aantal"] == 3 and fa_items["Geheim Persoon"]["label"] == "privé"
      and "Geheim onderwerp" in fa_items["Geheim Persoon"]["wat"], fa["items"])
check("W16 whatsapp prive=1: naam blijft, label privé door de vaste regel", wa["items"][0]["wie"] == "Sara"
      and wa["items"][0]["label"] == "privé" and wa["items"][0]["reden"].startswith("vaste regel"), wa["items"][0])
zo = {x["wie"]: x for x in w["zoom-wacht"]["items"]}
check("W11 zoom zonder privé: geen label", zo["Angela, Mehdi"]["label"] == "" and zo["Tom"]["label"] == "")
zc = {x["wie"]: x for x in w["zoom-chat"]["items"]}
check("W15 zoom in twee rijen, elk item in een rij", set(zo) == {"Angela, Mehdi", "Tom", "zoom-tekst"} and set(zc) == {"Sales_Won", "Collega"}
      and w["zoom-wacht"]["label"] == "De Zoomwacht: gesprekken" and w["zoom-chat"]["label"] == "De Zoomwacht: chat"
      and w["zoom-chat"]["agent"] == "zoom-wacht", (list(zo), list(zc)))
check("W15 chatitem leest als aantallen", zc["Sales_Won"]["wat"] == "4 berichten, 1 van jou, tussen 09:59 en 15:54 · kanaal"
      and zc["Collega"]["wat"] == "2 berichten, 2 van jou, om 11:45 · 1:1" and zc["Sales_Won"]["soort"] == "chat", zc)
check("W15 chatrij zonder eigen werkverslag, telregel", w["zoom-chat"]["rondes"] == 0 and w["zoom-chat"]["log"] == []
      and w["zoom-chat"]["samen"] == "6 berichten in 2 gesprekken, 1 kanalen", w["zoom-chat"]["samen"])
check("W16 bij twijfel privé is twijfel met reden", zc["Sales_Won"]["label"] == "twijfel"
      and "bij twijfel privé" in zc["Sales_Won"]["reden"] and zc["Sales_Won"]["reden"].endswith("Wat moet het zijn?"), zc["Sales_Won"])
check("W16 hoog en werk: geen label", zc["Collega"]["label"] == "" and zc["Collega"]["reden"] == "")
pl = {x["wie"]: x for x in w["plaud-wacht"]["items"]}
check("W16 zekerheid laag en onbekend zonder privé: twijfel", pl["Speaker 1, Speaker 2"]["label"] == "twijfel"
      and "geen sprekers herkend" in pl["Speaker 1, Speader 2".replace("d", "k")]["reden"], pl)
check("W16 bewust privé (afdeling prive, geen twijfel) blijft privé", fa_items["Geheim Persoon"]["label"] == "privé")
tel = w["belwacht"]["items"]
check("W16 zonder privévlag telt twijfel ook (middel, 'bij twijfel')", pl["Mehdi, Klant B"]["label"] == "twijfel"
      and "twee firma's" in pl["Mehdi, Klant B"]["reden"], pl["Mehdi, Klant B"])
check("W20 dezelfde opname telt één keer: transcript-item van fathom:11 en zoom-tekst van ABC== vallen weg",
      fa["aantal"] == 3 and set(zo) == {"Angela, Mehdi", "Tom", "zoom-tekst"} and zo["zoom-tekst"]["soort"] == "klaarzet"
      and w["zoom-wacht"]["aantal"] == 3 and w["zoom-wacht"]["samen"].startswith("2 gesprekken"), (fa["aantal"], list(zo), w["zoom-wacht"]["samen"]))
check("W20 klaarzet-inhoud (json) leesbaar in laag 2, ruw achter technisch", zo["zoom-tekst"]["kern"] == [{"kop": "Inhoud", "regels": [
      {"tekst": "stand: opname zonder tekst", "link": ""}, {"tekst": "minuten: 5", "link": ""}]}]
      and dict(zo["zoom-tekst"]["oordeel"])["titel"].startswith("2026-10-31 16:00") and "stand" in dict(zo["zoom-tekst"]["technisch"])["inhoud"], zo["zoom-tekst"])
check("W21 chatrij zonder hartslag, de echte agent wel", w["zoom-chat"]["status"] is None and w["zoom-wacht"]["status"]["status"] == "ok",
      (w["zoom-chat"]["status"], w["zoom-wacht"]["status"]))
check("W16 telefoon: vaste regel gaat voor", all(x["label"] == "privé" and x["reden"].startswith("vaste regel") for x in tel) and len(tel) == 2, tel)
check("W19 telregels", w["belwacht"]["samen"] == "2 oproepen, 1 gemist, 3 min"
      and wa["samen"] == "20 berichten (18 in, 2 uit), 2 gesprekken, 1 groepen", (w["belwacht"]["samen"], wa["samen"]))
fk = fa_items["Mehdi, Collega"]
check("W17 fathom kern uit de samenvatting", [k["kop"] for k in fk["kern"]] == ["Doel van de Vergadering", "Belangrijkste Conclusies", "Volgende Stappen"]
      and fk["kern"][1]["regels"] == [{"tekst": "Keuze: eerst de kleinste proef.", "link": "https://fathom.video/share/x?timestamp=10.0"}]
      and fk["kern_ontbreekt"] == "", fk["kern"])
check("W17 fathom taken voor jou en anderen", fk["taken"] == [
      {"wat": "Lijst doorsturen", "wie": "Collega (IT)", "mij": False, "klaar": False, "link": "https://fathom.video/calls/1?timestamp=20"},
      {"wat": "Proef goedkeuren", "wie": "Mehdi Chegini", "mij": True, "klaar": False, "link": "https://fathom.video/calls/1?timestamp=30"}], fk["taken"])
check("W17 fathom zonder samenvatting zegt dat", fa_items["Geheim Persoon"]["kern"] == [] and "geen samenvatting" in fa_items["Geheim Persoon"]["kern_ontbreekt"])
check("W17 zoom met tekst wacht op De Gespreksanalist", "T-0122" in zo["Angela, Mehdi"]["kern_ontbreekt"] and zo["Tom"]["kern_ontbreekt"] == "")
check("W19 fathom telregel", fa["samen"] == "3 gesprekken, 24 min, 1 taken voor jou", fa["samen"])
vj = d["voor_jou"]
check("W18 voor jou: taken uit gesprekken", [t["wat"] for t in vj["taken_mij"]] == ["Proef goedkeuren"] and vj["taken_mij"][0]["gesprek"] == "Mehdi, Collega"
      and vj["taken_mij"][0]["wacht"] == "fathom-wacht" and [t["wat"] for t in vj["taken_anderen"]] == ["Lijst doorsturen"], vj)
check("W18 voor jou: signalen per agent, alleen open en van die dag", [(x["van"], x["aantal"]) for x in vj["signalen"]] ==
      [("agenda-wacht", 1), ("dagbundelaar", 1), ("icloud-wacht", 4), ("mail-regisseur", 1), ("wispr-wacht", 1)]
      and vj["signalen"][0]["titels"][0]["titel"] == "3 afspraken zonder code", vj["signalen"])
check("W13 item weet of er tekst is", zo["Angela, Mehdi"]["tekst"] == "zoom:meeting:ABC==" and zo["Tom"]["tekst"] == ""
      and fa_items["Geheim Persoon"]["tekst"] == "fathom:9" and w["plaud-wacht"]["items"][0]["tekst"] == "plaud:of_1", w["zoom-wacht"]["items"])
fl_item = fa_items["Leeg"]
check("W13 fathom zonder transcript: geen tekst", fl_item["tekst"] == "" and "geen tekst bewaard" in
      C.get("/api/wachten/tekst?uniek=fathom:10", headers=K).get_json().get("fout", ""), fl_item)
li = w["dagbundelaar"]["items"][0]
check("W12 lange inhoud letterlijk en heel, als kern", li["kern"] == [{"kop": "", "tekst": lang}] and "\n" in li["kern"][0]["tekst"]
      and dict(li["technisch"]).get("inhoud") is None and dict(li["oordeel"]).get("soort") == "dagplan", (len(li["kern"]), li["oordeel"]))
check("W12 telling leesbaar in laag 2 (alleen die dag) en ruw als technisch", wi["items"][0]["kern"][0]["kop"] == "Inhoud"
      and any(r["tekst"].startswith("dictaten: 12") for r in wi["items"][0]["kern"][0]["regels"])
      and not any("per_dag" in r["tekst"] for r in wi["items"][0]["kern"][0]["regels"])
      and "per_dag" in dict(wi["items"][0]["technisch"])["inhoud"], wi["items"][0]["kern"])
check("W13 zonder token", C.get("/api/wachten/tekst?uniek=zoom:meeting:ABC==").status_code == 403)
t = C.get("/api/wachten/tekst?uniek=zoom:meeting:ABC%3D%3D", headers=K).get_json()
check("W13 zoomtekst", t.get("wie") == "Angela, Mehdi" and t.get("regels") == [{"tijd": "00:00:05", "wie": "Angela", "tekst": "Hallo Mehdi."},
      {"tijd": "00:00:09", "wie": "Mehdi", "tekst": "Dag Angela."}], t)
t = C.get("/api/wachten/tekst?uniek=fathom:9", headers=K).get_json()
check("W13 fathomtekst (md) met label en reden", t.get("md", "").startswith("# Geheim") and t.get("label") == "privé" and "reden" in t, t)
t = C.get("/api/wachten/tekst?uniek=plaud:of_2", headers=K).get_json()
check("W13 tekstpagina draagt twijfel zoals de dagpagina", t.get("label") == "twijfel" and t.get("reden", "").endswith("Wat moet het zijn?"), t)
t = C.get("/api/wachten/tekst?uniek=plaud:of_1", headers=K).get_json()
check("W13 plaudtekst", t.get("regels") == [{"tijd": "00:01:01", "wie": "Speaker 1", "tekst": "Eerste zin."}], t)
t = C.get("/api/wachten/tekst?uniek=zoom:meeting:ZONDER%3D%3D", headers=K).get_json()
check("W13 zonder tekst zegt dat", "geen tekst bewaard" in t.get("fout", "") and t.get("wie") == "Tom", t)
check("W13 onbekend gesprek", C.get("/api/wachten/tekst?uniek=niks", headers=K).get_json().get("fout") == "onbekend gesprek"
      and C.get("/api/wachten/tekst", headers=K).status_code == 400)
fo_ = dict(fa_items["Geheim Persoon"]["oordeel"])
ft_ = dict(fa_items["Geheim Persoon"]["technisch"])
check("W12 oordeel en technisch van een gesprek", fo_.get("afdeling") == "prive" and "firma" not in fo_ and ft_.get("minuten") == "10"
      and ft_.get("nummer") == "fathom:9" and "nummer" not in fo_, (fo_, ft_))
mo_ = dict(m["items"][0]["oordeel"])
mt_ = dict(m["items"][0]["technisch"])
check("W12 oordeel en technisch van een mail", mo_.get("soort") == "klant" and mt_.get("adres") == "a@b.be" and "adres" not in mo_
      and m["items"][0]["soort"] == "mail", (mo_, mt_))
check("W10 leesfout en logfout apart in het antwoord", wa.get("logfout") == "" and wa.get("leesfout") == "")

print("klaar" if not fout else f"{fout} fout(en)")
sys.exit(1 if fout else 0)
