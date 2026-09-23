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


def externe_relaties():
    """Externe partijen die bewust niet op organisatie.globaal.be staan: leveranciers
    en hun contactpersonen, plus de overkoepelende firmacode ALGE. Een aparte lijst,
    want het dashboard is de interne organisatie. Mandaat van Mehdi, 22-09-2026."""
    pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "werkwijze", "externe-relaties.json")
    try:
        return json.load(open(pad, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"overkoepelende_firmas": {}, "relaties": []}


EXTERNE = externe_relaties()
EXTERNE_FIRMAS = EXTERNE.get("overkoepelende_firmas", {})   # ALGE = algemeen/overkoepelend
EXTERNE_RELATIES = EXTERNE.get("relaties", [])              # Nadien (boekhouder), Wally (AI-software), ...

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
# De schrijfwijzen die Mehdi in zijn agenda gebruikte voor de firmacodes van
# organisatie.globaal.be de norm werden. Ze blijven leesbaar, zodat een afspraak van
# vorig jaar bij dezelfde firma terechtkomt als een van vandaag. "EE" gebruikte hij
# voor Energie Efficiënt, ook los in een titel zoals "AI & EE" (20-09-2026).
AGENDACODE_NAAR_FIRMA = {"HA": "HARC", "UNABO": "UNAB", "HB": "HARM", "HARMONIEBOUW": "HARM",
                         "CONTRAX": "CONT", "ENERGIE": "ENEF", "EE": "ENEF", "TKN": "TKNB",
                         "ELEVAIT": "ELEV"}

# PRIVE is geen firma maar hoort wel in een titel te mogen staan.
NIET_FIRMA = {"PRIVE": "privé van Mehdi"}

# Welke code op welk bord-afdeling terechtkomt. Alleen de afdelingen die op het
# bord bestaan; een firma zonder afdeling lees ik wel maar zet ik nergens klaar.
FIRMA_AFDELING = {"HARC": "h-architects", "UNAB": "unabo", "HARM": "harmoniebouw", "CONT": "contrax",
                  "TKNB": "tkn", "ELEV": "elevait", "ENEF": "unabo", "PRIVE": "prive"}
KALENDER_AFDELING = {"H-Architects": "h-architects", "UNABO": "unabo",
                     "zoomafspraken (sales via Calendly)": "h-architects"}
# L van leverancier: een extern bedrijf waar Mehdi de klant wordt. Dat is geen klant
# en geen prospect, en het onder prospect zetten draait de rollen om. Mandaat van
# Mehdi, 20-09-2026, gevonden bij de gesprekken met LegalFly en Libra AI.
SOORT = {"KB": "klant buiten", "PB": "prospect buiten (plaatsbezoek)", "KO": "klant online",
         "PO": "prospect online", "LB": "leverancier buiten (wij kopen)",
         "LO": "leverancier online (wij kopen)", "IN": "intern",
         # B2B: een externe professionele partij waar wij nog GEEN klant van zijn. Een
         # leverancier is hetzelfde, maar daar zijn we al klant. Mandaat van Mehdi,
         # 22-09-2026, gezien bij de Calendly-boeking [HA-B2B] Stefan Oosterbaan.
         "B2B": "professioneel extern, wij nog geen klant",
         # A van aannemer: als architect heeft Mehdi veel afspraken met aannemers van zijn klanten.
         # Geen klant, geen leverancier: een eigen soort. Mandaat van Mehdi, 23-09-2026.
         "AB": "aannemer buiten", "AO": "aannemer online"}
# Centraal, zodat een nieuwe soort nergens vergeten wordt (23-09-2026).
BUITEN_SOORTEN = ("PB", "KB", "LB", "AB")             # per definitie buiten
EXTERN_ONLINE = ("KO", "PO", "LO", "B2B", "AO")       # online met iemand van buiten: alleen geparkeerd
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

ALLE_CODES = sorted(set(FIRMACODES) | set(EXTERNE_FIRMAS) | set(AGENDACODE_NAAR_FIRMA) | set(NIET_FIRMA), key=len, reverse=True)
CODE_RE = re.compile(r"\[(" + "|".join(ALLE_CODES) + r")(?:-(" + "|".join(sorted(SOORT, key=len, reverse=True)) + r"))?\]", re.I)


def kalenders():
    ruw = os.environ.get("AGENDA_KALENDERS", "").strip()
    lijst = [k.strip() for k in ruw.split(",") if k.strip()] or list(KALENDERS)
    return [k for k in lijst if k not in gearchiveerd()]



def afspraken(van_dagen=-1, tot_dagen=8):
    """De afspraken van precies de agenda's die de Agendawacht leest. Eén plek, zodat de
    controle en de filewacht dezelfde agenda's zien als de agent. Gezien 21-09-2026:
    zij lazen alleen de werkagenda en zoomafspraken, niet Lara en niet privé."""
    os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())   # agenda.kalenders() leest die
    return agenda.afspraken(van_dagen, tot_dagen)



# Hoe ver vooruit ik ritten zet. Gewoon acht dagen, want werkafspraken schuiven. De
# agenda van Lara loopt in vaste reeksen per schooljaar; die ritten zet ik tot het
# einde ervan, zodat Mehdi ze vooruit ziet. Mandaat van Mehdi, 21-09-2026.
RIT_VOORUIT_DAGEN = {"Lara": 300}


def verre_afspraken():
    """De afspraken voorbij de gewone acht dagen, alleen van de agenda's in RIT_VOORUIT_DAGEN."""
    uit = []
    for kid, naam in KALENDERS.items():
        dagen = RIT_VOORUIT_DAGEN.get(naam)
        if dagen and kid in kalenders():
            os.environ["CONTRACTEN_KALENDERS"] = kid
            uit += agenda.afspraken(8, dagen)
    os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())
    return uit


def afspraken_dag(dag):
    """Alle afspraken van één dag, ook verder dan acht dagen. Zo werkt een wijziging op
    een verre dag (een reeks van Lara in november) ook de rit bij."""
    offset = (datetime.fromisoformat(dag).date() - datetime.now().date()).days
    return [a for a in afspraken(offset - 1, offset + 2) if a.get("start", "")[:10] == dag]


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
        if info["reistijd"]:
            continue   # een rit draagt zijn eigen melding, die zet reistijd_zetten
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
            elif not gewenst:
                # Stil is expliciet GEEN melding, niet de standaard van de agenda: die is op de
                # werkagenda 30 minuten en op Lara 10 minuten. Gezien 23-09-2026: "stil maken"
                # zette alles terug op die standaard, zodat 21 interne overleggen per week 30 min
                # vooraf rinkelden en de marker van Lara om 23:50 de avond ervoor.
                STIL = {"useDefault": False, "overrides": []}
                standaard = r.get("useDefault", True) and not eigen
                buitenachtig = info["buiten"] or info["soort"] in BUITEN_SOORTEN
                if mijn and (a.get("hele_dag") or not buitenachtig):
                    # een melding die ik vroeger zelf zette; op een buitenafspraak is die ene
                    # melding het vertrekmoment plus vijf (reistijd_zetten), die laat ik staan
                    _patch(a, {"reminders": STIL}, tok)
                    weg += 1
                elif standaard and (info["soort"] == "IN" or a.get("hele_dag")):
                    # intern en hele-dag-items blijven stil; de agenda-standaard telt niet als
                    # een melding die Mehdi zelf zette
                    _patch(a, {"reminders": STIL}, tok)
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


PLEKKEN_URL = os.environ.get("LOCATIE_URL", "http://127.0.0.1:3031") + "/api/plekken"
_plekken = {"tot": 0.0, "lijst": []}


def plekken():
    """De benoemde plaatsen uit locatie.globaal.be: naam, coordinaten en straal.
    Dat is de bron voor plaatsen. De agent houdt er geen eigen adresboek van bij;
    mandaat van Mehdi, 20-09-2026."""
    import time
    import urllib.request
    if _plekken["lijst"] and time.time() < _plekken["tot"]:
        return _plekken["lijst"]
    try:
        with urllib.request.urlopen(PLEKKEN_URL, timeout=15) as r:
            d = json.load(r)
        lijst = d if isinstance(d, list) else (d.get("plekken") or d.get("items") or [])
    except Exception:  # noqa: BLE001
        lijst = _plekken["lijst"]
    _plekken["lijst"], _plekken["tot"] = lijst, time.time() + 3600
    return lijst


def plek_zoeken(tekst):
    """Geeft (adres of 'lat,lon', naam) van de eerste benoemde plek die in de tekst staat."""
    t = (tekst or "").lower()
    if not t:
        return None, None
    for p in plekken():
        naam = (p.get("naam") or "").strip()
        # Thuis is het vertrekpunt, nooit een bestemming die ik uit een titel haal:
        # "Lara ophalen en thuis afzetten" gebeurt niet thuis. Gezien 21-09-2026, toen
        # maakte ik een rit van thuis naar thuis.
        if not naam or p.get("soort") == "thuis" or naam.lower() == "thuis":
            continue
        if re.search(r"(?<![\w])" + re.escape(naam.lower()) + r"(?![\w])", t):
            if p.get("adres"):
                return p["adres"], naam
            if p.get("lat") and p.get("lon"):
                return f"{p['lat']},{p['lon']}", naam
    return None, None


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


# De agenda- en boekingsaccounts zijn geen personen in kern.persoon; voor die
# adressen zeg ik zelf wat ze zijn. Een echt persoon zoek ik op in
# organisatie.globaal.be, dat blijft de bron voor mensen.
BOEKINGSACCOUNTS = {
    "mehdiprivewerkagenda@gmail.com": "Mehdi zelf",
    "siyanhdswerk@gmail.com": "Siyan",
    "haagendalightprojects@gmail.com": "Calendly (light projects)",
    "zoomafspraken@gmail.com": "Calendly (zoom)",
    "unabosdp@gmail.com": "Calendly (UNABO)",
    "contraxcalendar@gmail.com": "Calendly (Contrax)",
}


def maker(a):
    """Wie de afspraak heeft aangemaakt, als een naam die Mehdi herkent. Een
    boekingsaccount noem ik bij zijn rol, een echt persoon zoek ik op in
    organisatie.globaal.be, en anders toon ik het deel voor de @. Mandaat van
    Mehdi, 22-09-2026: zo weet hij wie iets zette en waarom het ergens staat."""
    mail = (a.get("maker") or "").strip().lower()
    if not mail:
        return ""
    if mail in BOEKINGSACCOUNTS:
        return BOEKINGSACCOUNTS[mail]
    try:
        p = organisatie.herken(mail)
    except Exception:  # noqa: BLE001
        p = None
    if p:
        return p["naam"].split(" (")[0]
    return mail.split("@")[0]



# ---------------------------------------------------------------------------------------
# In één keer goed zetten. Mandaat van Mehdi, 23-09-2026: "ik schrijf wat er moet, leer het
# om in een keer goed te zetten." Hij typt vrije tekst ("Harchitects-KB 2505", "elevait-
# Leverancie online"); de agent maakt er de titelcode van als dat eenduidig kan, anders doet
# hij een voorstel. En een online afspraak zonder link krijgt zijn vaste Zoom.
# ---------------------------------------------------------------------------------------
# De vaste Zoom-link van Mehdi is nog niet gekend: 9432885212 kwam het vaakst voor in de agenda, maar
# Mehdi zei op 23-09-2026 "stuur nog geen linken omdat je hebt die niet". Tot hij de juiste link geeft,
# zet de agent GEEN link, alleen de notitie dat Mehdi de link stuurt.
VASTE_ZOOM = ""
WERKAGENDA = "mehdiprivewerkagenda@gmail.com"
KANTELDATUM = "2026-09-21"                            # vanaf hier dragen nieuwe afspraken de vierletterige code
SOORT_CODES = set(SOORT)


def _plat(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def firma_aliassen():
    """Elke schrijfwijze van een firma die Mehdi typt -> de vierletterige code."""
    uit = {}
    for code, naam in {**FIRMACODES, **EXTERNE_FIRMAS}.items():
        uit[_plat(code)] = code
        kern = naam.split(" (")[0]
        uit[_plat(kern)] = code                     # "H-Architects" -> harchitects
        eerste = _plat(kern.split()[0]) if kern.split() else ""
        if len(eerste) >= 5:
            uit.setdefault(eerste, code)            # "Elevait NV" -> elevait
    for oud, nieuw in AGENDACODE_NAAR_FIRMA.items():
        uit[_plat(oud)] = nieuw
    return uit


def _van_mehdi(a):
    m = (a.get("maker") or "").lower()
    return m in ("", WERKAGENDA) and a.get("kalender") != "zoomafspraken@gmail.com" and not a.get("deelnemers")


def titel_voorstel(titel):
    """Leest vrije tekst en geeft (nieuwe titel of None, firma, soort, uitleg)."""
    if CODE_RE.search(titel) or ":" not in titel:
        return None, None, None, ""
    kop, rest = titel.split(":", 1)
    alias = firma_aliassen()
    relaties = {}
    for r in EXTERNE_RELATIES:
        for nm in [r.get("naam") or ""] + list(r.get("ook_geschreven") or []):
            if nm:
                relaties[_plat(nm)] = r.get("firma") or "ALGE"
    firma, soort_code, rol, waar = None, None, None, None
    weg = []
    for tok in re.split(r"[\s,;()\[\]/]+", rest):
        if not tok:
            continue
        delen = [tok] + tok.split("-")
        for d in delen:
            pd = _plat(d)
            if not pd:
                continue
            if pd in alias and firma in (None, alias[pd]):
                firma = alias[pd]; weg.append(tok if d == tok else d)
            elif pd in relaties and firma in (None, relaties[pd]):
                firma = relaties[pd]; rol = rol or "L"          # de naam blijft in de titel staan
            elif d.upper() in SOORT_CODES:
                soort_code = d.upper(); weg.append(d)
            elif pd.startswith("klant"):
                rol = "K"; weg.append(d)
            elif pd.startswith("prospect"):
                rol = "P"; weg.append(d)
            elif pd.startswith("aanne"):
                rol = "A"; weg.append(d)
            elif pd.startswith("leveranc") or pd.startswith("leverancie"):
                rol = "L"; weg.append(d)
            elif pd == "intern":
                rol = "IN"; weg.append(d)
            elif pd == "online":
                waar = "O"; weg.append(d)
            elif pd == "buiten":
                waar = "B"; weg.append(d)
    if not firma:
        return None, None, None, ""
    if not waar:
        waar = "B" if "!!" in titel else "O"
    soort = soort_code or ("IN" if rol == "IN" else (rol + waar if rol else None))
    over = rest
    for w in sorted(set(weg), key=len, reverse=True):
        over = re.sub(r"(?<![\w])" + re.escape(w) + r"(?![\w])", " ", over)
    over = re.sub(r"\s*-\s*(?=\s|$)", " ", over)
    over = re.sub(r"\s+", " ", over).strip(" -,")
    code = f"[{firma}-{soort}]" if soort else f"[{firma}]"
    nieuw = f"{kop.strip()}: {code}" + (f" {over}" if over else "")
    uitleg = f"firma {firma} uit de tekst" + (f", soort {soort}" if soort else ", soort niet te bepalen")
    return nieuw, firma, soort, uitleg


def titels_normaliseren(items, alleen_dag=None):
    """Vrije tekst naar de titelcode, alleen voor afspraken die Mehdi zelf maakte, zonder gasten.
    Eenduidig (firma én soort) -> herschrijven. Anders -> een voorstel in de regels.
    Een oude code in een nieuwe afspraak (na de kanteldatum) -> de vierletterige code."""
    tok = agenda._toegang()
    nu = datetime.now().astimezone().isoformat()
    gedaan, regels = 0, []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a["start"] < nu[:len(a["start"])]:
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if a.get("kalender") != WERKAGENDA or lees_titel(a["titel"])["reistijd"]:
            continue
        titel = a["titel"]
        info = lees_titel(titel)
        nieuw = None
        if info.get("agendacode") and (a.get("_gemaakt") or "")[:10] >= KANTELDATUM and _van_mehdi(a):
            nieuw = re.sub(r"\[" + re.escape(info["agendacode"]) + r"(?=[-\]])", "[" + info["firma"], titel, count=1, flags=re.I)
            uitleg = f"oude code {info['agendacode']} in een nieuwe afspraak -> {info['firma']}"
        elif not info.get("firma"):
            nieuw, firma, soort, uitleg = titel_voorstel(titel)
            if nieuw and not (firma and soort and _van_mehdi(a) and not a.get("_terugkerend")):
                regels.append(f"{a['start'][:16]} {titel[:50]}: VOORSTEL '{nieuw[:70]}' ({uitleg})")
                nieuw = None
        if nieuw and nieuw != titel:
            try:
                _patch(a, {"summary": nieuw}, tok)
                regels.append(f"{a['start'][:16]} '{titel[:45]}' -> '{nieuw[:60]}' ({uitleg})")
                a["titel"] = nieuw
                gedaan += 1
            except Exception as e:  # noqa: BLE001
                regels.append(f"{a['start'][:16]} {titel[:45]}: titel niet gezet ({type(e).__name__})")
    return gedaan, regels


def _heeft_zl(titel):
    kop = titel.split(":", 1)[0]
    return bool(re.search(r"(^|\s)ZL(\s|$)", kop))


def met_zl(titel):
    """ZL (zonder link) vooraan, zoals !! en ??: voor 'Mehdi', na de tekens !! en ??."""
    if _heeft_zl(titel):
        return titel
    kop_einde = titel.find(":") if ":" in titel else len(titel)
    m = re.search(r"\bMehdi\b", titel)
    if m and m.start() < kop_einde:
        return titel[:m.start()] + "ZL " + titel[m.start():]
    return "ZL " + titel


def zonder_zl(titel):
    return re.sub(r"(^|\s)ZL\s+", r"\1", titel, count=1)


def zoom_zetten(items, alleen_dag=None):
    """ZL = zonder link. Een online gesprek met een externe partij zonder link krijgt ZL in de titel
    (zoals !! en ??) en de notitie 'Online. Mehdi stuurt de link naar ...'. Staat er later een link in
    de afspraak, dan gaan ZL en de notitie er weer af. De agent zet zelf GEEN link: Mehdi stuurt die.
    Niet bij bellen, Calendly-boekingen, intern overleg, een taak of terugkerende overleggen.
    Mandaat van Mehdi, 23-09-2026."""
    tok = agenda._toegang()
    nu = datetime.now().astimezone().isoformat()
    gedaan, regels = 0, []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a["start"] < nu[:len(a["start"])]:
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if a.get("kalender") != WERKAGENDA or a.get("_terugkerend"):
            continue
        titel = a["titel"]
        info = lees_titel(titel)
        if info["reistijd"] or not info.get("firma") or info["soort"] == "IN" or info["buiten"] or info["soort"] in BUITEN_SOORTEN:
            continue
        oms = a.get("omschrijving") or ""
        heeft_link = bool(a.get("_conferentie")) or bool(re.search(r"https?://", f"{a.get('locatie') or ''} {oms}"))
        if heeft_link:
            if _heeft_zl(titel):
                nieuw = zonder_zl(titel)
                schoon = re.sub(r"Online\. Mehdi stuurt de link naar [^\n]*\.\n*", "", oms).strip()
                try:
                    _patch(a, {"summary": nieuw, "description": schoon}, tok)
                    a["titel"] = nieuw
                    regels.append(f"{a['start'][:16]} {nieuw[:45]}: link staat erin, ZL weggehaald")
                    gedaan += 1
                except Exception as e:  # noqa: BLE001
                    regels.append(f"{a['start'][:16]} {titel[:45]}: ZL niet weggehaald ({type(e).__name__})")
            continue
        if re.search(r"\bbel(t|len)?\b|telefo", f"{titel} {oms}", re.I):
            continue
        kop, _, rest = titel.partition(":")
        namen = [n.strip(" !?") for n in re.split(r"[,&+]| en ", kop)
                 if n.strip(" !?") and n.strip(" !?").lower() not in ("mehdi", "zl", "zl mehdi")]
        namen = [re.sub(r"^(ZL\s+)", "", n) for n in namen]
        rest_naam = CODE_RE.sub(" ", rest).strip(" -:")
        if rest_naam and not re.search(r"\d", rest_naam) and len(rest_naam.split()) <= 3:
            namen.append(rest_naam)
        if not namen:
            continue                      # een taak zonder iemand anders heeft geen link nodig
        wie = ", ".join(namen)
        wijzig = {}
        if not _heeft_zl(titel):
            wijzig["summary"] = met_zl(titel)
        if "stuurt de link" not in oms:
            wijzig["description"] = f"Online. Mehdi stuurt de link naar {wie}." + ("\n\n" + oms if oms else "")
        if not wijzig:
            continue
        try:
            _patch(a, wijzig, tok)
            if "summary" in wijzig:
                a["titel"] = wijzig["summary"]
            regels.append(f"{a['start'][:16]} {a['titel'][:45]}: ZL, stuur de link naar {wie}")
            gedaan += 1
        except Exception as e:  # noqa: BLE001
            regels.append(f"{a['start'][:16]} {titel[:45]}: ZL niet gezet ({type(e).__name__})")
    return gedaan, regels


def titelfouten(a, info):
    """De fouten die Mehdi hard wil zien. Geeft een lijst met korte redenen."""
    if info["reistijd"] or a.get("hele_dag"):
        return []
    fouten = []
    if a.get("kalender", "") not in AGENDA_VASTE_KLEUR and not info.get("firma"):
        # Niet alleen klagen, maar een firma voorstellen waar dat kan. Mandaat van Mehdi,
        # 22-09-2026: los zoveel mogelijk zelf op, van waar het probleem komt.
        voorstel = ""
        # 1) een projectnummer dat in de H-Architects-projectmap staat, is een H-A-project
        if info.get("nummer") and info["nummer"] in projectadressen.index():
            voorstel = "HARC"
        # 2) een externe leverancier uit de lijst (boekhouder Nadien/Nadine, Wally): ALGE
        if not voorstel:
            tl = (a.get("titel") or "").lower()
            for r in EXTERNE_RELATIES:
                namen_r = [r.get("naam") or ""] + list(r.get("ook_geschreven") or [])
                if any(nm and re.search(r"(?<![\w])" + re.escape(nm.lower()) + r"(?![\w])", tl) for nm in namen_r):
                    voorstel = r.get("firma") or "ALGE"
                    break
        if voorstel:
            fouten.append(f"geen firmacode, wellicht [{voorstel}]")
        else:
            # 3) staan er namen in die ik ken, dan zegt "diensten voor" op
            # organisatie.globaal.be voor welke firma die mensen werken. Mandaat 20-09-2026.
            namen = namen_in_titel(a.get("titel") or "")
            firmas = []
            if namen:
                try:
                    firmas = organisatie.firma_van([n.split(" (")[0] for n in namen])
                except Exception:  # noqa: BLE001
                    firmas = []
            if len(firmas) == 1:
                fouten.append(f"geen firmacode, maar de namen wijzen naar [{firmas[0]}]")
            elif firmas:
                fouten.append("geen firmacode; de namen werken voor " + " of ".join(firmas))
            else:
                fouten.append("geen firmacode")
    buiten = info["buiten"] or info["soort"] in BUITEN_SOORTEN
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
    if info["buiten"] or info["soort"] in BUITEN_SOORTEN:
        return "11"
    if info["soort"] == "AO":
        return "2"    # salie: aannemer online (een aannemer van een klant)
    if info["soort"] == "B2B":
        return "1"    # lavendel: professioneel extern, wij nog geen klant (lichter dan leverancier)
    if info["soort"] == "LO":
        return "3"    # druif, paars: geld dat buitengaat
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
        if "," in straat:
            # Een naam vooraan ("Brasserie 360°, Stadsplein 16") laat de kaartdienst struikelen:
            # alleen het laatste stuk voor de postcode is de straat. Gezien 23-09-2026, toen de
            # rit naar Genk daardoor niet gemaakt werd.
            kort = straat.split(",")[-1].strip()
            pogingen.append({"street": kort, "postalcode": post, "country": "Belgium",
                             "format": "jsonv2", "limit": 1})
            pogingen.append({"q": f"{kort}, {post} {gemeente}", "format": "jsonv2", "limit": 1,
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
    from datetime import timedelta
    # Google alleen voor ritten binnen 48 uur: daar telt het echte verkeer. Verder vooruit is
    # ook Google's verkeer maar een voorspelling, en elke aanvraag ging van dezelfde dagteller
    # af. Gezien 23-09-2026: de teller stond al om de middag op 100/100 door verre ritten, zodat
    # de rit van morgen naar Genk geen echt verkeer meer kreeg.
    dichtbij = vertrek <= datetime.now().astimezone() + timedelta(hours=48)
    if ROUTES_KEY and dichtbij:
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


_lara_vrij = {"tot": 0.0, "dagen": frozenset()}


def lara_vakantiedagen():
    """De dagen die de agenda van Lara als schoolvakantie of feestdag markeert. Op zo'n
    dag is er geen Lara-ophaling, dus maakt de agent geen Lara-rit. Mandaat van Mehdi,
    22-09-2026. Staat een vakantie maar als losse dag in de agenda in plaats van als
    volledige week, dan dekt deze grendel alleen die dag; de weken horen als meerdaagse
    events in de agenda te staan."""
    import time
    import urllib.parse
    import urllib.request
    from datetime import date, timedelta
    if time.time() < _lara_vrij["tot"]:
        return _lara_vrij["dagen"]
    lara = next((k for k, val in AGENDA_VASTE_KLEUR.items() if val.get("naam") == "Lara"), None)
    dagen = set()
    if lara:
        try:
            nu = datetime.now().astimezone()
            tok = None
            while True:
                q = {"timeMin": nu.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                     "timeMax": (nu + timedelta(days=400)).isoformat(),
                     "singleEvents": "true", "maxResults": "2500"}
                if tok:
                    q["pageToken"] = tok
                url = f"{agenda.API}/calendars/{urllib.parse.quote(lara, safe='')}/events?" + urllib.parse.urlencode(q)
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {agenda._toegang()}"})
                d = json.load(urllib.request.urlopen(req, timeout=25))
                for e in d.get("items", []):
                    t = (e.get("summary") or "").lower()
                    if "date" not in e.get("start", {}) or not ("vakanti" in t or "feestdag" in t):
                        continue
                    a, b = date.fromisoformat(e["start"]["date"]), date.fromisoformat(e["end"]["date"])
                    while a < b:
                        dagen.add(a.isoformat()); a += timedelta(days=1)
                tok = d.get("nextPageToken")
                if not tok:
                    break
        except Exception:  # noqa: BLE001
            pass
    _lara_vrij["dagen"] = frozenset(dagen)
    _lara_vrij["tot"] = time.time() + 3600
    return _lara_vrij["dagen"]


_geen_auto = {"tot": 0.0, "dagen": frozenset()}


def geen_auto_dagen():
    """Dagen waarop Mehdi geen auto heeft. Hij (of een planner) zet er een hele-dag
    marker met 'geen auto' in de titel op de werkagenda. Op zo'n dag kan hij niet naar
    buiten rijden: de agent maakt geen rit en waarschuwt als er toch buiten gepland
    staat. Buiten-boekingen gebeuren sowieso handmatig, niet via Calendly. Mandaat van
    Mehdi, 22-09-2026."""
    import time
    import urllib.parse
    import urllib.request
    from datetime import date, timedelta
    if time.time() < _geen_auto["tot"]:
        return _geen_auto["dagen"]
    werk = next((k for k, val in KALENDERS.items() if "werk agenda" in val), "mehdiprivewerkagenda@gmail.com")
    dagen = set()
    try:
        nu = datetime.now().astimezone()
        tok = None
        while True:
            q = {"timeMin": nu.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                 "timeMax": (nu + timedelta(days=400)).isoformat(), "singleEvents": "true", "maxResults": "2500", "q": "geen auto"}
            if tok:
                q["pageToken"] = tok
            url = f"{agenda.API}/calendars/{urllib.parse.quote(werk, safe='')}/events?" + urllib.parse.urlencode(q)
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {agenda._toegang()}"})
            d = json.load(urllib.request.urlopen(req, timeout=25))
            for e in d.get("items", []):
                if "date" not in e.get("start", {}) or "geen auto" not in (e.get("summary") or "").lower():
                    continue
                a, b = date.fromisoformat(e["start"]["date"]), date.fromisoformat(e["end"]["date"])
                while a < b:
                    dagen.add(a.isoformat()); a += timedelta(days=1)
            tok = d.get("nextPageToken")
            if not tok:
                break
    except Exception:  # noqa: BLE001
        pass
    _geen_auto["dagen"] = frozenset(dagen)
    _geen_auto["tot"] = time.time() + 3600
    return _geen_auto["dagen"]


def ritlabel(adres, ander_adres=""):
    """Een naam voor een rit die iets zegt. Thuis heet thuis; ligt de andere kant in
    dezelfde gemeente, dan de straat, want "Leuven → Leuven" zegt niets."""
    if not adres:
        return "?"
    if re.fullmatch(r"\s*-?\d+\.\d+\s*,\s*-?\d+\.\d+\s*", adres):
        lat, lon = (float(v) for v in adres.split(","))
        for p in plekken():
            if p.get("lat") and abs(p["lat"] - lat) < 0.0005 and abs(p["lon"] - lon) < 0.0005:
                return "thuis" if p.get("soort") == "thuis" else p["naam"]
        return "?"
    if adres.strip().lower() == THUIS.strip().lower() or adres.lower().startswith(THUIS.split(",")[0].lower()):
        return "thuis"
    g1, g2 = plaatsnaam(adres), plaatsnaam(ander_adres) if ander_adres else ""
    p1 = re.search(r"\b(\d{4})\s+[A-Za-zÀ-ÿ]", adres or "")
    p2 = re.search(r"\b(\d{4})\s+[A-Za-zÀ-ÿ]", ander_adres or "")
    if (g1 and g2 and g1 == g2) or (p1 and p2 and p1.group(1) == p2.group(1)):
        # zelfde gemeente of zelfde postcode: 3010 heet soms Leuven, soms Kessel-Lo
        return adres.split(",")[0].strip()
    return g1 or adres.split(",")[0].strip()


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
    vrij = lara_vakantiedagen()
    zonder_auto = geen_auto_dagen()
    for a in items:
        if a.get("hele_dag") or a.get("kalender", "").startswith("en.be#"):
            continue
        # Tijdens een schoolvakantie of feestdag haalt Mehdi Lara niet op: geen rit voor
        # een afspraak op de agenda van Lara op zo'n dag. Mandaat van Mehdi, 22-09-2026.
        if a.get("kalender") in AGENDA_VASTE_KLEUR and AGENDA_VASTE_KLEUR[a["kalender"]].get("naam") == "Lara" \
                and a.get("start", "")[:10] in vrij:
            continue
        info = lees_titel(a["titel"])
        # Geen auto die dag: geen rit. Staat er toch een buitenafspraak, dan is dat een
        # waarschuwing (collega die het vergat), geen gewone rit. Mandaat van Mehdi, 22-09-2026.
        if a.get("start", "")[:10] in zonder_auto and not lees_titel(a["titel"])["reistijd"]:
            if info["buiten"] or info["soort"] in BUITEN_SOORTEN:
                regels.append(f"{a['start'][:16]} {a['titel'][:50]}: BUITEN op een dag zonder auto (door {maker(a)})")
            continue
        adres = a.get("locatie") or ""
        fysiek = bool(adres) and not adres.lower().startswith("http")
        bron_adres = "agenda"
        if not fysiek and info["nummer"] and info["nummer"] in projecten:
            adres, fysiek, bron_adres = projecten[info["nummer"]]["adres"], True, "projectmap"
        if not fysiek:
            # geen adres in de agenda en geen projectnummer: misschien een benoemde plek
            # uit locatie.globaal.be, zoals de school of de zwemles van Lara. Dat is de
            # bron voor plaatsen; de agent houdt er geen eigen lijst van bij.
            gevonden, naam = plek_zoeken(a["titel"] + " " + (a.get("omschrijving") or ""))
            if gevonden:
                adres, fysiek, bron_adres = gevonden, True, f"locatiesysteem ({naam})"
        if info["reistijd"] or not (info["buiten"] or info["soort"] in BUITEN_SOORTEN):
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
        # Komt het adres uit de projectmap en staat er geen locatie in de afspraak, dan zet ik het
        # erin, zodat Mehdi (en wie meegaat) kan navigeren. Alleen bij zijn eigen afspraken zonder
        # gasten. Mandaat van Mehdi, 23-09-2026: "in een keer goed zetten".
        if (bron_adres == "projectmap" and fysiek and not (a.get("locatie") or "").strip()
                and _van_mehdi(a) and not a.get("_terugkerend")):
            try:
                _patch(a, {"location": adres}, tok)
                a["locatie"] = adres
                regels.append(f"{a['start'][:16]} {a['titel'][:45]}: projectadres in de afspraak gezet ({adres[:40]})")
            except Exception as e:  # noqa: BLE001
                regels.append(f"{a['start'][:16]} {a['titel'][:45]}: projectadres niet gezet ({type(e).__name__})")
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
    vorige_per_dag = {}   # dag -> (sleutel, coordinaten of None, adres of None, einde)

    def is_thuisrit(x):
        t = x.get("titel") or ""
        # Ook een rit naar huis die iemand zelf intikte ("Rijden naar huis"). Gezien 23-09-2026:
        # die werd niet herkend, zodat de rit naar oma van het stadskantoor vertrok.
        return ("Reistijd na:" in (x.get("omschrijving") or "") or "Reistijd ←" in t
                or bool(re.search(r"→\s*thuis\s*$", t)) or bool(re.search(r"\bnaar huis\b", t, re.I)))

    def thuisrit_tussen(t0, t1):
        for x in reistijden:
            if "T" in x.get("start", "") and is_thuisrit(x) and t0 <= datetime.fromisoformat(x["start"]) <= t1:
                return x
        return None

    def aan_bureau_tussen(t0, t1):
        """Een afspraak achter het bureau (niet buiten, geen rit, geen hele dag) tussen t0 en t1."""
        for x in items:
            if "T" not in x.get("start", "") or x.get("hele_dag"):
                continue
            ix = lees_titel(x["titel"])
            if ix["reistijd"] or ix["buiten"] or ix["soort"] in BUITEN_SOORTEN:
                continue
            try:
                if t0 <= datetime.fromisoformat(x["start"]) < t1:
                    return x
            except ValueError:
                continue
        return None

    # Na welke buitenafspraak gaat hij naar huis? Na de laatste van de dag. Ook als er al
    # een rit naar huis staat (gezien 21-09-2026: op vrijdag vertrok de rit naar Lara van
    # de griffie, terwijl er om 11:00 al een rit naar huis stond). En voorlopig ook als er
    # tussen twee buitenafspraken iets achter het bureau staat (afspraak C): dan reken ik
    # dat hij naar huis gaat, zoals op maandag 21-09-2026, en vraag ik het hem. Anders
    # rijdt hij rechtstreeks door naar de volgende.
    def extern_gesprek(x):
        """Een extern online gesprek: klant, prospect, leverancier, B2B of een Calendly-boeking.
        Dat voert Mehdi in de auto alleen geparkeerd, nooit rijdend. Een intern overleg mag wel
        tijdens het rijden. Mandaat van Mehdi, 23-09-2026."""
        if "T" not in x.get("start", "") or x.get("hele_dag"):
            return False
        ix = lees_titel(x.get("titel") or "")
        if ix["reistijd"] or ix["buiten"] or ix["soort"] in BUITEN_SOORTEN + ("IN",):
            return False
        return ix["soort"] in EXTERN_ONLINE or x.get("kalender") == "zoomafspraken@gmail.com"

    def externe_gesprekken(t0, t1):
        """Externe gesprekken die [t0, t1) raken, als (begin, einde, afspraak), op begin gesorteerd."""
        uit = []
        for x in items:
            if not extern_gesprek(x):
                continue
            try:
                xs, xe = datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["einde"])
            except ValueError:
                continue
            if xs < t1 and xe > t0:
                uit.append((xs, xe, x))
        return sorted(uit, key=lambda z: z[0])

    naar_huis_na = {}
    for rij in per_dag.values():
        for i, (s_, e_, a_, *_r) in enumerate(rij):
            sleutel_ = (a_["kalender"], a_.get("id"), a_["start"])
            if i == len(rij) - 1:
                naar_huis_na[sleutel_] = True
                continue
            s_volgend, a_volgend = rij[i + 1][0], rij[i + 1][2]
            if thuisrit_tussen(e_, s_volgend):
                naar_huis_na[sleutel_] = True
                regels.append(f"{a_['start'][:16]} {a_['titel'][:40]}: er staat al een rit naar huis, die telt")
                continue
            bureau = aan_bureau_tussen(e_, s_volgend)
            naar_huis_na[sleutel_] = bool(bureau)
            if bureau:
                regels.append(f"{a_['start'][:16]} {a_['titel'][:40]}: VRAAG om {bureau['start'][11:16]} "
                              f"'{bureau['titel'][:30]}' achter het bureau, om {a_volgend['start'][11:16]} weer buiten. "
                              f"Ik reken dat je tussendoor naar huis gaat. Klopt dat, of doe je het vanuit de auto?")

    for start, einde, a, info, adres, fysiek in buiten:
        dag = a["start"][:10]
        sleutel = (a["kalender"], a.get("id"), a["start"])
        vorige = vorige_per_dag.get(dag)
        if not fysiek:
            geen_adres += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: geen adres, geen reistijd")
            vorige_per_dag[dag] = (sleutel, None, None, einde)
            continue
        doel = coord(adres, cache)
        if not (doel and thuis):
            geen_adres += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: adres niet gevonden ({adres[:40]})")
            vorige_per_dag[dag] = (sleutel, None, None, einde)
            continue
        vorige_einde = None   # gezet als hij rechtstreeks van de vorige afspraak komt
        if vorige is None or naar_huis_na.get(vorige[0]):
            vertrek_van, van_adres = thuis, THUIS
        elif vorige[1] is None:
            vertrek_van, van_adres = thuis, THUIS
            regels.append(f"{a['start'][:16]} {a['titel'][:40]}: VRAAG de vorige buitenafspraak heeft geen adres, "
                          f"ik reken de rit vanaf thuis")
        else:
            vertrek_van, van_adres, vorige_einde = vorige[1], vorige[2], vorige[3]
        vorige_per_dag[dag] = (sleutel, doel, adres, einde)
        is_laatste = naar_huis_na.get(sleutel, True)
        # Gaat de eerstvolgende afspraak al naar huis, zoals "Lara naar huis brengen",
        # dan is dat zelf de terugrit en maak ik er geen tweede. Gezien 20-09-2026.
        for x in items:
            if x is a or not x.get("start", "").startswith(dag) or "T" not in x.get("start", ""):
                continue  # een afspraak van de hele dag heeft geen uur om mee te vergelijken
            try:
                xs = datetime.fromisoformat(x["start"])
            except (ValueError, KeyError):
                continue
            if einde <= xs <= einde + timedelta(minutes=15):
                xl = (x.get("locatie") or "").strip()
                if xl and not xl.lower().startswith("http") and coord(xl, cache) == thuis:
                    is_laatste = False
                    regels.append(f"{a['start'][:16]} {a['titel'][:40]}: geen terugrit, "
                                  f"'{x.get('titel','')[:30]}' gaat zelf naar huis")
                    break
        # Zuinig met aanvragen (Google Routes Pro: 5.000 gratis per maand): bestaan mijn twee
        # blokken al, dan herbereken ik alleen in de eerste ronde van de dag (voor 08:00) of met --dag.
        # Een rit hoort bij precies één afspraak: mijn heenrit eindigt op haar begin, mijn
        # terugrit begint op haar einde. Een rit van Mehdi zelf binnen drie uur telt ook.
        # Gezien 21-09-2026: de zwemles nam de rit naar oma over en gaf hem haar titel.
        def _mijn(x):
            return "OSRM" in (x.get("omschrijving") or "")

        def heenblok():
            # aankomen kan op het begin van de afspraak, of eerder: op het begin van een extern
            # gesprek dat Mehdi geparkeerd ter plaatse doet
            aankomsten = {start} | {z[0] for z in externe_gesprekken(start - timedelta(hours=3), start) if z[0] < start}
            for x in reistijden:
                if x["kalender"] == a["kalender"] and "T" in x["start"] and datetime.fromisoformat(x["einde"]) in aankomsten:
                    return x
            for x in reistijden:
                if (x["kalender"] == a["kalender"] and "T" in x["start"] and not _mijn(x)
                        and start - timedelta(hours=3) <= datetime.fromisoformat(x["start"]) <= start):
                    return x
            return None

        def terugblok():
            vertrekken = {einde} | {z[1] for z in externe_gesprekken(einde, einde + timedelta(hours=3)) if z[1] > einde}
            for x in reistijden:
                if x["kalender"] == a["kalender"] and "T" in x["start"] and datetime.fromisoformat(x["start"]) in vertrekken:
                    return x
            for x in reistijden:
                if (x["kalender"] == a["kalender"] and "T" in x["start"] and not _mijn(x)
                        and einde <= datetime.fromisoformat(x["start"]) <= einde + timedelta(hours=3)):
                    return x
            return None
        if (heenblok() and (terugblok() or not is_laatste)
                and (nu.hour >= 8 or start > nu + timedelta(days=8)) and not DAG_ARG):
            al += 2 if is_laatste else 1
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
        plaats = ritlabel(adres, van_adres)
        van_plaats = ritlabel(van_adres, adres)
        # Nooit vertrekken voor de vorige afspraak gedaan is: dinsdag ben je tot 17:40 bij
        # oma, dus de rit naar het zwembad begint om 17:40, ook als de rijtijd met buffer
        # langer is. Past de rit zelfs zonder buffer niet, dan meld ik dat.
        # Valt er een extern gesprek tijdens de heenrit, dan komt hij aan voor het begint en
        # doet hij het geparkeerd ter plaatse. Gezien 23-09-2026: Genk, aankomst 11:00 voor
        # het gesprek met Rem Braspenning, pas om 11:30 de brasserie in.
        aankomst, reden_aankomst = start, None
        for _ in range(3):
            vertrek = aankomst - timedelta(minutes=heen)
            tijdens = [z for z in externe_gesprekken(vertrek, aankomst) if vertrek <= z[0] < aankomst]
            if not tijdens:
                break
            aankomst, reden_aankomst = tijdens[0][0], tijdens[0][2]
            heen, fh = rijtijd_min(vertrek_van, doel, aankomst - timedelta(minutes=heen))
        lopend = [z for z in externe_gesprekken(aankomst - timedelta(minutes=heen), aankomst)
                  if z[0] < aankomst - timedelta(minutes=heen)]
        if lopend:
            regels.append(f"{a['start'][:16]} {a['titel'][:40]}: LET OP, extern gesprek "
                          f"'{lopend[0][2]['titel'][:30]}' loopt nog bij vertrek; rijdend kan dat niet")
        if reden_aankomst:
            regels.append(f"{a['start'][:16]} {a['titel'][:40]}: aankomst {aankomst:%H:%M} in plaats van "
                          f"{start:%H:%M}, want '{reden_aankomst['titel'][:30]}' doe je geparkeerd, niet rijdend")
        rit_start = aankomst - timedelta(minutes=heen)
        if vorige_einde and rit_start < vorige_einde:
            ruimte = (aankomst - vorige_einde).total_seconds() / 60
            if ruimte < heen - BUFFER_MIN:
                regels.append(f"{a['start'][:16]} {a['titel'][:40]}: TE KRAP, rijden duurt {heen - BUFFER_MIN} min, "
                              f"er is {ruimte:.0f} min na de vorige afspraak")
            rit_start = vorige_einde
        # Een schatting overschrijft nooit een echte meting. Staat er al een eigen rit met live
        # verkeer van Google en heb ik nu alleen de schatting (dagteller op), dan houd ik de live
        # rijtijd. Gezien 23-09-2026: de rit naar Genk schoof zo van 10:00 naar 09:45.
        _x = heenblok()
        _oms = (_x or {}).get("omschrijving") or ""
        if _x and "OSRM" in _oms and "live verkeer Google" in _oms and fh != "live":
            heen = int((datetime.fromisoformat(_x["einde"]) - datetime.fromisoformat(_x["start"])).total_seconds() // 60)
            fh = "live"
            rit_start = aankomst - timedelta(minutes=heen)
            if vorige_einde and rit_start < vorige_einde:
                rit_start = vorige_einde
        vertrek_min = int((start - rit_start).total_seconds() // 60)
        # Terug: valt er een extern gesprek tijdens de rit naar huis, dan doet hij het eerst
        # geparkeerd en vertrekt hij daarna.
        terug_start = einde
        _t = terugblok() if is_laatste else None
        _toms = (_t or {}).get("omschrijving") or ""
        if _t and "OSRM" in _toms and "live verkeer Google" in _toms and ft != "live":
            terug = int((datetime.fromisoformat(_t["einde"]) - datetime.fromisoformat(_t["start"])).total_seconds() // 60)
            ft = "live"
        if is_laatste and terug:
            for _ in range(3):
                tijdens = [z for z in externe_gesprekken(terug_start, terug_start + timedelta(minutes=terug)) if z[1] > terug_start]
                if not tijdens:
                    break
                terug_start = max(z[1] for z in tijdens)
            if terug_start != einde:
                regels.append(f"{a['start'][:16]} {a['titel'][:40]}: vertrek naar huis pas {terug_start:%H:%M}, "
                              f"eerst een extern gesprek geparkeerd")

        def eigen(x):
            return "OSRM" in (x.get("omschrijving") or "")

        def bijwerken(x, s, e, tekst, titel, melding=None):
            """Een blok dat ik zelf maakte, pas ik aan als de rijtijd meer dan 10 min verschilt,
            en altijd als titel of kleur niet meer klopt met de afspraak waarvoor ik rijd."""
            if not eigen(x):
                return False
            duur_oud = (datetime.fromisoformat(x["einde"]) - datetime.fromisoformat(x["start"])).total_seconds() / 60
            wijzig = {}
            begint_te_vroeg = bool(vorige_einde) and datetime.fromisoformat(x["start"]) < vorige_einde
            if (abs(duur_oud - (e - s).total_seconds() / 60) >= 10 or datetime.fromisoformat(x["einde"]) != e
                    or begint_te_vroeg):
                wijzig.update({"start": {"dateTime": s.isoformat()}, "end": {"dateTime": e.isoformat()}, "description": tekst})
            if x.get("titel") != titel:
                wijzig["summary"] = titel
            if (x.get("_kleur") or "") != rit_kleur.get("colorId", ""):
                wijzig["colorId"] = rit_kleur.get("colorId") or None
            r = x.get("_reminders") or {}
            if melding is not None and (r.get("useDefault", True) or (r.get("overrides") or []) != melding):
                wijzig["reminders"] = {"useDefault": False, "overrides": melding}
            if wijzig:
                _patch(x, wijzig, tok)
                return True
            return False
        uitleg_h = f"Reistijd voor: {a['titel']} ({heen} min = " + ("live verkeer Google" if fh == "live" else f"vrije rijtijd x filefactor {fh}") + f" + {BUFFER_MIN} min buffer, OSRM; adres uit {bron_adres})"
        uitleg_t = f"Reistijd na: {a['titel']} ({terug} min = " + ("live verkeer Google" if ft == "live" else f"vrije rijtijd x filefactor {ft}") + f" + {BUFFER_MIN} min buffer, OSRM)"
        # Een rit hoort bij de afspraak waarvoor je rijdt: zelfde agenda, zelfde kleur. Een
        # rit voor Lara staat roze op de agenda van Lara, een privérit zwart op privé. Rood
        # is alleen voor werk. Anders zien collega's op je werkagenda dat je ergens heen
        # gaat, zonder wat, en weer terugkomt. Mandaat van Mehdi, 21-09-2026.
        # De kleur komt uit dezelfde regel die elke afspraak nakijkt, zodat maker en
        # controleur het nooit oneens kunnen zijn.
        _wens = kleur_gewenst({"kalender": a["kalender"]}, {"reistijd": True})
        rit_kleur = {"colorId": _wens} if _wens else {}
        kleur = {**rit_kleur, "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 5}]}}
        try:
            x = heenblok()
            if x:
                al += 1
                if bijwerken(x, rit_start, aankomst, uitleg_h, f"🚗 Reistijd: {van_plaats} → {plaats}",
                             [{"method": "popup", "minutes": 5}]):
                    gemaakt += 1
            else:
                _insert(a["kalender"], {"summary": f"🚗 Reistijd: {van_plaats} → {plaats}", "start": {"dateTime": rit_start.isoformat()},
                                        "end": {"dateTime": aankomst.isoformat()}, "description": uitleg_h, **kleur}, tok)
                gemaakt += 1
            x = terugblok() if is_laatste else None
            if not is_laatste:
                regels.append(f"{a['start'][:16]} {a['titel'][:44]}: geen rit naar huis, je gaat door naar de volgende afspraak")
            if x:
                al += 1
                if bijwerken(x, terug_start, terug_start + timedelta(minutes=terug), uitleg_t, f"🚗 Reistijd: {plaats} → thuis", []):
                    gemaakt += 1
            elif is_laatste:
                _insert(a["kalender"], {"summary": f"🚗 Reistijd: {plaats} → thuis", "start": {"dateTime": terug_start.isoformat()},
                                        "end": {"dateTime": (terug_start + timedelta(minutes=terug)).isoformat()}, "description": uitleg_t,
                                        **{**rit_kleur, "reminders": {"useDefault": False, "overrides": []}}}, tok)
                gemaakt += 1
            _patch(a, {"reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": vertrek_min + 5}]}}, tok)
            regels.append(f"{a['start'][:16]} {a['titel'][:44]}: {van_plaats} → {plaats} {heen} min (file x{fh})"
                          + (f", terug naar huis {terug} min (file x{ft})" if is_laatste else ", daarna door naar de volgende")
                          + f", adres uit {bron_adres}, melding {vertrek_min + 5} min vooraf")
        except Exception as e:  # noqa: BLE001
            fout += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: reistijd niet gezet ({type(e).__name__})")
    # Een rit die ik zelf maakte en waarvan de afspraak weg of verzet is, meld ik. Een
    # heenrit eindigt op het begin van zijn afspraak, een terugrit begint op het einde.
    # Ik verwijder hem niet zelf; dat beslist Mehdi.
    grenzen = set()
    begins_alle, eindes_alle = set(), set()
    for x in items:
        if "T" in x.get("start", "") and not lees_titel(x["titel"])["reistijd"]:
            grenzen.add((x["kalender"], datetime.fromisoformat(x["start"])))
            grenzen.add((x["kalender"], datetime.fromisoformat(x["einde"])))
            if extern_gesprek(x):
                begins_alle.add(datetime.fromisoformat(x["start"]))
                eindes_alle.add(datetime.fromisoformat(x["einde"]))
    for x in reistijden:
        if ("OSRM" not in (x.get("omschrijving") or "") or "T" not in x.get("start", "")
                or (alleen_dag and x["start"][:10] != alleen_dag)):
            continue
        s0, e0 = datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["einde"])
        if (s0 >= nu and (x["kalender"], e0) not in grenzen and (x["kalender"], s0) not in grenzen
                and e0 not in begins_alle and s0 not in eindes_alle):
            regels.append(f"{x['start'][:16]} {x['titel'][:50]}: rit zonder afspraak")
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


def slot_nemen(max_wachten=900):
    """Nooit twee rondes tegelijk. Gezien 21-09-2026: een volledige ronde en de
    wijzigingswacht maakten tegelijk ritten, en zo stonden ze dubbel."""
    import fcntl
    import time
    from pathlib import Path
    pad = Path(os.path.expanduser("~/appportal/mijnagents-data/agenda_wacht.lock"))
    pad.parent.mkdir(parents=True, exist_ok=True)
    f = open(pad, "w")
    tot = time.time() + max_wachten
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if time.time() > tot:
                print("een andere ronde loopt al te lang, ik stop", file=sys.stderr)
                sys.exit(0)
            time.sleep(5)


def main():
    _slot = slot_nemen()  # noqa: F841  blijft open tot het einde van de ronde
    werkwijze = ag.werkwijze()
    ag.hartslag("actief", taak="agenda lezen")
    try:
        if not agenda.beschikbaar():
            ag.hartslag("fout", taak="geen agendatoegang", detail="GOOGLE_AGENDA_* ontbreekt in ~/appportal/.env")
            return
        items = afspraken(-1, 8)
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
                wie = maker(a)
                niet_conform.append(f"{dag} {a['start'][11:16]} {a['titel']} ({kal}"
                                    + (f", gezet door {wie}" if wie else "") + ")")
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
                                         "locatie": a["locatie"], "deelnemers": a["deelnemers"], "gezet_door": maker(a),
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
        gezien_ids = {(a["kalender"], a["id"], a["start"]) for a in items}
        if DAG_ARG:
            extra = afspraken_dag(DAG_ARG)
        elif not ALLEEN_VANDAAG:
            extra = verre_afspraken()
        else:
            extra = []
        rit_items = items + [a for a in extra if (a["kalender"], a["id"], a["start"]) not in gezien_ids]
        # eerst de titel in één keer goed, dan de vaste Zoom, dan de rest
        ng, nregels = titels_normaliseren(rit_items, dag_grens)
        zg, zregels = zoom_zetten(rit_items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"titels: {ng} rechtgezet uit vrije tekst; link-notitie: {zg} gezet",
               "\n".join(nregels + zregels))
        if zregels or [r for r in nregels if "VOORSTEL" in r]:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": "Link doorsturen of titel nakijken",
                          "uniek": f"agenda-zoom-titel:{vandaag}:{dag_grens or 'alle'}",
                          "inhoud": "\n".join("- " + r for r in (zregels + [r for r in nregels if "VOORSTEL" in r])[:30])}])
        # eerst de gewone herinneringen, dan de ritten: zo heeft de vertrekmelding het laatste woord
        gezet, al, weg, fout_h = herinneringen_zetten(rit_items, dag_grens)
        rg, ral, rgeen, rfout, rregels = reistijd_zetten(rit_items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"reistijd: {rg} blok(ken) gemaakt, {ral} bestonden al, {rgeen} zonder adres, {rfout} mislukt", "\n".join(rregels))
        # Een rit die niet berekend raakte mag nooit alleen een cijfer zijn: dan ziet
        # Mehdi niet welke afspraak zonder reistijd staat. Gezien 20-09-2026, toen het
        # wekelijkse werfbezoek geen rit kreeg omdat "3010 Kessel-Lo" niet om te zetten was.
        zonder_rit = {"geen adres in de agenda": [], "adres niet gevonden": [], "rijtijd niet berekend": [],
                      "rit zonder afspraak": [], "buiten op een dag zonder auto": []}
        for regel in rregels:
            if "geen adres, geen reistijd" in regel:
                # rsplit: in het uur staat zelf een dubbelpunt, dus split(":") hield alleen
                # "2026-09-21T16" over, zonder de afspraak. Gezien 21-09-2026.
                zonder_rit["geen adres in de agenda"].append(regel.rsplit(": geen adres", 1)[0][:80])
            elif "rit zonder afspraak" in regel:
                zonder_rit["rit zonder afspraak"].append(regel[:110])
            elif "BUITEN op een dag zonder auto" in regel:
                zonder_rit["buiten op een dag zonder auto"].append(regel[:110])
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
        kg, kgoed, kgeen, kfout, kvast = kleuren_zetten(rit_items if DAG_ARG else items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"kleuren: {kg} gezet, {kgoed} klopten al, {kvast} op een agenda met vaste kleur, {kgeen} ZONDER CODE (fout), {kfout} niet gelukt",
               "\n".join(f"{a['start'][:16]} {a['titel'][:60]} -> {KLEURNAAM.get(kleur_gewenst(a, lees_titel(a['titel'])), 'laten staan')}" for a in items if a['start'][:10] >= vandaag and (not dag_grens or a['start'][:10] == dag_grens)))
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
        # De plaatsen van Lara horen in locatie.globaal.be, niet in een lijst van mij.
        try:
            bekend = {(x.get("naam") or "").lower() for x in plekken()}
        except Exception:  # noqa: BLE001
            bekend = set()
        mist = [n for n in ("school", "zwemschool", "grootouders", "kantoor")
                if not any(n in b for b in bekend)]
        if mist:
            noden.append({"tekst": "Plaatsen die nog niet in locatie.globaal.be staan: " + ", ".join(mist),
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
