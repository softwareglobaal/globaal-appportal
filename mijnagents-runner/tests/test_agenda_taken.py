"""Grendel: werkwijze/agenda-taken.json moet kloppen met de code.

De JSON is de afspraak met Mehdi. Deze test faalt zodra iemand een agenda, een
code of een kleurregel in de code verandert zonder de afspraak bij te werken.
"""
import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W

taken = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


adressen = {a["adres"] for a in taken["agendas"]}
check("elke agenda uit de JSON staat in KALENDERS", adressen == set(W.KALENDERS),
      f"alleen in JSON: {adressen - set(W.KALENDERS)} | alleen in code: {set(W.KALENDERS) - adressen}")
import organisatie as O

bron = O.firmacodes()
check("de JSON houdt GEEN kopie van de firmalijst bij",
      "firmas" not in taken["titelconventie"],
      "er staat weer een lijst in; dat is een tweede waarheid")
check("de JSON wijst naar organisatie.globaal.be als bron",
      "organisatie.globaal.be" in taken["bronnen_van_waarheid"]["firmas_en_codes"]["waar"])
check("de JSON kent het dashboard als plek om te kijken",
      "organisatie.globaal.be" in taken["bronnen_van_waarheid"]["dashboard"]["waar"])
check("de JSON legt uit dat 'diensten voor' telt, niet de werkgever",
      "diensten voor" in taken["bronnen_van_waarheid"]["namen_van_collegas"].get("let_op", ""))
check("de bron geeft firmacodes", bool(bron), f"{len(bron)} codes gelezen")
check("de agent gebruikt diezelfde codes", W.FIRMACODES == bron)
check("elke agendacode wijst naar een bestaande firma",
      all(v in bron for v in W.AGENDACODE_NAAR_FIRMA.values()),
      str({k: v for k, v in W.AGENDACODE_NAAR_FIRMA.items() if v not in bron}))
check("elke afdeling op het bord hoort bij een bestaande code of is PRIVE",
      all(k in bron or k in W.NIET_FIRMA for k in W.FIRMA_AFDELING),
      str([k for k in W.FIRMA_AFDELING if k not in bron and k not in W.NIET_FIRMA]))
for code in bron:
    check(f"de titelregel herkent [{code}]", bool(W.CODE_RE.search(f"Mehdi: [{code}-IN] proef")))
for oudc, nieuwc in W.AGENDACODE_NAAR_FIRMA.items():
    d = W.lees_titel(f"Mehdi: [{oudc}-IN] proef")
    check(f"[{oudc}] hoort bij firma {nieuwc}", d["firma"] == nieuwc and d["agendacode"] == oudc)
check("soorten gelijk", taken["titelconventie"]["soorten"] == W.SOORT)
check("types gelijk", taken["titelconventie"]["types"] == W.TYPES)


# de kleurregels naspelen op de echte functie
WERK = "mehdiprivewerkagenda@gmail.com"
proeven = [
    (WERK, "Mehdi: !! [HARC-KB] WB 2310 - werf, Dorpstraat 5", "11", "rood, buiten voor het werk"),
    (WERK, "Mehdi: [HARC-KB] WB 2310 - werf zonder uitroeptekens", "11", "WB is per definitie buiten"),
    (WERK, "Mehdi: ?? [HARC-PB] PLB 2311 - nog niet vast", "5", "geel zolang het niet bevestigd is"),
    (WERK, "Mehdi: [HARC-KO] klant online", "7", "blauw"),
    (WERK, "Mehdi: [UNAB-PO] prospect online", "6", "oranje"),
    (WERK, "Mehdi: [ELEV-IN] intern", "10", "groen"),
    (WERK, "Mehdi: [UNAB-KO] EPB online", "7", "EPB is niet automatisch buiten"),
    (WERK, "Mehdi: !! [UNAB-KO] VC op de werf, Kerkstraat 1", "11", "met !! wel buiten"),
    (WERK, "Mehdi: afspraak zonder code", "", "geen kleur, dat is een fout"),
]
for kal, titel, verwacht, waarom in proeven:
    i = W.lees_titel(titel)
    uit = W.kleur_gewenst({"kalender": kal, "titel": titel}, i)
    check(f"{waarom}: {titel[:40]}", uit == verwacht, f"kreeg {uit or 'geen'}, verwacht {verwacht or 'geen'}")

for kal in W.AGENDA_VASTE_KLEUR:
    i = W.lees_titel("!! [PRIVE] iets buiten, Kerkstraat 1")
    check(f"vaste agendakleur blijft: {W.AGENDA_VASTE_KLEUR[kal]['naam']}",
          W.kleur_gewenst({"kalender": kal, "titel": "x"}, i) == "")
    check(f"maar buiten telt wel mee: {W.AGENDA_VASTE_KLEUR[kal]['naam']}", i["buiten"])

for ty in W.BUITEN_TYPES:
    i = W.lees_titel(f"Mehdi: [HARC-KB] {ty} 1234 - proef")
    check(f"{ty} is per definitie buiten", i["buiten"])
for ty in ("EPB", "VC", "STA", "SD"):
    i = W.lees_titel(f"Mehdi: [HARC-KO] {ty} 1234 - proef")
    check(f"{ty} is niet automatisch buiten", not i["buiten"])

check("de diensten in de JSON kloppen met de code",
      sorted(taken["buiten"]["diensten_altijd_buiten"]) == sorted(W.BUITEN_TYPES))
check("de reistijdbuffer in de JSON klopt", taken["reistijd"]["buffer_minuten"] == W.BUFFER_MIN)
check("de dagstop op Google Routes klopt", taken["reistijd"]["dagstop"]["aantal"] == W.ROUTES_DAGLIMIET)

# Een rit hoort bij de afspraak waarvoor Mehdi rijdt: zelfde agenda, zelfde kleur.
# Mandaat van Mehdi, 21-09-2026. Alleen werk is rood.
for kal in W.AGENDA_VASTE_KLEUR:
    check(f"een rit op {kal[:24]} krijgt de agendakleur, geen rood",
          W.kleur_gewenst({"kalender": kal}, {"reistijd": True}) == "")
check("een rit op de werkagenda is rood",
      W.kleur_gewenst({"kalender": "mehdiprivewerkagenda@gmail.com"}, {"reistijd": True}) == "11")
check("de agent herkent zijn eigen rit met het autootje",
      W.lees_titel("🚗 Reistijd: thuis → Wilselsesteenweg 57")["reistijd"])
check("de JSON zegt dat een rit op dezelfde agenda en in dezelfde kleur staat",
      "dezelfde agenda" in taken["reistijd"]["regel"] and "🚗" in taken["reistijd"]["regel"])
check("de dinsdagketen van Lara staat in de JSON", "lara_dinsdag" in taken["reistijd"])

# Thuis is het vertrekpunt, nooit een bestemming uit een titel. Gezien 21-09-2026:
# "Lara ophalen en thuis afzetten" gaf een rit van thuis naar thuis.
_echt = W.plekken
W.plekken = lambda: [{"naam": "Thuis", "soort": "thuis", "lat": 50.891811, "lon": 4.718396},
                     {"naam": "school Lara", "soort": "school", "lat": 50.88, "lon": 4.70},
                     {"naam": "Zwembad", "adres": "Stadionlaan 4, 3010 Leuven"}]
check("'thuis afzetten' maakt van de afspraak geen afspraak thuis",
      W.plek_zoeken("Mehdi: !! [LARA] Lara ophalen en thuis afzetten") == (None, None))
check("een benoemde plek wordt gevonden", W.plek_zoeken("!! Mehdi: school Lara")[1] == "school Lara")
check("een plek telt alleen als heel woord", W.plek_zoeken("zwembadrand kuisen") == (None, None))
check("een rit naar thuis heet thuis, niet coördinaten", W.ritlabel("50.891811,4.718396") == "thuis")
check("een plek zonder adres heet naar haar naam", W.ritlabel("50.88,4.70") == "school Lara")
W.plekken = _echt
check("binnen dezelfde gemeente heet de rit naar de straat",
      W.ritlabel("Vaartstraat 5, 3000 Leuven", "Herfstlaan 65, 3010 Leuven") == "Vaartstraat 5")

# De controle en de filewacht lezen dezelfde agenda's als de agent (gezien 21-09-2026).
for _script in ("controle_agenda.py", "file_wacht.py"):
    _code = (HIER / _script).read_text(encoding="utf-8")
    check(f"{_script} leest de agenda's via de Agendawacht zelf",
          "W.afspraken(" in _code and "A.afspraken(" not in _code)
check("zelfde postcode, andere gemeentenaam: de rit heet naar de plek",
      W.ritlabel("De Speelkriebel, Jozef Pierrestraat 104, 3010 Kessel-Lo", W.THUIS) == "De Speelkriebel")
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("een rit naar huis die al in de agenda staat, telt als thuiskomen",
      "if thuisrit_tussen(e_, s_volgend):" in _bron)
check("afspraak C: iets achter het bureau tussen twee buitenafspraken is een vraag, geen stille keuze",
      "bureau = aan_bureau_tussen(e_, s_volgend)" in _bron and "VRAAG om" in _bron)
check("een rit hoort bij precies één afspraak: de heenrit eindigt op haar begin of op een extern gesprek ervoor",
      'aankomsten = {start} |' in _bron and "x = heenblok()" in _bron and "x = terugblok()" in _bron)
check("nooit vertrekken voor de vorige afspraak gedaan is",
      "rit_start = vorige_einde" in _bron and "TE KRAP" in _bron)
check("nooit twee rondes tegelijk", "_slot = slot_nemen()" in _bron)

_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
# gedrag, geen broncode (FR-33): een eigen rit (OSRM) laat de herinneringsstap altijd staan
from datetime import timedelta as _td0
_gp0 = []
_op0, _ot0 = W._patch, W.agenda._toegang
W._patch = lambda a, body, tok: _gp0.append(a["titel"])
W.agenda._toegang = lambda: "tok"
_t0 = (W.nu_lokaal() + _td0(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
try:
    W.herinneringen_zetten([
        {"titel": "🚗 Reistijd: thuis → Genk", "start": _t0, "einde": _t0, "kalender": W.WERKAGENDA,
         "_reminders": {"useDefault": True}, "omschrijving": "Reistijd voor: x (60 min = live verkeer Google + 10 min buffer, OSRM)"},
        {"titel": "🚗 Reistijd: Genk → thuis", "start": _t0, "einde": _t0, "kalender": W.WERKAGENDA,
         "_reminders": {"useDefault": False, "overrides": []}, "omschrijving": "Reistijd na: x (60 min, OSRM)"}])
finally:
    W._patch, W.agenda._toegang = _op0, _ot0
check("de herinneringsregel raakt een rit niet aan", _gp0 == [], str(_gp0))
check("de herinneringen komen voor de ritten, de vertrekmelding heeft het laatste woord",
      _bron.index("gezet, al, weg, fout_h = herinneringen_zetten(") < _bron.index("rg, ral, rgeen, rfout, rregels = reistijd_zetten("))
check("de agenda van Lara krijgt ritten tot het einde van het schooljaar",
      W.RIT_VOORUIT_DAGEN.get("Lara", 0) >= 280 and "lara_vooruit" in json.dumps(taken["reistijd"]))

_agenda = (HIER / "koppelingen" / "agenda.py").read_text(encoding="utf-8")
check("de agenda wordt helemaal gelezen, niet alleen de eerste 250 afspraken",
      'params["pageToken"] = pagina' in _agenda)

# Externe relaties (buiten het dashboard) en de overkoepelende code ALGE. Mehdi, 22-09-2026.
check("de lijst externe-relaties.json bestaat", (HIER / "werkwijze" / "externe-relaties.json").exists())
check("ALGE is een geldige overkoepelende firmacode", "ALGE" in W.ALLE_CODES and "ALGE" in W.EXTERNE_FIRMAS)
_i = W.lees_titel("Mehdi & Angela: [ALGE-LO] Nadien boekhouder")
check("[ALGE-LO] leest als firma ALGE, leverancier online", _i["firma"] == "ALGE" and _i["soort"] == "LO")
check("een ALGE-leverancier online is paars (druif)",
      W.kleur_gewenst({"kalender": "mehdiprivewerkagenda@gmail.com"}, _i) == "3")
check("Nadien (boekhouder) en Wally (AI-software) staan in de lijst",
      {"Nadien", "Wally"} <= {r.get("naam") for r in W.EXTERNE_RELATIES})
check("ALGE staat niet op het dashboard (bewust een aparte lijst)", "ALGE" not in W.FIRMACODES)

# Tijdens een schoolvakantie of feestdag geen Lara-ophaling en geen rit. Mehdi, 22-09-2026.
_vak = W.lara_vakantiedagen()
check("de agent leest de schoolvakanties uit de agenda van Lara", len(_vak) > 30)
_lara = next((k for k, v in W.AGENDA_VASTE_KLEUR.items() if v.get("naam") == "Lara"), None)
_dag = sorted(_vak)[0] if _vak else "2026-10-26"
_items = [{"kalender": _lara, "titel": "Mehdi: !! [LARA] Lara ophalen en thuis afzetten",
           "start": _dag + "T16:00:00+02:00", "einde": _dag + "T17:00:00+02:00", "locatie": "De Speelkriebel, 3010 Kessel-Lo", "id": "t", "hele_dag": False}]
_g, _al, _geen, _fout, _reg = W.reistijd_zetten(_items, _dag)
check("geen Lara-rit op een vakantiedag", _g == 0 and _al == 0)
check("de schoolvakantie-regel staat in de JSON", "schoolvakantie" in json.dumps(taken.get("reistijd", {})) or "vakantie" in json.dumps(taken))

# Geen auto: de agent leest de marker en maakt geen rit op zo'n dag. Mehdi, 22-09-2026.
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("de agent kent de grendel geen_auto_dagen", "def geen_auto_dagen" in _bron and "zonder_auto = geen_auto_dagen()" in _bron)
check("een buitenafspraak op een dag zonder auto wordt gemeld", "BUITEN op een dag zonder auto" in _bron)
check("buiten-boekingen-handmatig staat vastgelegd in de JSON",
      "handmatig" in json.dumps(taken, ensure_ascii=False) and "Calendly" in json.dumps(taken, ensure_ascii=False))

# Wie de afspraak maakte, uit het creator-veld (feature van 22-09-2026, samen met een andere sessie).
check("de agent kent maker() en de boekingsaccounts", hasattr(W, "maker") and "siyanhdswerk@gmail.com" in W.BOEKINGSACCOUNTS)
check("een boekingsaccount wordt bij naam getoond", W.maker({"maker": "siyanhdswerk@gmail.com", "kalender": "x"}) == "Siyan")
check("de maker staat bij een buitenafspraak op een dag zonder auto",
      "BUITEN op een dag zonder auto (door {maker(a)})" in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))
check("de makerslijst is vastgelegd in de JSON", "maker" in json.dumps(taken, ensure_ascii=False) and "creator" in json.dumps(taken, ensure_ascii=False))

# Firma voorstellen bij een titel zonder code: uit projectnummer en leverancierslijst. Mehdi 22-09-2026.
def _tf(titel):
    a = {"titel": titel, "kalender": "mehdiprivewerkagenda@gmail.com", "hele_dag": False, "deelnemers": []}
    return W.titelfouten(a, W.lees_titel(titel))
check("een projectnummer uit de H-A map stelt [HARC] voor",
      any("HARC" in x for x in _tf("!! Mehdi: 2616 Stad Leuven stedenbouwkundige info")))
check("een leverancier uit de lijst stelt [ALGE] voor",
      any("ALGE" in x for x in _tf("?? Mehdi: Nadine Boekhouder")))

# B2B: professioneel extern waar wij nog geen klant van zijn. Mehdi, 22-09-2026.
_b = W.lees_titel("Mehdi & Siyan: [HA-B2B] Stefan Oosterbaan")
check("[HA-B2B] leest als firma HARC en soort B2B", _b["firma"] == "HARC" and _b["soort"] == "B2B")
check("B2B is lavendel, de lichte versie van leverancier-paars",
      W.kleur_gewenst({"kalender": "zoomafspraken@gmail.com"}, _b) == "1")
check("B2B staat in de soortenlijst", "B2B" in W.SOORT)

# Google alleen voor ritten binnen 48 uur, zodat de dagteller niet opgaat aan verre ritten (23-09-2026).
check("Google alleen voor ritten binnen 48 uur",
      "dichtbij = vertrek <= datetime.now().astimezone() + timedelta(hours=48)" in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))

# Een naam vooraan in het adres, en een handmatige rit naar huis (23-09-2026).
_c = {}
check("een adres met een naam vooraan wordt gevonden", bool(W.coord("Brasserie 360°, Stadsplein 16, 3600 Genk", _c)))
check("een handmatige 'Rijden naar huis' telt als rit naar huis",
      r'\bnaar huis\b' in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))

# Extern gesprek alleen geparkeerd, intern mag rijdend (23-09-2026).
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("een extern gesprek tijdens de heenrit vervroegt de aankomst",
      "tijdens = [z for z in externe_gesprekken(vertrek, aankomst)" in _bron and '"end": {"dateTime": aankomst.isoformat()}' in _bron)
check("een intern overleg telt niet als extern gesprek", 'ix["soort"] in BUITEN_SOORTEN + ("IN",)' in _bron)
check("op de terugweg wacht de rit tot het externe gesprek voorbij is", "terug_start = max(z[1] for z in tijdens)" in _bron)
check("de regel staat in de JSON", "geparkeerd" in json.dumps(taken, ensure_ascii=False))

# Een schatting overschrijft nooit een live meting; een hele-dag item krijgt geen melding (23-09-2026).
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("een schatting overschrijft nooit een live meting van Google",
      '"live verkeer Google" in _oms and fh != "live"' in _bron and '"live verkeer Google" in _toms and ft != "live"' in _bron)
check("een melding van de agent op een hele-dag item wordt weggehaald, ook met !!",
      'mijn and (a.get("hele_dag") or not' in _bron)

# Stil is expliciet geen melding, niet de agenda-standaard (werk 30 min, Lara 10 min). 23-09-2026.
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("stil maken zet expliciet geen melding, niet de agenda-standaard",
      'STIL = {"useDefault": False, "overrides": []}' in _bron and '"reminders": {"useDefault": True, "overrides": []}' not in _bron)
check("een intern overleg op de agenda-standaard wordt stil gemaakt",
      'elif standaard and (info["soort"] == "IN" or a.get("hele_dag"))' in _bron)

# In één keer goed: vrije tekst naar de titelcode, en de vaste Zoom (23-09-2026).
check("vrije tekst 'Harchitects-KB 2505' wordt [HARC-KB]",
      W.titel_voorstel("!! Mehdi & Catalin: Harchitects-KB 2505")[0] == "!! Mehdi & Catalin: [HARC-KB] 2505")
check("vrije tekst 'elevait-Leverancie online' wordt [ELEV-LO]",
      W.titel_voorstel("?? Mehdi en Shaniel: Robby elevait-Leverancie online")[0] == "?? Mehdi en Shaniel: [ELEV-LO] Robby")
check("een leverancier uit de lijst wordt [ALGE-LO]",
      (W.titel_voorstel("Mehdi: Nadine boekhouder online")[0] or "").startswith("Mehdi: [ALGE-LO]"))
check("een titel zonder dubbelpunt wordt niet blind herschreven", W.titel_voorstel("Mehdi, (HARC- aanne) Pioter 2405")[0] is None)
check("de agent zet zelf geen Zoom-link zolang de juiste niet gekend is", W.VASTE_ZOOM == "")
check("een online gesprek krijgt de notitie dat Mehdi de link stuurt",
      'f"Online. Mehdi stuurt de link naar {wie}."' in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))
check("de zoom-functie wijzigt de locatie niet",
      '"location": VASTE_ZOOM' not in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))
_zb = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("geen notitie bij bellen, Calendly of terugkerende overleggen",
      'bel(t|len)?' in _zb and 'a.get("_terugkerend")' in _zb and 'bool(a.get("_conferentie"))' in _zb)

check("een adres uit de projectmap komt ook in de afspraak zelf",
      'bron_adres == "projectmap" and fysiek and not (a.get("locatie") or "").strip()' in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))

# Aannemer (AB/AO) en ZL = zonder link (23-09-2026).
_a = W.lees_titel("Mehdi & Pioter: [HARC-AO] 2405 - aannemer van Dorien")
check("[HARC-AO] is aannemer online, kleur salie", _a["soort"] == "AO" and W.kleur_gewenst({"kalender": W.WERKAGENDA}, _a) == "2")
check("[HARC-AB] is aannemer buiten, rood", W.lees_titel("!! Mehdi: [HARC-AB] 2405")["buiten"]
      and W.kleur_gewenst({"kalender": W.WERKAGENDA}, W.lees_titel("!! Mehdi: [HARC-AB] 2405")) == "11")
check("de soorten komen uit een centrale lijst", "AB" in W.BUITEN_SOORTEN and "AO" in W.EXTERN_ONLINE)
check("vrije tekst 'aannemer online' wordt AO",
      W.titel_voorstel("Mehdi & Pioter: Harchitects aannemer online 2405")[0] == "Mehdi & Pioter: [HARC-AO] 2405")
check("ZL komt helemaal vooraan, ook voor ??", W.met_zl("?? Mehdi en Shaniel: [ELEV-LO] Robby") == "ZL ?? Mehdi en Shaniel: [ELEV-LO] Robby")
check("een ZL die verder staat, schuift naar voren", W.met_zl("?? ZL Mehdi en Shaniel: [ELEV-LO] Robby") == "ZL ?? Mehdi en Shaniel: [ELEV-LO] Robby")
check("ZL gaat er weer af", W.zonder_zl("ZL ?? Mehdi en Shaniel: [ELEV-LO] Robby") == "?? Mehdi en Shaniel: [ELEV-LO] Robby")
check("ZL breekt de titelcode niet", W.lees_titel("ZL Mehdi & Pioter: [HARC-AO] 2405")["soort"] == "AO")
check("ZL staat in de JSON", "ZL" in json.dumps(taken["titelconventie"], ensure_ascii=False))

# Weekcontrole 21-27 september (24-09-2026). Gedrag testen, geen letterlijke broncode.
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
import urllib.request as _ur

# FR-20 handkleur: wat een mens zette, is een vraag
check("een kleur die een mens zette, is een vraag en wordt niet overschreven",
      W.kleur_actie({"_kleur": "3", "_merk": {}}, "10") == "vraag"
      and W.kleur_actie({"_kleur": "10", "_merk": {W.KLEURMERK: "10"}}, "6") == "zetten"
      and W.kleur_actie({"_kleur": ""}, "6") == "zetten"
      and W.kleur_actie({"_kleur": "6", "_merk": {}}, "6") == "merken"
      and W.kleur_actie({"_kleur": "6", "_merk": {W.KLEURMERK: "6"}}, "6") == "goed")

# FR-17 het Google-plafond is hard
_oud = (W.ROUTES_KEY, W.routes_vandaag, W.google_rijtijd_min, W.vrije_rijtijd_min, W.ROUTES_DAGLIMIET)
_geroepen = []
W.ROUTES_KEY, W.ROUTES_DAGLIMIET = "proef", 400
W.routes_vandaag = lambda: ("vandaag", 100)
W.google_rijtijd_min = lambda *a: _geroepen.append(a) or 20.0
W.vrije_rijtijd_min = lambda *a: 20.0
W.rijtijd_min((50.9, 4.7), (50.95, 4.75), W.nu_lokaal() + _td(hours=2))
W.ROUTES_KEY, W.routes_vandaag, W.google_rijtijd_min, W.vrije_rijtijd_min, W.ROUTES_DAGLIMIET = _oud
check("het Google-plafond gaat nooit boven 100, ook niet via de omgeving",
      not _geroepen and W.ROUTES_PLAFOND == 100 and W.ROUTES_DAGLIMIET <= 100)

# FR-18 Brusselse tijd, zomer en winter
_u = lambda *a: _dt(*a, tzinfo=_tz.utc)
check("de ronde volgt de Brusselse tijd, zomer en winter",
      W.is_rondetijd(_u(2026, 9, 24, 4, 30)) and not W.is_rondetijd(_u(2026, 9, 24, 5, 30))
      and W.is_rondetijd(_u(2026, 12, 1, 5, 30)) and not W.is_rondetijd(_u(2026, 9, 26, 4, 30)))
check("de filewacht slaapt niet tijdens de ochtendspits",
      W.binnen_uren(6, 21, _u(2026, 9, 24, 5, 0)) and not W.binnen_uren(6, 21, _u(2026, 9, 24, 21, 0)))

# FR-19 elke ronde begint met zijn tijdstip
check("elke ronde begint met zijn tijdstip",
      "Brussel · " in (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
      and "nu_lokaal():%d-%m %H:%M" in (HIER / "agenda_signaal.py").read_text(encoding="utf-8"))

# nooit een mail naar gasten
_urls = []
_oud_open, _oud_mag = _ur.urlopen, W.mag_schrijven
_ur.urlopen = lambda req, timeout=0: (_urls.append(req.full_url), type("R", (), {"read": lambda s: b"{}"})())[1]
W.mag_schrijven = lambda k: True
try:
    W._patch({"kalender": W.WERKAGENDA, "id": "x"}, {}, "tok")
    try:
        W._insert(W.WERKAGENDA, {}, "tok")
    except Exception:
        pass
finally:
    _ur.urlopen, W.mag_schrijven = _oud_open, _oud_mag
check("een gast krijgt nooit een mail: sendUpdates=none bij wijzigen en aanmaken",
      len(_urls) == 2 and all("sendUpdates=none" in u for u in _urls), str(_urls))

# FR-23 maker
check("maker herkent een Calendly-boeking aan de inhoud",
      W.maker({"maker": W.WERKAGENDA, "omschrijving": "... https://calendly.com/cancellations/abc"}) == "Calendly (werkagenda)"
      and W.maker({"maker": W.WERKAGENDA, "omschrijving": ""}) == "Mehdi zelf"
      and W.maker({"maker": "haagendalightprojects@gmail.com", "omschrijving": ""}).startswith("account light projects"))

# FR-29 plaatsnaam
check("LEUVEN wordt Leuven in een ritlabel", W.plaatsnaam("Tessenstraat 3, 3000 LEUVEN") == "Leuven")

# FR-27 en FR-30 titelfouten
_f = W.titelfouten({"kalender": W.WERKAGENDA, "titel": "!! Mehdi: [HARC] 2616 Stad Leuven", "maker": W.WERKAGENDA},
                   W.lees_titel("!! Mehdi: [HARC] 2616 Stad Leuven"))
check("een firmacode zonder soort wordt gemeld", any("zonder soort" in x for x in _f), str(_f))
_f = W.titelfouten({"kalender": W.WERKAGENDA, "titel": "[ENEF-IN] Afdelings meeting Energy",
                    "maker": "ee.ashvand@globaal.be", "deelnemers": ["a@x.be", "b@x.be"]},
                   W.lees_titel("[ENEF-IN] Afdelings meeting Energy"))
check("een uitnodiging van een collega krijgt geen naamfout", not any("naam" in x for x in _f), str(_f))

# FR-26 ?? na afloop
_g = (W.nu_lokaal() - _td(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
_v = W.onbevestigd_voorbij([{"titel": "?? Mehdi: [ALGE-LO] Nadine", "start": _g.isoformat(),
                             "einde": (_g + _td(hours=1)).isoformat(), "kalender": W.WERKAGENDA}],
                           W.nu_lokaal().date().isoformat())
check("?? na afloop wordt gevraagd: doorgegaan of niet", len(_v) == 1 and "doorgegaan" in _v[0])

# FR-24 een handmatige rit krijgt de rit-melding
_gepatcht = []
_oud_p, _oud_t = W._patch, W.agenda._toegang
W._patch = lambda a, body, tok: _gepatcht.append((a["titel"], body))
W.agenda._toegang = lambda: "tok"
_m = (W.nu_lokaal() + _td(days=1)).replace(hour=13, minute=55, second=0, microsecond=0).isoformat()
try:
    W.herinneringen_zetten([
        {"titel": "!! Mehdi: Rijden naar Stadskantoor Leuven", "start": _m, "einde": _m, "kalender": W.WERKAGENDA,
         "_reminders": {"useDefault": True}, "omschrijving": ""},
        {"titel": "!! Mehdi: Rijden naar huis", "start": _m, "einde": _m, "kalender": W.WERKAGENDA,
         "_reminders": {"useDefault": True}, "omschrijving": ""},
        {"titel": "!! Mehdi: Rijden naar huis", "start": _m, "einde": _m, "kalender": W.WERKAGENDA,
         "_reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 25}]}, "omschrijving": ""}])
finally:
    W._patch, W.agenda._toegang = _oud_p, _oud_t
check("een handmatige rit krijgt de rit-melding, niet de agendastandaard",
      len(_gepatcht) == 2 and _gepatcht[0][1]["reminders"]["overrides"] == [{"method": "popup", "minutes": 5}]
      and _gepatcht[1][1]["reminders"]["overrides"] == [], str(_gepatcht))

# FR-25 de rit volgt de titel van zijn afspraak
check("een rit neemt de nieuwe titel van zijn afspraak over",
      'tekst.split(" (", 1)[0] not in (x.get("omschrijving") or "")' in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))

# FR-28 een rit verhuist mee met zijn afspraak
check("een eigen rit verhuist mee als zijn afspraak naar een andere agenda gaat",
      hasattr(W, "_verplaats") and "rit verhuisd naar" in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))

# de zelfcontrole en het register
import zelfcontrole as Z
_reg = Z.register()
_nu = W.nu_lokaal()
_mo = (_nu + _td(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
_b = Z.bevindingen([{"titel": "Mehdi: [UNAB-IN] overleg Tom", "start": _mo.isoformat(), "einde": (_mo + _td(hours=1)).isoformat(),
                     "kalender": W.WERKAGENDA, "_kleur": "3", "_merk": {}, "_reminders": {"useDefault": False, "overrides": []},
                     "maker": W.WERKAGENDA}], _nu.date().isoformat(), (_nu + _td(days=2)).date().isoformat(), _nu)
check("de zelfcontrole ziet een handkleur als vraag", [x["controle"] for x in _b] == ["handkleur"], str(_b))
_i = Z.indelen([{"controle": "kleur", "dag": "", "uur": ""}, {"controle": "iets_nieuws", "dag": "", "uur": ""}], _reg)
check("een opgeloste fout die terugkomt heet TERUGGEKEERD, een onbekende NIEUW",
      [x["staat"] for x in _i] == ["TERUGGEKEERD", "NIEUW"], str(_i))
check("de JSON wijst naar het foutenregister en de zelfcontrole",
      "foutenregister.json" in json.dumps(taken.get("leren", {})) and "zelfcontrole.py" in json.dumps(taken.get("leren", {})))

check("de controle bestaat", (HIER / "controle_agenda.py").exists())
check("de archiefgrendel bestaat", (HIER / "tests" / "test_agenda_archief.py").exists())

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
