"""Grendel op het Dagboek (dagboek.globaal.be). Leest proef/2026/2026-10-22.md en .json: een dagbestand en telling zoals
De Dagbundelaar ze schrijft (gemaakt met mijnagents-runner/koppelingen/dagvaststelling.py, verzonnen namen).

- D01: zonder de groep 403, met de groep 200; Authentik scheidt groepen met "|";
- D02: de dagpagina toont de afspraken met hun uitkomst in gewone woorden, zonder "Mehdi:" vooraan;
- D03: een privéafspraak toont geen titel; een privéoproep geen naam;
- D04: niet gepland toont met wie, via welk kanaal en hoe lang;
- D05: het overzicht toont de tegels van een vastgestelde dag, en "Nog niet vastgesteld" voor een dag zonder bestand;
- D06: een onbekend getal wordt een vraagteken; een kapotte telling laat de pagina niet vallen;
- D07: geen gedachtestreepje.
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
MAP = tempfile.mkdtemp()
os.environ["DAGBOEK_MAP"] = MAP
os.environ["DAGBOEK_GROUPS"] = "dagboek"
sys.path.insert(0, HIER)
import app as A  # noqa: E402

C = A.app.test_client()
MET = {"X-authentik-groups": "medewerkers|dagboek"}
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


PROEF = os.path.join(HIER, "proef", "2026")
os.makedirs(os.path.join(MAP, "2026"))
for ext in ("md", "json"):
    shutil.copy(os.path.join(PROEF, f"2026-10-22.{ext}"), os.path.join(MAP, "2026", f"2026-10-22.{ext}"))
gisteren = (A.vandaag() - timedelta(days=1)).isoformat()
os.makedirs(os.path.join(MAP, gisteren[:4]), exist_ok=True)
for ext in ("md", "json"):
    shutil.copy(os.path.join(PROEF, f"2026-10-22.{ext}"), os.path.join(MAP, gisteren[:4], f"{gisteren}.{ext}"))

check("D01 zonder groep 403", C.get("/", headers={"X-authentik-groups": "medewerkers"}).status_code == 403)
r = C.get("/dag/2026-10-22", headers=MET)
html = r.get_data(as_text=True)
check("D01 met groep 200", r.status_code == 200, r.status_code)
check("D02 afspraak met uitkomst", "[UB-KB] PL 9001" in html and "waarschijnlijk" in html and "geen spoor" in html, html[:400])
check("D02 zonder Mehdi: vooraan", "Mehdi: [UB-KB]" not in html)
check("D03 privéafspraak zonder titel", "Proefafspraak Zeta" not in html)
check("D03 privéoproep zonder naam", "Geheim" not in html)
check("D04 niet gepland: wie, kanaal, minuten", "Sara Proef" in html and "Zoom, 16 min" in html and "project HARC 9004" in html)
r = C.get("/", headers=MET)
html = r.get_data(as_text=True)
check("D05 overzicht laadt", r.status_code == 200, r.status_code)
check("D05 tegels van gisteren", "Gesprekken" in html and "41 min" in html, html[:300])
check("D05 dag zonder bestand", "Nog niet vastgesteld" in html)
t = json.load(open(os.path.join(MAP, "2026", "2026-10-22.json")))
t["gesprekken"] = {"aantal": None, "minuten": None}
t["mail"] = None
json.dump(t, open(os.path.join(MAP, gisteren[:4], f"{gisteren}.json"), "w"))
html = C.get("/", headers=MET).get_data(as_text=True)
check("D06 onbekend is een vraagteken", '<div class="groot">?</div>' in html and "niet gelezen" in html)
open(os.path.join(MAP, gisteren[:4], f"{gisteren}.json"), "w").write("{kapot")
check("D06 kapotte telling valt niet", C.get("/", headers=MET).status_code == 200)
alles = html + C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D07 geen gedachtestreepje", "—" not in alles and "–" not in alles)
# Locatie: zonder dashboard (zoals hierboven) een vraagteken, met dashboard de echte dagindeling.
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D10 locatie onbereikbaar: zin", "Locatie-dashboard is nu niet bereikbaar" in html)
check("D10 locatie onbereikbaar: tegel ?", "locatie niet bereikbaar" in html)
LOC = json.load(open(os.path.join(PROEF, "locatie-2026-10-22.json")))


def nep_locatie(pad):
    if pad.startswith("/api/dagboek/2026-10-22"):
        return LOC
    if pad.startswith("/api/dagcijfers"):
        return {"dagen": {gisteren: {"punten": 80, "km": 72.3, "verblijven": 3, "onderweg_min": 86}}}
    return None


A.haal_locatie = nep_locatie
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D08 plek met project", "project HARC 9004, Proefstraat 1" in html, html[-2500:])
check("D08 thuis en rit met km", "<b>Thuis</b>" in html and "rit auto, 36,2 km" in html)
check("D08 tracker in de auto", "waar de auto stond" in html)
check("D08 tegel Onderweg op de dag", "72,3 km" in html and "3 plekken" in html)
for ext in ("md", "json"):
    shutil.copy(os.path.join(PROEF, f"2026-10-22.{ext}"), os.path.join(MAP, gisteren[:4], f"{gisteren}.{ext}"))
html = C.get("/", headers=MET).get_data(as_text=True)
check("D09 overzicht tegel Onderweg", "Onderweg" in html and "72,3 km" in html and "1u26 rijden" in html)
check("D07 geen gedachtestreepje (locatie)", "—" not in html and "–" not in html)
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D11 blok gesprekken in Zoom, Fathom en Plaud", "Gesprekken in Zoom, Fathom en Plaud" in html
      and "<b>Ruben (H-AI &amp; ICT)</b> <span class=\"zacht\">Zoom, 25 min</span>" in html, html[:200])
check("D11 tegel noemt de bron", "2 Zoom; 41 min" in html)
r = C.get("/bronnen?dag=2026-10-22", headers=MET)
html = r.get_data(as_text=True)
check("D12 bronnen: alle vijftien met de stand van de dag", r.status_code == 200 and html.count("<tr><td><b>") == 15
      and "2 gesprekken, 0 chats" in html and "2 oproepen" in html and " km, " in html, html[-1500:])
check("D12 bronnen zonder groep 403", C.get("/bronnen", headers={"X-authentik-groups": "x"}).status_code == 403)
check("D12 overzicht wijst naar bronnen", "alle bronnen" in C.get("/", headers=MET).get_data(as_text=True))
check("D07 geen gedachtestreepje (bronnen)", "—" not in html and "–" not in html)
md = open(os.path.join(PROEF, "2026-10-22.md"), encoding="utf-8").read().replace("\n## Over deze vaststelling",
    "\n## Eigen werk en gezondheid\n\n- Wispr Flow: 19 dictaten, 2599 woorden, 15 min ingesproken\n"
    "- websites: 4 bezoeken op 3 sites; meest: monday.com (2)\n"
    "- YouTube: 3 video's, 22 min; meest: Proefvideo (2)\n- gezondheid (Apple Watch):\n  - Stappen: 8234\n"
    "\n## Over deze vaststelling")
open(os.path.join(MAP, "2026", "2026-10-22.md"), "w", encoding="utf-8").write(md)
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D13 blok eigen werk en gezondheid", "Eigen werk en gezondheid" in html and "19 dictaten" in html
      and "monday.com (2)" in html and "- Stappen: 8234" in html, html[-2000:])
html = C.get("/bronnen?dag=2026-10-22", headers=MET).get_data(as_text=True)
check("D13 bronnen Wispr, websites, YouTube, gezondheid", "4 bezoeken op 3 sites" in html
      and "3 video&#39;s, 22 min" in html and "Telefoon Xelion" in html and "gegevens van de Apple Watch" in html, html[-2500:])
check("D07 geen gedachtestreepje (eigen)", "\u2014" not in html and "\u2013" not in html)
check("healthz", C.get("/healthz").get_json().get("ok") is True)

# D14 (T-0099, T-0138): elke wacht en agent van De Dagbundelaar als rij op de dagpagina, uit het bord over het interne
# netwerk. Tik op de rij: alles van die dag; tik op een item: alles wat de wacht erover weet. Privé is een label.
# De testklok staat vast op 31-10-2026 (Codex 01-11).
A.vandaag = lambda: date(2026, 10, 31)
A._cache.clear()
A.haal_wachten = lambda dag: None
A.haal_locatie = lambda pad: None
html = C.get("/dag/2026-10-31", headers=MET).get_data(as_text=True)
check("D14 bord onbereikbaar: zin, dagbestand blijft", "Het bord antwoordt niet" in html
      and "Dagbestand van De Dagbundelaar" in html and "Nog niet vastgesteld" in html and "Voor jou" not in html, html[-1500:])
WACHTEN = {"dag": "2026-10-31", "items": 2, "telling": {}, "voor_jou": {
    "taken_mij": [{"wat": "Proef goedkeuren", "wie": "Mehdi", "mij": True, "klaar": False, "link": "https://voorbeeld.test/moment/30",
                   "gesprek": "Mehdi, Collega Proef", "tijd": "11:52", "wacht": "fathom-wacht"}],
    "taken_anderen": [{"wat": "Lijst doorsturen", "wie": "Collega Proef", "mij": False, "klaar": False, "link": "",
                       "gesprek": "Mehdi, Collega Proef", "tijd": "11:52", "wacht": "fathom-wacht"}],
    "signalen": [{"van": "sms-wacht", "aantal": 2, "titels": [{"tijd": "07:10", "soort": "signaal", "titel": "3 afspraken zonder code"},
                                                                 {"tijd": "07:10", "soort": "signaal", "titel": "Link nakijken"}]},
                 {"van": "archivaris", "aantal": 1, "titels": [{"tijd": "02:00", "soort": "signaal", "titel": "Archivaris: 1 gesprek waar ik twijfel"}]}]},
    "vakken": [
    {"vak": "De Dagbundelaar en Ai Angel", "wachten": [
        {"naam": "dagbundelaar", "label": "De Dagbundelaar", "kleur": "oranje", "oordeel": "draaide, niets binnen", "aantal": 0,
         "rondes": 1, "gedekt": None, "leesfout": "", "logfout": "", "noden": [], "fouten": [], "status": None, "items": [],
         "log": [{"tijd": "00:30", "stap": "klaar", "tekst": "dag vastgesteld", "fout": False}]}]},
    {"vak": "Communicatie", "wachten": [
        {"naam": "zoom-chat", "label": "De Zoomwacht: chat", "agent": "zoom-wacht", "kleur": "groen", "oordeel": "binnen", "aantal": 1,
         "rondes": 0, "gedekt": None, "leesfout": "", "logfout": "", "noden": [], "fouten": [], "status": None, "log": [],
         "samen": "4 berichten in 1 gesprekken, 1 kanalen",
         "items": [{"tijd": "09:59", "wie": "Kanaal Proef", "wat": "4 berichten, 1 van jou, tussen 09:59 en 15:54 · kanaal", "fout": False,
                    "label": "twijfel", "reden": "de wacht zette het op privé omdat ze twijfelde: bij twijfel privé. Wat moet het zijn?",
                    "soort": "chat", "kern": [], "kern_ontbreekt": "", "taken": [], "oordeel": [["afdeling", "onbekend"]], "technisch": []}]},
        {"naam": "fathom-wacht", "label": "De Fathomwacht", "kleur": "groen", "oordeel": "binnen", "aantal": 1, "rondes": 1,
         "gedekt": None, "leesfout": "", "logfout": "", "noden": [], "fouten": [], "status": None, "log": [], "samen": "1 gesprekken, 9 min, 1 taken voor jou",
         "items": [{"tijd": "11:52", "wie": "Mehdi, Collega Proef", "wat": "9 min, Automatisering", "fout": False, "label": "", "reden": "",
                    "soort": "gesprek", "kern": [{"kop": "Doel van de Vergadering", "regels": [{"tekst": "Afstemmen over de aanpak.", "link": "https://voorbeeld.test/moment/0"}]},
                                                 {"kop": "Volgende Stappen", "regels": [{"tekst": "Collega stuurt de lijst door.", "link": ""}]}],
                    "kern_ontbreekt": "", "taken": [{"wat": "Proef goedkeuren", "wie": "Mehdi", "mij": True, "klaar": False, "link": "https://voorbeeld.test/moment/30"},
                                                    {"wat": "Lijst doorsturen", "wie": "Collega Proef", "mij": False, "klaar": False, "link": ""}],
                    "oordeel": [["afdeling", "elevait"], ["zekerheid", "hoog"]], "technisch": [["minuten", "9"], ["nummer", "fathom:11"]], "tekst": "fathom:11"}]},
        {"naam": "whatsapp-wacht", "label": "De WhatsApp-wacht", "kleur": "groen", "oordeel": "binnen", "aantal": 2,
         "rondes": 3, "gedekt": True, "leesfout": "", "logfout": "", "noden": [], "fouten": [], "status": {"laatste": "21:37"},
         "items": [{"tijd": "09:15", "wie": "Sara Proef", "wat": "3 berichten", "fout": False, "label": "",
                    "oordeel": [["thema", "Proefthema"], ["link", "https://voorbeeld.test/opname/1"]], "technisch": [["nummer", "whatsapp:1"]]},
                   {"tijd": "10:02", "wie": "Tom Proef", "wat": "1 oproep", "fout": False, "label": "priv\u00e9",
                    "reden": "vaste regel: proef", "tekst": "zoom:meeting:ABC=="},
                   {"tijd": "12:00", "wie": "Leeg Proef", "wat": "niks", "fout": False, "label": ""}],
         "log": [{"tijd": "21:37", "stap": "bron", "tekst": "2 gesprekken", "fout": False}]},
        {"naam": "sms-wacht", "label": "De Sms-wacht", "kleur": "rood", "oordeel": "fout", "aantal": 0, "rondes": 1,
         "gedekt": None, "leesfout": "", "logfout": "", "noden": ["Full Disk Access ontbreekt"], "status": None,
         "fouten": [{"tijd": "11:00", "stap": "fout", "tekst": "kopie niet leesbaar", "fout": True}], "items": [],
         "log": [{"tijd": "11:00", "stap": "fout", "tekst": "kopie niet leesbaar", "fout": True}]},
        {"naam": "locatie-wacht", "label": "De Locatiewacht", "kleur": "grijs", "oordeel": "niets binnen, geen ronde",
         "aantal": 0, "rondes": 0, "gedekt": None, "leesfout": "", "logfout": "", "noden": [], "status": None, "fouten": [],
         "items": [], "log": []}]}]}
A.haal_wachten = lambda dag: json.loads(json.dumps(WACHTEN))
r = C.get("/dag/2026-10-31", headers=MET)
html = r.get_data(as_text=True)
check("D14 dagpagina laadt", r.status_code == 200, r.status_code)
check("D14 rij per wacht", html.count('<details class="wacht') == 6 and 'id="whatsapp-wacht"' in html
      and 'id="sms-wacht"' in html and 'id="dagbundelaar"' in html, html[-3000:])
check("D14 rij toont het eerste item", "09:15 Sara Proef 3 berichten" in html)
check("D14 rij toont de fout", "fout: kopie niet leesbaar" in html)
check("D14 telling", "1</span> fout" in html and "4</span> items binnen" in html, html[:3000])
with A.app.test_request_context():
    KZ = A.dagkeuze(A.vandaag())
check("D14 dagknoppen: vier, de laatste is vandaag", html.count('class="dagkeuze"') == 1
      and [k["dag"] for k in KZ] == [(A.vandaag() - timedelta(days=3 - i)).isoformat() for i in range(4)]
      and KZ[-1]["naam"].startswith("vandaag, ") and KZ[-1]["actief"] and not KZ[0]["actief"]
      and all(k["pad"] == "/dag/" + k["dag"] for k in KZ), KZ)
check("D14 rij toont open meldingen naast het item", "1 open nu</span>" in html)
check("D14 items met detail", "Sara Proef" in html and "Tom Proef" in html and "<dt>thema</dt><dd>Proefthema</dd>" in html
      and 'href="https://voorbeeld.test/opname/1"' in html, html[-6000:])
check("D14 priv\u00e9 is een label, naam blijft, met de reden", '<b>Tom Proef</b> <span class="etiket prive">priv\u00e9</span>' in html
      and '<p class="reden prive">priv\u00e9: vaste regel: proef</p>' in html, html[-9000:])
check("D16 twijfel is een oranje label met de reden en de vraag", '<span class="etiket twijfel">twijfel</span>' in html
      and 'bij twijfel priv\u00e9. Wat moet het zijn?</p>' in html and '<span class="etiket twijfel tel">1 twijfel</span>' in html, html[-12000:])
check("D16 zoom in twee rijen, chat als aantallen", 'id="zoom-chat"' in html and "De Zoomwacht: chat" in html
      and "4 berichten, 1 van jou, tussen 09:59 en 15:54 · kanaal" in html and "4 berichten in 1 gesprekken, 1 kanalen" in html
      and "zelfde agent als zoom-wacht" in html, html[-12000:])
check("D16 uitleg per wacht", '<span class="uitleg">telt WhatsApp per gesprek per dag' in html
      and "kopieert elke Zoom-opname" not in html and '<span class="uitleg">een wacht van De Dagbundelaar</span>' not in html, html[-12000:])
check("D16 kern en taken van een Fathom-gesprek", "<h5>Doel van de Vergadering</h5>" in html and "Afstemmen over de aanpak." in html
      and 'href="https://voorbeeld.test/moment/0"' in html and '<li class="mij"><b>voor jou:</b> Proef goedkeuren' in html
      and "<b>voor Collega Proef:</b> Lijst doorsturen" in html, html[-14000:])
check("D16 oordeel open, technisch achter een knop", "<h5>Oordeel van de wacht</h5>" in html and "<dt>afdeling</dt><dd>elevait</dd>" in html
      and '<details class="technisch"><summary>technisch</summary>' in html and "<dt>nummer</dt><dd>fathom:11</dd>" in html, html[-14000:])
check("D16 voor jou bovenaan", html.index("<h2>Voor jou</h2>") < html.index('class="wacht')
      and "Taken voor jou uit de gesprekken van deze dag (1)" in html and "<b>Proef goedkeuren</b>" in html
      and "uit het gesprek met Mehdi, Collega Proef om 11:52 (De Fathomwacht)" in html and "Taken voor anderen (1)" in html
      and "<b>De Sms-wacht</b> <span class=\"zacht\">2</span>" in html and "<b>archivaris</b>" in html
      and "3 afspraken zonder code" in html and "voor jou klaarzetten (3)" in html, html[:6000])
check("D16 werkverslag achter technisch", 'summary>technisch: 1 regel in het werkverslag' in html and "Werkverslag van deze dag (3)" in html)
check("D16 samen in de rij", '<span class="kort ">1 gesprekken, 9 min, 1 taken voor jou</span>' in html, html[-14000:])
check("D14 item zonder detail zegt het", "Meer weet de wacht hier niet over." in html)
check("D14 item met tekst wijst naar de tekstpagina", 'href="/dag/2026-10-31/tekst?gesprek=zoom:meeting:ABC%3D%3D"' in html
      and html.count("de volledige tekst lezen") == 2, html[-6000:])
# D15: de tekstpagina leest de tekst via het bord.
A.haal_tekst = lambda uniek: {"uniek": uniek, "wie": "Tom Proef", "wat": "Kort gesprek", "bron": "zoom", "datum": "2026-10-31",
                              "tijd": "10:02", "label": "priv\u00e9", "reden": "de wacht zette het bewust op priv\u00e9",
                              "regels": [{"tijd": "00:00:05", "wie": "Tom", "tekst": "Hallo."}]}
r = C.get("/dag/2026-10-31/tekst?gesprek=zoom:meeting:ABC==", headers=MET)
ht = r.get_data(as_text=True)
check("D15 tekstpagina met regels", r.status_code == 200 and "<b>Tom:</b> Hallo." in ht and "00:00:05" in ht
      and '<span class="etiket prive">priv\u00e9</span>' in ht and "priv\u00e9: de wacht zette het bewust op priv\u00e9" in ht
      and 'href="/dag/2026-10-31">terug naar za 31 okt 2026' in ht, ht[-2500:])
check("D07 geen gedachtestreepje (tekst)", "\u2014" not in ht and "\u2013" not in ht)
A.haal_tekst = lambda uniek: {"uniek": uniek, "wie": "Tom Proef", "md": "# Kop\n\nMehdi: tekst."}
check("D15 tekst als md", '<pre class="tekst"># Kop' in C.get("/dag/2026-10-31/tekst?gesprek=f:1", headers=MET).get_data(as_text=True))
A.haal_tekst = lambda uniek: {"uniek": uniek, "wie": "Tom", "fout": "geen tekst bewaard: proef"}
check("D15 zonder tekst zegt dat", "geen tekst bewaard: proef" in C.get("/dag/2026-10-31/tekst?gesprek=f:1", headers=MET).get_data(as_text=True))
A.haal_tekst = lambda uniek: None
check("D15 bord onbereikbaar", "Het bord antwoordt niet" in C.get("/dag/2026-10-31/tekst?gesprek=f:1", headers=MET).get_data(as_text=True))
check("D15 zonder gesprek 404, zonder groep 403", C.get("/dag/2026-10-31/tekst", headers=MET).status_code == 404
      and C.get("/dag/2026-10-31/tekst?gesprek=f:1", headers={"X-authentik-groups": "x"}).status_code == 403)
check("D14 werkverslag", "2 gesprekken" in html and "21:37" in html)
check("D14 dagbestand onder De Dagbundelaar", html.index('id="dagbundelaar"') < html.index("Dagbestand van De Dagbundelaar")
      < html.index('id="whatsapp-wacht"'))
check("D14 fout en open melding", "kopie niet leesbaar" in html and "Full Disk Access ontbreekt" in html)
check("D14 lege wacht zegt het", "Niets binnengekomen op deze dag." in html)
check("D14 ?open klapt de rij open", ' id="sms-wacht" open>' in C.get("/dag/2026-10-31?open=sms-wacht", headers=MET).get_data(as_text=True)
      and ' id="sms-wacht" open>' not in html)
r = C.get("/wachten?dag=2026-10-31", headers=MET)
check("D14 oude pagina wachten stuurt door", r.status_code == 302 and r.headers["Location"].endswith("/dag/2026-10-31"), r.headers.get("Location"))
r = C.get("/wachten/sms-wacht?dag=2026-10-31", headers=MET)
check("D14 oude pagina wacht stuurt door naar de rij", r.status_code == 302
      and r.headers["Location"].endswith("/dag/2026-10-31?open=sms-wacht#sms-wacht"), r.headers.get("Location"))
check("D14 doorsturen zonder groep 403", C.get("/wachten", headers={"X-authentik-groups": "medewerkers"}).status_code == 403)
ROOD = json.loads(json.dumps(WACHTEN))
ROOD["dag"] = A.vandaag().isoformat()
ROOD["vakken"][1]["wachten"][4].update(kleur="rood", oordeel="fout", status={"status": "fout", "detail": "Geen browsergeschiedenis", "laatste": "09:00"})
ROOD["vakken"][1]["wachten"][3]["fouten"] = [{"tijd": "10:00", "stap": "fout", "tekst": "a", "fout": True},
                                            {"tijd": "11:00", "stap": "fout", "tekst": "b", "fout": True},
                                            {"tijd": "12:00", "stap": "fout", "tekst": "a", "fout": True}]
A.haal_wachten = lambda dag: json.loads(json.dumps(ROOD))
html = C.get("/dag/" + A.vandaag().isoformat(), headers=MET).get_data(as_text=True)
check("D14 rood zonder logfout: stand van nu als reden", html.count("stand van nu: fout: Geen browsergeschiedenis") == 2, html[-2500:])
check("D14 gelijke fouten gegroepeerd, ook niet opeenvolgend", "12:00 a <span class=\"zacht\">(2 keer)</span>" in html
      and "11:00 b" in html and html.count("10:00 a") == 0, html[-2500:])
html = C.get("/dag/2026-10-30", headers=MET).get_data(as_text=True)
check("D14 hartslag telt niet voor een vorige dag, kleur van het bord blijft", "stand van nu" not in html
      and 'class="wacht kleur-rood" id="locatie-wacht"' in html and "vr 30 okt 2026: fout" in html, html[:2500])
LEES = json.loads(json.dumps(WACHTEN))
LEES["vakken"][1]["wachten"][4].update(leesfout="niet gelezen (OperationalError)", kleur="rood", oordeel="fout")
A.haal_wachten = lambda dag: json.loads(json.dumps(LEES))
html = C.get("/dag/2026-10-31", headers=MET).get_data(as_text=True)
check("D14 leesfout is onbekend, niet leeg", "onbekend items binnen" in html and html.count("Niets binnengekomen") == 2
      and "Onbekend: het bord kon deze wacht niet lezen (niet gelezen (OperationalError))" in html, html[-3000:])
check("D14 rij bij leesfout toont ?", '<span class="aantal">?</span>' in html and "kon niet lezen: niet gelezen (OperationalError)" in html)
check("D14 dagtotaal is minstens als een wacht niet gelezen is", "minstens 4</span> items binnen" in html, html[:3000])
LOG = json.loads(json.dumps(WACHTEN))
LOG["vakken"][1]["wachten"][2].update(logfout="werkverslag niet gelezen (OperationalError)", kleur="rood", log=[], rondes=0)
A.haal_wachten = lambda dag: json.loads(json.dumps(LOG))
html = C.get("/dag/2026-10-31", headers=MET).get_data(as_text=True)
check("D14 werkverslag niet gelezen: items blijven, werkverslag onbekend", "Sara Proef" in html and "2 items binnen" in html
      and "onbekend regels in het werkverslag" in html and "het bord kon het werkverslag niet lezen" in html, html[-3500:])
check("D14 rij bij werkverslagfout toont de fout, niet het item", "kon niet lezen: werkverslag niet gelezen (OperationalError)" in html
      and "09:15 Sara Proef 3 berichten</span>" not in html, html[-3000:])
check("D14 dag in de toekomst is 404", C.get("/dag/" + (A.vandaag() + timedelta(days=1)).isoformat(), headers=MET).status_code == 404)
check("D14 vandaag bereikbaar via volgende dag", 'href="/dag/2026-10-31">volgende dag' in C.get("/dag/2026-10-30", headers=MET).get_data(as_text=True))
check("D14 geen datum 404", C.get("/wachten?dag=gisteren", headers=MET).status_code == 404
      and C.get("/dag/gisteren", headers=MET).status_code == 404 and C.get("/dag/0001-01-01", headers=MET).status_code == 404
      and C.get("/wachten?dag=0001-01-01", headers=MET).status_code == 404)
check("D14 onbekende oude wachtlink 404", C.get("/wachten/geen-wacht?dag=2026-10-31", headers=MET).status_code == 404
      and C.get("/wachten/Geen%20Wacht?dag=2026-10-31", headers=MET).status_code == 404)
A.haal_wachten = lambda dag: None
check("D14 oude wachtlink zonder bord stuurt toch door", C.get("/wachten/sms-wacht?dag=2026-10-31", headers=MET).status_code == 302)
A.haal_wachten = lambda dag: json.loads(json.dumps(WACHTEN))
TEL = {"n": 0}
def tel_locatie(pad):
    TEL["n"] += 1
    return None
A.haal_locatie = tel_locatie
C.get("/dag/2026-10-31", headers=MET)
check("D14 locatie een keer per dagpagina", TEL["n"] == 1, TEL)
A.haal_locatie = lambda pad: None
check("D07 geen gedachtestreepje (wachten)", "\u2014" not in html and "\u2013" not in html)

print("dagboek:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
