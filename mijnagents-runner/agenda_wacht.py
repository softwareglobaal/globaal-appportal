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
from pathlib import Path
import os
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import agenda  # noqa: E402
import bellen  # noqa: E402
import projectadressen  # noqa: E402
import bord  # noqa: E402
import zoom  # noqa: E402
import organisatie  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "agenda-wacht"
ag = bord.Agent(NAAM)

# De VM draait op UTC en cron kent daar geen tijdzone. Gezien 24-09-2026: de ronde van
# "06:30" liep om 08:30 Belgische tijd en de filewacht sliep tijdens de ochtendspits.
# Daarom start cron elk uur en beslist de agent zelf op Brusselse tijd, zomer en winter.
TIJDZONE = ZoneInfo("Europe/Brussels")
RONDE_UREN = (6, 8, 10, 12, 14, 16, 18)               # werkdagen, telkens om half


def nu_lokaal():
    return datetime.now(TIJDZONE)


def is_rondetijd(t=None):
    """Hoort er nu een volledige ronde? Werkdag en een ronde-uur, op Brusselse tijd."""
    t = (t or nu_lokaal()).astimezone(TIJDZONE)
    return t.weekday() < 5 and t.hour in RONDE_UREN


def binnen_uren(van, tot, t=None):
    """Voor de signaal- en filewacht: alleen tussen van:00 en tot:59, Brusselse tijd."""
    t = (t or nu_lokaal()).astimezone(TIJDZONE)
    return van <= t.hour <= tot

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
# Privé: wat hier staat gaat nooit met titel of tekst naar het bord (nacontrole v1.2, V9)
PRIVE_KALENDERS = {k for k, n in KALENDERS.items() if n == "Lara" or "privé" in n}


def is_prive(a):
    return bool(a.get("_prive") or a.get("kalender") in PRIVE_KALENDERS)


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
# Bijgewerkt: dat gold tot de KANTELDATUM. Sinds het mandaat van 23-09-2026 ("In een keer
# goed" in mijn werkwijze) krijgt een afspraak die Mehdi vanaf 21-09-2026 zelf maakte de
# vierletterige code, ook als hij de oude typte; oudere afspraken houden hun schrijfwijze.
# Op organisatie.globaal.be heet de vierletterige code sinds 29-09-2026 de agendacode,
# naast de contactcode van twee letters voor Google Contacts. Gemeten op 29-09-2026: van
# de afspraken gemaakt sinds 21-09 dragen er 55 de vierletterige code en 12 nog een oude.
# Fout gemeten op 20-09-2026: ik meldde 28 titels als "oude firmacode" die
# rechtgezet moest worden. Dat advies was verkeerd om en is weggehaald.
# De schrijfwijzen die Mehdi in zijn agenda gebruikte voor de firmacodes van
# organisatie.globaal.be de norm werden. Ze blijven leesbaar, zodat een afspraak van
# vorig jaar bij dezelfde firma terechtkomt als een van vandaag. "EE" gebruikte hij
# voor Energie Efficiënt, ook los in een titel zoals "AI & EE" (20-09-2026).
# Mehdi, 02-10-2026 (goedgekeurd): in de titel van een afspraak heeft elke firma een code van TWEE letters. De bron
# is organisatie.globaal.be (kern.firma.code_agenda, migratie 183). Intern blijft de code van vier letters de sleutel
# (boekhouding, Pipedrive, mappen, bord); in een titel schrijf ik alleen de twee letters, ook bij een bronstoring
# (dan uit de vaste lijst hieronder). Oude schrijfwijzen (HARC, UNABO, TKN ...) blijven leesbaar. Vervangt de
# vierletterregel van 21-09-2026 en FR-22.
VALNET_AGENDACODES = {"HARC": "HA", "UNAB": "UB", "TKNB": "TK", "ENEF": "EE", "ELEV": "EL", "HINV": "HI", "HARM": "HB",
                      "CONT": "CX", "MELO": "ME", "HDSI": "DI", "HDSS": "DS", "BFUT": "BF", "CORE": "CB", "ENST": "ES",
                      "MEDI": "MS", "ORVA": "OR", "QOPP": "QP", "ZIDI": "ZC"}
NIET_FIRMA_CODES = {"ALGE": "AL", "PRIVE": "PR"}      # categorieën, geen firma's (Lara: LA, op haar eigen agenda)


def agendacodes():
    """firmacode (vier letters) -> agendacode (twee letters): de bron, aangevuld met de vaste lijst."""
    try:
        uit = organisatie.agendacodes()
    except Exception:  # noqa: BLE001
        uit = {}
    return {**VALNET_AGENDACODES, **{k: v for k, v in (uit or {}).items() if v and len(v) == 2}}


AGENDACODES = {**agendacodes(), **NIET_FIRMA_CODES}


def titelcode(firma):
    """De code die in een titel komt: altijd die van twee letters."""
    return AGENDACODES.get(firma or "", firma or "")


AGENDACODE_NAAR_FIRMA = {"HA": "HARC", "UNABO": "UNAB", "HB": "HARM", "HARMONIEBOUW": "HARM",
                         "CONTRAX": "CONT", "CTX": "CONT", "ENERGIE": "ENEF", "EE": "ENEF", "TKN": "TKNB",
                         "ELEVAIT": "ELEV",
                         **{twee: vier for vier, twee in AGENDACODES.items()}}

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
         "AB": "aannemer buiten", "AO": "aannemer online",
         # Sinds 02-10-2026 twee letters: B2B wordt XB (buiten) of XO (online). ZB/ZO blijven vrij voor het open
         # voorstel 'zakelijke klant met terugkerende opdrachten' (klantsoorten_voorstel, 22-09-2026).
         "XB": "extern professioneel buiten, wij nog geen klant", "XO": "extern professioneel online, wij nog geen klant"}
# Centraal, zodat een nieuwe soort nergens vergeten wordt (23-09-2026).
BUITEN_SOORTEN = ("PB", "KB", "LB", "AB", "XB")       # per definitie buiten
EXTERN_ONLINE = ("KO", "PO", "LO", "B2B", "AO", "XO")  # online met iemand van buiten: alleen geparkeerd
# Diensten met een verslagagent (Commandocentrum, 16-09-2026): WB/OPL werfverslag, VC veiligheidscoördinatie,
# PLB plaatsbeschrijving, BS/STA barsten en scheuren. De code staat na de firmacode, vóór het nummer of de naam.
# De activiteit: wat Mehdi gaat doen. Beslist op 25-09-2026: voor architectuur voorlopig alleen WB,
# VOPL, DOPL en OPL; voor UNABO de volledige lijst van de diensten op unabo.be; interne besprekingen
# over AI en automatisering AI+AT. De oude codes (OPM, SD ...) blijven geldig.
# Sinds 02-10-2026 heeft elke opdracht twee letters (Mehdi, goedgekeurd). De oude codes blijven leesbaar en worden
# bij het lezen omgezet (TYPE_ALIAS); geschreven wordt alleen de nieuwe code.
TYPES = {"WB": "werfbezoek", "PL": "plaatsbezoek", "PS": "plaatsbeschrijving", "SC": "scanning, 3D-scan",
         "BS": "barsten en scheuren", "ST": "stabiliteit", "EP": "EPB", "VC": "veiligheidscoördinatie", "OP": "oplevering",
         "VO": "voorlopige oplevering", "DO": "definitieve oplevering", "OM": "opmeting", "VE": "ventilatie, ventilatiemeting",
         "BD": "blowerdoortest", "VG": "vergunning of melding zonder architect", "FW": "functiewijziging", "RG": "regularisatie",
         "RD": "3D-rendering", "LM": "landmeter: opmeting, afpaling, muurovername", "DR": "drafting, plannen tekenen of digitaliseren",
         "MT": "meetstaat", "SD": "schetsontwerp", "KM": "kennismaking", "OB": "offertebespreking", "BU": "bundel van meerdere diensten",
         "AI": "AI en automatisering (interne bespreking)"}
TYPE_ALIAS = {"OPL": "OP", "PLB": "PS", "SCN": "SC", "EPB": "EP", "STA": "ST", "OPM": "OM", "VOPL": "VO", "DOPL": "DO",
              "VEN": "VE", "BDT": "BD", "VERG": "VG", "REG": "RG", "REN": "RD", "DRA": "DR", "MST": "MT", "OFB": "OB",
              "BUN": "BU", "AI+AT": "AI"}
ACTIVITEITEN = {"HARC": ("WB", "VO", "DO", "OP", "PL"),
                "UNAB": ("EP", "VE", "BD", "ST", "BS", "VG", "FW", "RG", "PS", "SC", "RD", "VC", "LM", "SD", "DR",
                         "MT", "KM", "OB", "BU", "PL"),
                "intern": ("AI",)}
TYPE_RE = re.compile(r"^\s*(" + "|".join(re.escape(k) for k in sorted(set(TYPES) | set(TYPE_ALIAS), key=len, reverse=True)) + r")(?![\w+])")
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
BUITEN_TYPES = {"WB", "OP", "VO", "DO", "PS", "SC", "OM", "BS", "LM", "BD", "VE", "PL"}

ALLE_CODES = sorted(set(FIRMACODES) | set(EXTERNE_FIRMAS) | set(AGENDACODE_NAAR_FIRMA) | set(NIET_FIRMA), key=len, reverse=True)
CODE_RE = re.compile(r"\[(" + "|".join(ALLE_CODES) + r")(?:-(" + "|".join(sorted(SOORT, key=len, reverse=True)) + r"))?\]", re.I)


def kalenders():
    ruw = os.environ.get("AGENDA_KALENDERS", "").strip()
    lijst = [k.strip() for k in ruw.split(",") if k.strip()] or list(KALENDERS)
    arch = gearchiveerd()
    return [k for k in lijst if arch is None or k not in arch]   # lezen mag; schrijven niet (mag_schrijven)



def afspraken(van_dagen=-1, tot_dagen=8):
    """De afspraken van precies de agenda's die de Agendawacht leest. Eén plek, zodat de
    controle en de filewacht dezelfde agenda's zien als de agent. Gezien 21-09-2026:
    zij lazen alleen de werkagenda en zoomafspraken, niet Lara en niet privé."""
    os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())   # agenda.kalenders() leest die
    return agenda.afspraken(van_dagen, tot_dagen)



def archief_afspraken(van_dagen=-1, tot_dagen=8):
    """De afspraken in een archiefagenda (naam begint met ZZ ARCHIEF), alleen om te lezen.
    Gezien 24-09-2026: Calendly boekte nog in 'ZZ ARCHIEF haagendalightprojects' (5520 Downs,
    2603 Lisa Cuppens) en niemand zag ze. Ze komen in het dagplan, het belrooster en de
    botsingen, en als signaal 'hoort op werk'. Schrijven blijft verboden (mag_schrijven)."""
    try:
        namen = agenda.kalendernamen()
    except Exception:  # noqa: BLE001
        return []
    ids = [k for k, naam in namen.items() if naam.strip().upper().startswith(ARCHIEFVOORVOEGSEL)]
    if not ids:
        return []
    os.environ["CONTRACTEN_KALENDERS"] = ",".join(ids)
    try:
        uit = [a for a in agenda.afspraken(van_dagen, tot_dagen) if not a.get("fout")]
    finally:
        os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())
    for a in uit:
        a["_archief"] = namen.get(a["kalender"], a["kalender"])
    return uit


# Hoe ver vooruit ik ritten zet. Gewoon acht dagen, want werkafspraken schuiven. De
# agenda van Lara loopt in vaste reeksen per schooljaar; die ritten zet ik tot het
# einde ervan, zodat Mehdi ze vooruit ziet. Mandaat van Mehdi, 21-09-2026.
RIT_VOORUIT_DAGEN = {"Lara": 300}
# Afspraak is afspraak: elke buitenafspraak krijgt meteen haar ritten, hoe ver vooruit ook. Mehdi, 28-09-2026,
# toen de zitting van 23-11 geen rit kreeg: "hoe komt dat je heen en terug niet gerekend hebt ... afspraak is
# afspraak". Dat vervangt de acht dagen van 21-09. Ver vooruit kost niets: Google telt alleen binnen 48 uur,
# daarbuiten is het OSRM met de filefactor, en die rijtijden bewaar ik (FR-65).
RIT_VOORUIT_ALLES = 365


def verre_afspraken():
    """De afspraken voorbij de gewone acht dagen, van elke agenda die ik lees, tot een jaar vooruit."""
    uit = []
    for kid, naam in KALENDERS.items():
        dagen = max(RIT_VOORUIT_DAGEN.get(naam, 0), RIT_VOORUIT_ALLES)
        if kid.startswith("en.be#"):
            continue
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
    nog in KALENDERS staan. Lukt het opvragen niet, dan weet ik niet wat archief is: None, en mag_schrijven zegt
    dan nee. Tot 02-10-2026 gaf een fout hier een lege set, en dus schrijfrecht overal (audit A12, FR-94)."""
    try:
        namen = agenda.kalendernamen()
    except Exception:  # noqa: BLE001
        return None
    return {k for k, naam in namen.items() if naam.strip().upper().startswith(ARCHIEFVOORVOEGSEL)}


def lees_titel(titel):
    """Ontleedt een titel volgens Mehdi's titelconventie. Geeft dict met firma, soort, type,
    nummer, klant, buiten (!!), onzeker (??), reistijd, conform."""
    t = titel.strip()
    # Ook wat Mehdi zelf als rit schrijft telt als reistijd: "Rijden naar huis",
    # "Rijden naar Stadskantoor". Anders meldt de wacht die als afspraak zonder code
    # en zet hij er een tweede reistijdblok naast. Gezien 20-09-2026.
    # En "Lara naar huis brengen" is de rit naar huis na de zwemles. Gezien 24-09-2026: die stond
    # als gewone afspraak, zonder autootje en met de melding van de agenda.
    # Een opmerking tussen haakjes maakt van een afspraak geen rit: '[TKNB-IN] Tom bellen (onderweg naar
    # Aalst)' kreeg op 26-09-2026 het autootje en rood (FR-61).
    uit = {"reistijd": bool(re.search(r"reistijd|\brijden naar\b|\bonderweg naar\b|\bnaar huis\b",
                                      re.sub(r"\([^)]*\)", "", t), re.I))
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
    rest = re.sub(r"^\s*((ZL|VR)\s+)+", "", rest)
    rest = re.sub(r"^\s*(mehdi|siyan|shelton|angela)[^:]{0,40}:\s*", "", rest, flags=re.I).strip(" -")
    mt = TYPE_RE.match(rest)      # hoofdletters: 'Ren' of 'Kim' als klantnaam is geen code
    if mt:
        uit["type"] = TYPE_ALIAS.get(mt.group(1).upper(), mt.group(1).upper())
        uit["type_geschreven"] = mt.group(1)
        rest = rest[mt.end():].strip(" -")
    if uit["type"] in BUITEN_TYPES:
        uit["buiten"] = True
    # Het adres is geen projectnummer: niet de postcode en niet het huisnummer. Gezien 26-09-2026: 'Hamid,
    # Nieuwstraat 39, 3360 Korbeek-Lo' werd project 3360; op 28-09 werd 'Shaniel, Mechelsesteenweg 1143, 3020
    # Herent' project 1143 en viel het huisnummer uit de belzin (FR-58). In de titelvorm staat het projectnummer
    # altijd voor de eerste komma, het adres erna.
    # vier tot zes cijfers: H-Architects JJNN (2607), TKN-Buro 46118 en vanaf 2026 260009 (FR-80)
    mn = re.search(r"\b(\d{4,6})\b", rest.split(",", 1)[0])
    if mn:
        uit["nummer"] = mn.group(1)
    kaal = re.sub(rf"\b{uit['nummer']}\b", "", rest, count=1) if uit["nummer"] else rest
    uit["klant"] = kaal.strip(" -:").split(" - ")[0][:80]
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


class DagMarkering(Exception):
    """Een afspraak op een dag die een hele-dag-markering afsluit; alleen met een ja van Mehdi (FR-83)."""


# Mehdi, 01-10-2026: "Morgen stond er op de agenda geen buitenafspraken, Lara ... je moet echt deterministisch worden ...
# zodra we een moment willen afspreken, had je eigenlijk moeten kijken". Een hele-dag-markering is een stop, geen
# achtergrond. Wat elke markering die dag verbiedt:
DAG_MARKERINGEN = (
    (re.compile(r"geen\s+buiten\s*-?\s*afspraken", re.I), "buiten"),
    (re.compile(r"geen\s+auto", re.I), "buiten"),
    # in het buitenland: geen buitenafspraken en ook geen online boekingen via de agenda (Mehdi, 01-10-2026)
    (re.compile(r"\bbuitenland\b", re.I), "alles"),
    (re.compile(r"^\W*(?:mehdi\s*:\s*)?geen\s+afspraken\W*$", re.I), "alles"),
)
_MARKERS = {}


def _transparantie(a, tok):
    """Wat Google nu als transparency van deze afspraak teruggeeft ('opaque' als het veld ontbreekt: dat is de standaard)."""
    import urllib.parse
    import urllib.request
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(a['id'], safe='')}?fields=transparency")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    return json.load(urllib.request.urlopen(req, timeout=30)).get("transparency") or "opaque"


def bezet_splitsen(regels):
    """(gezet, mislukt) uit de regels van markeringen_bezet: een mislukte teruglezing is nooit 'gezet' (v1.2, V12)."""
    mis = [r for r in regels if "niet op Bezet gezet" in r]
    return [r for r in regels if r not in mis], mis


def markeringen_bezet(items, tok=None):
    """Een markering die alles afsluit ('geen afspraken', 'Buitenland') moet in Google op Bezet staan, anders telt Calendly
    ze niet. Google zet een hele-dag-item standaard op Beschikbaar. Gezien 01-10-2026: zaterdag 03-10 'geen afspraken'
    stond op Beschikbaar en Jordy Scheurmans boekte via Calendly om 10:30 (FR-84). Geeft de lijst die ik op Bezet zette."""
    gezet = []
    for a in items:
        if not a.get("hele_dag") or not a.get("_vrij") or a.get("_archief"):
            continue
        if any(wat == "alles" and patroon.search(a.get("titel") or "") for patroon, wat in DAG_MARKERINGEN):
            try:
                _tok = tok or agenda._toegang()
                _patch(a, {"transparency": "opaque"}, _tok)
                # teruglezen: pas Bezet als Google het zo teruggeeft (audit A15)
                if _transparantie(a, _tok) != "opaque":
                    raise RuntimeError("Google geeft nog Beschikbaar terug")
                a["_vrij"] = False
                gezet.append(f"{a['start'][:10]} {a['titel'][:50]}: op Bezet gezet, zodat Calendly die dag niet boekt")
            except Exception as e:  # noqa: BLE001
                gezet.append(f"{a['start'][:10]} {a['titel'][:50]}: niet op Bezet gezet ({type(e).__name__})")
    return gezet


def markeringen_uit(items, dag):
    """[(titel, wat verboden is)] van de hele-dag-items die deze dag dekken. Pure functie op de items."""
    uit = []
    for x in items:
        if not x.get("hele_dag"):
            continue
        s, e = (x.get("start") or "")[:10], (x.get("einde") or "")[:10]
        if not (s == dag or s <= dag < (e or s)):
            continue
        for patroon, wat in DAG_MARKERINGEN:
            if patroon.search(x.get("titel") or ""):
                uit.append(((x.get("titel") or "").strip(), wat))
                break
    return uit


def dagmarkeringen(dag):
    """De markeringen van een dag over alle agenda's, een keer per dag gelezen. Is een agenda die dag niet te lezen,
    dan weet ik niet of de dag afgesloten is: DagMarkering, dus niet schrijven, en niet onthouden, zodat de volgende
    keer opnieuw gelezen wordt. Tot 02-10-2026 telde een fout als 'geen markering' (audit A12, FR-94)."""
    if dag not in _MARKERS:
        try:
            from datetime import date as _d
            off = (_d.fromisoformat(dag) - nu_lokaal().date()).days
            items = afspraken(off, off + 1)
        except Exception as e:  # noqa: BLE001
            raise DagMarkering(f"de markeringen van {dag} zijn niet te lezen ({type(e).__name__}): niets geschreven") from e
        stuk = [x.get("kalender", "?") for x in items if x.get("fout")]
        if stuk:
            raise DagMarkering(f"de markeringen van {dag} zijn niet volledig te lezen ({', '.join(KALENDERS.get(k, k)[:20] for k in stuk)}): niets geschreven")
        _MARKERS[dag] = markeringen_uit(items, dag)
    return _MARKERS[dag]


def markering_tegen(titel, dag, markers=None):
    """De markering die een afspraak met deze titel op deze dag tegenhoudt, of None. Een rit, een hele-dag-item en Lara
    zelf (de reden van de markering) tellen niet."""
    t = (titel or "").strip()
    if not t or not dag or t.startswith("\U0001F697") or "[LARA]" in t.upper() or "[LA]" in t.upper():
        return None
    info = lees_titel(t)
    if info["reistijd"]:
        return None
    buiten = info["buiten"] or info["soort"] in BUITEN_SOORTEN
    for m, wat in (dagmarkeringen(dag) if markers is None else markers):
        if wat == "alles" or (wat == "buiten" and buiten):
            return m
    return None


def mag_schrijven(kal):
    """Mandaat van Mehdi, 20-09-2026: uit het archief mag ik lezen, er nooit iets
    nieuws in zetten. Schrijven mag alleen in de agenda's die vandaag in gebruik
    zijn, en nooit in iets dat op ZZ ARCHIEF staat. Dit staat hier in de code en
    niet alleen in de rechten bij Google, want de agent draait op het account van
    Mehdi zelf en heeft daar overal schrijfrecht."""
    arch = gearchiveerd()
    return kal in KALENDERS and arch is not None and kal not in arch


def canoniek(titel, online=None):
    """De titel zoals de agent hem schrijft: alleen codes van twee letters. Elke schrijfroute en elk voorstel gaat
    hierdoor, zodat geen enkele route nog HARC of UNABO kan schrijven (nacontrole v1.2, V1, FR-104). B2B wordt alleen
    XB of XO als buiten of online vaststaat."""
    return codes_twee_letters(titel or "", online) if titel else titel


def _patch(a, body, tok, toch=False):
    import urllib.parse
    import urllib.request
    if not mag_schrijven(a["kalender"]):
        raise GeenSchrijfrecht(a["kalender"])
    if body.get("summary"):
        body["summary"] = canoniek(body["summary"])
    # een afspraak naar een dag verzetten die een markering afsluit, kan alleen met een ja van Mehdi (FR-83)
    if "start" in body and not toch:
        dag = ((body.get("start") or {}).get("dateTime") or "")[:10]
        m = markering_tegen(body.get("summary") or a.get("titel"), dag)
        if m:
            raise DagMarkering(f"{dag} staat '{m}': '{(body.get('summary') or a.get('titel') or '')[:60]}' kan die dag niet zonder ja van Mehdi")
    elif "start" in body:
        _ja_stempel(body, ((body.get("start") or {}).get("dateTime") or "")[:10])
    # sendUpdates=none: een gast krijgt nooit een mail omdat de agent iets bijzet. Google
    # doet dat standaard ook niet, maar hier staat het expliciet, met een test erop.
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(a['id'], safe='')}?sendUpdates=none")
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
        if info["reistijd"]:
            # Mijn eigen ritten krijgen hun melding van reistijd_zetten. Een rit die iemand met de
            # hand zette ("Rijden naar Stadskantoor") stond op de agendastandaard: 30 minuten
            # vooraf, midden in de afspraak ervoor. Gezien 24-09-2026 in Genk. Zo'n rit krijgt
            # dezelfde melding als de mijne: heen 5 minuten vooraf, naar huis stil. Een melding
            # die iemand zelf koos, laat ik staan.
            standaard = r.get("useDefault", True) and not (r.get("overrides") or [])
            if standaard and "OSRM" not in (a.get("omschrijving") or "") and not a.get("hele_dag"):
                naar_huis = bool(re.search(r"naar huis|→\s*thuis", a["titel"], re.I))
                try:
                    _patch(a, {"reminders": {"useDefault": False, "overrides": [] if naar_huis else
                                             [{"method": "popup", "minutes": 5}]}}, tok)
                    if naar_huis:
                        weg += 1
                    else:
                        gezet += 1
                except Exception as e:  # noqa: BLE001
                    fout += 1
                    print("rit-melding mislukt:", a["titel"][:40], type(e).__name__, file=sys.stderr)
            continue
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
KLEURNAAM = {"4": "roze", "6": "oranje", "11": "rood", "7": "blauw", "10": "groen", "5": "geel",
             "1": "lavendel", "2": "salie", "3": "paars (druif)", "8": "grafiet", "9": "bosbes"}

# Welke kleur zette ik zelf? Dat staat als onzichtbaar merk in de afspraak (Google:
# extendedProperties.private, alleen op deze agenda). Zo weet ik of een kleur van mij komt
# of van een mens. Gezien 24-09-2026: om 00:15 kregen de UNABO-overleggen paars en AI
# stabiliteit geel, niet door de agent; de ronde erna had dat stil teruggezet, zoals eerder
# met AI stabiliteit van 30-09. Een kleur die een mens zette, is een vraag, geen fout.
KLEURMERK = "agendawacht_kleur"
# Een ja van Mehdi voor een afspraak op een afgesloten dag (toch=True) staat op de afspraak zelf, zodat de
# dagcontrole het niet opnieuw vraagt (audit A13, FR-92).
JA_MERK = "agendawacht_ja"


def _ja_stempel(body, dag):
    body.setdefault("extendedProperties", {}).setdefault("private", {})[JA_MERK] = dag or "ja"
    return body


def kleur_actie(a, wens):
    """Wat doe ik met de kleur van deze afspraak? Geeft 'goed', 'merken' (klopt, maar mijn
    merk ontbreekt nog), 'zetten' (leeg, of een kleur die ik zelf zette en die niet meer
    klopt) of 'herstellen' (iets anders zette een andere kleur: terugzetten en melden).
    Mehdi, 25-09-2026: "ik zie op vandaag dat verschillende interne gesprekken verschillende
    kleuren hebben ... waarom los je niet constructief deze type problemen op". De kleur volgt
    de titel; wie iets anders wil tonen, verandert de titel (?? voor onzeker)."""
    huidig = a.get("_kleur") or ""
    merk = (a.get("_merk") or {}).get(KLEURMERK, "")
    if huidig == wens:
        return "goed" if merk == wens else "merken"
    if not huidig or huidig == merk or "OSRM" in (a.get("omschrijving") or ""):
        return "zetten"
    return "herstellen"
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


def _vaste_plekken():
    """Wat Mehdi met een woord bedoelt, uit werkwijze/agenda-taken.json (vaste_plekken). Mehdi, 01-10-2026: "als ik KBC
    kantoor zeg dan is het altijd in de KBC Ladeuze in Leuven". Geen adresboek: alleen wat hij zo vastlegt."""
    try:
        return json.loads((Path(__file__).resolve().parent / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8")).get("vaste_plekken") or {}
    except (OSError, ValueError):
        return {}


def vaste_plek(tekst):
    """(woord, plek) als een vaste plek van Mehdi in de tekst staat, anders (None, None)."""
    for woord, plek in _vaste_plekken().items():
        if isinstance(plek, dict) and plek.get("adres") and re.search(rf"(?<![\w]){re.escape(woord)}(?![\w])", tekst or "", re.I):
            return woord, plek
    return None, None


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
    # Gemeten 24-09-2026: dit account zette "Rijden naar huis" en "Rijden naar Stadskantoor",
    # geen Calendly-boekingen. Wie erachter zit (Chilton?) moet Mehdi nog bevestigen.
    "haagendalightprojects@gmail.com": "account light projects (handmatig)",
    "zoomafspraken@gmail.com": "Calendly (zoom)",
    "unabosdp@gmail.com": "Calendly (UNABO)",
    "contraxcalendar@gmail.com": "Calendly (Contrax)",
}


# Accounts die alleen Calendly gebruikt: daar staat Calendly al in de naam.
CALENDLY_ACCOUNTS = {"zoomafspraken@gmail.com", "unabosdp@gmail.com", "contraxcalendar@gmail.com"}


def maker(a):
    """Wie de afspraak heeft aangemaakt, als een naam die Mehdi herkent. Een
    boekingsaccount noem ik bij zijn rol, een echt persoon zoek ik op in
    organisatie.globaal.be, en anders toon ik het deel voor de @. Mandaat van
    Mehdi, 22-09-2026: zo weet hij wie iets zette en waarom het ergens staat."""
    mail = (a.get("maker") or "").strip().lower()
    if not mail:
        return ""
    # Een Calendly-boeking herken ik aan de inhoud (de annuleer- en verzetlinks van
    # calendly.com), niet aan het account. Gezien 24-09-2026: boekingen op de werkagenda
    # stonden als "Mehdi zelf", en handmatige ritten van light projects als "Calendly".
    if "calendly.com" in (a.get("omschrijving") or "").lower() and mail not in CALENDLY_ACCOUNTS:
        return "Calendly (" + {"mehdiprivewerkagenda@gmail.com": "werkagenda"}.get(
            mail, BOEKINGSACCOUNTS.get(mail, mail.split("@")[0])) + ")"
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


def titel_voorstel(titel, online=None):
    """Leest vrije tekst en geeft (nieuwe titel of None, firma, soort, uitleg). Buiten of online komt uit de tekst
    ('online', 'buiten', '!!') of uit de afspraak zelf (online: True/False/None). Staat het nergens, dan geen soort
    en dus een voorstel met beide mogelijkheden, nooit een gok (nacontrole v1.2, V2, FR-105)."""
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
        waar = "B" if "!!" in titel else ({True: "O", False: "B"}.get(online))
    if soort_code == "B2B":
        rol, soort_code = "X", None
    soort = soort_code or ("IN" if rol == "IN" else (rol + waar if rol and waar else None))
    over = rest
    for w in sorted(set(weg), key=len, reverse=True):
        over = re.sub(r"(?<![\w])" + re.escape(w) + r"(?![\w])", " ", over)
    over = re.sub(r"\s*-\s*(?=\s|$)", " ", over)
    over = re.sub(r"\s+", " ", over).strip(" -,")
    code = f"[{titelcode(firma)}-{soort}]" if soort else f"[{titelcode(firma)}]"
    nieuw = f"{kop.strip()}: {code}" + (f" {over}" if over else "")
    if soort:
        uitleg = f"firma {firma} uit de tekst, soort {soort}"
    elif rol and rol != "IN":
        uitleg = (f"firma {firma} uit de tekst; buiten of online staat nergens: [{titelcode(firma)}-{rol}B] (buiten) of "
                  f"[{titelcode(firma)}-{rol}O] (online)?")
    else:
        uitleg = f"firma {firma} uit de tekst, soort niet te bepalen"
    return nieuw, firma, soort, uitleg


def codes_twee_letters(titel, online=None):
    """Zet firma-, soort- en opdrachtcode in een titel om naar twee letters: [HARC-KB] WB -> [HA-KB] WB,
    [UNABO-PO] Stijn - STA -> [UB-PO] Stijn - ST, [TKNB-IN] AI+AT -> [TK-IN] AI. B2B wordt XB of XO, maar alleen
    als buiten of online vaststaat (online: True/False/None). Geeft de nieuwe titel (of dezelfde)."""
    m = CODE_RE.search(titel)
    if not m:
        return titel
    info = lees_titel(titel)
    firma, soort = info.get("firma"), (m.group(2) or "").upper()
    if soort == "B2B":
        if "!!" in titel or online is False:
            soort = "XB"
        elif online is True:
            soort = "XO"
    code = f"[{titelcode(firma)}-{soort}]" if soort else f"[{titelcode(firma)}]"
    nieuw = titel[:m.start()] + code + titel[m.end():]
    # het opdrachttype meteen na de code (of na een dubbelpunt): oude code -> nieuwe
    na = nieuw[m.start() + len(code):]
    mt = re.match(r"(\s*:?\s*)(" + "|".join(re.escape(k) for k in sorted(TYPE_ALIAS, key=len, reverse=True)) + r")(?![\w+])", na)
    if mt:
        na = na[:mt.start(2)] + TYPE_ALIAS[mt.group(2)] + na[mt.end(2):]
    # ook in titels waar het type na de naam staat: '[UNABO-PO] Stijn Hahn - STA'
    na = re.sub(r"(\s-\s*)(" + "|".join(re.escape(k) for k in sorted(TYPE_ALIAS, key=len, reverse=True)) + r")(\s*$)",
                lambda x: x.group(1) + TYPE_ALIAS[x.group(2)] + x.group(3), na)
    return nieuw[:m.start() + len(code)] + na


def _online(a):
    loc = (a.get("locatie") or "").lower()
    if loc.startswith("http") or "zoom.us" in loc or re.search(r"zoom\.us/j/", a.get("omschrijving") or ""):
        return True
    if loc and not loc.startswith("http"):
        return False
    return None


def titels_normaliseren(items, alleen_dag=None):
    """Vrije tekst naar de titelcode, alleen voor afspraken die Mehdi zelf maakte, zonder gasten.
    Eenduidig (firma én soort) -> herschrijven. Anders -> een voorstel in de regels.
    Een code van drie of vier letters (HARC, UNABO, STA, AI+AT) -> twee letters (Mehdi, 02-10-2026). Met gasten
    of in een reeks wordt het een voorstel; een reeks zet codes_reeksen in een keer om."""
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
        if info.get("firma"):
            kandidaat = codes_twee_letters(titel, _online(a))
            if kandidaat != titel:
                if _van_mehdi(a) and not a.get("_terugkerend"):
                    nieuw, uitleg = kandidaat, "codes van twee letters (Mehdi, 02-10-2026)"
                elif not a.get("_terugkerend"):
                    regels.append(f"{a['start'][:16]} {titel[:50]}: VOORSTEL '{kandidaat[:70]}' (twee letters; met gasten verander ik de titel niet)")
        else:
            nieuw, firma, soort, uitleg = titel_voorstel(titel, _online(a))
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


def codes_reeksen(items, droog=False):
    """Een terugkerende afspraak van Mehdi zelf (zonder gasten) krijgt de codes van twee letters in de reeks zelf, een
    keer; op de agenda van Lara wordt [LARA] [LA]. Geeft (gezet, regels)."""
    import urllib.parse
    import urllib.request
    tok = agenda._toegang()
    gedaan, regels, gezien = 0, [], set()
    for a in items:
        if not a.get("_reeks") or a["_reeks"] in gezien or a.get("deelnemers") or a.get("_archief") \
                or not mag_schrijven(a.get("kalender", "")) or (a.get("maker") or WERKAGENDA).lower() != WERKAGENDA:
            continue
        gezien.add(a["_reeks"])
        try:
            url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='@')}/events/{urllib.parse.quote(a['_reeks'])}"
            reeks = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer " + tok}), timeout=30))
            oud = reeks.get("summary") or ""
            if [g for g in reeks.get("attendees") or [] if (g.get("email") or "").lower() not in agenda.interne_adressen()]:
                continue          # gasten van buiten: een voorstel; een agendagast (collega) telt niet (03-10-2026)
            nieuw = re.sub(r"\[LARA\]", "[LA]", oud, flags=re.I) if "[LARA]" in oud.upper() else codes_twee_letters(oud, _online(a))
            if nieuw == oud:
                continue
            if not droog:
                _patch({"kalender": a["kalender"], "id": a["_reeks"], "titel": oud}, {"summary": nieuw}, tok)
            gedaan += 1
            regels.append(f"reeks '{oud[:50]}' -> '{nieuw[:60]}'")
        except Exception as e:  # noqa: BLE001
            regels.append(f"reeks {a['titel'][:45]}: niet omgezet ({type(e).__name__})")
    return gedaan, regels


def tekens_vooraan(titel):
    """'!!' staat altijd helemaal vooraan, voor de naam; alleen VR gaat er nog voor. Mehdi, 28-09-2026: "ik wil
    dat !! altijd eerst is en dan mijn naam". Een rit (autootje) blijft zoals hij is (FR-64)."""
    # alleen het teken zelf, niet de uitroep achter een woord ('Lara jaardag!!')
    if not re.search(r"(?<!\w)!!", titel) or titel.lstrip().startswith("\U0001F697"):
        return titel
    vr = re.match(r"^\s*VR\s+", titel)
    kern = titel[vr.end():] if vr else titel
    kern = re.sub(r"\s{2,}", " ", re.sub(r"\s*(?<!\w)!!\s*", " ", kern)).strip()
    return ("VR " if vr else "") + "!! " + kern


def uitroep_vooraan(items, alleen_dag=None):
    """Zet !! vooraan in elke komende titel zonder gasten, op elke agenda waar ik mag schrijven. Een reeks krijgt
    het een keer, in de reeks zelf. Geeft (gezet, regels)."""
    import urllib.parse
    import urllib.request
    tok = agenda._toegang()
    nu = nu_lokaal().isoformat()
    gedaan, regels, reeksen = 0, [], set()
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a["start"] < nu[:len(a["start"])] \
                or a.get("_archief") or a.get("deelnemers") or not mag_schrijven(a.get("kalender", "")):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        nieuw = tekens_vooraan(a["titel"])
        if nieuw == a["titel"]:
            continue
        try:
            if a.get("_reeks"):
                if a["_reeks"] not in reeksen:
                    reeksen.add(a["_reeks"])
                    url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='@')}/events/{urllib.parse.quote(a['_reeks'])}"
                    reeks = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer " + tok}), timeout=30))
                    nieuw_reeks = tekens_vooraan(reeks.get("summary") or "")
                    if nieuw_reeks != (reeks.get("summary") or ""):
                        _patch({"kalender": a["kalender"], "id": a["_reeks"]}, {"summary": nieuw_reeks}, tok)
                        regels.append(f"reeks '{(reeks.get('summary') or '')[:50]}' -> '{nieuw_reeks[:60]}'")
                        gedaan += 1
            else:
                _patch(a, {"summary": nieuw}, tok)
                regels.append(f"{a['start'][:16]} '{a['titel'][:50]}' -> '{nieuw[:60]}'")
                gedaan += 1
            a["titel"] = nieuw
        except Exception as e:  # noqa: BLE001
            regels.append(f"{a['start'][:16]} {a['titel'][:45]}: !! niet vooraan gezet ({type(e).__name__})")
    return gedaan, regels


_KLANTEN = {}
KLANTEN_CACHE = os.path.expanduser("~/appportal/mijnagents-data/klanten.json")


def _klanten_cache():
    try:
        return json.load(open(KLANTEN_CACHE))
    except (OSError, ValueError):
        return {}


def _namen_uit_contract(tekst):
    """De opdrachtgevers uit een architectuurovereenkomst: 'Naam: Carolan Patrick Rijksregisternummer ...'
    -> ['Patrick Carolan']. Alleen de naam; een rijksregisternummer lees ik niet uit en bewaar ik nooit."""
    kop = tekst.split("Hierna genoemd", 1)[0][:4000]
    uit = []
    for n in re.findall(r"Naam:\s*([A-Za-zÀ-ÿ' .-]+?)\s+Rijksregisternummer", kop):
        delen = n.split()
        if len(delen) >= 2:
            uit.append(f"{delen[-1]} {' '.join(delen[:-1])}")
    return uit


def klant_van_nummer(nr):
    """De klant bij een H-Architects-projectnummer. Ik vraag het aan wie het weet, in deze volgorde:
    1. het contractsysteem (contracten.globaal.be): het dossier met precies dat projectnummer;
    2. de projectmap in H-A WORK: het contract in '0. General Information/2. Contract' (de opdrachtgevers),
       anders de CLAUDE.md van het project (de bouwheer);
    3. de agenda van vroeger: de naam die al bij dat nummer stond;
    4. Pipedrive: de persoon van de deal, als laatste.
    Mehdi, 24-09-2026: 'waarom kijk je in de salesmap, je moet in de architectuurmap kijken ... Norma is
    1,5 jaar klant ... waarom praat je niet met andere agenten om slimmer te worden'. Een gevonden naam
    bewaar ik dertig dagen, met de bron erbij."""
    if nr in _KLANTEN:
        return _KLANTEN[nr]
    cache = _klanten_cache()
    c = cache.get(nr) or {}
    if c.get("naam") and time.time() - c.get("ts", 0) < 30 * 86400:
        _KLANTEN[nr] = c["naam"]
        return c["naam"]
    naam, bron = "", ""
    # 1 het contractsysteem
    try:
        import contracten_mcp
        r = contracten_mcp.call("zoek", term=nr)
        for d in (r.get("dossiers") if isinstance(r, dict) else []) or []:
            if str(d.get("project_nummer")) == nr and d.get("klant"):
                naam, bron = d["klant"].strip(), "contractsysteem"
                break
    except Exception:  # noqa: BLE001
        pass
    # 2 de projectmap: het contract, anders de CLAUDE.md van het project
    kaart = (projectadressen.index() or {}).get(nr) or {}
    if not naam and kaart.get("map"):
        import bronnen
        try:
            for e in bronnen.lijst(kaart["map"] + "/0. General Information/2. Contract", recursief=False) or []:
                if e.get(".tag") == "file" and e["name"].lower().endswith(".pdf") and e["name"].startswith(nr):
                    namen = _namen_uit_contract(bronnen.pdf_tekst(bronnen.download(e["path_display"])) or "")
                    if namen:
                        naam, bron = " & ".join(namen), "contract in de projectmap"
                        break
        except Exception:  # noqa: BLE001
            pass
        if not naam:
            try:
                md = bronnen.download(kaart["map"] + "/CLAUDE.md", 200_000).decode("utf-8", "ignore")
                m = re.search(r"bouwheer\s*\|\s*([^—|\n]+?)\s*(?:—|\||$)", md, re.I | re.M)
                if m:
                    naam, bron = m.group(1).strip(), "CLAUDE.md van het project"
            except Exception:  # noqa: BLE001
                pass
    # 3 de agenda van vroeger
    if not naam:
        try:
            naam = _naam_uit_oude_agenda(nr)
            bron = "de agenda van vroeger" if naam else ""
        except Exception:  # noqa: BLE001
            naam = ""
    # 4 Pipedrive, als laatste
    if not naam:
        try:
            d = pipedrive.get("harchitects", "/deals/search", {"term": nr, "fields": "title", "limit": 5})
            lijst = d.get("items") if isinstance(d, dict) else d
            for it in lijst or []:
                x = it.get("item", it)
                if re.match(rf"^\s*{re.escape(nr)}\b", x.get("title") or ""):
                    naam = ((x.get("person") or {}).get("name") or re.sub(rf"^\s*{re.escape(nr)}\s*", "", x["title"])).strip()
                    bron = "Pipedrive"
                    break
        except Exception:  # noqa: BLE001
            naam = ""
    if naam.islower():
        naam = naam.title()          # 'lisa cuppens' uit een mail wordt 'Lisa Cuppens'
    _KLANTEN[nr] = naam
    if naam:
        cache[nr] = {"naam": naam, "bron": bron, "ts": time.time()}
        try:
            os.makedirs(os.path.dirname(KLANTEN_CACHE), exist_ok=True)
            json.dump(cache, open(KLANTEN_CACHE, "w"), ensure_ascii=False, indent=0)
        except OSError:
            pass
    return naam


def _naam_uit_oude_agenda(nr):
    """De naam die in de afgelopen twee jaar al bij dit nummer stond ('2505 - Norma Gleeson'), in alle
    agenda's van het account, ook de archieven. De meest gebruikte naam wint."""
    import urllib.parse
    import urllib.request
    from collections import Counter
    tok = agenda._toegang()
    van = (nu_lokaal() - timedelta(days=730)).isoformat()
    tel = Counter()
    for kal in agenda.kalendernamen():
        url = (f"{agenda.API}/calendars/{urllib.parse.quote(kal, safe='')}/events?"
               + urllib.parse.urlencode({"q": nr, "timeMin": van, "singleEvents": "true", "maxResults": 50}))
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"}), timeout=30))
        except Exception:  # noqa: BLE001
            continue
        for ev in d.get("items", []):
            m = re.search(rf"\b{re.escape(nr)}\b\s*[-:]?\s*([A-ZÀ-Ý][A-Za-zÀ-ÿ'-]+(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'-]+){{0,3}})", ev.get("summary") or "")
            if m and "@" not in m.group(1) and not re.search(r"straat|steenweg|laan|weg\b", m.group(1), re.I):
                tel[m.group(1).strip()] += 1
    return tel.most_common(1)[0][0] if tel else ""


# Welke woorden in een titel naar welke activiteit wijzen (beslist 25-09-2026). Per firma alleen de
# codes die voor die firma gelden; wijzen de woorden naar meer dan een code, dan geen voorstel.
ACTIVITEIT_WOORDEN = {
    "HARC": [(r"voorlopige oplevering", "VO"), (r"definitieve oplevering", "DO"), (r"\boplevering\b", "OP"), (r"werfbezoek", "WB"),
             (r"plaatsbezoek", "PL")],
    "UNAB": [(r"stabiliteit", "ST"), (r"barst|scheur", "BS"), (r"\bEPB\b", "EP"), (r"ventilatie", "VE"), (r"blower", "BD"),
             (r"vergunning|melding", "VG"), (r"functiewijziging", "FW"), (r"regularisatie", "RG"), (r"plaatsbeschrijving", "PS"),
             (r"3D.?scan|scanning", "SC"), (r"render", "RD"), (r"veiligheid|\bVC\b", "VC"), (r"landmeter|afpaling|muurovername", "LM"),
             (r"ontwerp|schets", "SD"), (r"drafting", "DR"), (r"meetstaat", "MT"), (r"kennismaking", "KM"), (r"offerte", "OB"),
             (r"bundel", "BU"), (r"plaatsbezoek", "PL")],
    "intern": [(r"\bAI\b|automation|automatisering", "AI")],
}


def activiteit_voorstel(titel, info):
    """De activiteitscode die de woorden in de titel eenduidig aanwijzen, of ''."""
    if info.get("type") or info["reistijd"] or not info.get("firma"):
        return ""
    lijst = ACTIVITEIT_WOORDEN["intern"] if info["soort"] == "IN" else ACTIVITEIT_WOORDEN.get(info["firma"], [])
    rest = CODE_RE.sub(" ", titel)
    codes = {code for rx, code in lijst if re.search(rx, rest, re.I)}
    if {"VO", "OP"} <= codes or {"DO", "OP"} <= codes:
        codes.discard("OP")             # 'voorlopige oplevering' bevat ook 'oplevering'
    return next(iter(codes)) if len(codes) == 1 else ""


def met_activiteit(titel, code):
    """Zet de code meteen na [FIRMA-SOORT]. Bij AI valt een los 'AI' of 'Automation' erna weg."""
    nieuw = CODE_RE.sub(lambda m: f"{m.group(0)} {code}", titel, count=1)
    if code == "AI":
        nieuw = re.sub(r"\b(AI)\s+(AI|Automation|automatisering)\b\s*", r"\1 ", nieuw, count=1, flags=re.I).rstrip()
    return re.sub(r"\s{2,}", " ", nieuw)


PIPEDRIVE_VAN = {"HARC": "harchitects", "UNAB": "unabo"}
_DEALS_OP_ADRES = {}


def _deal_op_adres(firma, adres):
    """De deal van die firma met dit adres in de titel (UNABO noemt een deal naar het adres).
    Geeft (klant, gewonnen) of None. De persoonsnaam 'Natasja Gerritsen Natasja' wordt 'Natasja Gerritsen'."""
    straat = adres.split(",")[0].strip()
    sleutel = (firma, straat.lower())
    if sleutel in _DEALS_OP_ADRES:
        return _DEALS_OP_ADRES[sleutel]
    uit = None
    try:
        d = pipedrive.get(PIPEDRIVE_VAN[firma], "/deals/search", {"term": straat, "fields": "title", "limit": 10})
        for it in (d.get("items") if isinstance(d, dict) else d) or []:
            x = it.get("item", it)
            if straat.lower() in (x.get("title") or "").lower():
                naam = ((x.get("person") or {}).get("name") or "").split()
                naam = [w for w in naam if w not in ("PA", "KL")]
                if len(naam) > 2 and naam[-1] == naam[0]:
                    naam = naam[:-1]
                uit = (" ".join(naam), x.get("status") == "won")
                if uit[1]:
                    break
    except Exception:  # noqa: BLE001
        uit = None
    _DEALS_OP_ADRES[sleutel] = uit
    return uit


def titel_uit_onderzoek(a):
    """Een korte titel zonder firmacode ('mehdi; barsten en scheuren') met een adres, zelf uitzoeken:
    de activiteit uit de woorden, de firma uit de activiteit (alleen als die code bij precies een firma hoort),
    klant en soort uit de deal met dat adres (gewonnen = klant). Mehdi, 25-09-2026: 'ik ga niet uitgebreid
    schrijven wat ik ga doen, dit is je werk'. Lukt een stap niet, dan geen titel: dan vraagt de agent het."""
    titel = a["titel"]
    info = lees_titel(titel)
    if info.get("firma") or info["reistijd"] or a.get("hele_dag"):
        return None, ""
    # Spoor 1: een H-Architects-projectnummer (JJNN) met een projectmap. De map ontstaat bij de ondertekening,
    # dus klant; zonder !! is het achter het bureau (online). Gezien 25-09-2026: 'Mehdi: 2607' kreeg een vraag
    # terwijl de bronnen het antwoord hadden (Robin Verlinden en Silvie Boudou).
    kaart = (projectadressen.index() or {}).get(info["nummer"]) if info["nummer"] else None
    if kaart:
        klant = klant_van_nummer(info["nummer"])
        if klant:
            code = next((c for rx, c in ACTIVITEIT_WOORDEN["HARC"] if re.search(rx, titel, re.I)), "")
            buiten = info["buiten"] or code in BUITEN_TYPES
            adres = ((a.get("locatie") or "").strip() or kaart.get("adres", "")) if buiten else ""
            nieuw = (f"{'!! ' if buiten else ''}Mehdi: [{titelcode('HARC')}-K{'B' if buiten else 'O'}] {code + ' ' if code else ''}{info['nummer']} - {klant}"
                     + (f", {re.sub(r',\s*(Belgi[eë]|Belgium)\s*$', '', adres)}" if adres else ""))
            return nieuw, f"uitgezocht: {info['nummer']} is een H-Architects-project met een projectmap, klant {klant}"
    # Spoor 2: een activiteit met een adres
    adres = (a.get("locatie") or "").strip()
    if not adres or adres.lower().startswith("http"):
        return None, ""
    adres = re.sub(r",\s*(Belgi[eë]|Belgium)\s*$", "", adres)
    gevonden = {}
    for firma in ("HARC", "UNAB"):
        for rx, code in ACTIVITEIT_WOORDEN[firma]:
            if re.search(rx, titel, re.I):
                gevonden.setdefault(code, set()).add(firma)
    if "VO" in gevonden or "DO" in gevonden:
        gevonden.pop("OP", None)
    if len(gevonden) != 1:
        return None, ""
    code, firmas = next(iter(gevonden.items()))
    if len(firmas) != 1:
        return None, ""
    firma = next(iter(firmas))
    deal = _deal_op_adres(firma, adres)
    if not deal or not deal[0]:
        return None, ""
    klant, gewonnen = deal
    buiten = code in BUITEN_TYPES or info["buiten"]
    soort = ("K" if gewonnen else "P") + ("B" if buiten else "O")
    nieuw = f"{'!! ' if buiten else ''}Mehdi: [{titelcode(firma)}-{soort}] {code} - {klant}, {adres}"
    return nieuw, f"uitgezocht: activiteit {code}, firma {firma}, klant {klant} ({'getekend' if gewonnen else 'nog niet getekend'}) uit de deal op dit adres"


def titel_aanvulling(a, projecten):
    """Wat ontbreekt aan een titel, als canonieke titel (twee letters, ook in een voorstel: nacontrole v1.2, V1)."""
    nieuw, uitleg = _titel_aanvulling(a, projecten)
    return (canoniek(nieuw, _online(a)) if nieuw else nieuw), uitleg


def _titel_aanvulling(a, projecten):
    """Wat ontbreekt aan een titel om conform te zijn? Geeft (nieuwe titel, uitleg) of (None, '').
    - een rit draagt het autootje vooraan (Mehdi, 24-09-2026: 'autootje niet vergeten');
    - '[HARC-..] nummer' zonder klant krijgt ' - klant' uit Pipedrive, en buiten ook het adres
      uit de agenda of de projectmap: '[FIRMA-SOORT] TYPE nummer - klant, adres'."""
    titel = a["titel"]
    info = lees_titel(titel)
    if not info.get("firma") and not info["reistijd"]:
        return titel_uit_onderzoek(a)
    code = activiteit_voorstel(titel, info)
    if code and not info["reistijd"]:
        nieuw = met_activiteit(titel, code)
        if nieuw != titel:
            return nieuw, f"activiteit {code} ({TYPES.get(code, '')})"
    if info["reistijd"]:
        if not titel.lstrip().startswith("🚗"):
            return "🚗 " + re.sub(r"^\s*!!\s*", "", titel), "een rit draagt het autootje"
        return None, ""
    if info.get("firma") != "HARC" or not info["nummer"]:
        return None, ""
    m = re.search(rf"\b{info['nummer']}\b(.*)$", titel)
    rest = (m.group(1) if m else "").strip(" -,:")
    buiten = info["buiten"] or info["soort"] in BUITEN_SOORTEN
    adres = ""
    if buiten:
        loc = (a.get("locatie") or "").strip()
        adres = loc if loc and not loc.lower().startswith("http") else (projecten.get(info["nummer"]) or {}).get("adres", "")
        adres = re.sub(r",\s*(Belgi[eë]|Belgium)\s*$", "", adres)
    if not rest:
        klant = klant_van_nummer(info["nummer"])
        if klant:
            return (f"{titel.rstrip()} - {klant}" + (f", {adres}" if adres else ""),
                    "klant uit Pipedrive" + (", adres uit de agenda of de projectmap" if adres else ""))
    elif buiten and adres and not re.search(r"\b\d{4}\s+[A-Za-zÀ-ÿ]", rest):
        return f"{titel.rstrip()}, {adres}", "adres bij een buitenafspraak"
    return None, ""


def titels_aanvullen(items, alleen_dag=None):
    """Maakt titels conform (zie titel_aanvulling). Zelf rechtzetten mag bij een afspraak zonder
    gasten die niet terugkeert, ook als een collega ze zette (Mehdi, 24-09-2026: 'zijn vooral
    handmatige of via de calendly die nog niet ok zijn'). Met gasten, Calendly of een reeks:
    een voorstel. Archiefagenda's komen hier nooit binnen."""
    tok = agenda._toegang()
    nu = nu_lokaal().isoformat()
    projecten = projectadressen.index()
    gedaan, regels = 0, []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a["start"] < nu[:len(a["start"])] or a.get("_archief"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if a.get("kalender", "").startswith("en.be#"):
            continue
        nieuw, uitleg = titel_aanvulling(a, projecten)
        nieuw = canoniek(nieuw, _online(a))
        if not nieuw or nieuw == a["titel"]:
            continue
        zelf = (not a.get("deelnemers") and not a.get("_terugkerend") and a.get("kalender") != "zoomafspraken@gmail.com")
        if not zelf:
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: VOORSTEL '{nieuw[:90]}' ({uitleg})")
            continue
        try:
            _patch(a, {"summary": nieuw}, tok)
            regels.append(f"{a['start'][:16]} '{a['titel'][:45]}' -> '{nieuw[:80]}' ({uitleg})")
            a["titel"] = nieuw
            gedaan += 1
        except Exception as e:  # noqa: BLE001
            regels.append(f"{a['start'][:16]} {a['titel'][:45]}: titel niet aangevuld ({type(e).__name__})")
    return gedaan, regels


def _heeft_zl(titel):
    kop = titel.split(":", 1)[0]
    return bool(re.search(r"(^|\s)ZL(\s|$)", kop))


def met_zl(titel):
    """ZL (zonder link) helemaal vooraan, voor ?? en voor alles, zodat Mehdi het meteen ziet.
    Mandaat van Mehdi, 23-09-2026: "die teken van ZL moet van voor komen". Staat ZL al ergens
    anders in de kop, dan schuift het naar voren."""
    if titel.startswith("VR "):
        return "VR " + met_zl(titel[3:])       # VR (vraag van de agent) blijft helemaal vooraan
    if titel.startswith("ZL "):
        return titel
    return "ZL " + (zonder_zl(titel) if _heeft_zl(titel) else titel)


def zonder_zl(titel):
    return re.sub(r"(^|\s)ZL\s+", r"\1", titel, count=1)


RIT_TITEL_RE = re.compile(r"Reistijd (voor|na): (.+?) \(\d+ min")


def titel_sleutel(titel):
    """Dezelfde afspraak, ook na de omzetting naar twee letters of met en zonder ZL: '[HARC-KB] 2443' en '[HA-KB] 2443'
    zijn een titel, net als B2B, XB en XO. Gezien 02-10-2026: na de omzetting leek de rit 'Merksem -> thuis' te verwijzen
    naar een titel die niet meer bestond (FR-91). Ook VR (mijn eigen vraagteken, dat komt en gaat) telt niet."""
    s = codes_twee_letters(zonder_zl(re.sub(r"^\s*VR\s+", "", titel or ""))).strip()
    return re.sub(r"-(?:XB|XO)\]", "-B2B]", s)


def rit_hoort_bij(rit, titel, richting=None):
    """Draagt deze rit de titel van deze afspraak in zijn omschrijving ('Reistijd voor: <titel> (..'), ongeacht de code."""
    m = RIT_TITEL_RE.search(rit.get("omschrijving") or "")
    return bool(m) and (richting is None or m.group(1) == richting) and titel_sleutel(m.group(2)) == titel_sleutel(titel)


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
        if not namen and info["soort"] in EXTERN_ONLINE and info.get("klant"):
            namen = [info["klant"]]       # '[HARC-KO] 2607 - Robin Verlinden en Silvie Boudou': de klant (25-09-2026)
        if not namen:
            continue                      # een taak zonder iemand anders heeft geen link nodig
        wie = ", ".join(namen)
        wijzig = {}
        if met_zl(titel) != titel:
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
            fouten.append(f"geen firmacode, wellicht [{titelcode(voorstel)}]")
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
                fouten.append(f"geen firmacode, maar de namen wijzen naar [{titelcode(firmas[0])}]")
            elif firmas:
                fouten.append("geen firmacode; de namen werken voor " + " of ".join(firmas))
            else:
                fouten.append("geen firmacode")
    if info.get("firma") == "HARC" and info["soort"] in ("PO", "PB") and info["nummer"] \
            and info["nummer"] in projectadressen.index():
        # Een projectmap ontstaat bij de ondertekening (A13): wie er een heeft, is klant. Gezien
        # 24-09-2026: 5520 stond op prospect terwijl de projectmap in 'permission received' stond.
        fouten.append("prospect met een projectmap: is al klant (K in plaats van P)")
    if info.get("firma") and not info["soort"] and a.get("kalender", "") not in AGENDA_VASTE_KLEUR:
        # "[HARC] 2616 Stad Leuven" of "[HARC] Rechtbank": firma wel, soort niet. Een gemeente
        # of rechtbank past in geen enkele soort; dat is een vraag aan Mehdi. Gezien 24-09-2026.
        fouten.append("firmacode zonder soort (welke soort? gemeente of rechtbank past nog nergens)")
    buiten = info["buiten"] or info["soort"] in BUITEN_SOORTEN
    if buiten and "!!" not in (a.get("titel") or ""):
        # Mehdi leest weinig en kijkt: buiten hoort altijd zichtbaar te zijn met !!
        fouten.append("buiten zonder !!")
    eigen_titel = (a.get("maker") or WERKAGENDA).lower() == WERKAGENDA
    if info["soort"] == "IN" and eigen_titel and not namen_in_titel(a.get("titel") or ""):
        # Alleen voor titels van Mehdi zelf: een uitnodiging van een collega ("Afdelings
        # meeting Energy" van ashvand) raakt de agent niet aan, dus hij zeurt er ook niet over.
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
    - Op de werkagenda's: rood als het buiten is, ook met `??` (Mehdi, 29-09-2026); anders geel zolang `??`,
      daarna blauw voor klant online, oranje voor prospect online, groen voor intern.
    - Een titel zonder code krijgt geen kleur en is een fout, geen uitzondering.
    """
    if a.get("kalender", "") in AGENDA_VASTE_KLEUR:
        return ""   # die agenda heeft een vaste kleur, per afspraak niets zetten
    if info["reistijd"]:
        return "11"
    if not info.get("firma"):
        return ""   # geen code: fout, wordt gemeld
    if info["buiten"] or info["soort"] in BUITEN_SOORTEN:
        return "11"   # buiten is altijd rood, ook als het nog niet bevestigd is (Mehdi, 29-09-2026, FR-67)
    if info["onzeker"]:
        return "5"
    if info["soort"] == "AO":
        return "2"    # salie: aannemer online (een aannemer van een klant)
    if info["soort"] in ("B2B", "XO"):
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


HANDKLEUREN = []   # de vragen van de laatste kleurronde


def kleuren_zetten(items, alleen_dag=None):
    """Werkwijze: elke komende afspraak krijgt de kleur van zijn soort. Alleen als de
    kleur afwijkt; agenda's waar Mehdi enkel leesrecht heeft (Lara) kan ik niet
    veranderen en meld ik. Geeft (gezet, al_goed, geen_regel, fout)."""
    tok = agenda._toegang()
    nu_dag = nu_lokaal().date().isoformat()
    gezet, goed, geen, fout, vast = 0, 0, 0, 0, 0
    global HANDKLEUREN
    HANDKLEUREN = []
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
        actie = kleur_actie(a, wens)
        regel = None
        if actie == "herstellen":
            # Iets buiten de agent zette een andere kleur. Ik zet ze terug en meld het, met het
            # tijdstip van die wijziging: zo is te zien wie of wat het doet (FR-20, FR-21).
            regel = (f"{a['start'][:16]} {a['titel'][:55]}: {KLEURNAAM.get(a.get('_kleur'), a.get('_kleur'))} "
                     f"teruggezet naar {KLEURNAAM.get(wens, wens)} (gewijzigd op {(a.get('_gewijzigd') or '?')[:16]} UTC)")
        merk = {"extendedProperties": {"private": {KLEURMERK: wens}}}
        try:
            if actie == "goed":
                goed += 1
                continue
            if actie == "merken":
                _patch(a, merk, tok)
                goed += 1
                continue
            _patch(a, {"colorId": wens, **merk}, tok)
            gezet += 1
            if regel:
                HANDKLEUREN.append(regel)     # pas na een geslaagde patch: 'teruggezet' telt alleen wat lukte (audit A14, FR-95)
        except Exception as e:  # noqa: BLE001
            fout += 1
            print("kleur mislukt:", a["titel"][:40], type(e).__name__, file=sys.stderr)
    return gezet, goed, geen, fout, vast


# Kleurherstel om :17 en :47, ook 's nachts en in het weekend (FR-21). Gemeten 26-09-2026 met een
# volgmeting: elke 30 minuten, om :15 en :45 UTC, zet iets buiten de agent, rechtstreeks bij Google,
# elke afspraak met UNABO of TKNB in de titel voor de komende vier weken op paars en geel, een per seconde. Het zit niet op de server,
# niet op de Mac, niet in Claude of Codex. De volledige ronde kijkt maar acht dagen vooruit en
# draait niet in het weekend, dus bleef de agenda van zaterdag de hele dag fout. Deze korte ronde
# zet alleen de kleuren terug (geen ritten, geen Routes, geen oproepen) en onthoudt wanneer.
KLEUR_VOORUIT_DAGEN = 29
KLEURHERSTEL_LOG = os.path.expanduser("~/appportal/mijnagents-data/agenda-kleurherstel.json")


def kleurherstel():
    """Alleen de kleuren, vier weken vooruit. Geeft het aantal teruggezette kleuren."""
    _slot = slot_nemen()  # noqa: F841
    items = [i for i in afspraken(0, KLEUR_VOORUIT_DAGEN) if not i.get("fout")]
    gezet, goed, geen, fout, vast = kleuren_zetten(items)
    terug = len(HANDKLEUREN)
    print(f"  [schrijf] kleurherstel ({KLEUR_VOORUIT_DAGEN} dagen): {terug} teruggezet omdat iets anders ze veranderde, "
          f"{gezet - terug} nieuw gezet, {goed} klopten al, {geen} zonder code, {fout} niet gelukt", flush=True)
    for regel in HANDKLEUREN[:40]:
        print("    " + regel)
    if gezet or fout:
        try:
            with open(KLEURHERSTEL_LOG, encoding="utf-8") as f:
                geschiedenis = json.load(f)
        except (OSError, ValueError):
            geschiedenis = []
        geschiedenis.append({"tijd": nu_lokaal().isoformat(timespec="minutes"), "teruggezet": terug,
                             "nieuw": gezet - terug, "mislukt": fout, "voorbeelden": HANDKLEUREN[:10]})
        with open(KLEURHERSTEL_LOG, "w", encoding="utf-8") as f:
            json.dump(geschiedenis[-200:], f, ensure_ascii=False, indent=1)
    return terug


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
        zonder_bus = re.sub(r"\s+bus\s+\w+$", "", straat, flags=re.I)
        if zonder_bus != straat:
            # Een busnummer ("Pontstraat 72 bus 1") kent de kaartdienst niet. Gezien 26-09-2026: de rit naar
            # het kantoor in Aalst werd daardoor niet gemaakt (FR-61).
            pogingen.append({"street": zonder_bus, "postalcode": post, "country": "Belgium",
                             "format": "jsonv2", "limit": 1})
            pogingen.append({"q": f"{zonder_bus}, {post} {gemeente}", "format": "jsonv2", "limit": 1,
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


THUIS_MIN = 30   # minstens zoveel minuten thuis na de rit heen en terug, anders rijdt hij rechtstreeks (FR-75)


def via_huis_zinvol(gat_min, heen_min, terug_min):
    """Tussendoor naar huis heeft alleen zin als er na de rit naar huis en de rit terug nog tijd thuis overblijft.
    Gezien 30-09-2026: tussen Lanaken (tot 12:00) en MediaMarkt Woluwe (13:50) rekende de agent langs huis, met
    75 + 35 minuten rijden in 110 minuten; de ritten overlapten en de 90 minuten van FR-69 hielden dat niet tegen (FR-75).
    Zonder rijtijden (adres onbekend) blijft de grens van 90 minuten."""
    if heen_min is None or terug_min is None:
        return gat_min >= 90
    return gat_min - heen_min - terug_min >= THUIS_MIN


def filefactor(vertrek):
    if vertrek.weekday() >= 5:
        return 1.0
    u = (vertrek.hour, vertrek.minute)
    for van, tot, f in SPITS:
        if van <= u < tot:
            return f
    return DAL_FACTOR


OSRM_CACHE = os.path.expanduser("~/appportal/mijnagents-data/osrm-rijtijden.json")
_osrm = {}


def vrije_rijtijd_min(van, naar):
    """Rijtijd zonder verkeer (OSRM). Die verandert niet tussen twee vaste punten, dus ik bewaar ze 90 dagen:
    met ritten tot een jaar vooruit (FR-65) zou elke ronde anders honderden aanvragen doen bij de openbare server."""
    import time as _t
    import urllib.request
    if not _osrm:
        try:
            _osrm.update(json.load(open(OSRM_CACHE)))
        except (OSError, ValueError):
            _osrm["_"] = {}
    sleutel = f"{van[0]:.5f},{van[1]:.5f}>{naar[0]:.5f},{naar[1]:.5f}"
    bewaard = _osrm.get(sleutel)
    if bewaard and _t.time() - bewaard[1] < 90 * 86400:
        return bewaard[0]
    url = f"https://router.project-osrm.org/route/v1/driving/{van[1]},{van[0]};{naar[1]},{naar[0]}?overview=false"
    d = json.load(urllib.request.urlopen(url, timeout=20))
    minuten = d["routes"][0]["duration"] / 60
    _osrm[sleutel] = [minuten, _t.time()]
    try:
        with open(OSRM_CACHE, "w") as f:
            json.dump(_osrm, f)
    except OSError:
        pass
    return minuten


ROUTES_KEY = os.environ.get("GOOGLE_ROUTES_KEY", "").strip()

# Harde dagstop op de Google-aanroepen. Google laat de dagquota van de Routes API niet
# verlagen (in de console staat die rij op "Adjustable: No"), dus houden we de teller
# zelf bij. Bij het plafond rekent de wacht verder met de filefactor en komt het op het
# bord. 100 per dag is ruim: ook een volle maand op het plafond blijft onder de 5.000
# gratis aanvragen per maand.
# Het plafond is hard: de omgeving mag het verlagen, nooit verhogen. Gezien 23-09-2026:
# Claude trok het voor handmatige rondes zelf op (110, 150, 200, 400) en de teller eindigde
# op 137 van 100. Op 20-09-2026 at een proefronde de teller al eens leeg. Een grendel die
# de uitvoerder zelf kan openzetten, is geen grendel. Verhogen gebeurt alleen hier, in de
# code, met een commit die Mehdi ziet.
ROUTES_PLAFOND = 100
ROUTES_DAGLIMIET = min(int(os.environ.get("AGENDA_ROUTES_DAGLIMIET", str(ROUTES_PLAFOND))), ROUTES_PLAFOND)
ROUTES_TELLER = os.path.expanduser("~/appportal/mijnagents-data/routes-teller.json")
ROUTES_GESTOPT = False


def routes_vandaag():
    """Geeft (datum, aantal Google-aanroepen vandaag). De teller begint elke dag opnieuw."""
    vandaag = nu_lokaal().strftime("%Y-%m-%d")
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
        if gebruikt >= min(ROUTES_DAGLIMIET, ROUTES_PLAFOND):
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
    naam = (m.group(1).strip() if m else (adres or "").split(",")[0]).strip()[:30]
    # een adres in hoofdletters ("3000 LEUVEN") gaf "thuis → LEUVEN"; gezien 23-09-2026
    return naam.title() if naam.isupper() else naam


def _insert(kalender, body, tok, toch=False):
    import urllib.parse
    import urllib.request
    if not mag_schrijven(kalender):
        raise GeenSchrijfrecht(kalender)
    if body.get("summary"):
        body["summary"] = canoniek(body["summary"])
    # een nieuwe afspraak op een dag die een markering afsluit, kan alleen met een ja van Mehdi (FR-83)
    dag = ((body.get("start") or {}).get("dateTime") or "")[:10]
    m = markering_tegen(body.get("summary"), dag) if not toch else None
    if m:
        raise DagMarkering(f"{dag} staat '{m}': '{(body.get('summary') or '')[:60]}' kan die dag niet zonder ja van Mehdi")
    if toch:
        _ja_stempel(body, dag)
    url = f"{agenda.API}/calendars/{urllib.parse.quote(kalender, safe='')}/events?sendUpdates=none"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _verplaats(x, doel, tok):
    """Verhuist een eigen rit naar de agenda waar zijn afspraak nu staat (Google: events.move)."""
    import urllib.parse
    import urllib.request
    if not (mag_schrijven(x["kalender"]) and mag_schrijven(doel)):
        raise GeenSchrijfrecht(doel)
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(x['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(x['id'], safe='')}/move?" + urllib.parse.urlencode({"destination": doel, "sendUpdates": "none"}))
    req = urllib.request.Request(url, data=b"", method="POST", headers={"Authorization": f"Bearer {tok}"})
    urllib.request.urlopen(req, timeout=30)


def is_eigen_rit(x):
    """Een ritblok dat de agent zelf maakte: het autootje vooraan en zijn uitleg (Reistijd voor/na ... OSRM)
    in de omschrijving. Alleen zo'n blok mag hij ooit weghalen."""
    oms = x.get("omschrijving") or ""
    return ((x.get("titel") or "").lstrip().startswith("\U0001F697") and "OSRM" in oms
            and ("Reistijd voor:" in oms or "Reistijd na:" in oms))


def _eigen_rit_weg(x, tok):
    """Haalt een eigen ritblok weg dat niet meer klopt (de afspraak is weg of verzet, of er komt nog een
    buitenafspraak na, zodat de rit naar huis niet meer past). Mehdi, 29-09-2026: "je hebt zelf dat toegevoegd
    en nu heb je mij nodig om dat weg te doen ... dus ja doe weg! pas aan!". Nooit iets anders: een afspraak,
    een rit die Mehdi zelf zette of iets in het archief blijft altijd staan (FR-68)."""
    import urllib.parse
    import urllib.request
    if not is_eigen_rit(x) or not mag_schrijven(x.get("kalender", "")) or not x.get("id"):
        return False
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(x['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(x['id'], safe='')}?sendUpdates=none")
    urllib.request.urlopen(urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {tok}"}), timeout=30)
    return True


# Mail als afsprakenbron (audit 02-10-2026, werkpakket 2, FR-101). Wat uit mch@ of Hotmail komt en niet in de agenda
# staat, of in mail geannuleerd is en er nog staat, toont de agent in de privé-agenda (alleen Mehdi ziet die): een
# hele-dag-melding op Beschikbaar met de bron. Hij zet de afspraak zelf nooit en verplaatst niets. Is het opgelost,
# dan zet hij op zijn eigen melding 'Opgelost'; weghalen doet Mehdi (alleen eigen ritten mag de agent wissen, FR-68).
MAILMERK = "agendawacht_mail"
PRIVE_AGENDA = "mehdipriveagena@gmail.com"
MAIL_VOORUIT_DAGEN = 14


def _mail_melding_body(a, k, dag):
    """De melding in de privé-agenda voor een afspraak uit mail (zie MAIL_VRAGEN)."""
    from datetime import date as _d  # noqa: PLC0415
    uur = a["start"][11:16] if "T" in (a.get("start") or "") else "hele dag"
    titels = {"ontbreekt": f"VR Agendawacht: uit mail, niet in je agenda: {uur} {a['titel'][:60]}",
              "geannuleerd_staat_er": f"VR Agendawacht: in mail geannuleerd, staat nog in je agenda: {uur} {a['titel'][:50]}",
              "afwijkend": f"VR Agendawacht: in mail om {uur}, {a.get('detail') or 'in je agenda anders'}: {a['titel'][:45]}",
              "kandidaat": f"VR Agendawacht: uit mail om {uur}, {a.get('detail') or 'op dat uur staat iets anders'}: {a['titel'][:40]}",
              "zonder_tijd": f"VR Agendawacht: uitnodiging zonder uur: {a['bron_onderwerp'][:70]}"}
    vraag = {"zonder_tijd": "zeg of het een afspraak wordt en wanneer. Ik zet zelf niets.",
             "ontbreekt": "zeg of ik deze afspraak in je agenda zet, of dat ze niet doorgaat. Ik zet zelf niets."
             }.get(a["status"], "zeg wat klopt: de mail of de agenda. Ik zet en verander zelf niets.")
    d = _d.fromisoformat(dag)
    return {"summary": titels[a["status"]][:200], "start": {"date": d.isoformat()}, "end": {"date": (d + timedelta(days=1)).isoformat()},
            "transparency": "transparent", "reminders": {"useDefault": False, "overrides": []},
            "description": (f"Agendawacht vraagt: {vraag}\n\nBron: {a['bron_mailbox']}, '{a['bron_onderwerp']}', ontvangen "
                            f"{a['bron_ontvangen'][:16].replace('T', ' ')}, van {a['bron_afzender']}. Message-ID {a['bron_message_id']}."),
            "extendedProperties": {"private": {MAILMERK: k}}}


def mail_meldingen(res, bestaande, tok, nu=None):
    """Zet, werkt bij of rondt af: de meldingen voor afspraken uit mail, in de privé-agenda (alleen Mehdi ziet die).
    Een melding volgt haar afspraak: verandert de dag of de tekst, dan wordt de bestaande melding bijgewerkt, niet
    overgeslagen (nacontrole v1.2, V11). Een uitnodiging zonder uur krijgt een keer een blijvende vraag op de dag dat
    de agent ze zag; die rondt de agent niet zelf af. Geeft regels."""
    import mail_afspraken as MA  # noqa: PLC0415
    nu = nu or nu_lokaal()
    vandaag = nu.date().isoformat()
    grens = (nu + timedelta(days=MAIL_VOORUIT_DAGEN)).date().isoformat()
    open_ = {MA.sleutel_kort(a): a for a in res if a["status"] in MA.VRAAG_STATUSSEN
             and a["start"] and vandaag <= a["start"][:10] <= grens}
    er = {(x.get("_merk") or {}).get(MAILMERK): x for x in bestaande
          if x.get("kalender") == PRIVE_AGENDA and (x.get("_merk") or {}).get(MAILMERK)
          and not (x.get("_merk") or {}).get(MAILMERK, "").startswith("opgelost:")}
    regels = []
    for k, a in open_.items():
        body = _mail_melding_body(a, k, a["start"][:10])
        x = er.get(k)
        try:
            if x is None:
                _insert(PRIVE_AGENDA, body, tok)
                regels.append(f"{a['start'][:16]} melding gezet ({a['status']})")
            elif (x.get("start") or "")[:10] != a["start"][:10] or (x.get("titel") or "") != body["summary"]:
                _patch(x, {k2: body[k2] for k2 in ("summary", "start", "end", "description")}, tok)
                regels.append(f"{a['start'][:16]} melding bijgewerkt ({a['status']}, was {(x.get('start') or '')[:10]})")
        except Exception as e:  # noqa: BLE001
            regels.append(f"{a['start'][:16]} melding niet gezet ({type(e).__name__})")
    # een uitnodiging zonder uur: een keer een vraag, en het register onthoudt dat (geen dagelijkse herhaling)
    for a in res:
        if a["status"] != "zonder_tijd" or a.get("melding") or (a.get("bron_ontvangen") or "")[:10] < (nu - timedelta(days=MAIL_VOORUIT_DAGEN)).date().isoformat():
            continue
        k = "z:" + MA.sleutel_kort(a)
        try:
            if k not in er:
                _insert(PRIVE_AGENDA, _mail_melding_body(a, k, vandaag), tok)
            MA.melding_zet(a["sleutel"], vandaag)
            regels.append(f"uitnodiging zonder uur: vraag gezet ({a['bron_mailbox']})")
        except Exception as e:  # noqa: BLE001
            regels.append(f"uitnodiging zonder uur: vraag niet gezet ({type(e).__name__})")
    for k, x in er.items():
        if k in open_ or k.startswith("z:"):
            continue
        try:
            if _eigen_melding_opgelost(x, k, tok, nu):
                regels.append(f"{x['start'][:10]} melding op opgelost gezet")
        except Exception as e:  # noqa: BLE001
            regels.append(f"{x['start'][:10]} melding niet op opgelost gezet ({type(e).__name__})")
    return regels


def _eigen_melding_opgelost(x, k, tok, nu):
    """Zet alleen een eigen mailmelding (merk van de agent, privé-agenda) op 'Opgelost'. Wissen doet de agent niet."""
    if x.get("kalender") != PRIVE_AGENDA or (x.get("_merk") or {}).get(MAILMERK) != k or not x.get("id"):
        return False
    titel = re.sub(r"^VR Agendawacht:\s*", "", x.get("titel") or "")
    _patch(x, {"summary": f"Opgelost: {titel}"[:200],
               "description": f"Opgelost op {nu:%d-%m-%Y %H:%M}: de afspraak staat in de agenda, is geannuleerd of voorbij. "
                              f"Je mag deze melding weghalen.\n\n" + (x.get("omschrijving") or ""),
               "extendedProperties": {"private": {MAILMERK: f"opgelost:{k}"}}}, tok)
    return True


# Agendagasten (Mehdi, 03-10-2026: "een systeem waarbij je iemand kunt toevoegen ... zodat het gewoon op hun agenda
# verschijnt ... dan hoef ik niet handmatig mails te ontvangen"). Collega's en partners met een agenda-adres op
# organisatie.globaal.be (kern.persoon.email_agenda) staan als gast op de afspraken waar ze bij horen, zonder mail
# (sendUpdates=none, zoals elke schrijfactie van de agent): de afspraak verschijnt in hun eigen agenda. Wie erbij hoort:
# zijn naam na 'Mehdi' voor de dubbele punt ('Mehdi & Catalin:', 'Mehdi, Matthew, Gul & Aqib:'), of de firma van de
# afspraak (Harmoniebouw: Catalin). Alleen op komende afspraken die Mehdi zelf organiseert; nooit iemand weghalen.
def _gastregels():
    try:
        return json.loads((Path(__file__).resolve().parent / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8")).get("agendagasten") or {}
    except (OSError, ValueError):
        return {}


def agendagasten_voor(titel, regels=None, mensen=None):
    """De agenda-adressen die bij deze titel horen. mensen = {adres: persoon} uit organisatie.agenda_adressen().
    Een naam telt alleen als hij precies een persoon aanwijst; anders geen gok."""
    regels = _gastregels() if regels is None else regels
    mensen = organisatie.agenda_adressen() if mensen is None else mensen
    per_naam = {}
    for adres, p in mensen.items():
        if not p.get("in_dienst", True):
            continue
        for n in {p.get("voornaam") or "", p.get("naam") or "", f"{p.get('voornaam') or ''} {p.get('achternaam') or ''}"}:
            if n.strip():
                per_naam.setdefault(n.strip().lower(), set()).add(adres)
    for bijnaam, naam in (regels.get("bijnamen") or {}).items():
        per_naam.setdefault(bijnaam.lower(), set()).update(per_naam.get(naam.lower(), set()))
    uit = set()
    t = re.sub(r"^[!?\s]+", "", zonder_zl(re.sub(r"^\s*VR\s+", "", titel or "")))
    if ":" in t:
        m = re.match(r"\s*Mehdi\b(.*)$", t.split(":", 1)[0], re.I)
        if m:
            for naam in re.split(r"[,&+/]|\ben\b|\band\b", m.group(1), flags=re.I):
                naam = naam.strip(" !?").lower()
                if naam and len(per_naam.get(naam, ())) == 1:
                    uit |= per_naam[naam]
    for naam in (regels.get("firma_gasten") or {}).get(lees_titel(titel or "").get("firma") or "", []):
        if len(per_naam.get(naam.lower(), ())) == 1:
            uit |= per_naam[naam.lower()]
    return uit


def _event(a, tok):
    import urllib.parse
    import urllib.request
    url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/{urllib.parse.quote(a['id'], safe='')}"
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"}), timeout=30))


def agendagasten_zetten(items, tok=None, nu=None):
    """Zet ontbrekende agendagasten op komende afspraken op de werkagenda die Mehdi zelf organiseert, een reeks in de
    reeks zelf. Bestaande gasten blijven staan; niemand krijgt een mail; daarna teruggelezen. Geeft regels."""
    mensen = organisatie.agenda_adressen()
    if not mensen:
        return []
    regels_ = _gastregels()
    nu_iso = (nu or nu_lokaal()).isoformat()
    uit, reeksen = [], set()
    for a in items:
        if (a.get("hele_dag") or a.get("fout") or a.get("_archief") or "T" not in a.get("start", "")
                or a["start"] < nu_iso[:len(a["start"])] or not a.get("_organisator_zelf")
                or a.get("kalender") != WERKAGENDA or lees_titel(a["titel"])["reistijd"]):
            continue
        ontbreekt = agendagasten_voor(a["titel"], regels_, mensen) - set(a.get("_agendagasten") or [])
        if not ontbreekt:
            continue
        if a.get("_reeks"):
            if a["_reeks"] in reeksen:
                continue
            reeksen.add(a["_reeks"])
        doel = {"kalender": a["kalender"], "id": a.get("_reeks") or a["id"], "titel": a["titel"]}
        try:
            tok = tok or agenda._toegang()
            bestaand = _event(doel, tok).get("attendees") or []
            erbij = sorted(ontbreekt - {(g.get("email") or "").lower() for g in bestaand})
            if not erbij:
                continue
            _patch(doel, {"attendees": bestaand + [{"email": e} for e in erbij]}, tok)
            terug = {(g.get("email") or "").lower() for g in (_event(doel, tok).get("attendees") or [])}
            wie = ", ".join(mensen[e].get("voornaam") or e for e in erbij)
            if set(erbij) <= terug:
                uit.append(f"{a['start'][:16]} {a['titel'][:45]}: {wie} als gast gezet, zonder mail{' (de hele reeks)' if a.get('_reeks') else ''}")
            else:
                uit.append(f"{a['start'][:16]} {a['titel'][:45]}: {wie} niet teruggevonden na het zetten")
        except Exception as e:  # noqa: BLE001
            uit.append(f"{a['start'][:16]} {a['titel'][:45]}: agendagast niet gezet ({type(e).__name__})")
    return uit


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
    nu = nu_lokaal()
    gemaakt, al, geen_adres, fout, regels = 0, 0, 0, 0, []
    reistijden = [x for x in items if lees_titel(x["titel"])["reistijd"]]
    projecten = projectadressen.index()
    buiten = []
    begonnen = set()      # buitenafspraken van vandaag die al begonnen zijn: vertrekpunt, geen eigen ritten meer (FR-97)
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
            else:
                woord, vp = vaste_plek(a["titel"])
                if vp:
                    adres, fysiek, bron_adres = vp["adres"], True, f"vaste plek ({woord})"
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
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if start < nu:
            # Een buitenafspraak van vandaag die al begonnen is, blijft het vertrekpunt van de volgende rit. Gezien
            # 02-10-2026: om 13:49, negen minuten na het begin van Belauto in Mortsel, verdween Belauto uit de planning,
            # en de rit 'Mortsel -> Mechelen' om 14:55 werd 'thuis -> Mechelen' van 13:05 tot 14:00 (FR-97).
            if start.date() != nu.date():
                continue
            begonnen.add((a["kalender"], a.get("id"), a["start"]))
        # Komt het adres uit de projectmap en staat er geen locatie in de afspraak, dan zet ik het
        # erin, zodat Mehdi (en wie meegaat) kan navigeren. Alleen bij zijn eigen afspraken zonder
        # gasten. Mandaat van Mehdi, 23-09-2026: "in een keer goed zetten".
        if ((bron_adres == "projectmap" or bron_adres.startswith("vaste plek")) and fysiek and not (a.get("locatie") or "").strip()
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
        # Alleen een rit naar huis die Mehdi zelf zette, telt. Mijn eigen terugrit (OSRM in de omschrijving) is geen
        # bewijs dat hij tussendoor naar huis gaat: die zette ik toen die afspraak nog de laatste van de dag was.
        # Gezien 29-09-2026: na Boechout kwam 2443 in Merksem erbij en ik rekende van thuis, met overlappende ritten (FR-68).
        for x in reistijden:
            if "T" in x.get("start", "") and is_thuisrit(x) and "OSRM" not in (x.get("omschrijving") or "") \
                    and t0 <= datetime.fromisoformat(x["start"]) <= t1:
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
            # Naar huis tussendoor alleen als het kan: met minder dan 90 minuten tussen twee buitenafspraken rijd je
            # rechtstreeks, ook als er iets achter het bureau in staat. Gezien 29-09-2026: 'Calendly opruimen' om 09:00
            # tussen Belauto (tot 09:00) en Berchem (09:20) liet de agent langs huis rekenen (FR-69).
            if bureau and (s_volgend - e_) < timedelta(minutes=90):
                bureau = None
            if bureau:
                # ook met 90 minuten of meer: past de rit naar huis en terug niet met tijd thuis, dan rechtstreeks (FR-75)
                try:
                    c1 = coord(rij[i][4], cache) if rij[i][5] and rij[i][4] else None
                    c2 = coord(rij[i + 1][4], cache) if rij[i + 1][5] and rij[i + 1][4] else None
                    heen = vrije_rijtijd_min(c1, thuis) * filefactor(e_) + BUFFER_MIN if c1 and thuis else None
                    terug = vrije_rijtijd_min(thuis, c2) * filefactor(s_volgend) + BUFFER_MIN if c2 and thuis else None
                except Exception:  # noqa: BLE001
                    heen = terug = None
                # een extern gesprek doet hij geparkeerd voor hij vertrekt; dat schuift het vertrek naar huis op (FR-78,
                # gezien 01-10-2026: na Belauto Mortsel om 14:00 eerst Elena en Lien tot 14:50, dan bleef er thuis niets over)
                vertrek_thuis = e_
                if heen is not None:
                    for _ in range(3):
                        tijdens = [z for z in externe_gesprekken(vertrek_thuis, vertrek_thuis + timedelta(minutes=heen)) if z[1] > vertrek_thuis]
                        if not tijdens:
                            break
                        vertrek_thuis = max(z[1] for z in tijdens)
                if not via_huis_zinvol((s_volgend - vertrek_thuis).total_seconds() / 60, heen, terug):
                    regels.append(f"{a_['start'][:16]} {a_['titel'][:40]}: geen tijd om tussendoor naar huis te gaan, "
                                  f"rechtstreeks naar {a_volgend['titel'][:30]}")
                    bureau = None
            naar_huis_na[sleutel_] = bool(bureau)
            if bureau:
                regels.append(f"{a_['start'][:16]} {a_['titel'][:40]}: VRAAG om {bureau['start'][11:16]} "
                              f"'{bureau['titel'][:30]}' achter het bureau, om {a_volgend['start'][11:16]} weer buiten. "
                              f"Ik reken dat je tussendoor naar huis gaat. Klopt dat, of doe je het vanuit de auto?")

    for start, einde, a, info, adres, fysiek in buiten:
        dag = a["start"][:10]
        sleutel = (a["kalender"], a.get("id"), a["start"])
        vorige = vorige_per_dag.get(dag)
        def zonder_plek():
            # Zonder adres weet ik niet waar hij is; de volgende rit vertrekt dan van de laatste plek die ik ken, niet van
            # thuis. Gezien 30-09-2026: 'KBC ophalen' zonder adres tussen MediaMarkt Woluwe en MegaMobile Mechelen liet de
            # rit naar Mechelen van thuis vertrekken, terwijl hij van Woluwe kwam (FR-75).
            if vorige is not None and vorige[1] is not None and not naar_huis_na.get(vorige[0]):
                vorige_per_dag[dag] = (sleutel, vorige[1], vorige[2], vorige[3])
            else:
                vorige_per_dag[dag] = (sleutel, None, None, einde)

        if not fysiek:
            if sleutel not in begonnen:
                geen_adres += 1
                regels.append(f"{a['start'][:16]} {a['titel'][:50]}: geen adres, geen reistijd")
            zonder_plek()
            continue
        doel = coord(adres, cache)
        if not (doel and thuis):
            geen_adres += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: adres niet gevonden ({adres[:40]})")
            zonder_plek()
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
        if sleutel in begonnen:
            continue          # al begonnen: alleen vertrekpunt; haar ritten raak ik niet meer aan (FR-97)
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
                # mijn rit voor precies deze afspraak, ook als hij te laat aankomt (te krap)
                if (x["kalender"] == a["kalender"] and _mijn(x) and x["start"][:10] == a["start"][:10]
                        and rit_hoort_bij(x, a["titel"], "voor")):
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
        # Mehdi, 29-09-2026: "ik moet de afspraken hiervoor in de auto doen zodat ik op tijd daar ben". Staat 'in de auto'
        # in de afspraak, dan doet hij de gesprekken onderweg: ik vervroeg de aankomst niet en waarschuw niet (FR-70).
        # 'In de auto' betekent geparkeerd in de auto, ter plaatse, niet rijdend: een extern Zoom-gesprek kan nooit
        # onderweg. FR-70 las het als rijdend; Mehdi, 01-10-2026: "extern kan ik niet rijden en op zoom zijn ... ik kan
        # onmogelijk om 19:30 vertrekken en ook in de auto zitten en niet rijden en op tijd komen" (FR-82).
        in_de_auto = False
        aankomst, reden_aankomst = start, None
        for _ in range(0 if in_de_auto else 3):
            vertrek = aankomst - timedelta(minutes=heen)
            tijdens = [z for z in externe_gesprekken(vertrek, aankomst) if vertrek <= z[0] < aankomst]
            if not tijdens:
                break
            aankomst, reden_aankomst = tijdens[0][0], tijdens[0][2]
            heen, fh = rijtijd_min(vertrek_van, doel, aankomst - timedelta(minutes=heen))
        lopend = [] if in_de_auto else [z for z in externe_gesprekken(aankomst - timedelta(minutes=heen), aankomst)
                                        if z[0] < aankomst - timedelta(minutes=heen)]
        if lopend:
            # Loopt er bij vertrek al een extern gesprek, dan komt hij aan voor het begint en doet hij het geparkeerd ter
            # plaatse; vertrekken mag na een vorig gesprek, zonder buffer als het moet (FR-81, gezien 01-10-2026: KBC
            # Ladeuze 10:30, Benny om 10:00, en de rit vertrok om 10:10, midden in het gesprek)
            nieuwe = lopend[0][0]
            for _ in range(3):
                # past de rit niet tussen een vorig gesprek en dit (ook zonder buffer), kom dan voor dat vorige aan
                # (gezien 01-10-2026: Tim 19:00-19:20 en Levi 19:30, beide op Zoom, voor Nelleke om 20:00 in Bertem)
                h2, f2 = rijtijd_min(vertrek_van, doel, nieuwe - timedelta(minutes=heen))
                vorig = [z for z in externe_gesprekken(nieuwe - timedelta(minutes=h2), nieuwe) if z[0] < nieuwe]
                if not vorig or nieuwe - max(z[1] for z in vorig) >= timedelta(minutes=h2 - BUFFER_MIN):
                    break
                nieuwe = min(z[0] for z in vorig)
            ervoor = [z[1] for z in externe_gesprekken(nieuwe - timedelta(minutes=h2), nieuwe) if z[0] < nieuwe]
            vroegst = max([t for t in ervoor + [vorige_einde] if t] or [nieuwe - timedelta(minutes=h2)])
            if nieuwe - vroegst >= timedelta(minutes=h2 - BUFFER_MIN):
                aankomst, reden_aankomst, heen, fh = nieuwe, next((z[2] for z in externe_gesprekken(nieuwe, nieuwe + timedelta(minutes=1))), lopend[0][2]), h2, f2
                if vroegst > nieuwe - timedelta(minutes=h2):
                    vorige_einde = vroegst
                lopend = []
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
                # Past de rit niet, dan toont hij de echte rijtijd en dus de late aankomst, geen
                # blok van nul minuten. Gezien 24-09-2026: rechtbank tot 16:00, Lara om 16:00 in
                # Kessel-Lo, en de rit stond van 16:00 tot 16:00.
                rijden = heen - BUFFER_MIN
                aankomst = vorige_einde + timedelta(minutes=rijden)
                regels.append(f"{a['start'][:16]} {a['titel'][:40]}: TE KRAP, rijden duurt {rijden} min, "
                              f"er is {ruimte:.0f} min na de vorige afspraak: aankomst {aankomst:%H:%M}, "
                              f"{int(rijden - ruimte)} min te laat")
            rit_start = vorige_einde
        # Een schatting overschrijft nooit een echte meting. Staat er al een eigen rit met live
        # verkeer van Google en heb ik nu alleen de schatting (dagteller op), dan houd ik de live
        # rijtijd. Gezien 23-09-2026: de rit naar Genk schoof zo van 10:00 naar 09:45.
        _x = heenblok()
        _oms = (_x or {}).get("omschrijving") or ""
        # alleen voor dezelfde rit: kwam hij vroeger van elders, dan geldt die meting niet (FR-79, gezien 01-10-2026: de
        # rit naar de post nam de 15 minuten over van 'De Speelkriebel -> post', terwijl hij nu uit Mortsel kwam)
        if _x and "OSRM" in _oms and "live verkeer Google" in _oms and fh != "live" \
                and f"rit {van_plaats} → {plaats})" in _oms:
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
        if _t and "OSRM" in _toms and "live verkeer Google" in _toms and ft != "live" \
                and f"rit {plaats} → thuis)" in _toms:
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
            if tekst.split(" (", 1)[0] not in (x.get("omschrijving") or ""):
                # de afspraak kreeg een andere titel ("Harchitects-KB 2505" werd "[HARC-KB] 2505"):
                # de rit zegt anders nog waarvoor hij vroeger was. Gezien 24-09-2026.
                wijzig["description"] = tekst
            if (x.get("_kleur") or "") != rit_kleur.get("colorId", ""):
                wijzig["colorId"] = rit_kleur.get("colorId") or None
            r = x.get("_reminders") or {}
            if melding is not None and (r.get("useDefault", True) or (r.get("overrides") or []) != melding):
                wijzig["reminders"] = {"useDefault": False, "overrides": melding}
            if wijzig:
                _patch(x, wijzig, tok)
                return True
            return False
        uitleg_h = f"Reistijd voor: {a['titel']} ({heen} min = " + ("live verkeer Google" if fh == "live" else f"vrije rijtijd x filefactor {fh}") + f" + {BUFFER_MIN} min buffer, OSRM; adres uit {bron_adres}; rit {van_plaats} → {plaats})"
        uitleg_t = f"Reistijd na: {a['titel']} ({terug} min = " + ("live verkeer Google" if ft == "live" else f"vrije rijtijd x filefactor {ft}") + f" + {BUFFER_MIN} min buffer, OSRM; rit {plaats} → thuis)"
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
                # Een afspraak heeft precies één heenrit. Staat er nog een tweede eigen heenrit voor dezelfde afspraak, dan
                # haal ik die weg. Gezien 30-09-2026: 'Sint-Lambrechts-Woluwe -> Mechelen' stond twee keer, nadat de oude rit
                # 'thuis -> Mechelen' was herrekend terwijl de nieuwe al bestond (FR-76).
                for y in [y for y in reistijden if y is not x and y["kalender"] == a["kalender"] and _mijn(y)
                          and y["start"][:10] == a["start"][:10] and rit_hoort_bij(y, a["titel"], "voor")]:
                    if _eigen_rit_weg(y, tok):
                        reistijden.remove(y)
                        regels.append(f"{a['start'][:16]} {a['titel'][:44]}: dubbele heenrit weggehaald")
            else:
                _insert(a["kalender"], {"summary": f"🚗 Reistijd: {van_plaats} → {plaats}", "start": {"dateTime": rit_start.isoformat()},
                                        "end": {"dateTime": aankomst.isoformat()}, "description": uitleg_h, **kleur}, tok)
                gemaakt += 1
            x = terugblok() if is_laatste else None
            if not is_laatste:
                regels.append(f"{a['start'][:16]} {a['titel'][:44]}: geen rit naar huis, je gaat door naar de volgende afspraak")
                oud_terug = terugblok()
                # terugblok() geeft de rit die op het einde van deze afspraak vertrekt; mijn eigen terugrit
                # herken ik aan zijn merk, niet aan de titel (die kan intussen veranderd zijn, bv. ?? eraf)
                if oud_terug and "Reistijd na:" in (oud_terug.get("omschrijving") or "") \
                        and _eigen_rit_weg(oud_terug, tok):
                    reistijden.remove(oud_terug) if oud_terug in reistijden else None
                    regels.append(f"{a['start'][:16]} {a['titel'][:44]}: mijn oude rit naar huis weggehaald, "
                                  f"er komt nog een buitenafspraak na")
                # ook een terugrit van mij die nog op het oude einde staat (gezien 01-10-2026: Lara ophalen eindigde om
                # 16:10 in plaats van 17:00, en 'De Speelkriebel -> thuis' om 17:00 bleef staan, FR-78)
                for y in [y for y in reistijden if y is not oud_terug and y["kalender"] == a["kalender"] and _mijn(y)
                          and y["start"][:10] == a["start"][:10] and rit_hoort_bij(y, a["titel"], "na")]:
                    if _eigen_rit_weg(y, tok):
                        reistijden.remove(y)
                        regels.append(f"{a['start'][:16]} {a['titel'][:44]}: mijn oude terugrit (ander einde) weggehaald")
            if is_laatste:
                # precies één terugrit: een tweede eigen terugrit voor deze afspraak (op een oud einde) gaat weg (FR-78)
                for y in [y for y in reistijden if y is not x and y["kalender"] == a["kalender"] and _mijn(y)
                          and y["start"][:10] == a["start"][:10] and rit_hoort_bij(y, a["titel"], "na")]:
                    if _eigen_rit_weg(y, tok):
                        reistijden.remove(y)
                        regels.append(f"{a['start'][:16]} {a['titel'][:44]}: dubbele terugrit weggehaald")
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
    elders = {}          # tijdstip -> agenda's met een afspraak die dan begint of eindigt
    begins_alle, eindes_alle = set(), set()
    for x in items:
        _lx = lees_titel(x["titel"]) if "T" in x.get("start", "") else None
        # alleen een afspraak die een rit heeft, houdt een rit vast; een afspraak die geen rit meer vraagt (Lara
        # 'overgeslagen', zonder !!) niet (FR-79, gezien 01-10-2026)
        if _lx and not _lx["reistijd"] and (_lx["buiten"] or _lx["soort"] in BUITEN_SOORTEN):
            grenzen.add((x["kalender"], datetime.fromisoformat(x["start"])))
            grenzen.add((x["kalender"], datetime.fromisoformat(x["einde"])))
        if "T" in x.get("start", "") and not _lx["reistijd"]:
            elders.setdefault(datetime.fromisoformat(x["start"]), set()).add(x["kalender"])
            elders.setdefault(datetime.fromisoformat(x["einde"]), set()).add(x["kalender"])
            if extern_gesprek(x):
                begins_alle.add(datetime.fromisoformat(x["start"]))
                eindes_alle.add(datetime.fromisoformat(x["einde"]))
    for x in reistijden:
        if ("OSRM" not in (x.get("omschrijving") or "") or "T" not in x.get("start", "")
                or (alleen_dag and x["start"][:10] != alleen_dag)):
            continue
        s0, e0 = datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["einde"])
        # een heenrit hangt aan zijn einde (begin van de afspraak of van een geparkeerd gesprek), een terugrit aan
        # zijn begin; een heenrit die toevallig na een gesprek vertrekt, hangt nergens aan (FR-79, Lara 02-10)
        if "Reistijd voor:" in (x.get("omschrijving") or ""):
            vast = (x["kalender"], e0) in grenzen or e0 in begins_alle
        else:
            vast = (x["kalender"], s0) in grenzen or s0 in eindes_alle or (x["kalender"], e0) in grenzen
        if s0 >= nu and not vast:
            # Staat de afspraak intussen op een andere agenda (privé in plaats van werk), dan
            # verhuist mijn rit mee. Gezien 24-09-2026: de ritten voor een privé-afspraak van
            # 23-09 bleven rood op de werkagenda staan, zichtbaar voor collega's.
            m = re.search(r"Reistijd (?:voor|na): (.+?) \(\d+ min", x.get("omschrijving") or "")
            bij = [y for y in items if m and not lees_titel(y["titel"])["reistijd"] and y["start"][:10] == x["start"][:10]
                   and titel_sleutel(y["titel"]) == titel_sleutel(m.group(1))]
            if any(y["kalender"] == x["kalender"] for y in bij):
                continue          # de afspraak staat er nog, op deze agenda (bv. te laat aankomen)
            ander = {y["kalender"] for y in bij} & ((elders.get(e0, set()) | elders.get(s0, set())) - {x["kalender"]})
            if len(ander) == 1:
                doel = next(iter(ander))
                try:
                    _verplaats(x, doel, tok)
                    regels.append(f"{x['start'][:16]} {x['titel'][:50]}: rit verhuisd naar "
                                  f"{KALENDERS.get(doel, doel)[:20]}, want de afspraak staat daar nu")
                    continue
                except Exception as e:  # noqa: BLE001
                    regels.append(f"{x['start'][:16]} {x['titel'][:50]}: rit niet verhuisd ({type(e).__name__})")
            try:
                if _eigen_rit_weg(x, tok):
                    regels.append(f"{x['start'][:16]} {x['titel'][:50]}: mijn rit zonder afspraak weggehaald")
                    continue
            except Exception as e:  # noqa: BLE001
                regels.append(f"{x['start'][:16]} {x['titel'][:50]}: rit niet weggehaald ({type(e).__name__})")
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
            # Een oproep betekent altijd: je hebt vijf minuten om iets te doen (Mehdi, 25-09-2026). Buiten dus
            # vijf minuten voor het vertrek, zoals de melding op de rit; online vijf minuten voor het begin.
            # Zonder reistijdblok ken ik het vertrek niet: dan reken ik BEL_BUITEN_MIN rijden en bel ik ook
            # vijf minuten voor dat vertrek. Het afsprakennummer betekent altijd vijf minuten, nooit dertig
            # (Mehdi, 25-09-2026: "als hij belt, altijd vijf minuten van tevoren").
            vertrek = datetime.fromisoformat(blok[-1]["start"]) if blok else start - timedelta(minutes=BEL_BUITEN_MIN)
            beltijd = vertrek - timedelta(minutes=BEL_ONLINE_MIN)
            hoe = f"over {BEL_ONLINE_MIN} minuten vertrekken"
        else:
            beltijd = start - timedelta(minutes=BEL_ONLINE_MIN)
            hoe = f"over {BEL_ONLINE_MIN} minuten online"
        klant = info["klant"] or a["titel"][:60]
        tekst = f"Mehdi, {hoe}: {klant}, om {start.strftime('%H:%M')}." + (" De link staat in je agenda." if not buiten else " Adres staat in je agenda.")
        regels.append({"sleutel": f"{a['kalender']}:{a['id']}:{a['start']}", "tijd": beltijd.isoformat(), "tekst": tekst, "titel": a["titel"][:80]})
    regels.sort(key=lambda r: r["tijd"])
    return regels


def onbevestigd_voorbij(items, vandaag):
    """Afspraken van gisteren en vandaag die voorbij zijn en nog ?? dragen. Of ze doorgingen,
    weet alleen Mehdi; zonder die vraag blijft ?? eeuwig staan. Gezien 24-09-2026: de
    boekhouder op 22-09 stond twee dagen later nog op ??. Mandaat: "laat ons nadien de
    afspraken van vandaag valideren zodat we weten welke is doorgegaan en welke niet"."""
    nu = nu_lokaal()
    gisteren = (datetime.fromisoformat(vandaag) - timedelta(days=1)).date().isoformat()
    uit = []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("einde", "") or a["start"][:10] < gisteren:
            continue
        if not lees_titel(a["titel"])["onzeker"] or lees_titel(a["titel"])["reistijd"]:
            continue
        try:
            if datetime.fromisoformat(a["einde"]) > nu:
                continue
        except ValueError:
            continue
        uit.append(f"{a['start'][:16]} {a['titel'][:60]}: doorgegaan? Dan ?? weg; niet doorgegaan? Dan annuleren of verzetten")
    return uit


BELVRAGEN = os.path.expanduser("~/appportal/mijnagents-data/agenda-belvragen.json")


# Mehdi, 01-10-2026: "ik wil dat voor alle klanten dat ik naar toe ga ongeacht de firma altijd de projectnummer erin
# staat". H-Architects nummert JJNN in de projectmap (H-A WORK). UNABO, TKN-Buro en Energie Efficiënt laten uitvoeren
# door TKN-Buro: het nummer staat vooraan de map in TKN BURO WORK/1 Projects/<jaar>, bv. '46118_Barsten & Scheuren_
# Koning Albertlaan 206, 3620 Lanaken'. Gezien die dag: 'BS - Natasja Gerritsen' had geen nummer (FR-80).
TKN_PROJECTEN = "/Work/TKN BURO WORK/1 Projects"
TKN_FIRMAS = ("UNAB", "TKNB", "ENEF")
_TKN_MAPPEN = {"lijst": None}


def _plat_adres(t):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).split())


def straat_nummer(a):
    """'Koning Albertlaan 206' uit de locatie, anders uit de titel (het stuk na de eerste komma); zonder 'bus'."""
    loc = (a.get("locatie") or "").strip()
    bron = loc if loc and not loc.lower().startswith("http") else ",".join((a.get("titel") or "").split(",")[1:2])
    eerste = re.sub(r"\bbus\s*\w+", "", bron.split(",")[0], flags=re.I).strip()
    return eerste if re.search(r"[A-Za-zÀ-ÿ].*\d", eerste) else ""


def _tkn_mappen():
    """De projectmappen van TKN-Buro van dit en vorig jaar, een keer per ronde."""
    if _TKN_MAPPEN["lijst"] is None:
        uit = []
        try:
            import bronnen
            jaar = nu_lokaal().year
            for j in (jaar, jaar - 1):
                uit += [e["name"] for e in (bronnen.lijst(f"{TKN_PROJECTEN}/{j}", recursief=False) or [])
                        if e.get(".tag", "folder") == "folder"]
        except Exception:  # noqa: BLE001
            pass
        _TKN_MAPPEN["lijst"] = uit
    return _TKN_MAPPEN["lijst"]


def projectnummer_zoeken(a, info):
    """(nummer, bron) voor een klantafspraak zonder nummer, op straat en huisnummer in de projectmap van de firma.
    Past er geen of meer dan één nummer, dan None: liever geen nummer dan een verkeerd."""
    sn = _plat_adres(straat_nummer(a))
    if not sn or not re.search(r"\d", sn):
        return None
    patroon = re.compile(rf"(?<![a-z0-9]){re.escape(sn)}(?![0-9])")
    kandidaten, bron = set(), ""
    if info.get("firma") == "HARC":
        for nr, p in (projectadressen.index() or {}).items():
            if patroon.search(_plat_adres((p or {}).get("adres"))):
                kandidaten.add(str(nr))
                bron = "projectmap H-Architects"
    elif info.get("firma") in TKN_FIRMAS:
        for naam in _tkn_mappen():
            m = re.match(r"^(\d{4,6})_", naam)
            if m and patroon.search(_plat_adres(naam)):
                kandidaten.add(m.group(1))
                bron = "projectmap TKN-Buro"
    return (kandidaten.pop(), bron) if len(kandidaten) == 1 else None


def met_nummer(titel, nr):
    """'[UNAB-KB] BS - Natasja, ...' wordt '[UNAB-KB] BS 46118 - Natasja, ...'; zonder dienstcode
    '[UNAB-KB] 46118 - Natasja, ...'."""
    m = CODE_RE.search(titel)
    if not m:
        return titel
    kop, rest = titel[:m.end()], titel[m.end():]
    lead = re.match(r"\s*:?\s*", rest).group(0) or " "
    na = rest.lstrip(" :")
    mt = TYPE_RE.match(na)
    if mt:
        verder = na[mt.end():].lstrip()
        verder = verder[1:].lstrip() if verder.startswith("-") else verder
        return f"{kop}{lead}{mt.group(1)} {nr} - {verder}"
    return f"{kop}{lead}{nr} - {na}"


def projectnummers_zetten(items, alleen_dag=None, ook_verleden=False):
    """Elke klantafspraak buiten (KB), van welke firma ook, draagt het projectnummer in de titel (FR-80). Zonder
    gasten en buiten een reeks zet ik het zelf; anders is het een voorstel."""
    tok = agenda._toegang()
    nu = nu_lokaal().isoformat()
    gezet, regels = 0, []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a.get("_archief") \
                or a["titel"].lower().startswith("canceled"):
            continue
        if (not ook_verleden and a["start"] < nu[:len(a["start"])]) or (alleen_dag and a["start"][:10] != alleen_dag):
            continue
        info = lees_titel(a["titel"])
        if info["reistijd"] or info["soort"] != "KB" or info["nummer"]:
            continue
        r = projectnummer_zoeken(a, info)
        if not r:
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: geen projectnummer gevonden op het adres")
            continue
        nr, bron = r
        nieuw = met_nummer(a["titel"], nr)
        if lees_titel(nieuw)["nummer"] != nr:
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: nummer {nr} gevonden, maar de titel laat zich niet aanvullen")
            continue
        extern = [g for g in a.get("deelnemers") or [] if not any(e in g.lower() for e in EIGEN_ADRESSEN)]
        if extern or a.get("_terugkerend") or a.get("_reeks"):
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: VOORSTEL '{nieuw}' ({bron})")
            continue
        try:
            _patch(a, {"summary": nieuw}, tok)
            a["titel"] = nieuw
            gezet += 1
            regels.append(f"{a['start'][:16]} {nieuw[:70]}: projectnummer {nr} ({bron})")
        except Exception as e:  # noqa: BLE001
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: projectnummer niet gezet ({type(e).__name__})")
    return gezet, regels


# Mehdi, 01-10-2026, onderweg en te laat voor barsten en scheuren in Lanaken: "bij alle afspraken altijd het
# telefoonnummer van de betrokken persoon ... telefoonnummer, adres en projectnummer moeten altijd in de agenda staan
# ... zodat zowel ik als mijn agent kunnen bellen". Het nummer van Natasja Gerritsen stond alleen in Pipedrive (FR-77).
CONTACT_PD = {"HARC": "harchitects", "UNAB": "unabo", "TKNB": "tkn-buro", "ENEF": "energie-efficient"}
EIGEN_ADRESSEN = ("h-architects", "harchitects", "unabo", "tkn-buro", "h-invest", "elevait", "globaal", "mehdi",
                  "haprospecties", "zoomafspraken", "haagendalight")
_TEL_RE = re.compile(r"(?:\+3[1-3][\s.]?|(?<![\d+])0)[1-9](?:[\s./-]?\d){7,10}(?!\d)")
_CONTACT = {}


def telefoon_in(tekst):
    """Het eerste telefoonnummer in een tekst (+32, +31, +33 of 0...), of ''. Een btw- of ondernemingsnummer, een
    IBAN of een meeting-ID telt niet."""
    schoon = re.sub(r"<[^>]+>", " ", tekst or "")
    for m in _TEL_RE.finditer(schoon):
        voor = schoon[max(0, m.start() - 16):m.start()].lower()
        cijfers = re.sub(r"\D", "", m.group(0))
        if any(w in voor for w in ("btw", "be0", "be ", "ondernemingsnr", "iban", "meeting id", "bestel")):
            continue
        if 9 <= len(cijfers) <= 12:
            return m.group(0).strip()
    return ""


def _naam_schoon(naam):
    delen = [w for w in (naam or "").split() if w not in ("PA", "KL")]
    if len(delen) > 2 and delen[-1] == delen[0]:
        delen = delen[:-1]          # 'Natasja Gerritsen Natasja' wordt 'Natasja Gerritsen'
    return " ".join(delen)


def contact_van(a, info):
    """(naam, telefoon, bron) van de klant, prospect of leverancier, uit Pipedrive van de firma: de deal op het
    projectnummer of de straat, dan de persoon op zijn volledige naam. Alleen een treffer die echt past; liever
    geen nummer dan een verkeerd nummer. None als niets gevonden."""
    woord, vp = vaste_plek(a.get("titel") or "")
    if vp and telefoon_in(vp.get("tel") or ""):
        return (vp.get("naam") or woord, telefoon_in(vp["tel"]), f"vaste plek {woord}", [])
    naam = re.sub(r"\([^)]*\)", "", (info.get("klant") or "").split(",")[0]).strip(" -:")
    # eerst de agenda van vroeger: een Calendly-boeking of dossier van dezelfde persoon droeg vaak al het nummer
    # (gezien 01-10-2026: Nelleke Stropke had 0499700230 in haar afspraak van 29-09, Pipedrive zei 'onbekend')
    if len(naam.split()) >= 2:
        for x in _vroegere_afspraken():
            if x.get("id") != a.get("id") and naam.lower() in (x.get("titel") or "").lower():
                tel = telefoon_in(f"{x.get('locatie') or ''} {x.get('omschrijving') or ''}")
                if tel:
                    return (naam, tel, f"agenda {x['start'][8:10]}-{x['start'][5:7]}-{x['start'][:4]}", list(x.get("deelnemers") or []))
    pd = CONTACT_PD.get(info.get("firma") or "")
    if not pd:
        return None
    loc = (a.get("locatie") or "").strip()
    straat = (loc if loc and not loc.lower().startswith("http") else
              ((a.get("titel") or "").split(",")[1] if (a.get("titel") or "").count(",") >= 2 else "")).split(",")[0].strip()
    # 'Koen Van den Steen & Laura Vanovertveldt': elke naam apart (gezien 01-10-2026, samen vond Pipedrive niets)
    namen = [n.strip() for n in re.split(r"\s+(?:&|en|and)\s+", naam) if n.strip()]
    for soort, term in [("nummer", info.get("nummer") or ""), ("straat", straat)] + [("naam", n) for n in namen]:
        if len(term) < 4:
            continue
        sleutel = (pd, soort, term.lower())
        if sleutel not in _CONTACT:
            r = None
            try:
                if soort in ("nummer", "straat"):
                    d = pipedrive.get(pd, "/deals/search", {"term": term, "fields": "title", "limit": 10})
                    for it in (d.get("items") if isinstance(d, dict) else d) or []:
                        x = it.get("item", it)
                        titel = (x.get("title") or "").lower()
                        if not (titel.startswith(term.lower()) if soort == "nummer" else term.lower() in titel):
                            continue
                        pid = (x.get("person") or {}).get("id")
                        p = pipedrive.get(pd, f"/persons/{pid}") if pid else {}
                        # alleen een echt nummer: Pipedrive heeft soms 'onbekend' als telefoon (gezien 01-10-2026)
                        tel = next((telefoon_in(t.get("value") or "") for t in (p or {}).get("phone") or [] if telefoon_in(t.get("value") or "")), "")
                        if tel:
                            mails = [m.get("value", "").lower() for m in (p or {}).get("email") or [] if m.get("value")]
                            r = (_naam_schoon(p.get("name")), tel, f"Pipedrive {pd}, deal {x.get('id')}", mails)
                            break
                elif len(term.split()) >= 2:
                    d = pipedrive.get(pd, "/persons/search", {"term": term, "fields": "name", "limit": 5})
                    passend = []
                    for it in (d.get("items") if isinstance(d, dict) else d) or []:
                        x = it.get("item", it)
                        if set(term.lower().split()) <= set((x.get("name") or "").lower().split()):
                            tel = next((telefoon_in(t or "") for t in x.get("phones") or [] if telefoon_in(t or "")), "")
                            if tel:
                                passend.append((_naam_schoon(x.get("name")), tel, f"Pipedrive {pd}, persoon {x.get('id')}",
                                                [m.lower() for m in x.get("emails") or [] if m]))
                    r = passend[0] if len({c[1] for c in passend}) == 1 else None   # twee kandidaten: geen gok
            except Exception:  # noqa: BLE001
                r = None
            _CONTACT[sleutel] = r
        if _CONTACT[sleutel]:
            return _CONTACT[sleutel]
    return None


_VROEGER = {"lijst": None}


def _vroegere_afspraken():
    """De afspraken van de laatste zestig dagen, een keer per ronde."""
    if _VROEGER["lijst"] is None:
        try:
            _VROEGER["lijst"] = [x for x in afspraken(-60, 0) if not x.get("fout")]
        except Exception:  # noqa: BLE001
            _VROEGER["lijst"] = []
    return _VROEGER["lijst"]


def _volledige_omschrijving(a, tok):
    """De afspraak leest maar 2000 tekens van de omschrijving; voor ik er iets voor zet, haal ik de hele tekst op."""
    import urllib.parse
    import urllib.request
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(a['id'], safe='')}")
    ev = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"}), timeout=30))
    return ev.get("description") or ""


def contact_zetten(items, alleen_dag=None):
    """Elke afspraak met iemand van buiten krijgt bovenaan het telefoonnummer van de betrokken persoon, zodat Mehdi
    of de agent onderweg kan bellen (FR-77). Staat er al een nummer in, dan blijft alles zoals het is. Met meer dan
    een gast van buiten zet ik niets: die zien elkaars omschrijving."""
    tok = agenda._toegang()
    nu = nu_lokaal().isoformat()
    gezet, regels = 0, []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a["start"] < nu[:len(a["start"])] or a.get("_archief"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        info = lees_titel(a["titel"])
        if info["reistijd"] or info["soort"] not in EXTERNE_SOORTEN or not info.get("firma") \
                or a["titel"].lower().startswith("canceled"):
            continue
        if telefoon_in(f"{a.get('locatie') or ''} {a.get('omschrijving') or ''}"):
            continue
        extern = [g.lower() for g in a.get("deelnemers") or [] if not any(e in g.lower() for e in EIGEN_ADRESSEN)]
        c = contact_van(a, info)
        if not c:
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: geen telefoonnummer gevonden (agenda, Pipedrive)")
            continue
        naam, tel, bron, mails = c
        # met meer gasten van buiten zien die elkaars omschrijving: alleen als de persoon zelf gast is (een koppel,
        # gezien 01-10-2026 bij Koen Van den Steen en Laura Vanovertveldt), anders niet
        if len(extern) > 1 and not set(mails) & set(extern):
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: geen nummer gezet, {len(extern)} gasten van buiten")
            continue
        try:
            oms = _volledige_omschrijving(a, tok)
            if telefoon_in(oms):
                continue
            regel = f"Tel. {naam or 'klant'}: {tel} ({bron})"
            html = bool(re.search(r"<(br|a|b|p|div|ul|li)\b", oms, re.I))
            nieuw = (regel + ("<br><br>" if html else "\n\n") + oms) if oms.strip() else regel
            _patch(a, {"description": nieuw}, tok)
            a["omschrijving"] = nieuw[:2000]
            gezet += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: {regel}")
        except Exception as e:  # noqa: BLE001
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: telefoon niet gezet ({type(e).__name__})")
    return gezet, regels


def zoom_zonder_wachtwoord(items, nu=None, uren=48):
    """Online afspraken met een gast waarvan de Zoom-link geen wachtwoord bevat (geen ?pwd= en geen passcode
    in de uitnodiging). Gezien 25-09-2026: Maureen Van De Poel annuleerde met 'ik heb geen wachtwoord voor de
    meeting'; de Calendly-links van het account General dragen het wachtwoord niet."""
    nu = nu or nu_lokaal()
    uit = []
    for a in items:
        if not a.get("deelnemers") or "T" not in a.get("start", "") or a["titel"].lower().startswith("canceled"):
            continue
        try:
            start = datetime.fromisoformat(a["start"])
        except ValueError:
            continue
        if not (nu < start <= nu + timedelta(hours=uren)):
            continue
        tekst = f"{a.get('locatie') or ''} {re.sub(r'<[^>]+>', ' ', a.get('omschrijving') or '')}"
        m = re.search(r"zoom\.us/j/(\d+)", tekst)
        if not m or re.search(r"zoom\.us/j/\d+\?pwd=|passcode|password|wachtwoord|toegangscode", tekst, re.I):
            continue
        # Heeft de meeting zelf geen toegangscode, dan komt de klant met de link binnen (in de wachtkamer, FR-63).
        # Gezien 30-09-2026: de Calendly-meetings sinds 28-09 hebben geen code meer, en toch belde de agent elke
        # dag over 'een link zonder wachtwoord' (FR-73). Is Zoom niet te lezen, dan telt de link, zoals voorheen.
        d = zoom.meeting(m.group(1)) if zoom.beschikbaar() else None
        if d is not None and not d.get("password"):
            continue
        uit.append(a)
    return uit


def zoom_zonder_wachtkamer(items, nu=None, uren=48):
    """Online afspraken met een gast waarvan de Zoom-meeting geen wachtkamer heeft: met het wachtwoord in de link
    staat de klant meteen binnen, ook voor Mehdi er is. Gezien 28-09-2026: Alexander Uwents stond in de meeting
    zonder dat Mehdi hem toeliet; als enige van 18 Calendly-meetings sinds 18-09 had die geen wachtkamer (FR-63).
    Leest Zoom alleen. Geeft [(a, meeting_id)]."""
    if not zoom.beschikbaar():
        return []
    nu = nu or nu_lokaal()
    uit = []
    for a in items:
        if not a.get("deelnemers") or "T" not in a.get("start", "") or a["titel"].lower().startswith("canceled"):
            continue
        try:
            start = datetime.fromisoformat(a["start"])
        except ValueError:
            continue
        if not (nu < start <= nu + timedelta(hours=uren)):
            continue
        m = re.search(r"zoom\.us/j/(\d+)", f"{a.get('locatie') or ''} {a.get('omschrijving') or ''}")
        if not m:
            continue
        d = zoom.meeting(m.group(1))
        if d and not (d.get("settings") or {}).get("waiting_room"):
            uit.append((a, m.group(1)))
    return uit


EXTERNE_SOORTEN = {"KB", "KO", "PB", "PO", "LB", "LO", "AB", "AO", "B2B", "XB", "XO"}


def dubbele_boekingen(items, nu=None, uren=48):
    """Twee afspraken met iemand van buiten die elkaar overlappen, op welke agenda ook (ook het archief).
    Gezien 26-09-2026: Calendly light@ telde geen enkele agenda als bezet en boekte 2610 om 09:00 bovenop
    Cel Breugelmans. Geeft [(a, b)]."""
    nu = nu or nu_lokaal()
    def extern(a):
        info = lees_titel(a["titel"])
        return not info["reistijd"] and info["soort"] != "IN" and (bool(a.get("deelnemers")) or info["soort"] in EXTERNE_SOORTEN)
    lijst = []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a["titel"].lower().startswith("canceled") or not extern(a):
            continue
        try:
            s_, e_ = datetime.fromisoformat(a["start"]), datetime.fromisoformat(a["einde"])
        except ValueError:
            continue
        if nu < s_ <= nu + timedelta(hours=uren):
            lijst.append((s_, e_, a))
    lijst.sort(key=lambda x: x[0])
    uit = []
    for i, (s1, e1, a) in enumerate(lijst):
        for s2, e2, b in lijst[i + 1:]:
            if s2 >= e1:
                break
            if a.get("id") != b.get("id"):
                uit.append((a, b))
    return uit


def vastgelopen(items, nu=None, uren=48):
    """Afspraken binnen 48 uur waar de agent niet verder kan: geen firmacode na zijn onderzoek, of buiten
    zonder adres. Geeft [(sleutel, zin)], de zin is wat Mehdi moet doen, in een zin."""
    nu = nu or nu_lokaal()
    projecten = projectadressen.index()
    uit = []
    for a in items:
        if a.get("hele_dag") or "T" not in a.get("start", "") or a.get("kalender") in AGENDA_VASTE_KLEUR \
                or a.get("kalender", "").startswith("en.be#"):
            continue
        try:
            start = datetime.fromisoformat(a["start"])
        except ValueError:
            continue
        if not (nu < start <= nu + timedelta(hours=uren)):
            continue
        info = lees_titel(a["titel"])
        if info["reistijd"]:
            continue
        wanneer = f"{['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag'][start.weekday()]} om {start:%H:%M}"
        kort = re.sub(r"[^\w ]", " ", a["titel"])[:40].strip()
        if not info.get("firma") and a.get("kalender") == WERKAGENDA:
            uit.append((f"{a['id']}:firma", f"Mehdi, de afspraak van {wanneer}, {kort}: zeg voor welke firma en welke klant."))
        elif (info["buiten"] or info["soort"] in BUITEN_SOORTEN) and not (a.get("locatie") or "").strip() \
                and not (info["nummer"] and info["nummer"] in projecten):
            uit.append((f"{a['id']}:adres", f"Mehdi, de afspraak buiten van {wanneer}, {kort}: zet het adres erin."))
    # Twee klanten tegelijk: een zin per paar, wat Mehdi moet doen
    for a, b in dubbele_boekingen(items, nu, uren):
        s_ = datetime.fromisoformat(a["start"])
        dagnaam = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag'][s_.weekday()]
        na = lambda x: (lees_titel(x["titel"])["klant"] or x["titel"])[:30]
        sleutel = "dubbel:" + ":".join(sorted([a.get("id", "")[:16], b.get("id", "")[:16]]))
        uit.append((sleutel, f"Mehdi, {dagnaam} om {s_:%H:%M} staan twee afspraken tegelijk: {na(a)} en {na(b)}. Verzet er een."))
    # Zoom zonder wachtwoord: een zin per dag voor alle klanten samen, want de klant raakt er niet in
    per_dag = {}
    for a in zoom_zonder_wachtwoord(items, nu, uren):
        per_dag.setdefault(a["start"][:10], []).append(a)
    for dag, lijst in sorted(per_dag.items()):
        namen = ", ".join(f"{(lees_titel(x['titel'])['klant'] or x['titel'])[:25]} om {x['start'][11:16]}" for x in lijst[:4])
        uit.append((f"zoompwd:{dag}", f"Mehdi, {len(lijst)} Zoom-afspraken op {dag[8:10]}-{dag[5:7]} hebben een link zonder wachtwoord "
                    f"({namen}): stuur de klant de uitnodiging vanuit Zoom."))
    # De dagcontrole (FR-71): wat alleen Mehdi kan beslissen, wordt een vraag in de agenda en een oproep
    import dagcontrole as _dc
    for dag in sorted({(x.get("start") or "")[:10] for x in items if (x.get("start") or "")[:10]}):
        try:
            d0 = datetime.fromisoformat(dag + "T00:00:00").replace(tzinfo=nu.tzinfo)
        except ValueError:
            continue
        if d0 + timedelta(days=1) < nu or d0 > nu + timedelta(hours=uren):
            continue
        for b in _dc.dagcontrole(items, dag):
            if b["soort"] in _dc.VRAGEN and b["a"].get("id"):
                s_ = datetime.fromisoformat(b["a"]["start"])
                if nu < s_ <= nu + timedelta(hours=uren):
                    uit.append((f"{b['a']['id']}:{b['soort']}", f"Mehdi, {dag[8:10]}-{dag[5:7]}: {b['tekst']}. Zeg wat ik doe."))
    # Zoom zonder wachtkamer: de klant staat meteen binnen (FR-63)
    for a, mid in zoom_zonder_wachtkamer(items, nu, uren):
        s_ = datetime.fromisoformat(a["start"])
        dagnaam = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag'][s_.weekday()]
        klant = (lees_titel(a["titel"])["klant"] or a["titel"])[:30]
        uit.append((f"wachtkamer:{mid}", f"Mehdi, de Zoom met {klant} van {dagnaam} om {s_:%H:%M} heeft geen wachtkamer: "
                    f"zet ze aan in Zoom bij die meeting, anders staat de klant meteen binnen."))
    return uit


AGENDA_SLOT = "Details staan in je agenda."     # Mehdi leest Telegram niet voor de agenda (25-09-2026)
VR_REGEL = "Agendawacht vraagt: "


def vragen_in_agenda(items, nu=None):
    """Mehdi, 25-09-2026: 'ik lees de telegram niet voor de agenda ... de agenda zelf op een oogopslag geeft mij
    veel meer inzicht'. Wat de agent van hem nodig heeft, staat daarom in de afspraak zelf: VR (vraag) helemaal
    vooraan de titel en de vraag in een zin bovenaan de omschrijving. Opgelost: VR en de zin gaan er weer af.
    Alleen bij eigen afspraken op de werkagenda zonder gasten en niet in een reeks. Geeft (gezet, weg)."""
    tok = agenda._toegang()
    open_ = {sleutel.split(":")[0]: zin for sleutel, zin in vastgelopen(items, nu, uren=24 * 8)}
    gezet = weg = 0
    for a in items:
        if a.get("kalender") != WERKAGENDA or a.get("deelnemers") or a.get("_terugkerend") or a.get("_archief"):
            continue
        titel, oms = a["titel"], a.get("omschrijving") or ""
        zin = open_.get(a.get("id"))
        try:
            if zin and not titel.startswith("VR "):
                schoon = re.sub(rf"^{VR_REGEL}[^\n]*\n*", "", oms)
                _patch(a, {"summary": "VR " + titel, "description": VR_REGEL + zin.split(": ", 1)[-1] + ("\n\n" + schoon if schoon else "")}, tok)
                a["titel"] = "VR " + titel
                gezet += 1
            elif not zin and (titel.startswith("VR ") or oms.startswith(VR_REGEL)):
                nieuw = titel[3:] if titel.startswith("VR ") else titel
                _patch(a, {"summary": nieuw, "description": re.sub(rf"^{VR_REGEL}[^\n]*\n*", "", oms)}, tok)
                a["titel"] = nieuw
                weg += 1
        except Exception as e:  # noqa: BLE001
            print("vraag in agenda mislukt:", titel[:40], type(e).__name__, file=sys.stderr)
    return gezet, weg


def belvenster_uren(nu):
    """Hoe ver vooruit een vastgelopen afspraak een oproep waard is. In het weekend loopt geen geplande
    ronde, dus vrijdag kijkt tot en met maandag: een probleem voor maandagochtend moet vrijdag gemeld zijn.
    Gezien 26-09-2026: de Zoom-links zonder wachtwoord van maandag 09:00 kwamen pas zaterdag aan het licht (FR-59)."""
    return 96 if nu.weekday() == 4 else 48


def bel_als_vastgelopen(items, nu=None):
    """Mehdi, 25-09-2026: 'als je vast zit dan kan je mij bellen via de agent en in een zin zeggen wat ik moet
    doen'. Een oproep per ronde, tussen 08:00 en 20:00, en nooit twee keer voor dezelfde vraag."""
    nu = nu or nu_lokaal()
    if not (8 <= nu.hour < 20) or not bellen.afspraak_bellen_beschikbaar():
        return None
    try:
        staat = json.load(open(BELVRAGEN))
    except (OSError, ValueError):
        staat = {}
    for sleutel, zin in vastgelopen(items, nu, uren=belvenster_uren(nu)):
        if sleutel in staat:
            continue
        uit = bellen.bel_vast(zin, AGENDA_SLOT) or bellen.bel_afspraak(zin, AGENDA_SLOT)  # vastzit-nummer, niet het afsprakennummer
        staat[sleutel] = {"tijd": nu.isoformat(), "zin": zin, "resultaat": str(uit)[:200]}
        json.dump(staat, open(BELVRAGEN, "w"), ensure_ascii=False, indent=0)
        return zin
    return None


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
                # niet 0: de wijzigingswacht moet zien dat deze dag NIET verwerkt is en hem opnieuw proberen
                # (audit 02-10-2026, A6; EX_TEMPFAIL)
                print("een andere ronde loopt al te lang, ik stop", file=sys.stderr)
                sys.exit(75)
            time.sleep(5)


def main():
    _slot = slot_nemen()  # noqa: F841  blijft open tot het einde van de ronde
    werkwijze = ag.werkwijze()
    ag.hartslag("actief", taak="agenda lezen")
    try:
        if not agenda.beschikbaar():
            ag.hartslag("fout", taak="geen agendatoegang", detail="GOOGLE_AGENDA_* ontbreekt in ~/appportal/.env")
            print("geen agendatoegang: GOOGLE_AGENDA_* ontbreekt", file=sys.stderr)
            return 78                    # niet 0: niets verwerkt (A6)
        items = afspraken(-1, 8)
        fouten = [i for i in items if i.get("fout")]
        items = [i for i in items if not i.get("fout")]
        archief = archief_afspraken(-1, 8)     # alleen lezen (FR-39)
        deals = deals_index()
        vandaag = nu_lokaal().date().isoformat()
        gisteren = (nu_lokaal().date() - timedelta(days=1)).isoformat()
        klaar, gekoppeld, niet_conform, dagplan, gisteren_lijst = [], 0, [], [], []
        per_afdeling = {}
        for a in items + archief:
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
        # Ver vooruit (FR-65) dient alleen voor de ritten en !! vooraan. Titels aanvullen, Zoom en herinneringen
        # blijven bij de acht dagen (en Lara, zoals voorheen). Gezien 28-09-2026: met een jaar aan afspraken voor
        # elke stap duurde de ronde langer dan 25 minuten en werd elk exemplaar van elke reeks apart herschreven.
        lara = {k for k, n in KALENDERS.items() if n == "Lara"}
        kort_items = rit_items if DAG_ARG else [a for a in rit_items
                                                if (a["kalender"], a["id"], a["start"]) in gezien_ids or a["kalender"] in lara]
        # eerst de titel in één keer goed, dan de vaste Zoom, dan de rest
        ng, nregels = titels_normaliseren(kort_items, dag_grens)
        ag_, aregels = titels_aanvullen(kort_items, dag_grens)
        ug, uregels = uitroep_vooraan(rit_items, dag_grens)
        ng += ag_ + ug
        nregels += aregels + uregels
        zg, zregels = zoom_zetten(kort_items, dag_grens)
        # Ook in de wijzigingsroute (--dag): een nieuwe blokkade op vrijdagavond of in het weekend wachtte anders tot
        # maandag 06:30 op Bezet, en zolang boekte Calendly erdoor (audit A15, FR-96)
        mb = markeringen_bezet([x for x in (rit_items if DAG_ARG else afspraken(0, 180)) if x.get("hele_dag") and not x.get("fout")])
        mb_ok, mb_mis = bezet_splitsen(mb)
        mail_noden = []
        if mb_ok:
            ag.log(f"dag {vandaag}", "schrijf", f"markeringen: {len(mb_ok)} op Bezet gezet", "\n".join(mb_ok))
        if mb_mis:
            # mislukt is geen 'gezet': apart gemeld, en open tot een volgende ronde het wel zet (nacontrole v1.2, V12)
            ag.log(f"dag {vandaag}", "bevinding", f"markeringen: {len(mb_mis)} NIET op Bezet gezet", "\n".join(mb_mis))
            mail_noden.append({"tekst": "Een markering die alles afsluit staat nog op Beschikbaar: Calendly kan erdoor boeken", "wie": "claude"})
        if not DAG_ARG:
            # Mail als afsprakenbron: mch@ en Hotmail, twee weken terug (FR-101). Een fout is een nood, nooit stilte.
            try:
                import mail_afspraken as MA  # noqa: PLC0415
                _alle = [x for x in afspraken(-14, 120) if not x.get("fout")] + archief_afspraken(-14, 120)
                mres, mfout = MA.ronde(_alle, (datetime.now() - timedelta(days=14)).date().isoformat())
                mregels = mail_meldingen(mres, _alle, agenda._toegang())
                _tel = {s: sum(1 for a in mres if a["status"] == s) for s in ("gekoppeld",) + MA.VRAAG_STATUSSEN + ("zonder_tijd",)}
                ag.log(f"dag {vandaag}", "schrijf", f"mail als bron: {len(mres)} afspraken uit mail ({_tel})", "\n".join(mregels))
                if any(_tel[s] for s in MA.VRAAG_STATUSSEN):
                    mail_noden.append({"tekst": "Afspraken uit mail kloppen niet met de agenda; details in je privé-agenda", "wie": "mehdi"})
                for _mb in sorted({f_["mailbox"] for f_ in mfout}):
                    _stuk = any(not f_.get("map") for f_ in mfout if f_["mailbox"] == _mb)
                    mail_noden.append({"tekst": f"Mailbron {_mb} {'niet' if _stuk else 'niet volledig'} gelezen; zie de leesstand", "wie": "claude"})
            except Exception as e:  # noqa: BLE001
                mail_noden.append({"tekst": f"Mail als afsprakenbron mislukt ({type(e).__name__}: {str(e)[:120]})", "wie": "claude"})
        pg, pregels = projectnummers_zetten(kort_items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"projectnummer: {pg} in de titel gezet", "\n".join(pregels))
        if not DAG_ARG:
            rg, rregels = codes_reeksen(kort_items)
            if rregels:
                ag.log(f"dag {vandaag}", "schrijf", f"codes van twee letters: {rg} reeks(en) omgezet", "\n".join(rregels))
        # Agendagasten: collega's en partners op de afspraken waar ze bij horen, zonder mail (Mehdi, 03-10-2026).
        # Volledige ronde: twee maanden vooruit; de wijzigingsroute: de dag die veranderde.
        try:
            gregels = agendagasten_zetten(rit_items if DAG_ARG else [x for x in afspraken(0, 60) if not x.get("fout")])
        except Exception as e:  # noqa: BLE001
            gregels = [f"agendagasten niet gezet ({type(e).__name__}: {str(e)[:120]})"]
        if gregels:
            ag.log(f"dag {vandaag}", "schrijf", f"agendagasten: {len(gregels)} afspraak/afspraken", "\n".join(gregels))
        tg, tregels = contact_zetten(kort_items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"telefoon: {tg} nummer(s) bovenaan gezet", "\n".join(tregels))
        ag.log(f"dag {vandaag}", "schrijf", f"titels: {ng} rechtgezet uit vrije tekst; link-notitie: {zg} gezet",
               "\n".join(nregels + zregels))
        if zregels or [r for r in nregels if "VOORSTEL" in r]:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": "Link doorsturen of titel nakijken",
                          "uniek": f"agenda-zoom-titel:{vandaag}:{dag_grens or 'alle'}",
                          "inhoud": "\n".join("- " + r for r in (zregels + [r for r in nregels if "VOORSTEL" in r])[:30])}])
        # eerst de gewone herinneringen, dan de ritten: zo heeft de vertrekmelding het laatste woord
        gezet, al, weg, fout_h = herinneringen_zetten(kort_items, dag_grens)
        rg, ral, rgeen, rfout, rregels = reistijd_zetten(rit_items, dag_grens)
        # Laag 2 (FR-71): na alle schrijfacties de dag opnieuw inlezen en nakijken zoals Mehdi hem ziet
        try:
            import dagcontrole as _dc
            if DAG_ARG:
                _off = (datetime.fromisoformat(DAG_ARG).date() - nu_lokaal().date()).days
                _na = [x for x in afspraken(_off - 1, _off + 2) if not x.get("fout")] + archief_afspraken(_off - 1, _off + 2)
                _dagen = [DAG_ARG]
            else:
                _na = [x for x in afspraken(-1, 8) if not x.get("fout")] + archief_afspraken(-1, 8)
                _dagen = sorted({x["start"][:10] for x in _na if x["start"][:10] >= vandaag})
            _tel = 0
            for _dag in _dagen:
                for _b in _dc.dagcontrole(_na, _dag):
                    _tel += 1
                    print(f"  [dagcontrole] {_dag} {_b['soort']}: {_b['tekst']}", flush=True)
            print(f"  [dagcontrole] {len(_dagen)} dag(en) nagekeken, {_tel} bevinding(en)", flush=True)
        except Exception as _e:  # noqa: BLE001
            print(f"  [dagcontrole] niet gelukt: {type(_e).__name__}: {str(_e)[:120]}", flush=True)
        ag.log(f"dag {vandaag}", "schrijf", f"reistijd: {rg} blok(ken) gemaakt, {ral} bestonden al, {rgeen} zonder adres, {rfout} mislukt", "\n".join(rregels))
        # Een rit die niet berekend raakte mag nooit alleen een cijfer zijn: dan ziet
        # Mehdi niet welke afspraak zonder reistijd staat. Gezien 20-09-2026, toen het
        # wekelijkse werfbezoek geen rit kreeg omdat "3010 Kessel-Lo" niet om te zetten was.
        zonder_rit = {"geen adres in de agenda": [], "adres niet gevonden": [], "rijtijd niet berekend": [],
                      "rit zonder afspraak": [], "buiten op een dag zonder auto": []}
        te_krap = [r[:140] for r in rregels if "TE KRAP" in r]
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

        rooster = belrooster(items + archief, vandaag)
        bellen.rooster_schrijven(rooster)
        ag.log(f"dag {vandaag}", "schrijf", f"belrooster: {len(rooster)} oproepen gepland (een oproep per afspraak: online {BEL_ONLINE_MIN} min vooraf, buiten {BEL_ONLINE_MIN} min voor het vertrek)",
               "\n".join(f"{r['tijd'][:16]} bel: {r['titel']}" for r in rooster[:60]))
        bots = [b for b in botsingen(items + archief) if b[:10] >= vandaag]
        in_archief = [f"{a['start'][:16]} {a['titel'][:60]} (in '{a['_archief'][:40]}', gezet door {maker(a)})"
                      for a in archief if a["start"][:10] >= vandaag and not a.get("hele_dag")]
        if in_archief:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": "Afspraken in een archiefagenda: horen op werk",
                          "uniek": f"agenda-archief:{vandaag}", "inhoud": "\n".join("- " + x for x in in_archief[:30])
                          + "\n\nDe agent leest ze mee (dagplan, belrooster, botsingen) maar schrijft er niets in."}])
        if bots:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(bots)} botsende afspraken in de komende week",
                          "uniek": f"agenda-botsing:{vandaag}", "inhoud": "\n".join("- " + b for b in bots)}])
            ag.log(f"dag {vandaag}", "bevinding", f"{len(bots)} botsende afspraken", "\n".join(bots))
        kg, kgoed, kgeen, kfout, kvast = kleuren_zetten(rit_items if DAG_ARG else items, dag_grens)
        if HANDKLEUREN:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": "Kleuren teruggezet naar de regel: iets anders had ze veranderd",
                          "uniek": f"agenda-handkleur:{vandaag}:{dag_grens or 'alle'}",
                          "inhoud": "\n".join("- " + x for x in HANDKLEUREN[:40])}])
        open_na = onbevestigd_voorbij(items, vandaag)
        if open_na:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": "Doorgegaan of niet? Staat nog op ??",
                          "uniek": f"agenda-validatie:{vandaag}",
                          "inhoud": "\n".join("- " + x for x in open_na)}])
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
        noden = list(mail_noden)       # wat de mailbron vond (FR-101)
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
        if te_krap:
            rit_signalen.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                                 "titel": "Te krap: je komt te laat", "uniek": f"agenda-te-krap:{vandaag}:{dag_grens or 'alle'}",
                                 "inhoud": "\n".join("- " + x for x in te_krap[:30])})
            noden.append({"tekst": "Afspraken die te krap op elkaar volgen: wie verschuift?", "wie": "mehdi"})
        if rit_signalen:
            ag.klaarzet(rit_signalen)
        titel_fouten = {}
        for a in items + archief:
            if a.get("fout"):
                continue
            inf = lees_titel(a.get("titel", ""))
            for reden in titelfouten(a, inf):
                titel_fouten.setdefault(reden, []).append(f"{a['start'][:16]} {a.get('titel','')[:58]}")
        # Zelf versturen: 'klaar' is hierboven al klaargezet, wat er daarna bij kwam ging nooit weg (audit A13, FR-93)
        titel_signalen = []
        for reden, rij in sorted(titel_fouten.items()):
            titel_signalen.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                                   "titel": f"Titels: {reden}", "uniek": f"agenda-titel-{reden[:20]}:{vandaag}",
                                   "inhoud": "\n".join("- " + x for x in rij[:40])})
            noden.append({"tekst": f"Afspraken met een titel die niet klopt: {reden}", "wie": "mehdi"})
        if titel_signalen:
            ag.klaarzet(titel_signalen)
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
        if in_archief:
            noden.append({"tekst": "Er wordt nog geboekt in een archiefagenda: het Calendly-kanaal omzetten naar werk", "wie": "mehdi"})
        vg, vw = vragen_in_agenda(kort_items)
        if vg or vw:
            ag.log(f"dag {vandaag}", "schrijf", f"vragen in de agenda: {vg} gezet (VR), {vw} opgelost")
        if not DAG_ARG and "--ronde" in sys.argv:
            # het archief telt mee: een Calendly-boeking kan daar nog staan (FR-39). Een sleutel per dag, zonder
            # aantal, zodat een telling met of zonder archief geen tweede oproep geeft (gezien 25-09-2026, 13:51).
            # Alleen de geplande ronde belt: een ronde die Claude met de hand start, belt nooit (FR-59).
            gebeld = bel_als_vastgelopen(items + archief)
            if gebeld:
                ag.log(f"dag {vandaag}", "bellen", "vastgelopen: Mehdi gebeld", gebeld)
        if HANDKLEUREN:
            noden.append({"tekst": "Iets buiten de agent verandert kleuren (tijdstippen in het signaal): welke tool of wie?", "wie": "mehdi"})
        if open_na:
            noden.append({"tekst": "Afspraken voorbij met ??: doorgegaan of niet?", "wie": "mehdi"})
        if ROUTES_GESTOPT:
            noden.append({"tekst": "Dagplafond van de Google Routes API bereikt; reistijden lopen verder op "
                                   "de filefactor. Het plafond (ROUTES_PLAFOND) verhoogt alleen Mehdi, "
                                   "in de code", "wie": "mehdi"})
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
    if "--kleuren" in sys.argv:          # om :17 en :47, ook 's nachts en in het weekend (FR-21)
        print(f"=== {nu_lokaal():%Y-%m-%d %H:%M} Brussel · kleurherstel", flush=True)
        kleurherstel()
        sys.exit(0)
    if "--ronde" in sys.argv and not is_rondetijd():
        sys.exit(0)          # cron start elk uur; alleen op de ronde-uren (Brusselse tijd) werk ik
    # Elke ronde begint met zijn tijdstip. Gezien 24-09-2026: het logboek had geen enkele tijd,
    # zodat niet na te gaan was wanneer iets gebeurde.
    print(f"=== {nu_lokaal():%Y-%m-%d %H:%M} Brussel · " + (f"dag {DAG_ARG}" if DAG_ARG else "volledige ronde"), flush=True)
    sys.exit(main() or 0)
