"""Grendel op het Dagboek (dagboek.globaal.be). Leest proef/2026/2026-10-22.md en .json: een dagbestand en telling zoals
De Dagbundelaar ze schrijft (gemaakt met mijnagents-runner/koppelingen/dagvaststelling.py, verzonnen namen).

- D01: zonder de groep 403, met de groep 200; Authentik scheidt groepen met "|";
- D02: de dagpagina toont de afspraken met hun uitkomst in gewone woorden, zonder "Mehdi:" vooraan;
- D03: een privéafspraak toont geen titel; een privéoproep geen naam;
- D04: niet gepland toont met wie, via welk kanaal en hoe lang;
- D05: het overzicht toont de tegels van een vastgestelde dag, en "Nog niet vastgesteld" voor een dag zonder bestand;
- D06: een onbekend getal wordt een vraagteken; een kapotte telling laat de pagina niet vallen;
- D07: geen gedachtestreepje;
- D30 (WISPR-3): een fout-hartslag van een vorige dag staat als tekst met zijn dag, niet als fout van vandaag;
- D31 (LOC-1): de Locatiewacht toont haar plekken en ritten ook op een dag met een bord-item;
- D32 (LOC-2): een plek zonder naam en zonder adres is "onbekende plek", nooit een coördinaat.
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
# WA-6 (T-0120): WhatsApp en telefoon onbekend (getallen None, stand niet aangesloten) tonen een vraagteken, nooit een 0
tg = {x["naam"]: x for x in A.tegels(dict(t, whatsapp={"stand": "stil sinds 27-10 10:07", "gesprekken": None,
                                                        "berichten": None, "oproepen": None, "minuten": None},
                                          telefoon={"stand": "onbekend voor deze dag", "oproepen": None,
                                                    "minuten": None}))}
check("D06 WA-6 WhatsApp onbekend: vraagteken, geen 0", tg["WhatsApp"]["groot"] == "?"
      and tg["WhatsApp"]["klein"] == "berichten, ? oproepen (stil sinds 27-10 10:07)", tg["WhatsApp"])
check("D06 WA-6 telefoon onbekend: vraagteken, geen 0", tg["Telefoon"]["groot"] == "?"
      and tg["Telefoon"]["klein"] == "oproepen, ? (onbekend voor deze dag)", tg["Telefoon"])
tg = {x["naam"]: x for x in A.tegels(dict(t, whatsapp={"stand": "aangesloten", "gesprekken": 0, "berichten": 0,
                                                        "oproepen": 0, "minuten": 0}))}
check("D06 WA-6 aangesloten zonder bericht blijft 0", tg["WhatsApp"]["groot"] == 0
      and tg["WhatsApp"]["klein"] == "berichten, 0 oproepen", tg["WhatsApp"])
# WA-6, Codex-toets 2: ook /bronnen toont een onbekend aantal als vraagteken, nooit als 0
_bs = A.bron_stand({"gesprekken": [], "telling": dict(t, whatsapp={"stand": "stil sinds 27-10 10:07", "gesprekken": 2,
                                                                     "berichten": 5, "oproepen": None, "minuten": None},
                                                       telefoon={"stand": "onbekend voor deze dag", "oproepen": None,
                                                                 "minuten": None},
                                                       sms={"stand": "stil sinds 27-10 10:07", "gesprekken": None,
                                                            "berichten": None},
                                                       xelion={"stand": "onbekend voor deze dag", "oproepen": None,
                                                               "minuten": None, "gemist": None})}, "", None)
check("D12 WA-6 bronnen: onbekend is een vraagteken", _bs["WhatsApp"]["tekst"] == "5 berichten, ? oproepen"
      and _bs["Telefoon"]["tekst"] == "? oproepen" and _bs["Sms en iMessage"]["tekst"] == "? berichten in ? gesprekken"
      and _bs["Telefoon Xelion"]["tekst"] == "? oproepen, ? gemist", json.dumps({k: _bs[k] for k in
                                                                              ("WhatsApp", "Telefoon", "Sms en iMessage",
                                                                               "Telefoon Xelion")}))
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
# D32 (LOC-2): een plek zonder naam en zonder adres toont geen coördinaten maar "onbekende plek"; met het adres uit de
# verrijking van het Locatie-dashboard toont ze dat adres.
naamloos = {"soort": "bezoek", "van": 1792652400, "tot": 1792653600, "minuten": 20, "lat": 50.71234, "lon": 4.61234}
rij = A.verplaatsingen({"indeling": [naamloos]})
check("D32 plek zonder naam: geen coördinaten", rij and rij[0]["wat"] == "onbekende plek" and "50.71" not in str(rij), rij)
check("D32 plek met adres uit de verrijking", A.waar(dict(naamloos, adres="Proeflaan 3, 3999 Proefdorp"))
      == "Proeflaan 3, 3999 Proefdorp")
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
# De rij van Zoom alleen: Fathom draait wel 2 keer per dag, alleen in de dagketen (T-0120 FATHOM-8)
zoomrij = html[html.find("Zoom-account"):].split("</tr>")[0]
check("D12 bronnen: Zoom 3 keer per dag (T-0120 WACHT-7)", "3 keer per dag (08:00, 14:00 en 00:30 Brussel" in zoomrij
      and "2 keer per dag" not in zoomrij, zoomrij[:200])
fathomrij = html[html.find("Fathom-account"):].split("</tr>")[0]
check("D12 bronnen: Fathom 2 keer per dag (T-0120 FATHOM-8)", "2 keer per dag, 08:00 en 14:00" in fathomrij
      and "elk uur" not in fathomrij, fathomrij[:200])
check("D12 bronnen zonder groep 403", C.get("/bronnen", headers={"X-authentik-groups": "x"}).status_code == 403)
check("D12 overzicht wijst naar bronnen", "alle bronnen" in C.get("/", headers=MET).get_data(as_text=True))
check("D07 geen gedachtestreepje (bronnen)", "—" not in html and "–" not in html)
check("D12 bronnen: postvakken zonder wacht als niet bewaakt (VOL-10)", "niet bewaakt: light@ en standaard@" in html
      and "boekhouding@" in html)
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

# D14: de pagina Wachten (Mehdi, 01-11-2026): per wacht wat binnenkwam, uit het bord over het interne netwerk.
# De testklok staat vast op 31-10-2026 (Codex 01-11): de pagina toont alleen de laatste WACHT_DAGEN dagen.
A.vandaag = lambda: date(2026, 10, 31)
check("D14 wachten zonder groep 403", C.get("/wachten", headers={"X-authentik-groups": "medewerkers"}).status_code == 403)
A._cache.clear()
A.haal_wachten = lambda dag: None
html = C.get("/wachten", headers=MET).get_data(as_text=True)
check("D14 bord onbereikbaar: zin, geen lege dag", "Het bord antwoordt niet" in html, html[-1500:])
WACHTEN = {"dag": "2026-10-31", "items": 2, "telling": {}, "vakken": [
    {"vak": "Communicatie", "wachten": [
        {"naam": "whatsapp-wacht", "label": "De WhatsApp-wacht", "kleur": "groen", "oordeel": "binnen", "aantal": 2,
         "rondes": 3, "gedekt": True, "leesfout": "", "logfout": "", "noden": [], "fouten": [], "status": {"laatste": "21:37"},
         "items": [{"tijd": "09:15", "wie": "Sara Proef", "wat": "3 berichten", "fout": False},
                   {"tijd": "10:02", "wie": "Tom Proef", "wat": "1 oproep", "fout": False}],
         "log": [{"tijd": "21:37", "stap": "bron", "tekst": "2 gesprekken", "fout": False}]},
        {"naam": "sms-wacht", "label": "De Sms-wacht", "kleur": "rood", "oordeel": "fout", "aantal": 0, "rondes": 1,
         "gedekt": None, "leesfout": "", "logfout": "", "noden": ["Full Disk Access ontbreekt"], "status": None,
         "fouten": [{"tijd": "11:00", "stap": "fout", "tekst": "kopie niet leesbaar", "fout": True}], "items": [],
         "log": [{"tijd": "11:00", "stap": "fout", "tekst": "kopie niet leesbaar", "fout": True}]},
        {"naam": "locatie-wacht", "label": "De Locatiewacht", "kleur": "grijs", "oordeel": "niets binnen, geen ronde",
         "aantal": 0, "rondes": 0, "gedekt": None, "leesfout": "", "logfout": "", "noden": [], "status": None, "fouten": [],
         "items": [], "log": []}]}]}
A.haal_wachten = lambda dag: json.loads(json.dumps(WACHTEN))
A.haal_locatie = lambda pad: None
r = C.get("/wachten?dag=2026-10-31", headers=MET)
html = r.get_data(as_text=True)
check("D14 wachten laadt", r.status_code == 200, r.status_code)
check("D14 tegel per wacht met link", "De WhatsApp-wacht" in html and 'href="/wachten/whatsapp-wacht?dag=2026-10-31"' in html
      and 'href="/wachten/sms-wacht?dag=2026-10-31"' in html, html[-3000:])
check("D14 tegel toont het eerste item", "09:15 Sara Proef 3 berichten" in html)
check("D14 tegel toont de fout", "fout: kopie niet leesbaar" in html)
check("D14 telling", "1</span> fout" in html and "2</span> items binnen" in html, html[:3000])
with A.app.test_request_context():
    KZ = A.dagkeuze(A.vandaag())
check("D14 dagknoppen: vier, de laatste is vandaag", html.count('class="dagkeuze"') == 1
      and [k["dag"] for k in KZ] == [(A.vandaag() - timedelta(days=3 - i)).isoformat() for i in range(4)]
      and KZ[-1]["naam"].startswith("vandaag, ") and KZ[-1]["actief"] and not KZ[0]["actief"], KZ)
check("D14 tegel toont open meldingen naast het item", "1 open nu</span>" in html)
r = C.get("/wachten/whatsapp-wacht?dag=2026-10-31", headers=MET)
html = r.get_data(as_text=True)
check("D14 wacht laadt", r.status_code == 200, r.status_code)
check("D14 wacht items", "Sara Proef" in html and "09:15" in html and "Tom Proef" in html and "2</span> items binnen" in html,
      html[-3000:])
check("D14 wacht werkverslag", "2 gesprekken" in html and "21:37" in html)
check("D14 wacht dagknoppen blijven bij de wacht", 'href="/wachten/whatsapp-wacht?dag=' in html
      and 'href="/wachten?dag=2026-10-31"' in html)
html = C.get("/wachten/sms-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("D14 wacht fout en open melding", "kopie niet leesbaar" in html and "Full Disk Access ontbreekt" in html)
check("D14 lege wacht zegt het", "Niets binnengekomen op deze dag." in html)
ROOD = json.loads(json.dumps(WACHTEN))
ROOD["dag"] = A.vandaag().isoformat()
ROOD["vakken"][0]["wachten"][2].update(kleur="rood", oordeel="fout", status={"status": "fout", "detail": "Geen browsergeschiedenis", "laatste": "09:00"})
ROOD["vakken"][0]["wachten"][1]["fouten"] = [{"tijd": "10:00", "stap": "fout", "tekst": "a", "fout": True},
                                            {"tijd": "11:00", "stap": "fout", "tekst": "b", "fout": True},
                                            {"tijd": "12:00", "stap": "fout", "tekst": "a", "fout": True}]
A.haal_wachten = lambda dag: json.loads(json.dumps(ROOD))
html = C.get("/wachten/locatie-wacht?dag=" + A.vandaag().isoformat(), headers=MET).get_data(as_text=True)
check("D14 rood zonder logfout: stand van nu als reden", "stand van nu: fout: Geen browsergeschiedenis" in html, html[-2500:])
html = C.get("/wachten?dag=" + A.vandaag().isoformat(), headers=MET).get_data(as_text=True)
check("D14 tegel: stand van nu als reden", "stand van nu: fout: Geen browsergeschiedenis" in html)
html = C.get("/wachten/sms-wacht?dag=" + A.vandaag().isoformat(), headers=MET).get_data(as_text=True)
check("D14 gelijke fouten gegroepeerd, ook niet opeenvolgend", "12:00 a <span class=\"zacht\">(2 keer)</span>" in html
      and "11:00 b" in html and html.count("10:00 a") == 0, html[-2500:])
html = C.get("/wachten/locatie-wacht?dag=2026-10-30", headers=MET).get_data(as_text=True)
check("D14 hartslag telt niet voor een vorige dag, kleur van het bord blijft", "stand van nu" not in html
      and '<span class="stip rood"></span> vr 30 okt 2026: fout' in html, html[:2500])
LEES = json.loads(json.dumps(WACHTEN))
LEES["vakken"][0]["wachten"][2].update(leesfout="niet gelezen (OperationalError)", kleur="rood", oordeel="fout")
A.haal_wachten = lambda dag: json.loads(json.dumps(LEES))
html = C.get("/wachten/locatie-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("D14 leesfout is onbekend, niet leeg", "onbekend</span> items binnen" in html and "Niets binnengekomen" not in html
      and "Onbekend: het bord kon deze wacht niet lezen (niet gelezen (OperationalError))" in html, html[-3000:])
html = C.get("/wachten?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("D14 tegel bij leesfout toont ?", ">?</div>" in html and "kon niet lezen: niet gelezen (OperationalError)" in html)
check("D14 dagtotaal is minstens als een wacht niet gelezen is", "minstens 2</span> items binnen" in html, html[:3000])
LOG = json.loads(json.dumps(WACHTEN))
LOG["vakken"][0]["wachten"][0].update(logfout="werkverslag niet gelezen (OperationalError)", kleur="rood", log=[], rondes=0)
A.haal_wachten = lambda dag: json.loads(json.dumps(LOG))
html = C.get("/wachten/whatsapp-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("D14 werkverslag niet gelezen: items blijven, werkverslag onbekend", "Sara Proef" in html and "2</span> items binnen" in html
      and "onbekend</span> regels in het werkverslag" in html and "Geen ronde op deze dag" not in html
      and "het bord kon het werkverslag niet lezen" in html, html[-3500:])
html = C.get("/wachten?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("D14 tegel bij werkverslagfout toont de fout, niet het item", "kon niet lezen: werkverslag niet gelezen (OperationalError)" in html
      and "09:15 Sara Proef 3 berichten" not in html, html[-3000:])
check("D14 dag buiten de vier dagen is 404", C.get("/wachten?dag=2020-01-01", headers=MET).status_code == 404
      and C.get("/wachten/whatsapp-wacht?dag=2020-01-01", headers=MET).status_code == 404
      and C.get("/wachten?dag=" + (A.vandaag() + timedelta(days=1)).isoformat(), headers=MET).status_code == 404)
# D30 (WISPR-3): een fout-hartslag van een vorige dag maakt vandaag niet meer rood (het bord), maar blijft als tekst
# zichtbaar, met zijn dag erbij.
OUD = json.loads(json.dumps(WACHTEN))
OUD["dag"] = A.vandaag().isoformat()
OUD["vakken"][0]["wachten"][2].update(status={"status": "fout", "detail": "portaal niet gelezen", "laatste": "23:45",
                                              "laatste_ts": "2026-10-30T22:45:00+00:00"})
A.haal_wachten = lambda dag: json.loads(json.dumps(OUD))
html = C.get("/wachten?dag=" + A.vandaag().isoformat(), headers=MET).get_data(as_text=True)
check("D30 oude fout-hartslag: tekst met zijn dag", "stand van nu (sinds 30-10 23:45): fout: portaal niet gelezen" in html,
      html[-2500:])
# D31 (LOC-1): een vorige dag met het bord-item "Locatielogboek" toont ook de plekken en ritten van het Locatie-dashboard.
MET_ITEM = json.loads(json.dumps(WACHTEN))
MET_ITEM["dag"] = "2026-10-30"
MET_ITEM["vakken"][0]["wachten"][2].update(kleur="groen", oordeel="binnen", aantal=1, rondes=1, items=[
    {"tijd": "21:30", "wie": "locatie", "wat": "Locatielogboek 2026-10-30", "fout": False}])
LOC30 = dict(LOC, datum="2026-10-30")
A.haal_wachten = lambda dag: json.loads(json.dumps(MET_ITEM))
A.haal_locatie = lambda pad: json.loads(json.dumps(LOC30)) if pad.startswith("/api/dagboek/2026-10-30") else None
html = C.get("/wachten/locatie-wacht?dag=2026-10-30", headers=MET).get_data(as_text=True)
check("D31 vorige dag: bord-item en ritten samen", "Locatielogboek 2026-10-30" in html and "rit auto, 36,2 km" in html
      and "Thuis" in html and "6</span> items binnen" in html, html[-3000:])
# Codex-toets 1: haal_wachten geeft een minuut lang hetzelfde (bewaarde) antwoord; twee aanvragen gaven dubbele ritten.
VAST = json.loads(json.dumps(MET_ITEM))
A.haal_wachten = lambda dag: VAST
for _ in range(2):
    html = C.get("/wachten/locatie-wacht?dag=2026-10-30", headers=MET).get_data(as_text=True)
check("D31 tweede aanvraag: geen dubbels, bewaard antwoord onveranderd", "6</span> items binnen" in html
      and len(VAST["vakken"][0]["wachten"][2]["items"]) == 1, html[-1500:])
A.haal_locatie = lambda pad: None
A.haal_wachten = lambda dag: json.loads(json.dumps(WACHTEN))
check("D14 onbekende wacht 404", C.get("/wachten/geen-wacht?dag=2026-10-31", headers=MET).status_code == 404)
check("D14 wacht zonder groep 403", C.get("/wachten/sms-wacht", headers={"X-authentik-groups": "medewerkers"}).status_code == 403)
A.haal_wachten = lambda dag: None
html = C.get("/wachten/sms-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("D14 wacht, bord onbereikbaar: zin", "Het bord antwoordt niet" in html)
A.haal_wachten = lambda dag: json.loads(json.dumps(WACHTEN))
check("D14 geen datum 404", C.get("/wachten?dag=gisteren", headers=MET).status_code == 404)
check("D07 geen gedachtestreepje (wachten)", "—" not in html and "–" not in html)
# MAIL-6 (T-0120): een mailwacht die het postvak las en niets kreeg, zegt dat; een andere lege wacht blijft "niets binnengekomen"
GELEZEN = json.loads(json.dumps(WACHTEN))
GELEZEN["vakken"][0]["wachten"].append({"naam": "mail-melo", "label": "De Mailwacht Proef", "kleur": "oranje",
                                        "oordeel": "postvak gelezen, 0 nieuwe mails", "aantal": 0, "rondes": 14, "gedekt": None,
                                        "leesfout": "", "logfout": "", "noden": [], "status": None, "fouten": [], "items": [],
                                        "log": [{"tijd": "21:05", "stap": "ronde", "tekst": "laatste 24 u: hoog 0", "fout": False}]})
A._cache.clear()
A.haal_wachten = lambda dag: json.loads(json.dumps(GELEZEN))
html = C.get("/wachten/mail-melo?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("D15 mailwacht: postvak gelezen, 0 nieuwe mails", "Postvak gelezen, 0 nieuwe mails op deze dag." in html
      and "Niets binnengekomen" not in html, html[-2500:])
html = C.get("/wachten", headers=MET).get_data(as_text=True)
check("D15 tegel zegt postvak gelezen", "postvak gelezen, 0 nieuwe mails" in html)

# --- T-0120 groep pagina (verzonnen voorbeelden; het bord is nagebootst): VOL-14 (archieflink vanaf 01-10), VOL-19 en
# DB-5 (elke link via een route achter Authentik, nooit bij privé of bij WhatsApp, sms, telefoon en Xelion), VOL-13
# (gelezen tot, onbekend nooit 0), ANGEL-6 (de taken van Ai Angel), PLAUD-7 en ARCH-2 (de stand van Plaud en Zoom).
A.vandaag = lambda: date(2026, 10, 31)
A.haal_locatie = lambda pad: None
A._cache.clear()


def wacht_(naam, **extra):
    w = {"naam": naam, "label": "De Proefwacht", "kleur": "groen", "oordeel": "binnen", "aantal": 1, "rondes": 1,
         "gedekt": None, "leesfout": "", "logfout": "", "noden": [], "fouten": [], "status": None, "items": [], "log": []}
    w.update(extra)
    return w


ITEMS = {
    "fathom-wacht": [{"tijd": "10:00", "wie": "Proef Persoon", "wat": "12 min, proef", "fout": False,
                      "link": {"soort": "fathom", "uniek": "fathom:f1", "tekst": "open in Fathom"}},
                     {"tijd": "11:00", "wie": "privégesprek", "wat": "5 min", "fout": False,
                      "link": {"soort": "fathom", "uniek": "fathom:f2", "tekst": "open in Fathom"}}],
    "plaud-wacht": [{"tijd": "10:00", "wie": "Proef Persoon", "wat": "12 min", "fout": False,
                     "link": {"soort": "transcript", "uniek": "plaud:pw1", "tekst": "transcript lezen"}}],
    "whatsapp-wacht": [{"tijd": "09:00", "wie": "Sara Proef", "wat": "3 berichten", "fout": False,
                        "link": {"soort": "dag", "dag": "2026-10-27", "tekst": "mag niet"}}],
    "dagbundelaar": [{"tijd": "21:00", "wie": "dagvaststelling", "wat": "Dagvaststelling", "fout": False,
                      "link": {"soort": "dag", "dag": "2026-10-27", "tekst": "de dag openen"}}],
    "icloud-wacht": [{"tijd": "10:00", "wie": "foto", "wat": "HA 9001 Proefproject: 3 werkfoto's", "fout": False,
                      "link": {"soort": "fotos", "dag": "2026-10-27", "tekst": "foto's per project"}},
                     {"tijd": "11:00", "wie": "foto", "wat": "oud", "fout": False,
                      "link": {"soort": "url", "href": "https://www.dropbox.com/s/proef", "tekst": "Dropbox"}}],
    "mehdi-agent": [{"tijd": "10:20", "wie": "taken", "wat": "Te doen 27-10: 14 open", "fout": False,
                     "regels": ["1. Proeftaak nummer 1 (normaal)", "2. privé", "en nog 2 op het bord"],
                     "link": {"soort": "bord", "pad": "/agent/mehdi-agent", "tekst": "de volledige lijst op het bord"}}],
}
GELEZEN = {"stand": "tot", "tekst": "gelezen tot 16:30", "bewijs": "de laatste ronde in het werkverslag van deze dag"}
PAGINA = {"dag": "2026-10-27", "items": 0, "telling": {}, "vakken": [{"vak": "Proef", "wachten": [
    wacht_(n, items=i, aantal=len(i), gelezen=GELEZEN) for n, i in ITEMS.items()] + [
    wacht_("gezondheid-wacht", kleur="grijs", oordeel="niets binnen, geen ronde", aantal=0, rondes=0,
           gelezen={"stand": "niet", "tekst": "niet gelezen", "bewijs": "geen ronde, geen dekking en geen item van deze dag"},
           uitleg={"rol": "Leest de proefgegevens van het horloge", "cadans": "elke ochtend"}),
    wacht_("plaud-wacht-2", plaud=None)]}]}
PAGINA["vakken"][0]["wachten"][-1]["naam"] = "zoom-archief"
PAGINA["vakken"][0]["wachten"][-1].update(archief={"gekopieerd": 2, "verdwenen": 1, "overzicht_van": "x", "na_de_dag": True},
                                          items=[], aantal=0)
PAGINA["vakken"][0]["wachten"][1]["plaud"] = {"opnames": 2, "in_tabel": 1, "wacht_op_transcript": 0, "kort": 0,
                                              "onvolledig": 0, "zonder_audio": 1, "manifest_van": "x", "na_de_dag": True}
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(PAGINA))
r = C.get("/wachten?dag=2026-10-05", headers=MET)
html = r.get_data(as_text=True)
check("D40 (VOL-14) ?dag= werkt terug als archieflink: 05-10 laadt, de knop 'archief' staat aan",
      r.status_code == 200 and '<a class="aan" href="/wachten?dag=2026-10-05">archief, ma 5 okt</a>' in html, html[:2500])
check("D40 de vier dagknoppen blijven", html.count('href="/wachten?dag=2026-10-2') + html.count('href="/wachten?dag=2026-10-3') >= 4
      and 'href="/wachten?dag=2026-10-28"' in html and 'href="/wachten?dag=2026-10-31"' in html)
check("D40 de dagkiezer begint op 01-10 en de vorige dag is een link", 'min="2026-10-01"' in html and 'max="2026-10-31"' in html
      and 'href="/wachten?dag=2026-10-04"' in html)
check("D40 01-10 laadt, 30-09 en morgen zijn 404, ook op de pagina van een wacht",
      C.get("/wachten?dag=2026-10-01", headers=MET).status_code == 200
      and C.get("/wachten?dag=2026-09-30", headers=MET).status_code == 404
      and C.get("/wachten/fathom-wacht?dag=2026-09-30", headers=MET).status_code == 404
      and C.get("/wachten/fathom-wacht?dag=2026-10-02", headers=MET).status_code == 200
      and C.get("/wachten?dag=2026-11-01", headers=MET).status_code == 404)
html = C.get("/wachten/fathom-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D41 (VOL-19) Fathom: 'open in Fathom' via de route van het Dagboek, in een nieuw venster, nooit de url zelf",
      '<a class="open" href="/wachten/gesprek/fathom:f1/fathom" target="_blank" rel="noopener noreferrer">open in Fathom</a>'
      in html and "fathom.video" not in html, html[-4000:])
check("D41 een privégesprek krijgt geen link, ook als het bord er een gaf (archiefdag: privé blijft verborgen)",
      "fathom:f2" not in html and "privégesprek" in html)
html = C.get("/wachten/whatsapp-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D41 WhatsApp krijgt nooit een link", 'class="open"' not in html and "Sara Proef" in html)
html = C.get("/wachten/plaud-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D41 Plaud: 'transcript lezen' via de route van het Dagboek, en de audio alleen geteld",
      '<a class="open" href="/wachten/gesprek/plaud:pw1/transcript">transcript lezen</a>' in html
      and "1 zonder audio" in html and "er is geen audiolink" in html, html[-4000:])
html = C.get("/wachten/dagbundelaar?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D41 De Dagbundelaar: de dag op /dag/<dag>", '<a class="open" href="/dag/2026-10-27">de dag openen</a>' in html)
html = C.get("/wachten/icloud-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D41 De Fotowacht: de foto's per project; een onbekende soort of een Dropbox-link wordt geen link",
      '<a class="open" href="/fotos/2026-10-27">foto&#39;s per project</a>' in html and "dropbox.com" not in html, html[-4000:])
html = C.get("/wachten/mehdi-agent?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D42 (ANGEL-6) Ai Angel: de genummerde taken en de link naar het bord; een privétaak alleen 'privé'",
      "<li>1. Proeftaak nummer 1 (normaal)</li><li>2. privé</li><li>en nog 2 op het bord</li>" in html
      and 'href="https://mijnagents.globaal.be/agent/mehdi-agent" target="_blank"' in html, html[-4000:])
html = C.get("/wachten/fathom-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D43 (VOL-13) de pagina zegt tot waar de wacht las, met het bewijs",
      "gelezen tot 16:30 <span" in html and "(de laatste ronde in het werkverslag van deze dag)" in html, html[:3000])
html = C.get("/wachten/gezondheid-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D43 niet gelezen is onbekend, nooit 0, en de uitleg komt uit de agenttabel",
      "onbekend</span> items binnen" in html and "Onbekend: deze wacht las deze dag niet" in html
      and "Leest de proefgegevens van het horloge" in html and "<b>Wanneer:</b> elke ochtend" in html, html[-4000:])
html = C.get("/wachten?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D43 de tegel van een wacht die niet las is een vraagteken, en het dagtotaal is minstens",
      '<div class="groot">?</div>' in html and "minstens " in html and "(een wacht is niet gelezen)" in html, html[:3500])
check("D43 de regel onderaan: nooit tekst, privé alleen geteld",
      "Privéfoto's en privégesprekken worden alleen geteld." in html and "—" not in html and "–" not in html)
html = C.get("/wachten/zoom-archief?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D44 (ARCH-2) De Zoomarchivaris zegt hoeveel bestanden gekopieerd en verdwenen zijn",
      "2 bestanden op deze dag gekopieerd naar je Dropbox, 1 verdwenen in Zoom" in html, html[-3000:])

# Codex-toets 2: de fotolink bovenaan alleen op een dag met een werfgroep; 'minstens' ook in het vak Wat binnenkwam.
html = C.get("/wachten/icloud-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D48 (Codex 2 en 3) een werfgroep: de link naar de foto's per project staat ook bovenaan, naar de dag van het item",
      '<a href="/fotos/2026-10-27">foto\'s per project van 27-10</a>' in html and 'href="/fotos/2026-10-05"' not in html,
      html[:1500])
TEL = json.loads(json.dumps(PAGINA))
for w in TEL["vakken"][0]["wachten"]:
    if w["naam"] == "icloud-wacht":
        w["items"] = [{"tijd": "21:00", "wie": "foto", "fout": False,
                       "wat": "geen werk: privé 7, met mensen 2 (alleen geteld, geen plaats)"}]
    if w["naam"] == "plaud-wacht":
        w["gelezen"] = {"stand": "onvolledig", "tekst": "het manifest van de Mac is niet gelezen", "bewijs": ""}
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(TEL))
html = C.get("/wachten/icloud-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D48 een dag met alleen de telling van privé en mensen: geen fotolink, geen plaats", "/fotos/" not in html
      and "alleen geteld, geen plaats" in html, html[:1500])
html = C.get("/wachten/plaud-wacht?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D48 zonder het eigen overzicht is het aantal een ondergrens, bovenaan en in Wat binnenkwam",
      "minstens 1</span> items binnen" in html and "Wat binnenkwam (minstens 1)" in html, html[:3000])
html = C.get("/wachten?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D48 de tegel toont de ondergrens en het dagtotaal is minstens", "&ge; 1" in html and "minstens " in html)
# Codex-toets 3: een ronde maar geen eigen overzicht en geen item: de pagina zegt 'wat er was is onbekend', nooit 'niets'
for w in TEL["vakken"][0]["wachten"]:
    if w["naam"] == "zoom-archief":
        w.update(kleur="oranje", oordeel="draaide, wat er was is onbekend", items=[], aantal=0, archief=None, rondes=1,
                 log=[{"tijd": "07:00", "stap": "bron", "tekst": "proefronde", "fout": False}],
                 gelezen={"stand": "onvolledig", "tekst": "het overzicht van De Zoomarchivaris is niet gelezen", "bewijs": ""})
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(TEL))
html = C.get("/wachten/zoom-archief?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D49 (Codex 3) zonder overzicht en zonder item: de kop zegt 'wat er was is onbekend', het vak 'onbekend'",
      "ma 5 okt 2026: draaide, wat er was is onbekend</h2>" in html and "Wat binnenkwam (onbekend)" in html
      and "Onbekend: het eigen overzicht van deze wacht is niet gelezen" in html and "niets binnen" not in html.split("<main>")[1]
      .split("Groen:")[0], html[-4000:])
html = C.get("/wachten?dag=2026-10-05", headers=MET).get_data(as_text=True)
check("D49 de tegel is dan een vraagteken", "draaide, wat er was is onbekend" in html and '<div class="groot">?' in html)

# De route naar een gesprek: het bord beslist, het Dagboek stuurt alleen naar fathom.video door.
GEVRAAGD = []


def bord_gesprek(antwoord):
    def f(uniek, wat):
        GEVRAAGD.append((uniek, wat))
        return antwoord
    return f


A.haal_gesprek = bord_gesprek({"uniek": "fathom:f1", "link": "https://fathom.video/share/PROEF1"})
r = C.get("/wachten/gesprek/fathom:f1/fathom", headers=MET)
check("D45 (VOL-19) de route naar Fathom stuurt door naar de link van het bord, zonder referrer",
      r.status_code == 302 and r.headers["Location"] == "https://fathom.video/share/PROEF1"
      and r.headers.get("Referrer-Policy") == "no-referrer" and GEVRAAGD[-1] == ("fathom:f1", "fathom"), r.headers)
check("D45 zonder de groep 403, ook voor een gesprek", C.get("/wachten/gesprek/fathom:f1/fathom",
                                                         headers={"X-authentik-groups": "medewerkers"}).status_code == 403)
A.haal_gesprek = bord_gesprek({"uniek": "fathom:f1", "link": "https://www.dropbox.com/s/proef"})
check("D45 een link die niet naar fathom.video gaat: 404", C.get("/wachten/gesprek/fathom:f1/fathom", headers=MET).status_code == 404)
A.haal_gesprek = bord_gesprek({})
check("D45 het bord zegt nee (privé, andere bron, niets): 404", C.get("/wachten/gesprek/fathom:f2/fathom", headers=MET).status_code == 404)
n = len(GEVRAAGD)
check("D45 een andere bron of een verkeerde combinatie vraagt het bord niet eens: 404",
      [C.get(p, headers=MET).status_code for p in ("/wachten/gesprek/whatsapp:1/fathom", "/wachten/gesprek/plaud:pw1/fathom",
                                                   "/wachten/gesprek/fathom:f1/transcript", "/wachten/gesprek/fathom:f1/audio")]
      == [404] * 4 and len(GEVRAAGD) == n, GEVRAAGD[n:])
A.haal_gesprek = bord_gesprek(None)
r = C.get("/wachten/gesprek/plaud:pw1/transcript", headers=MET)
check("D45 het bord antwoordt niet: dat staat er, onbekend", r.status_code == 503 and "Het bord antwoordt niet" in r.get_data(as_text=True))
A.haal_gesprek = bord_gesprek({"uniek": "plaud:pw1", "dag": "2026-10-27", "tijd": "10:00", "minuten": 12, "wie": "Proef Persoon",
                               "thema": "Proefonderwerp", "meer": 0,
                               "regels": [{"tijd": "00:00:00", "wie": "Spreker Proef", "tekst": "Goedemorgen <b>proef</b>."}]})
r = C.get("/wachten/gesprek/plaud:pw1/transcript", headers=MET)
html = r.get_data(as_text=True)
check("D46 (PLAUD-7) het transcript van een werkopname, als tekst, niet bewaard, met de weg terug",
      r.status_code == 200 and "Goedemorgen &lt;b&gt;proef&lt;/b&gt;." in html and "Spreker Proef" in html
      and "no-store" in r.headers.get("Cache-Control", "") and 'href="/wachten/plaud-wacht?dag=2026-10-27"' in html
      and "geen audiolink" in html, html[-2500:])
A.haal_gesprek = bord_gesprek({})
check("D46 een privéopname (het bord zegt nee): 404", C.get("/wachten/gesprek/plaud:pw2/transcript", headers=MET).status_code == 404)
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
check("D47 (VOL-14) de dagpagina linkt naar wat de wachten die dag kregen, vanaf 01-10",
      'href="/wachten?dag=2026-10-22">wat de wachten kregen</a>' in html)
html = C.get("/dag/2026-09-22", headers=MET).get_data(as_text=True)
check("D47 voor 01-10 geen link naar de wachten", "wat de wachten kregen" not in html)

# samen2 (Codex-toets 1): de vier blokken van De Dagbundelaar voor Ai Angel staan op de dagpagina, met hun volledige kop
# en zoals het dagbestand ze schrijft (privé zonder naam); een dag zonder die blokken toont ze niet.
BLOKKEN = ("\n## Werkgesprekken\n\nSamenvatting en actiepunten van Fathom.\n\n"
           "- 10:00 Fathom, 25 min: Proef Klant, dossier: 9001 (bevestigd) [fathom:7001]\n"
           "  - actiepunt: Offerte proefdak sturen\n- 18:00 privégesprek, 12 min\n\n"
           "## Gemist zonder terugbellen\n\n- 09:12 telefoon (privé): geen terugbelpoging gezien\n\n"
           "## Mail wacht op antwoord\n\n- proef@voorbeeld.test: belangrijk, van Proef Klant: Vraag over de offerte\n"
           "- privé@voorbeeld.test: 2 mails (privé)\n\n"
           "## Morgen, 2026-10-23 (agenda onvolledig)\n\n- 09:00 [HA] 9001 Proefbezoek\n- 12:00 (privé)\n")
md = os.path.join(MAP, "2026", "2026-10-22.md")
oud_md = open(md, encoding="utf-8").read()
open(md, "w", encoding="utf-8").write(oud_md + BLOKKEN)
html = C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True)
open(md, "w", encoding="utf-8").write(oud_md)
check("D50 (samen2) de vier bundelblokken staan op de dagpagina, met hun kop",
      all(f"<h2>{k}</h2>" in html for k in ("Werkgesprekken", "Gemist zonder terugbellen", "Mail wacht op antwoord",
                                             "Morgen, 2026-10-23 (agenda onvolledig)")), html[-3000:])
check("D50 hun regels zoals in het dagbestand, privé zonder naam",
      "Offerte proefdak sturen" in html and "18:00 privégesprek, 12 min" in html and "09:12 telefoon (privé)" in html
      and "privé@voorbeeld.test: 2 mails (privé)" in html and "12:00 (privé)" in html, html[-3000:])
check("D50 (Codex-toets 2) een ingesprongen regel blijft ingesprongen, een gewone niet",
      '<div class="klein zacht inspring" style="margin:3px 0 3px 18px">actiepunt: Offerte proefdak sturen</div>' in html
      and '<div class="" style="margin:3px 0">18:00 privégesprek, 12 min</div>' in html, html[-3000:])
check("D50 een dag zonder die blokken toont ze niet",
      "<h2>Werkgesprekken</h2>" not in C.get("/dag/2026-10-22", headers=MET).get_data(as_text=True))

print("dagboek:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
