#!/usr/bin/env python3
"""De Agendawacht (Privé) — leest Mehdi's agenda's volgens de agenda-regels van Mehdi
en zet klaar wat anderen nodig hebben.

Elke werkdag om 06:30 en daarna elke twee uur:
  1. de zeven actieve agenda's (AGENDA_KALENDERS in mijnagents-data/.env, anders
     de vaste lijst hieronder) van gisteren tot zeven dagen vooruit;
  2. per afspraak de titel lezen volgens de titelconventie: "Mehdi: !! [HA-KB] WB 2310 -
     werfbezoek ..." -> firma HA, soort KB (klant buiten), type WB, nummer 2310;
     "!!" = buiten met reistijd, "??" = niet bevestigd; "Reistijd"-blokken slaan we over;
  3. koppelen aan een deal (Pipedrive H-Architects: projectnummer, anders naam);
  4. klaarzetten per firma (h-architects, unabo, harmoniebouw, contrax; PRIVE -> mehdi),
     het dagplan van vandaag en "gisteren zonder verslag" voor Mehdi, en een signaal
     voor titels die de conventie niet volgen (zodat we beter communiceren);
  5. werkverslag op het bord.
Leest alleen. Verandert nooit een afspraak.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import agenda  # noqa: E402
import bellen  # noqa: E402
import projectadressen  # noqa: E402
import bord  # noqa: E402
import organisatie  # noqa: E402
import adresboek  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "agenda-wacht"
ag = bord.Agent(NAAM)

# De negen actieve agenda's van Mehdi (Feestdagen is read-only).
KALENDERS = {
    "mehdiprivewerkagenda@gmail.com": "mehdi werk agenda (alle firma's, via de code in de titel)",
    "73e8b6359d04b7bdb02aa045e668cd6f9d9f007bec51ce370494e7de7501f0c4@group.calendar.google.com": "H-Architects",
    "b135d9900db83399539bb5fe4ad9dc1ace19af20273c078ce2180cc47e9232fe@group.calendar.google.com": "UNABO",
    "385ee9ff8749fe5e5929090550d42611f4ce2437d11b56f3d4d943619b4c479f@group.calendar.google.com": "Lara",
    "mehdipriveagena@gmail.com": "prive agenda Mehdi (privé, alleen Mehdi)",
    "zoomafspraken@gmail.com": "zoomafspraken (sales via Calendly)",
    "en.be#holiday@group.v.calendar.google.com": "Feestdagen BE",
}
# Wat Mehdi archiveert krijgt "ZZ ARCHIEF" voor de naam, nadat hij de agenda van
# alle andere accounts heeft losgekoppeld. Tweede grendel naast KALENDERS: ook als
# zo'n agenda ooit in de lijst hierboven belandt, laat ik hem met rust. 19-09-2026.
ARCHIEFVOORVOEGSEL = "ZZ ARCHIEF"

# De firmacodes komen uit organisatie.globaal.be (tabel kern.firma), de enige bron.
# Ik houd hier geen eigen lijst bij; valt de bron weg, dan val ik terug op wat er
# het laatst gelezen is. Mandaat van Mehdi, 20-09-2026.
VALNET_FIRMAS = {"BFUT": "Build for Future", "CONT": "Contrax", "CORE": "Corenbo", "ELEV": "Elevait NV",
                 "ENEF": "Energie Efficiënt", "ENST": "ENSTACO", "HARC": "H-Architects", "HARM": "Harmoniebouw",
                 "HDSI": "High Design Studio (India)", "HDSS": "High Design Studio (Suriname)",
                 "HINV": "H-Invest", "MELO": "Melodie", "ORVA": "Orvantis", "QOPP": "Qoppa",
                 "TKNB": "TKN-Buro", "UNAB": "UnaBo", "ZIDI": "Zidi Construct"}


def firmacodes():
    try:
        uit = organisatie.firmacodes()
        if uit:
            return uit
    except Exception:  # noqa: BLE001
        pass
    return dict(VALNET_FIRMAS)


FIRMACODES = firmacodes()

# Twee soorten codes, allebei juist, elk met hun eigen bron:
#   de AGENDACODE staat in de titel (HA, UNABO, ELEVAIT, TKN). Bron: het document
#   'agenda afspraken met Nova.docx'. Dat is volgens mijn werkwijze de enige bron
#   voor titels, dus deze codes zijn niet oud en horen niet vervangen te worden.
#   de FIRMACODE is de vierletterige code van organisatie.globaal.be (HARC, UNAB,
#   ELEV, TKNB). Bron: het schema kern. Die gebruik ik intern, om een afspraak aan
#   een firma en een afdeling te koppelen.
# Ik vertaal tussen die twee, ik vervang nooit de ene door de andere in een titel.
# Fout gemeten op 20-09-2026: ik meldde 28 titels als "oude firmacode" die
# rechtgezet moest worden. Dat advies was verkeerd om en is weggehaald.
AGENDACODE_NAAR_FIRMA = {"HA": "HARC", "UNABO": "UNAB", "HB": "HARM", "HARMONIEBOUW": "HARM",
                         "CONTRAX": "CONT", "ENERGIE": "ENEF", "TKN": "TKNB", "ELEVAIT": "ELEV"}

# PRIVE is geen firma maar hoort wel in een titel te mogen staan.
NIET_FIRMA = {"PRIVE": "privé van Mehdi"}

# Welke code op welk bord-afdeling terechtkomt. Alleen de afdelingen die op het
# bord bestaan; een firma zonder afdeling lees ik wel maar zet ik nergens klaar.
FIRMA_AFDELING = {"HARC": "h-architects", "UNAB": "unabo", "HARM": "harmoniebouw", "CONT": "contrax",
                  "TKNB": "tkn", "ELEV": "elevait", "ENEF": "unabo", "PRIVE": "prive"}
KALENDER_AFDELING = {"H-Architects": "h-architects", "UNABO": "unabo",
                     "zoomafspraken (sales via Calendly)": "h-architects"}
SOORT = {"KB": "klant buiten", "PB": "prospect buiten (plaatsbezoek)", "KO": "klant online",
         "PO": "prospect online", "IN": "intern"}
# Diensten met een verslagagent (Commandocentrum, 16-09-2026): WB/OPL werfverslag, VC veiligheidscoördinatie,
# PLB plaatsbeschrijving, BS/STA barsten en scheuren. De code staat na de firmacode, vóór het nummer of de naam.
TYPES = {"WB": "werfbezoek", "OPL": "oplevering", "PLB": "plaatsbeschrijving", "SCN": "3D-scan", "EPB": "EPB",
         "VC": "veiligheidscoördinatie", "BS": "barsten en scheuren", "STA": "stabiliteit", "SD": "schetsontwerp", "OPM": "opmeting"}
# Agenda's met één aard krijgen hun kleur op de agenda zelf, niet per afspraak.
# Mandaat van Mehdi, 20-09-2026: "voor prive wil ik zwart en de agenda is al zwart
# gezet zodat altijd zwart komt, en de agent kan controleren. Lara is al flamingo
# roze." Ik zet daar dus geen kleur per afspraak en haal een kleur die er staat weg,
# want die overschrijft de agendakleur. Alleen de werkagenda mengt firma's en soorten
# en heeft wel kleur per afspraak nodig.
AGENDA_VASTE_KLEUR = {
    "385ee9ff8749fe5e5929090550d42611f4ce2437d11b56f3d4d943619b4c479f@group.calendar.google.com":
        {"naam": "Lara", "kleur": "flamingo roze", "achtergrond": "#f691b2", "agenda_kleurid": "22"},
    "mehdipriveagena@gmail.com":
        {"naam": "prive agenda Mehdi", "kleur": "zwart", "achtergrond": "#000000", "agenda_kleurid": "8"},
}

# Diensten die per definitie buiten gebeuren; daar hoeft Mehdi geen !! meer bij te
# typen. Beslist 20-09-2026. EPB, VC, STA en SD staan er bewust niet bij: die kunnen
# evengoed online.
BUITEN_TYPES = {"WB", "OPL", "PLB", "SCN", "OPM", "BS"}

ALLE_CODES = sorted(set(FIRMACODES) | set(AGENDACODE_NAAR_FIRMA) | set(NIET_FIRMA), key=len, reverse=True)
CODE_RE = re.compile(r"\[(" + "|".join(ALLE_CODES) + r")(?:-(KB|PB|KO|PO|IN))?\]", re.I)


def kalenders():
    ruw = os.environ.get("AGENDA_KALENDERS", "").strip()
    lijst = [k.strip() for k in ruw.split(",") if k.strip()] or list(KALENDERS)
    return [k for k in lijst if k not in gearchiveerd()]


def gearchiveerd():
    """Agenda's die Mehdi op archief heeft gezet: hij koppelt ze eerst los van alle
    andere accounts en zet er dan ZZ ARCHIEF voor. Die laat ik met rust, ook als ze
    nog in KALENDERS staan. Lukt het opvragen niet, dan raak ik niets aan."""
    try:
        namen = agenda.kalendernamen()
    except Exception:
        return set()
    return {k for k, naam in namen.items() if naam.strip().upper().startswith(ARCHIEFVOORVOEGSEL)}


def lees_titel(titel):
    """Ontleedt een titel volgens Mehdi's titelconventie. Geeft dict met firma, soort, type,
    nummer, klant, buiten (!!), onzeker (??), reistijd, conform."""
    t = titel.strip()
    # Ook wat Mehdi zelf als rit schrijft telt als reistijd: "Rijden naar huis",
    # "Rijden naar Stadskantoor". Anders meldt de wacht die als afspraak zonder code
    # en zet hij er een tweede reistijdblok naast. Gezien 20-09-2026.
    uit = {"reistijd": bool(re.search(r"reistijd|\brijden naar\b|\bonderweg naar\b", t, re.I))
                       or t.startswith("🚗"),
           "buiten": "!!" in t, "onzeker": "??" in t, "firma": "", "soort": "", "type": "", "nummer": "", "klant": ""}
    m = CODE_RE.search(t)
    if m:
        gevonden = m.group(1).upper()
        uit["firma"] = AGENDACODE_NAAR_FIRMA.get(gevonden, gevonden)
        uit["agendacode"] = gevonden if gevonden in AGENDACODE_NAAR_FIRMA else ""
        uit["soort"] = (m.group(2) or "").upper()
    else:
        uit["agendacode"] = ""
    # eerst !! en ?? weg, dan de naam vooraan: anders bleef bij "!! Mehdi: BS ..." de naam staan en werd de
    # dienstcode niet gelezen (klant droeg "Mehdi:" mee; gezien in het Commandocentrum, 16-09-2026)
    rest = CODE_RE.sub("", t).replace("!!", "").replace("??", "")
    rest = re.sub(r"^\s*(mehdi|siyan|shelton|angela)[^:]{0,40}:\s*", "", rest, flags=re.I).strip(" -")
    mt = re.match(r"^\s*(WB|OPL|PLB|SCN|EPB|VC|BS|STA|SD|OPM)\b", rest, re.I)
    if mt:
        uit["type"] = mt.group(1).upper()
        rest = rest[mt.end():].strip(" -")
    if uit["type"] in BUITEN_TYPES:
        uit["buiten"] = True
    mn = re.search(r"\b(\d{4,5})\b", rest)
    if mn:
        uit["nummer"] = mn.group(1)
    uit["klant"] = re.sub(r"\b\d{4,5}\b", "", rest).strip(" -:").split(" - ")[0][:80]
    uit["conform"] = bool(m) or uit["reistijd"]
    return uit


def deals_index():
    d = pipedrive.get("harchitects", "/deals", {"status": "open", "limit": 500})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    uit = []
    for x in items:
        titel = x.get("title", "")
        m = re.match(r"^\s*((?:26|56)\d\d)\b", titel)
        uit.append({"id": x.get("id"), "titel": titel, "nummer": m.group(1) if m else "",
                    "delen": {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()}})
    return uit


def koppel(info, titel, deals):
    if info["nummer"]:
        for d in deals:
            if d["nummer"] == info["nummer"]:
                return d, "projectnummer in de titel"
    delen = {w for w in re.split(r"[^a-z0-9]+", (info["klant"] or titel).lower()) if len(w) > 2}
    beste, score = None, 0
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score = d, s
    return (beste, f"naam in de titel ({score} woorden)") if beste and score >= 2 else (None, "")


ONLINE_MIN = int(os.environ.get("AGENDA_HERINNERING_ONLINE", "5"))
BUITEN_MIN = int(os.environ.get("AGENDA_HERINNERING_BUITEN", "30"))
OVERIG_MIN = int(os.environ.get("AGENDA_HERINNERING_OVERIG", "10"))


# Mandaat van Mehdi, 20-09-2026: iedereen behalve intern krijgt een melding. Klanten
# dus ook, niet alleen prospecten. Voor een afspraak buiten telt het vertrekmoment,
# niet het beginuur: daar zorgt het reistijdblok voor, dat zelf een melding draagt.
GEEN_MELDING_SOORTEN = ("IN",)


def melding_gewenst(a):
    """Regel van Mehdi, 20-09-2026: elke afspraak met iemand van buiten het huis
    krijgt een melding, klant zowel als prospect. Alleen intern (-IN) blijft stil.
    Hele-dag-items en reistijdblokken tellen niet mee; een reistijdblok draagt zijn
    eigen melding op het vertrekmoment."""
    info = lees_titel(a["titel"])
    if a.get("hele_dag") or info["reistijd"]:
        return False, info
    if not info["firma"] or info["soort"] in GEEN_MELDING_SOORTEN:
        return False, info
    return True, info


class GeenSchrijfrecht(Exception):
    """Ik probeerde te schrijven in een agenda waar dat niet mag."""


def mag_schrijven(kal):
    """Mandaat van Mehdi, 20-09-2026: uit het archief mag ik lezen, er nooit iets
    nieuws in zetten. Schrijven mag alleen in de agenda's die vandaag in gebruik
    zijn, en nooit in iets dat op ZZ ARCHIEF staat. Dit staat hier in de code en
    niet alleen in de rechten bij Google, want de agent draait op het account van
    Mehdi zelf en heeft daar overal schrijfrecht."""
    return kal in KALENDERS and kal not in gearchiveerd()


def _patch(a, body, tok):
    import urllib.parse
    import urllib.request
    if not mag_schrijven(a["kalender"]):
        raise GeenSchrijfrecht(a["kalender"])
    url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/{urllib.parse.quote(a['id'], safe='')}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)


def herinneringen_zetten(items, alleen_dag=None):
    """Werkwijze stap 5: een pop-upherinnering op elke komende prospect-afspraak
    (regel in melding_gewenst) die er nog geen heeft: online 5 min, buiten (!!) 30 min.
    Een herinnering die ik zelf eerder op een niet-gewenste afspraak zette (mijn
    handtekening: één pop-up van 10 of 30 min) haal ik weer weg, zodat intern en
    terugkerend stil blijven. Bestaande herinneringen van Mehdi laat ik staan.
    Geeft (gezet, al, weggehaald, fout)."""
    tok = agenda._toegang()
    nu_iso = datetime.now().astimezone().isoformat()
    gezet, al, weg, fout = 0, 0, 0, 0
    for a in items:
        if a["start"] < nu_iso[:len(a["start"])] or a.get("kalender", "").startswith("en.be#"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        gewenst, info = melding_gewenst(a)
        r = a.get("_reminders") or {}
        eigen = r.get("overrides") or []
        mijn = len(eigen) == 1 and eigen[0].get("method") == "popup" and eigen[0].get("minutes") in (OVERIG_MIN, BUITEN_MIN, ONLINE_MIN)
        try:
            if gewenst and not eigen:
                minuten = BUITEN_MIN if info["buiten"] else ONLINE_MIN
                _patch(a, {"reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": minuten}]}}, tok)
                gezet += 1
            elif gewenst:
                al += 1
            elif not gewenst and mijn:
                _patch(a, {"reminders": {"useDefault": True, "overrides": []}}, tok)
                weg += 1
        except Exception as e:  # noqa: BLE001
            fout += 1
            print("herinnering mislukt:", a["titel"][:40], type(e).__name__, file=sys.stderr)
    return gezet, al, weg, fout


# Kleuren (de regels van Mehdi, Google-kleurnummers): roze 4 flamingo = Lara;
# oranje 6 mandarijn = prospect (PO, PB); rood 11 tomaat = !! buiten en reistijd;
# blauw 7 pauw = klant online (KO); groen 10 basilicum = intern (IN); geel 5 banaan = ?? niet bevestigd.
KLEURNAAM = {"4": "roze", "6": "oranje", "11": "rood", "7": "blauw", "10": "groen", "5": "geel"}
ALLEEN_VANDAAG = "--vandaag" in sys.argv


def namen_in_titel(titel):
    """Wie staat er in de titel, getoetst aan kern.persoon via organisatie.globaal.be.
    Mandaat van Mehdi, 20-09-2026: bij een interne afspraak hoort altijd een naam,
    anders is achteraf niet te zien wie er niet kwam opdagen."""
    # de hele titel, niet alleen de kop: een naam staat even vaak achter de code
    # ("[ELEV-IN] Shaniel - LegalFly") als ervoor ("Mehdi+Tom: [UNAB-IN] ...")
    zonder_code = CODE_RE.sub(" ", titel)
    stukken = re.split(r"[+&,/:\-]| en | met ", zonder_code, flags=re.I)
    uit = []
    for stuk in stukken:
        stuk = stuk.strip(" -!?").strip()
        if not stuk or stuk.lower() in ("mehdi", "mehdi ", ""):
            continue
        try:
            p = organisatie.herken(stuk)
        except Exception:  # noqa: BLE001
            p = None
        if p:
            uit.append(p["naam"])
    return uit


def titelfouten(a, info):
    """De fouten die Mehdi hard wil zien. Geeft een lijst met korte redenen."""
    if info["reistijd"] or a.get("hele_dag"):
        return []
    fouten = []
    if a.get("kalender", "") not in AGENDA_VASTE_KLEUR and not info.get("firma"):
        fouten.append("geen firmacode")
    buiten = info["buiten"] or info["soort"] in ("PB", "KB")
    if buiten and "!!" not in (a.get("titel") or ""):
        # Mehdi leest weinig en kijkt: buiten hoort altijd zichtbaar te zijn met !!
        fouten.append("buiten zonder !!")
    if info["soort"] == "IN" and not namen_in_titel(a.get("titel") or ""):
        # Een blok dat Mehdi alleen doet ("Ai stabiliteit") heeft geen naam nodig.
        # Pas als er iemand bij is, hoort die naam erbij, anders is achteraf niet te
        # zien wie niet kwam opdagen. Verfijnd op 20-09-2026.
        met_iemand = bool(a.get("deelnemers")) or bool(re.search(r"[+&]| en | met ", 
                          (a.get("titel") or "").split("[")[0], re.I))
        if met_iemand:
            fouten.append("intern met iemand, maar zonder herkende naam")
    return fouten


def kleur_gewenst(a, info):
    """De kleur zegt waarvóór Mehdi ergens is; `!!` zegt dat hij naar buiten gaat.
    Dat zijn twee verschillende dingen. Mandaat van Mehdi, 20-09-2026:

    - Lara en de privé-agenda houden altijd hun eigen agendakleur, ook buiten.
    - Op de werkagenda's: geel zolang `??`, daarna rood als het buiten is,
      anders blauw voor klant online, oranje voor prospect online, groen voor intern.
    - Een titel zonder code krijgt geen kleur en is een fout, geen uitzondering.
    """
    if a.get("kalender", "") in AGENDA_VASTE_KLEUR:
        return ""   # die agenda heeft een vaste kleur, per afspraak niets zetten
    if info["reistijd"]:
        return "11"
    if not info.get("firma"):
        return ""   # geen code: fout, wordt gemeld
    if info["onzeker"]:
        return "5"
    if info["buiten"] or info["soort"] in ("PB", "KB"):
        return "11"
    if info["soort"] == "KO":
        return "7"
    if info["soort"] == "PO":
        return "6"
    if info["soort"] == "IN":
        return "10"
    return ""


def kleuren_zetten(items, alleen_dag=None):
    """Werkwijze: elke komende afspraak krijgt de kleur van zijn soort. Alleen als de
    kleur afwijkt; agenda's waar Mehdi enkel leesrecht heeft (Lara) kan ik niet
    veranderen en meld ik. Geeft (gezet, al_goed, geen_regel, fout)."""
    tok = agenda._toegang()
    nu_dag = datetime.now().date().isoformat()
    gezet, goed, geen, fout, vast = 0, 0, 0, 0, 0
    for a in items:
        if a["start"][:10] < nu_dag or a.get("kalender", "").startswith("en.be#"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if a.get("kalender", "") in AGENDA_VASTE_KLEUR:
            vast += 1          # die agenda heeft een vaste kleur, hier hoort niets gezet
            continue
        info = lees_titel(a["titel"])
        wens = kleur_gewenst(a, info)
        if not wens:
            geen += 1          # geen code in de titel: dat is een fout, geen uitzondering
            continue
        if (a.get("_kleur") or "") == wens:
            goed += 1
            continue
        try:
            _patch(a, {"colorId": wens}, tok)
            gezet += 1
        except Exception as e:  # noqa: BLE001
            fout += 1
            print("kleur mislukt:", a["titel"][:40], type(e).__name__, file=sys.stderr)
    return gezet, goed, geen, fout, vast


# Reistijd, taak van de Agendawacht. Thuisbasis en bufferminuten in de omgeving.
THUIS = os.environ.get("AGENDA_THUIS", "Herfstlaan 65, 3010 Leuven")
BUFFER_MIN = int(os.environ.get("AGENDA_REISTIJD_BUFFER", "10"))
ADRES_CACHE = os.path.expanduser("~/appportal/mijnagents-data/agenda-adressen.json")
DAG_ARG = None
for _i, _a in enumerate(sys.argv):
    if _a == "--dag" and _i + 1 < len(sys.argv):
        DAG_ARG = sys.argv[_i + 1]


def _cache_laden():
    try:
        return json.load(open(ADRES_CACHE))
    except (OSError, ValueError):
        return {}


def _cache_bewaren(c):
    os.makedirs(os.path.dirname(ADRES_CACHE), exist_ok=True)
    json.dump(c, open(ADRES_CACHE, "w"), ensure_ascii=False)


def _nominatim(params):
    import time
    import urllib.parse
    import urllib.request
    time.sleep(1.1)
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "MehdiAgents-agendawacht/1.0 (mch@h-architects.be)"}), timeout=20))
        return [float(d[0]["lat"]), float(d[0]["lon"])] if d else None
    except Exception:  # noqa: BLE001
        return None


def coord(adres, cache):
    """Adres naar coordinaten. Probeert meerdere schrijfwijzen, want een deelgemeente
    zoals "3010 Kessel-Lo" kent Nominatim niet terwijl "3010 Leuven" wel lukt. Gezien
    op 20-09-2026: daardoor kreeg het wekelijkse werfbezoek geen reistijd.
    Een mislukking wordt niet blijvend onthouden; anders blijft hij voor altijd fout."""
    sleutel = adres.strip().lower()
    if cache.get(sleutel):
        return cache[sleutel]

    pogingen = [{"q": adres, "format": "jsonv2", "limit": 1, "countrycodes": "be,nl"}]
    m = re.search(r"^(.*?),?\s*(\d{4})\s+([A-Za-zÀ-ÿ '\-]+)\s*$", adres.strip())
    if m:
        straat, post, gemeente = m.group(1).strip(" ,"), m.group(2), m.group(3).strip()
        # gestructureerd zoeken: postcode telt, de naam van de deelgemeente niet
        pogingen.append({"street": straat, "postalcode": post, "country": "Belgium",
                         "format": "jsonv2", "limit": 1})
        pogingen.append({"q": f"{straat}, {post}", "format": "jsonv2", "limit": 1,
                         "countrycodes": "be,nl"})
        pogingen.append({"q": f"{straat}, {gemeente}, België", "format": "jsonv2", "limit": 1,
                         "countrycodes": "be,nl"})
    for i, params in enumerate(pogingen):
        uit = _nominatim(params)
        if uit:
            if i:
                print(f"adres gevonden via poging {i + 1}: {adres}", file=sys.stderr)
            cache[sleutel] = uit
            return uit
    cache.pop(sleutel, None)   # niet blijvend onthouden dat het mislukte
    return None


# Filefactor op de vrije rijtijd, per vertrekuur op een werkdag (Vlaanderen: ochtend- en
# avondspits). Weekend en feestdagen: 1.0. Mehdi kan dit bijstellen in de werkwijze; de
# tabel hier is de uitvoering ervan.
SPITS = [((7, 0), (9, 30), 1.6), ((6, 30), (7, 0), 1.3), ((9, 30), (10, 0), 1.3),
         ((16, 0), (18, 30), 1.6), ((15, 30), (16, 0), 1.3), ((18, 30), (19, 0), 1.3)]
DAL_FACTOR = 1.1


def filefactor(vertrek):
    if vertrek.weekday() >= 5:
        return 1.0
    u = (vertrek.hour, vertrek.minute)
    for van, tot, f in SPITS:
        if van <= u < tot:
            return f
    return DAL_FACTOR


def vrije_rijtijd_min(van, naar):
    import urllib.request
    url = f"https://router.project-osrm.org/route/v1/driving/{van[1]},{van[0]};{naar[1]},{naar[0]}?overview=false"
    d = json.load(urllib.request.urlopen(url, timeout=20))
    return d["routes"][0]["duration"] / 60


ROUTES_KEY = os.environ.get("GOOGLE_ROUTES_KEY", "").strip()

# Harde dagstop op de Google-aanroepen. Google laat de dagquota van de Routes API niet
# verlagen (in de console staat die rij op "Adjustable: No"), dus houden we de teller
# zelf bij. Bij het plafond rekent de wacht verder met de filefactor en komt het op het
# bord. 100 per dag is ruim: ook een volle maand op het plafond blijft onder de 5.000
# gratis aanvragen per maand.
ROUTES_DAGLIMIET = int(os.environ.get("AGENDA_ROUTES_DAGLIMIET", "100"))
ROUTES_TELLER = os.path.expanduser("~/appportal/mijnagents-data/routes-teller.json")
ROUTES_GESTOPT = False


def routes_vandaag():
    """Geeft (datum, aantal Google-aanroepen vandaag). De teller begint elke dag opnieuw."""
    vandaag = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(ROUTES_TELLER) as f:
            d = json.load(f)
        return vandaag, (int(d["aantal"]) if d.get("dag") == vandaag else 0)
    except (OSError, ValueError, KeyError, TypeError):
        return vandaag, 0


def routes_tel_op():
    """Telt een aanroep mee voordat hij gedaan wordt: een mislukte aanroep telt bij
    Google evengoed mee, dus hier ook."""
    vandaag, aantal = routes_vandaag()
    try:
        os.makedirs(os.path.dirname(ROUTES_TELLER), exist_ok=True)
        with open(ROUTES_TELLER, "w") as f:
            json.dump({"dag": vandaag, "aantal": aantal + 1}, f)
    except OSError as e:  # noqa: BLE001
        print("routes-teller niet weggeschreven:", e, file=sys.stderr)
    return aantal + 1


def google_rijtijd_min(van, naar, vertrek):
    """Rijtijd met live verkeer via Google Routes API (alleen als GOOGLE_ROUTES_KEY gezet is).
    Vertrek moet in de toekomst liggen; anders neemt Google 'nu'. Geeft minuten of None."""
    import urllib.request
    from datetime import timezone
    body = {"origin": {"location": {"latLng": {"latitude": van[0], "longitude": van[1]}}},
            "destination": {"location": {"latLng": {"latitude": naar[0], "longitude": naar[1]}}},
            "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE_OPTIMAL"}
    if vertrek > datetime.now().astimezone():
        body["departureTime"] = vertrek.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request("https://routes.googleapis.com/directions/v2:computeRoutes", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Goog-Api-Key": ROUTES_KEY, "X-Goog-FieldMask": "routes.duration"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=20))
        return float(d["routes"][0]["duration"].rstrip("s")) / 60
    except Exception:  # noqa: BLE001
        return None


def rijtijd_min(van, naar, vertrek):
    """Rijtijd in minuten + buffer, afgerond op 5. Met GOOGLE_ROUTES_KEY: live verkeer van Google
    op het vertrekuur (factor 'live'). Zonder: vrije rijtijd (OSRM) x filefactor op het vertrekuur.
    Geeft (minuten, factor)."""
    global ROUTES_GESTOPT
    import math
    if ROUTES_KEY:
        _, gebruikt = routes_vandaag()
        if gebruikt >= ROUTES_DAGLIMIET:
            ROUTES_GESTOPT = True
        else:
            routes_tel_op()
            live = google_rijtijd_min(van, naar, vertrek)
            if live is not None:
                return int(math.ceil((live + BUFFER_MIN) / 5) * 5), "live"
    vrij = vrije_rijtijd_min(van, naar)
    f = filefactor(vertrek)
    return int(math.ceil((vrij * f + BUFFER_MIN) / 5) * 5), f


def plaatsnaam(adres):
    m = re.search(r"\d{4}\s+([A-Za-zÀ-ÿ' -]+)", adres or "")
    return (m.group(1).strip() if m else (adres or "").split(",")[0]).strip()[:30]


def _insert(kalender, body, tok):
    import urllib.parse
    import urllib.request
    if not mag_schrijven(kalender):
        raise GeenSchrijfrecht(kalender)
    url = f"{agenda.API}/calendars/{urllib.parse.quote(kalender, safe='')}/events"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def reistijd_zetten(items, alleen_dag=None):
    """Werkwijze: elke komende afspraak buiten (!!, of PB/KB met een adres) krijgt een
    blok 'Reistijd -> plaats' ervoor en 'Reistijd <- plaats' erna, met de rijtijd
    vanaf thuis (of de vorige buitenafspraak van die dag) plus buffer, rood, op
    dezelfde agenda. Bestaat er al een reistijdblok binnen drie uur voor of na,
    dan niets. De afspraak zelf krijgt een herinnering op het vertrekmoment plus 5.
    Geeft (gemaakt, al, geen_adres, fout, regels)."""
    from datetime import timedelta
    tok = agenda._toegang()
    cache = _cache_laden()
    thuis = coord(THUIS, cache)
    nu = datetime.now().astimezone()
    gemaakt, al, geen_adres, fout, regels = 0, 0, 0, 0, []
    reistijden = [x for x in items if lees_titel(x["titel"])["reistijd"]]
    projecten = projectadressen.index()
    buiten = []
    for a in items:
        if a.get("hele_dag") or a.get("kalender", "").startswith("en.be#"):
            continue
        info = lees_titel(a["titel"])
        adres = a.get("locatie") or ""
        fysiek = bool(adres) and not adres.lower().startswith("http")
        bron_adres = "agenda"
        if not fysiek and info["nummer"] and info["nummer"] in projecten:
            adres, fysiek, bron_adres = projecten[info["nummer"]]["adres"], True, "projectmap"
        if not fysiek:
            # geen adres in de agenda en geen projectnummer: misschien een vaste plaats
            # uit het adresboek, zoals de school of de zwemles van Lara
            gevonden, naam = adresboek.zoek(a["titel"] + " " + (a.get("omschrijving") or ""))
            if gevonden:
                adres, fysiek, bron_adres = gevonden, True, f"adresboek ({naam})"
        if info["reistijd"] or not (info["buiten"] or info["soort"] in ("PB", "KB")):
            continue
        a["_bron_adres"] = bron_adres
        if fysiek and bron_adres == "agenda" and info["nummer"] in projecten:
            g = projecten[info["nummer"]]["gemeente"].lower()
            if g and g not in adres.lower():
                regels.append(f"{a['start'][:16]} {a['titel'][:50]}: adres in agenda ({adres[:35]}) wijkt af van projectmap {info['nummer']} ({projecten[info['nummer']]['adres'][:35]})")
        try:
            start = datetime.fromisoformat(a["start"]); einde = datetime.fromisoformat(a["einde"])
        except ValueError:
            continue
        if start < nu or (alleen_dag and a["start"][:10] != alleen_dag):
            continue
        buiten.append((start, einde, a, info, adres, fysiek))
    buiten.sort(key=lambda x: x[0])
    # Mandaat van Mehdi, 20-09-2026: "als er twee afspraken buiten zijn en het is ver,
    # dan kom ik niet naar huis om dan te gaan". Dus: de rit terug naar huis maak ik
    # alleen na de laatste buitenafspraak van de dag. Tussen twee buitenafspraken is er
    # één rit, en dat is de heenrit van de volgende. Elke rit draagt in zijn titel van
    # waar naar waar hij gaat.
    per_dag = {}
    for _ in buiten:
        per_dag.setdefault(_[2]["start"][:10], []).append(_)
    laatste_van_de_dag = {d: rij[-1][2].get("id") for d, rij in per_dag.items()}
    vorige_per_dag = {}
    vorige_plaats_per_dag = {}
    for start, einde, a, info, adres, fysiek in buiten:
        dag = a["start"][:10]
        if not fysiek:
            geen_adres += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: geen adres, geen reistijd")
            continue
        doel = coord(adres, cache)
        if not (doel and thuis):
            geen_adres += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: adres niet gevonden ({adres[:40]})")
            continue
        vertrek_van = vorige_per_dag.get(dag, thuis)
        van_plaats = vorige_plaats_per_dag.get(dag, plaatsnaam(THUIS) or "thuis")
        vorige_per_dag[dag] = doel
        is_laatste = laatste_van_de_dag.get(dag) == a.get("id")
        # Zuinig met aanvragen (Google Routes Pro: 5.000 gratis per maand): bestaan mijn twee
        # blokken al, dan herbereken ik alleen in de eerste ronde van de dag (voor 08:00) of met --dag.
        def _bestaand(t0, t1):
            for x in reistijden:
                if x["kalender"] == a["kalender"] and "T" in x["start"] and t0 <= datetime.fromisoformat(x["start"]) <= t1:
                    return x
            return None
        if (_bestaand(start - timedelta(hours=3), start) and _bestaand(einde, einde + timedelta(hours=3))
                and nu.hour >= 8 and not DAG_ARG):
            al += 2
            continue
        try:
            # eerste schatting om het vertrekuur te kennen, dan de filefactor op dat uur
            heen, _ = rijtijd_min(vertrek_van, doel, start)
            heen, fh = rijtijd_min(vertrek_van, doel, start - timedelta(minutes=heen))
            terug, ft = (rijtijd_min(doel, thuis, einde) if is_laatste else (0, ""))
        except Exception as e:  # noqa: BLE001
            fout += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: rijtijd niet berekend ({type(e).__name__})")
            continue
        plaats = plaatsnaam(adres)
        vorige_plaats_per_dag[dag] = plaats
        def bestaand(t0, t1):
            for x in reistijden:
                if x["kalender"] == a["kalender"] and "T" in x["start"] and t0 <= datetime.fromisoformat(x["start"]) <= t1:
                    return x
            return None

        def eigen(x):
            return "OSRM" in (x.get("omschrijving") or "")

        def bijwerken(x, s, e, tekst):
            """Een blok dat ik zelf maakte, pas ik aan als de rijtijd meer dan 10 min verschilt."""
            duur_oud = (datetime.fromisoformat(x["einde"]) - datetime.fromisoformat(x["start"])).total_seconds() / 60
            if eigen(x) and abs(duur_oud - (e - s).total_seconds() / 60) >= 10:
                _patch(x, {"start": {"dateTime": s.isoformat()}, "end": {"dateTime": e.isoformat()}, "description": tekst}, tok)
                return True
            return False
        uitleg_h = f"Reistijd voor: {a['titel']} ({heen} min = " + ("live verkeer Google" if fh == "live" else f"vrije rijtijd x filefactor {fh}") + f" + {BUFFER_MIN} min buffer, OSRM; adres uit {bron_adres})"
        uitleg_t = f"Reistijd na: {a['titel']} ({terug} min = " + ("live verkeer Google" if ft == "live" else f"vrije rijtijd x filefactor {ft}") + f" + {BUFFER_MIN} min buffer, OSRM)"
        kleur = {"colorId": "11", "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 5}]}}
        try:
            x = bestaand(start - timedelta(hours=3), start)
            if x:
                al += 1
                if bijwerken(x, start - timedelta(minutes=heen), start, uitleg_h):
                    gemaakt += 1
            else:
                _insert(a["kalender"], {"summary": f"🚗 Reistijd: {van_plaats} → {plaats}", "start": {"dateTime": (start - timedelta(minutes=heen)).isoformat()},
                                        "end": {"dateTime": start.isoformat()}, "description": uitleg_h, **kleur}, tok)
                gemaakt += 1
            x = bestaand(einde, einde + timedelta(hours=3)) if is_laatste else None
            if not is_laatste:
                regels.append(f"{a['start'][:16]} {a['titel'][:44]}: geen rit naar huis, je gaat door naar de volgende buitenafspraak")
            if x:
                al += 1
                if bijwerken(x, einde, einde + timedelta(minutes=terug), uitleg_t):
                    gemaakt += 1
            elif is_laatste:
                _insert(a["kalender"], {"summary": f"🚗 Reistijd: {plaats} → {plaatsnaam(THUIS) or 'thuis'}", "start": {"dateTime": einde.isoformat()},
                                        "end": {"dateTime": (einde + timedelta(minutes=terug)).isoformat()}, "description": uitleg_t,
                                        **{"colorId": "11", "reminders": {"useDefault": False, "overrides": []}}}, tok)
                gemaakt += 1
            _patch(a, {"reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": heen + 5}]}}, tok)
            regels.append(f"{a['start'][:16]} {a['titel'][:44]}: {van_plaats} → {plaats} {heen} min (file x{fh})"
                          + (f", terug naar huis {terug} min (file x{ft})" if is_laatste else ", daarna door naar de volgende")
                          + f", adres uit {bron_adres}, melding {heen + 5} min vooraf")
        except Exception as e:  # noqa: BLE001
            fout += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: reistijd niet gezet ({type(e).__name__})")
    _cache_bewaren(cache)
    return gemaakt, al, geen_adres, fout, regels


def onvolledige_afspraken(items, vandaag):
    """Regel van Mehdi (11-09-2026): elke klantafspraak draagt een projectnummer; online volstaat
    het nummer, buiten moet er ook een adres zijn (uit de agenda of uit de projectmap).
    Prospecten (PO/PB) hebben nog geen nummer: daar vraag ik alleen een adres bij buiten."""
    projecten = projectadressen.index()
    uit = []
    for a in items:
        if a.get("hele_dag") or a["start"][:10] < vandaag or a.get("kalender", "").startswith("en.be#") or a.get("_terugkerend"):
            continue
        info = lees_titel(a["titel"])
        if info["reistijd"] or info["soort"] == "IN" or not (info["firma"] or info["buiten"]):
            continue
        adres = a.get("locatie") or ""
        fysiek = bool(adres) and not adres.lower().startswith("http")
        wat = []
        if info["soort"] in ("KB", "KO") and not info["nummer"]:
            wat.append("geen projectnummer")
        if info["soort"] in ("KB", "PB") or info["buiten"]:
            if not fysiek and not (info["nummer"] in projecten):
                wat.append("geen adres (niet in agenda, geen projectmap met dit nummer)")
        if wat:
            uit.append(f"{a['start'][:16]} {a['titel'][:60]} ({KALENDERS.get(a['kalender'], '')[:12]}): " + ", ".join(wat))
    return uit


BEL_ONLINE_MIN = int(os.environ.get("AGENDA_BEL_ONLINE", "5"))
BEL_BUITEN_MIN = int(os.environ.get("AGENDA_BEL_BUITEN", "30"))


def belrooster(items, vandaag):
    """Regel van Mehdi (11-09-2026): voor elke afspraak effectief gebeld worden, een gemiste
    oproep volstaat. Online: BEL_ONLINE_MIN minuten vooraf. Buiten: op het vertrekmoment
    (start van mijn reistijdblok), anders BEL_BUITEN_MIN vooraf. Niet voor intern (IN),
    terugkerend, hele dag, reistijd, Lara, feestdagen."""
    from datetime import timedelta
    reistijden = [x for x in items if lees_titel(x["titel"])["reistijd"] and "T" in x["start"]]
    regels = []
    for a in items:
        if a.get("hele_dag") or a.get("_terugkerend") or a["start"][:10] < vandaag or a.get("kalender", "").startswith("en.be#"):
            continue
        kal = KALENDERS.get(a["kalender"], "")
        info = lees_titel(a["titel"])
        if info["reistijd"] or info["soort"] == "IN" or kal == "Lara":
            continue
        start = datetime.fromisoformat(a["start"])
        adres = a.get("locatie") or ""
        buiten = info["buiten"] or info["soort"] in ("KB", "PB") or (adres and not adres.lower().startswith("http"))
        if buiten:
            blok = [x for x in reistijden if x["kalender"] == a["kalender"] and start - timedelta(hours=3) <= datetime.fromisoformat(x["start"]) < start]
            beltijd = datetime.fromisoformat(blok[-1]["start"]) if blok else start - timedelta(minutes=BEL_BUITEN_MIN)
            hoe = "vertrekken" if blok else f"over {BEL_BUITEN_MIN} minuten vertrekken"
        else:
            beltijd = start - timedelta(minutes=BEL_ONLINE_MIN)
            hoe = f"over {BEL_ONLINE_MIN} minuten online"
        klant = info["klant"] or a["titel"][:60]
        tekst = f"Mehdi, {hoe}: {klant}, om {start.strftime('%H:%M')}." + (" De link staat in je agenda." if not buiten else " Adres staat in je agenda.")
        regels.append({"sleutel": f"{a['kalender']}:{a['id']}:{a['start']}", "tijd": beltijd.isoformat(), "tekst": tekst, "titel": a["titel"][:80]})
    regels.sort(key=lambda r: r["tijd"])
    return regels


def botsingen(items):
    """Twee afspraken die elkaar overlappen op dezelfde dag (bv. een Zoom tijdens een opmeting)."""
    uit = []
    tijd = [(datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["einde"]), x) for x in items
            if "T" in x["start"] and not lees_titel(x["titel"])["reistijd"] and not x.get("kalender", "").startswith("en.be#")]
    tijd.sort(key=lambda t: t[0])
    for i, (s1, e1, a) in enumerate(tijd):
        for s2, e2, b in tijd[i + 1:]:
            if s2 >= e1:
                break
            uit.append(f"{a['start'][:16]} {a['titel'][:45]}  ×  {b['start'][11:16]} {b['titel'][:45]}")
    return uit


def main():
    werkwijze = ag.werkwijze()
    ag.hartslag("actief", taak="agenda lezen")
    try:
        if not agenda.beschikbaar():
            ag.hartslag("fout", taak="geen agendatoegang", detail="GOOGLE_AGENDA_* ontbreekt in ~/appportal/.env")
            return
        os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())   # agenda.kalenders() leest die
        items = agenda.afspraken(-1, 8)
        fouten = [i for i in items if i.get("fout")]
        items = [i for i in items if not i.get("fout")]
        deals = deals_index()
        vandaag = datetime.now().date().isoformat()
        gisteren = (datetime.now().date() - timedelta(days=1)).isoformat()
        klaar, gekoppeld, niet_conform, dagplan, gisteren_lijst = [], 0, [], [], []
        per_afdeling = {}
        for a in items:
            info = lees_titel(a["titel"])
            if info["reistijd"] or a["kalender"] == "en.be#holiday@group.v.calendar.google.com":
                continue
            kal = KALENDERS.get(a["kalender"], a["kalender"])
            dag = a["start"][:10]
            afdeling = FIRMA_AFDELING.get(info["firma"]) or KALENDER_AFDELING.get(kal) or "mehdi"
            deal, hoe = (None, "")
            if afdeling == "h-architects":
                deal, hoe = koppel(info, a["titel"], deals)
                gekoppeld += 1 if deal else 0
            if not info["conform"] and kal not in ("Lara", "Prive Buiten", "Feestdagen BE") and dag >= vandaag:
                niet_conform.append(f"{dag} {a['start'][11:16]} {a['titel']} ({kal})")
            oms = ", ".join(x for x in (SOORT.get(info["soort"], ""), TYPES.get(info["type"], ""),
                                        "buiten + reistijd" if info["buiten"] else "", "niet bevestigd" if info["onzeker"] else "") if x)
            regel = f"{'hele dag' if a['hele_dag'] else a['start'][11:16]} {a['titel']}" + (f" [{oms}]" if oms else "") + (f" · deal {deal['id']}" if deal else "")
            if dag == vandaag:
                dagplan.append(regel)
            if dag == gisteren and (info["soort"] in ("KB", "PB", "KO", "PO") or deal):
                gisteren_lijst.append(regel)
            if dag >= vandaag and afdeling != "mehdi":
                per_afdeling[afdeling] = per_afdeling.get(afdeling, 0) + 1
                klaar.append({"voor": afdeling, "soort": "afspraak", "sleutel": str(deal["id"]) if deal else (info["nummer"] or ""),
                              "titel": f"{dag} {regel}", "uniek": f"agenda:{a['kalender']}:{a['id']}", "verwijzing": a.get("link", ""),
                              "inhoud": {"datum": dag, "start": a["start"], "einde": a["einde"], "titel": a["titel"], "agenda": kal,
                                         "firma": info["firma"], "soort": info["soort"], "type": info["type"], "nummer": info["nummer"],
                                         "klant": info["klant"], "buiten": info["buiten"], "onzeker": info["onzeker"],
                                         "locatie": a["locatie"], "deelnemers": a["deelnemers"],
                                         "deal_id": deal["id"] if deal else None, "koppeling": hoe, "omschrijving": a["omschrijving"][:800]}})
        tekst = "Vandaag:\n" + ("\n".join("- " + r for r in dagplan) or "- niets in de agenda") + \
                "\n\nGisteren, klantcontact waar een verslag of opname bij hoort:\n" + ("\n".join("- " + r for r in gisteren_lijst) or "- niets")
        klaar.append({"voor": "mehdi", "soort": "dagplan", "sleutel": vandaag, "titel": f"Dagplan {vandaag}", "uniek": f"dagplan:{vandaag}", "inhoud": tekst})
        if niet_conform:
            klaar.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(niet_conform)} afspraken zonder code ([HA-KB] enz.)",
                          "uniek": f"agenda-conventie:{vandaag}", "inhoud": "\n".join("- " + x for x in niet_conform[:40])})
        onvolledig = onvolledige_afspraken(items, vandaag)
        if onvolledig:
            klaar.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(onvolledig)} afspraken zonder projectnummer of adres",
                          "uniek": f"agenda-onvolledig:{vandaag}", "inhoud": "\n".join("- " + x for x in onvolledig[:40])})
        uit = ag.klaarzet(klaar)
        dag_grens = DAG_ARG or (vandaag if ALLEEN_VANDAAG else None)
        rg, ral, rgeen, rfout, rregels = reistijd_zetten(items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"reistijd: {rg} blok(ken) gemaakt, {ral} bestonden al, {rgeen} zonder adres, {rfout} mislukt", "\n".join(rregels))
        # Een rit die niet berekend raakte mag nooit alleen een cijfer zijn: dan ziet
        # Mehdi niet welke afspraak zonder reistijd staat. Gezien 20-09-2026, toen het
        # wekelijkse werfbezoek geen rit kreeg omdat "3010 Kessel-Lo" niet om te zetten was.
        zonder_rit = {"geen adres in de agenda": [], "adres niet gevonden": [], "rijtijd niet berekend": []}
        for regel in rregels:
            if "geen adres, geen reistijd" in regel:
                zonder_rit["geen adres in de agenda"].append(regel.split(":")[0][:80])
            elif "adres niet gevonden" in regel:
                zonder_rit["adres niet gevonden"].append(regel[:110])
            elif "rijtijd niet berekend" in regel:
                zonder_rit["rijtijd niet berekend"].append(regel[:110])

        rooster = belrooster(items, vandaag)
        bellen.rooster_schrijven(rooster)
        ag.log(f"dag {vandaag}", "schrijf", f"belrooster: {len(rooster)} oproepen gepland (online {BEL_ONLINE_MIN} min vooraf, buiten op het vertrekmoment)",
               "\n".join(f"{r['tijd'][:16]} bel: {r['titel']}" for r in rooster[:60]))
        bots = [b for b in botsingen(items) if b[:10] >= vandaag]
        if bots:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(bots)} botsende afspraken in de komende week",
                          "uniek": f"agenda-botsing:{vandaag}", "inhoud": "\n".join("- " + b for b in bots)}])
            ag.log(f"dag {vandaag}", "bevinding", f"{len(bots)} botsende afspraken", "\n".join(bots))
        kg, kgoed, kgeen, kfout, kvast = kleuren_zetten(items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"kleuren: {kg} gezet, {kgoed} klopten al, {kvast} op een agenda met vaste kleur, {kgeen} ZONDER CODE (fout), {kfout} niet gelukt",
               "\n".join(f"{a['start'][:16]} {a['titel'][:60]} -> {KLEURNAAM.get(kleur_gewenst(a, lees_titel(a['titel'])), 'laten staan')}" for a in items if a['start'][:10] >= vandaag and (not dag_grens or a['start'][:10] == dag_grens)))
        gezet, al, weg, fout_h = herinneringen_zetten(items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"herinneringen (alles behalve intern): {gezet} gezet (online {ONLINE_MIN} min, buiten {BUITEN_MIN} min), {al} hadden er al een, {weg} weggehaald van intern, {fout_h} mislukt",
               "\n".join(f"{'MELDING ' if melding_gewenst(a)[0] else 'stil    '} {a['start'][:16]} {a['titel'][:70]}" for a in items if a['start'][:10] >= vandaag and not a.get('hele_dag')))
        ag.log(f"dag {vandaag}", "bron", f"{len(items)} afspraken uit {len(kalenders())} agenda's; {gekoppeld} H-A-afspraken aan een deal gekoppeld; per afdeling: " +
               ", ".join(f"{k} {v}" for k, v in sorted(per_afdeling.items())) + (f"; {len(fouten)} agenda's niet leesbaar: " + ", ".join(f['kalender'] for f in fouten) if fouten else ""),
               "\n".join(f"{a['start'][:16]} {KALENDERS.get(a['kalender'], a['kalender'])[:14]} | {a['titel']}" for a in items))
        ag.log(f"dag {vandaag}", "bevinding", f"{len(niet_conform)} toekomstige afspraken zonder code", "\n".join(niet_conform[:60]))
        ag.log(f"dag {vandaag}", "schrijf", f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend", tekst)
        if ROUTES_KEY:
            _, routes_gebruikt = routes_vandaag()
            ag.log(f"dag {vandaag}", "bron", f"Google Routes: {routes_gebruikt} van {ROUTES_DAGLIMIET} aanroepen vandaag"
                   + (" (plafond bereikt, reistijden verder op de filefactor)" if ROUTES_GESTOPT else ""))
        ag.log_verstuur()
        # Norm N4: melden welk regelboek ik deze ronde las, zodat achteraf te zien is
        # welke versie van de regels gold toen ik iets deed.
        try:
            ag.kennis(f"werkwijze van het bord, {len(werkwijze or '')} tekens; "
                      f"afspraken uit werkwijze/agenda-taken.json; "
                      f"firmacodes uit organisatie.globaal.be ({len(FIRMACODES)} firma's)",
                      bron="bord + agenda-taken.json + kern.firma")
        except Exception:  # noqa: BLE001
            pass
        # Norm N10: een nood draagt geen aantal in zijn tekst, anders is elke ronde
        # formeel een nieuwe nood en sluit de lus nooit. Het aantal hoort in het detail.
        noden = []
        # Een rit die niet berekend raakte mag nooit alleen een cijfer zijn, anders ziet
        # Mehdi niet welke afspraak zonder reistijd staat. Gezien 20-09-2026, toen het
        # wekelijkse werfbezoek geen rit kreeg omdat "3010 Kessel-Lo" niet om te zetten was.
        rit_signalen = []
        for reden, rij in zonder_rit.items():
            if not rij:
                continue
            rit_signalen.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                                 "titel": f"Buitenafspraak zonder reistijd: {reden}",
                                 "uniek": f"agenda-reistijd-{reden[:18]}:{vandaag}",
                                 "inhoud": "\n".join("- " + x for x in rij[:30])})
            noden.append({"tekst": f"Buitenafspraken zonder reistijd, reden: {reden}", "wie": "mehdi"})
        if rit_signalen:
            ag.klaarzet(rit_signalen)
        titel_fouten = {}
        for a in items:
            if a.get("fout"):
                continue
            inf = lees_titel(a.get("titel", ""))
            for reden in titelfouten(a, inf):
                titel_fouten.setdefault(reden, []).append(f"{a['start'][:16]} {a.get('titel','')[:58]}")
        for reden, rij in sorted(titel_fouten.items()):
            klaar.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": f"Titels: {reden}", "uniek": f"agenda-titel-{reden[:20]}:{vandaag}",
                          "inhoud": "\n".join("- " + x for x in rij[:40])})
            noden.append({"tekst": f"Afspraken met een titel die niet klopt: {reden}", "wie": "mehdi"})
        if niet_conform and "geen firmacode" not in titel_fouten:
            noden.append({"tekst": "Afspraken zonder firmacode in de titel: rechtzetten, anders krijgen ze geen kleur",
                          "wie": "mehdi"})
        if onvolledig:
            noden.append({"tekst": "Buitenafspraken zonder adres: zonder adres kan ik geen reistijd berekenen",
                          "wie": "mehdi"})
        try:
            ontbreekt = adresboek.onvolledig()
        except Exception:  # noqa: BLE001
            ontbreekt = []
        if ontbreekt:
            noden.append({"tekst": "Vaste plaatsen zonder adres in het adresboek: " + ", ".join(ontbreekt),
                          "wie": "mehdi"})
        if fout_h:
            noden.append({"tekst": "Herinneringen konden niet gezet worden", "wie": "claude-code"})
        if ROUTES_GESTOPT:
            noden.append({"tekst": "Dagplafond van de Google Routes API bereikt; reistijden lopen verder op "
                                   "de filefactor. Klopt dat met het aantal buitenafspraken, dan mag "
                                   "AGENDA_ROUTES_DAGLIMIET omhoog", "wie": "claude-code"})
        if fouten:
            noden.append({"tekst": "Agenda's die ik niet kan lezen: " + ", ".join(f["kalender"][:30] for f in fouten),
                          "wie": "mehdi"})
        ag.hartslag("waakt", taak="agenda in het oog",
                    detail=f"vandaag {len(dagplan)} afspraken; {gekoppeld} gekoppeld; "
                           f"{len(niet_conform)} zonder code; "
                           f"{len(onvolledig)} zonder adres",
                    nood=noden)
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()
