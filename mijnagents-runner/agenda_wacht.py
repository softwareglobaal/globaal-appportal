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
import argparse
import hashlib
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
import nummerlezer  # noqa: E402
import pipedrive  # noqa: E402
import beweging as locatiebeweging  # noqa: E402

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


# Persoonlijke zorg is privé, op welke agenda het ook staat: nooit met titel naar het bord, geen vraag
# naar firma en klant ('Opdracht kine en tandarts' v1.0, 14-10-2026). 'Kinepolis' is geen kine.
ZORG_TITEL = re.compile(r"\bkine\b|kinesi|kinésit|tandarts|mondhygi|dentist|huisarts", re.I)


def is_zorg_titel(titel):
    """Een zorgwoord zonder zakelijke firmacode. Met een firmacode is het een zakelijke afspraak met een praktijk als
    klant (EPB voor een tandartspraktijk, een verbouwing van een kinepraktijk): die blijft zakelijk, wordt niet privé en
    verhuist nooit (Codex-controle ronde 1, A02). [PR] en Lara tellen als privé."""
    t = titel or ""
    if not ZORG_TITEL.search(t):
        return False
    m = CODE_RE.search(t)
    return not m or (m.group(1) or "").upper() in ("PRIVE", "PR", "LA", "LARA")


def _toon(a, n=40):
    """Een titel voor een logregel: een privé-afspraak heet '(privé)' (Codex A25, ronde 3: foutpaden drukten de ruwe
    titel af in logboeken op de server)."""
    return "(privé)" if is_prive(a) else (a.get("titel") or "")[:n]


PRIVECODE_RE = re.compile(r"\[(?:PR|PRIVE|LA|LARA)(?:-[A-Za-z0-9]{1,4})?\]", re.I)


def is_prive(a):
    """Privé: uit een privébron, op een privé-agenda of van Lara, een zorgtitel, of een privécode in de titel ([PR], [LA]),
    op welke agenda ook. Tot 15-10-2026 telde '[PR] etentje' op de werkagenda niet als privé (Codex A05, ronde 3)."""
    return bool(a.get("_prive") or a.get("kalender") in PRIVE_KALENDERS or is_zorg_titel(a.get("titel"))
                or PRIVECODE_RE.search(a.get("titel") or ""))


def prive_teksten(items):
    """De teksten van afspraken uit een privébron (titel, de titel na de kop, klant, plaats): de bordklant maskeert ze
    in elk bericht (nacontrole v1.3, R1)."""
    uit = set()
    for x in items:
        if not is_prive(x) or x.get("fout"):
            continue
        t = (x.get("titel") or "").strip()
        uit |= {t, re.sub(r"^(VR|ZL|!!|\?\?|\s)+", "", t).strip()}
        if ":" in t:
            uit.add(t.split(":", 1)[1].strip())
        uit.add((x.get("locatie") or "").strip())
    return {u for u in met_ingekort(uit) if u}


# De logregels korten een titel in ([:40], [:44], [:50] ...); het masker vervangt alleen wat het letterlijk kent.
# Daarom kent het ook die stukken (Codex-controle ronde 1, A05: een ingekorte privétitel glipte erlangs).
KORT_LENGTES = (30, 40, 44, 45, 50, 55, 60, 70, 80)


def met_ingekort(teksten):
    uit = set(teksten)
    for t in list(uit):
        for n in KORT_LENGTES:
            if t and len(t) > n:
                uit.add(t[:n])
    return uit


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



def afspraken(van_dagen=-1, tot_dagen=8, alleen_lezen=False):
    """De afspraken van precies de agenda's die de Agendawacht leest. Eén plek, zodat de
    controle en de filewacht dezelfde agenda's zien als de agent. Gezien 21-09-2026:
    zij lazen alleen de werkagenda en zoomafspraken, niet Lara en niet privé."""
    os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())   # agenda.kalenders() leest die
    uit = agenda.afspraken(van_dagen, tot_dagen, schrijf_leesstand=False) if alleen_lezen \
        else agenda.afspraken(van_dagen, tot_dagen)
    ag.prive(prive_teksten(uit))          # wat uit een privébron komt, gaat nooit naar het bord (R1)
    return uit



ARCHIEF_FOUT = ""      # laatste leesfout van de archiefagenda's (Codex A16)
VERRE_FOUT = []        # foutrecords van de verre lezing: nooit als afspraak verwerken (Codex A17)
ONGELEZEN = set()      # agenda's die deze ronde niet gelezen zijn: dan ruim ik geen ritten op (Codex A15, A17)


def archief_afspraken(van_dagen=-1, tot_dagen=8, alleen_lezen=False):
    """De afspraken in een archiefagenda (naam begint met ZZ ARCHIEF), alleen om te lezen.
    Gezien 24-09-2026: Calendly boekte nog in 'ZZ ARCHIEF haagendalightprojects' (5520 Downs,
    2603 Lisa Cuppens) en niemand zag ze. Ze komen in het dagplan, het belrooster en de
    botsingen, en als signaal 'hoort op werk'. Schrijven blijft verboden (mag_schrijven).
    Lukt het lezen niet, dan blijft de lijst leeg maar staat de reden in ARCHIEF_FOUT: onbekend is niet leeg (Codex A16)."""
    global ARCHIEF_FOUT
    ARCHIEF_FOUT = ""
    try:
        namen = agenda.kalendernamen()
    except Exception as e:  # noqa: BLE001
        ARCHIEF_FOUT = f"archiefagenda's niet te lezen ({type(e).__name__})"
        return []
    ids = [k for k, naam in namen.items() if naam.strip().upper().startswith(ARCHIEFVOORVOEGSEL)]
    if not ids:
        return []
    os.environ["CONTRACTEN_KALENDERS"] = ",".join(ids)
    try:
        ruw = agenda.afspraken(van_dagen, tot_dagen, schrijf_leesstand=False) if alleen_lezen \
            else agenda.afspraken(van_dagen, tot_dagen)
    finally:
        os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())
    stuk = sorted({namen.get(a["kalender"], a["kalender"]) for a in ruw if a.get("fout")})
    if stuk:
        ARCHIEF_FOUT = "archiefagenda niet gelezen: " + ", ".join(x[:40] for x in stuk)
    uit = [a for a in ruw if not a.get("fout")]
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
    """De afspraken voorbij de gewone acht dagen, van elke agenda die ik lees, tot een jaar vooruit. Een agenda die niet
    te lezen is, geeft een foutrecord zonder titel of ID: dat gaat naar VERRE_FOUT, nooit naar de ritten. Tot 15-10-2026
    stopte een enkele fout zo de hele ronde met een KeyError (Codex A17)."""
    global VERRE_FOUT
    VERRE_FOUT, uit = [], []
    for kid, naam in KALENDERS.items():
        dagen = max(RIT_VOORUIT_DAGEN.get(naam, 0), RIT_VOORUIT_ALLES)
        if kid.startswith("en.be#"):
            continue
        if dagen and kid in kalenders():
            os.environ["CONTRACTEN_KALENDERS"] = kid
            for x in agenda.afspraken(8, dagen):
                (VERRE_FOUT if x.get("fout") else uit).append(x)
    os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())
    return uit


def afspraken_dag(dag, alleen_lezen=False):
    """Alle afspraken van één dag, ook verder dan acht dagen. Zo werkt een wijziging op
    een verre dag (een reeks van Lara in november) ook de rit bij."""
    offset = (datetime.fromisoformat(dag).date() - datetime.now().date()).days
    ruw = afspraken(offset - 1, offset + 2, alleen_lezen=True) if alleen_lezen else afspraken(offset - 1, offset + 2)
    ONGELEZEN.update(a["kalender"] for a in ruw if a.get("fout"))      # niet stil laten vallen (Codex A17)
    return [a for a in ruw if not a.get("fout") and a.get("start", "")[:10] == dag]


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
    # H1-1, driehoeksoverleg C2, 17-10-2026: alle codes lezen; de eerste is geen bewijs van een firma.
    firmas = list(dict.fromkeys(AGENDACODE_NAAR_FIRMA.get(m.group(1).upper(), m.group(1).upper())
                               for m in CODE_RE.finditer(t)))
    conflict = len(firmas) > 1
    uit = {"reistijd": bool(re.search(r"reistijd|\brijden naar\b|\bonderweg naar\b|\bnaar huis\b",
                                      re.sub(r"\([^)]*\)", "", t), re.I))
                       or t.startswith("🚗"),
           "buiten": "!!" in t, "onzeker": "??" in t, "firma": "", "firmas": firmas,
           "firma_conflict": conflict, "soort": "", "type": "", "nummer": "", "klant": ""}
    m = CODE_RE.search(t)
    if m and not conflict:
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
    kandidaten = nummerlezer.lees(t, "agenda_titel")
    if not kandidaten and not nummerlezer.agendacode_van_titel(t):
        # Een oude titel zonder codes, bv. 'Mehdi: 2607 werfbezoek', blijft een kandidaat.
        # De bronbewuste lezer sluit huisnummers, postcodes en kalenderjaren uit.
        kandidaten = nummerlezer.lees(rest, "vergadertitel")
    kandidaat = nummerlezer.enig(kandidaten)
    if kandidaat:
        uit["nummer"] = kandidaat.nummer
    kaal = re.sub(rf"\b{uit['nummer']}\b", "", rest, count=1) if uit["nummer"] else rest
    uit["klant"] = kaal.strip(" -:").split(" - ")[0][:80]
    uit["conform"] = (bool(m) and not conflict) or uit["reistijd"]
    return uit


def deals_index():
    pipedrive.controleer_bedrijf("harchitects", 10068585)
    items = pipedrive.alles("harchitects", "/deals", {"status": "open"})     # alle pagina's, niet 500
    uit = []
    for x in items:
        titel = x.get("title", "")
        uit.append({"id": x.get("id"), "titel": titel, "nummer": nummerlezer.ha_nummer(titel, "pipedrive_titel"),
                    "delen": {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()}})
    return uit


def koppel(info, titel, deals):
    if info.get("firma_conflict"):
        return None, "meer firmacodes in de titel; geen dossierkoppeling"
    code = nummerlezer.agendacode_van_titel(titel) or info.get("firma") or ""
    firma = nummerlezer.firma_van_code(code)
    # Een gelijk nummer bij UB of TK is geen bewijs voor een H-A-deal.
    if code and firma != "HARC":
        return None, "geen bewezen H-A-dossierkoppeling"
    if info["nummer"]:
        passend = [d for d in deals if d["nummer"] == info["nummer"]]
        if len(passend) == 1:
            return passend[0], "projectnummer in de titel"
        if len(passend) > 1:
            return None, "meer deals met hetzelfde projectnummer; nakijken"
        return None, "geen deal met het projectnummer; nakijken"
    delen = {w for w in re.split(r"[^a-z0-9]+", (info["klant"] or titel).lower()) if len(w) > 2}
    beste, score, gelijk = None, 0, False
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score, gelijk = d, s, False
        elif s == score and score >= 2:
            gelijk = True
    return (beste, f"naam in de titel ({score} woorden)") if beste and score >= 2 and not gelijk else (None, "")


def afspraak_klaarzetitem(a, info, afdeling, kal, regel, deal, hoe, terugkijken=False):
    """Hetzelfde borditem in de gewone ronde en bij alleen lezend terugkijken."""
    dag = a["start"][:10]
    inhoud = {"datum": dag, "start": a["start"], "einde": a["einde"], "titel": a["titel"], "agenda": kal,
              "firma": info["firma"], "soort": info["soort"], "type": info["type"], "nummer": info["nummer"],
              "klant": info["klant"], "buiten": info["buiten"], "onzeker": info["onzeker"],
              "locatie": a["locatie"], "deelnemers": a["deelnemers"], "gezet_door": maker(a),
              "deal_id": deal["id"] if deal else None, "koppeling": hoe, "omschrijving": a["omschrijving"][:800]}
    if terugkijken:
        inhoud["terugkijken"] = True
    return {"voor": afdeling, "soort": "afspraak", "sleutel": str(deal["id"]) if deal else (info["nummer"] or ""),
            "titel": f"{dag} {regel}", "uniek": f"agenda:{a['kalender']}:{a['id']}", "verwijzing": a.get("link", ""),
            "inhoud": inhoud}


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


class TitelVoorstel(Exception):
    """De titel heeft geen bewezen schrijfrecht; de voorgestelde titel staat in het verslag."""


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
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if not a.get("hele_dag") or not a.get("_vrij") or a.get("_archief") or (a.get("_merk") or {}).get(LARAMERK):
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
        if not x.get("hele_dag") or lara_vervalt(x) or (x.get("_merk") or {}).get(LARAMERK):
            continue          # een markering met 'vervalt' vooraan of een eigen Lara-vraag sluit geen dag af (FR-210)
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


def markering_tegen(titel, dag, markers=None, locatie=""):
    """De markering die een afspraak met deze titel op deze dag tegenhoudt, of None. Een rit, een hele-dag-item en Lara
    zelf (de reden van de markering) tellen niet."""
    t = (titel or "").strip()
    if not t or not dag or t.startswith("\U0001F697") or bellen.is_lara_titel(t):
        return None
    info = lees_titel(t)
    if info["reistijd"]:
        return None
    buiten = (info["buiten"] or info["soort"] in BUITEN_SOORTEN) and not is_thuis_adres(locatie)
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
    if not titel:
        return titel
    nieuw = codes_twee_letters(titel, online)
    if nieuw != titel and re.search(r"-B2B\]", nieuw):
        # zonder bewijs van buiten of online geen nieuwe gecodeerde B2B-titel: de bron blijft staan, de vraag XB of XO
        # komt via het voorstel (nacontrole v1.3, R8)
        return titel
    return nieuw


def _eigen_accounts():
    """H1-1c, driehoeksoverleg C4, 17-10-2026: de twee eigen agenda-accounts, geen firma- of groepsagenda's."""
    return {adres.strip().lower() for adres in (WERKAGENDA, PRIVE_AGENDA)}


def _eigen_hulpblok(a, nieuw, eigen_rit=False):
    """C5: maker, gasten, merk en titelovergang bewijzen samen een eigen mail- of ritblok."""
    merk = a.get("_merk") or {}
    maker = a.get("maker")
    if (not isinstance(merk, dict) or not isinstance(maker, str) or maker.strip().lower() not in _eigen_accounts()
            or a.get("deelnemers") or a.get("_agendagasten")):
        return False
    mailmerk = merk.get(MAILMERK)
    geldig_mailmerk = isinstance(mailmerk, str) and bool(re.fullmatch(r"(?:z:|opgelost:)?[0-9a-f]{16}", mailmerk))
    oude_titel = a.get("titel") or ""
    rittitel = nieuw.lstrip().startswith("🚗")
    mailovergang = (oude_titel.startswith("VR Agendawacht:")
                    and (nieuw.startswith("VR Agendawacht:") or nieuw.startswith("Opgelost:")))
    return (bool(a.get("id")) and merk.get(RITMERK) == a["id"] and _rit_tekst(a) and rittitel
            or a.get("kalender") == PRIVE_AGENDA and geldig_mailmerk and mailovergang
            or eigen_rit and "OSRM" in (a.get("omschrijving") or "") and rittitel)


def _titel_patch_reden(a, nieuw, eigen_rit=False, eigen_zorgverhuis=False, alleen_vr=False,
                       uit_onderzoek=False):
    """H1-1c, driehoeksoverleg C4, 17-10-2026: alleen bewezen maker, gasten en route geven titelrecht."""
    if is_zorgschaduw(a):
        return "schaduw van een privé-zorgafspraak"
    oud = a.get("titel")
    if not isinstance(oud, str) or not isinstance(nieuw, str) or "deelnemers" not in a:
        return "gasten, maker, omschrijving of oude titel niet volledig bekend"
    if not isinstance(a["deelnemers"], list) or any(not isinstance(g, str) for g in a["deelnemers"]):
        return "gasten, maker of omschrijving niet volledig bekend"
    if any(g.strip().lower() not in _eigen_accounts() for g in a["deelnemers"]):
        return "externe gast"
    merk = a.get("_merk") or {}
    heeft_hulpmerk = isinstance(merk, dict) and any(merk.get(k) for k in (RITMERK, MAILMERK, ZORGMERK))
    if (a["deelnemers"] or a.get("_agendagasten")) and (heeft_hulpmerk or eigen_rit or eigen_zorgverhuis):
        return "eigen blok met gasten"
    maker = a.get("maker")
    if not isinstance(maker, str) or not maker.strip():
        return "maker onbekend"
    if maker.strip().lower() not in _eigen_accounts():
        return "door een ander gemaakt"
    mailmerk = merk.get(MAILMERK) if isinstance(merk, dict) else None
    if (a.get("kalender") == PRIVE_AGENDA and isinstance(mailmerk, str)
            and re.fullmatch(r"(?:z:|opgelost:)?[0-9a-f]{16}", mailmerk)
            and not ((oud.startswith("VR Agendawacht:"))
                     and (nieuw.startswith("VR Agendawacht:") or nieuw.startswith("Opgelost:")))):
        return "mailblok zonder verwachte titelovergang"
    if ((isinstance(merk, dict) and a.get("id") and merk.get(RITMERK) == a["id"] and _rit_tekst(a)
         or eigen_rit and "OSRM" in (a.get("omschrijving") or ""))
            and not nieuw.lstrip().startswith("🚗")):
        return "ritblok zonder rittitel"
    eigen = not eigen_zorgverhuis and _eigen_hulpblok(a, nieuw, eigen_rit)
    if eigen:
        return ""
    if not isinstance(a.get("omschrijving"), str):
        return "omschrijving onbekend"
    if eigen_zorgverhuis and (a.get("_titel_bronkalender") != WERKAGENDA
                              or a.get("kalender") != PRIVE_AGENDA):
        return "geen zorgverhuizing van werk naar privé"
    # De oude vraagroute zette VR ook op een Calendly-omschrijving. Precies die prefixwijziging
    # blijft mogelijk onder haar bestaande kalender-, gast- en reeksvoorwaarden.
    vr_kalender = (a.get("kalender") == WERKAGENDA or
                   a.get("kalender") in PRIVE_KALENDERS and a.get("_organisator_zelf") is True)
    vr_alleen = (vr_kalender and not a.get("_agendagasten") and not a.get("_terugkerend")
                 and not a.get("_reeks") and not a.get("_archief") and alleen_vr)
    if vr_alleen:
        return ""
    if (a.get("kalender") == WERKAGENDA and oud.startswith("VR ") != nieuw.startswith("VR ")
            and not (uit_onderzoek and oud.startswith("VR ") and not nieuw.startswith("VR "))):
        return "VR met andere titelwijziging"
    if is_calendly(a):
        return "Calendly-boeking"
    oud_info, nieuw_info = lees_titel(oud), lees_titel(nieuw)
    if oud_info["firma_conflict"] or nieuw_info["firma_conflict"]:
        return "meer verschillende firmacodes in de titel"
    if eigen_zorgverhuis and nieuw_info["firma"] != "PRIVE":
        return "zorgverhuizing zonder privécode"
    if oud_info["firma"] and oud_info["firma"] != nieuw_info["firma"]:
        if eigen_zorgverhuis:
            return ""
        return "firmawissel"
    return ""


def _reeks_als_afspraak(a, reeks):
    """H1-1, driehoeksoverleg C2, 17-10-2026: de gelezen reeks met haar echte gast- en makerbewijs."""
    gasten = reeks.get("attendees", [])
    intern = {e.strip().lower() for e in agenda.interne_adressen() if isinstance(e, str)}
    deelnemers = [g.get("email") if isinstance(g, dict) else None for g in gasten] if isinstance(gasten, list) else [None]
    deelnemers = [g for g in deelnemers if not isinstance(g, str) or g.strip().lower() not in intern]
    deelnemers += a["deelnemers"] if isinstance(a.get("deelnemers"), list) else [None]
    creator = reeks.get("creator") or {}
    maker_reeks = creator.get("email") if isinstance(creator, dict) else None
    maker_a = a.get("maker")
    maker_bekend = (maker_a if maker_a.strip().lower() in CALENDLY_ACCOUNTS else maker_reeks) \
        if isinstance(maker_a, str) else None
    oms_reeks = reeks.get("description") or ""
    omschrijving = (oms_reeks + "\n" + a["omschrijving"]
                    if isinstance(oms_reeks, str) and isinstance(a.get("omschrijving"), str) else None)
    return {"kalender": a["kalender"], "id": a["_reeks"], "titel": reeks.get("summary") or "",
            "deelnemers": deelnemers,
            "_agendagasten": list(a.get("_agendagasten") or []),
            "maker": maker_bekend,
            "omschrijving": omschrijving}


def _eigen_vertrekmelding_index(a, overrides):
    """Alleen een passende private marker bewijst welke override van de agent is."""
    try:
        minuten = int((a.get("_merk") or {}).get(VERTREKMELDINGMERK))
    except (TypeError, ValueError):
        return None
    return next((i for i, ov in enumerate(overrides)
                 if minuten > 0 and ov == {"method": "popup", "minutes": minuten}), None)


def _herinneringen_behouden(a, gevraagd, eigen_rit=False, beheerde_vertrekmelding=False):
    """Bewaar bestaande overrides; alleen de herkenbaar eigen vertrekmelding mag worden vervangen."""
    if not isinstance(gevraagd, dict):
        return gevraagd
    nieuw = [dict(ov) for ov in (gevraagd.get("overrides") or [])
             if isinstance(ov, dict) and int(ov.get("minutes") or 0) > 0]
    schoon = {"useDefault": bool(gevraagd.get("useDefault", False)), "overrides": nieuw}
    if beheerde_vertrekmelding:
        if len(nieuw) > 5:
            raise ValueError("meer dan vijf vertrekmeldingen")
        return schoon
    if eigen_rit or is_eigen_rit(a) or lees_titel(a.get("titel") or "")["reistijd"]:
        schoon["overrides"] = nieuw[:5]
        return schoon
    bestaand = [dict(ov) for ov in ((a.get("_reminders") or {}).get("overrides") or [])
                if isinstance(ov, dict) and int(ov.get("minutes") or 0) > 0]
    eigen_index = _eigen_vertrekmelding_index(a, bestaand)
    extra = [ov for ov in nieuw if ov not in bestaand]
    if eigen_index is not None and (not nieuw or len(bestaand) + len(extra) > 5):
        bestaand.pop(eigen_index)
    if len(bestaand) > 5:
        raise ValueError("meer dan vijf bestaande herinneringen")
    if not bestaand:
        schoon["overrides"] = nieuw[:5]
        return schoon
    # De herkomst van een bestaande override is niet te bewijzen. Bewaar hem ook als een andere
    # stap stilte vraagt; voeg nieuwe meldingen alleen toe als Google nog plaats heeft.
    samen = list(bestaand)
    for ov in nieuw:
        if ov not in samen and len(samen) < 5:
            samen.append(ov)
    return {"useDefault": False, "overrides": samen}


def _patch(a, body, tok, toch=False, eigen_rit=False, eigen_zorgverhuis=False, uit_onderzoek=False,
           beheerde_vertrekmelding=False):
    import urllib.parse
    import urllib.request
    if is_zorgschaduw(a):
        raise SchaduwItem("schaduw van een privé-zorgafspraak")
    if _firma_kopie(a):
        raise SchaduwItem("gastkopie van een firma-afspraak")    # elke route slaat ze over; dit is de grendel
    if not mag_schrijven(a["kalender"]):
        raise GeenSchrijfrecht(a["kalender"])
    nieuwe_herinneringen = None
    eigen_merk_wissen = False
    if "reminders" in body and isinstance(body["reminders"], dict):
        body = {**body, "reminders": _herinneringen_behouden(
            a, body["reminders"], eigen_rit=eigen_rit, beheerde_vertrekmelding=beheerde_vertrekmelding)}
        nieuwe_herinneringen = dict(body["reminders"])
        if not beheerde_vertrekmelding:
            oude = (a.get("_reminders") or {}).get("overrides") or []
            index = _eigen_vertrekmelding_index(a, oude)
            if index is not None:
                eigen = oude[index]
                nieuw_aantal = nieuwe_herinneringen["overrides"].count(eigen)
                eigen_merk_wissen = nieuw_aantal < oude.count(eigen)
                if eigen_merk_wissen:
                    body.setdefault("extendedProperties", {}).setdefault("private", {})[VERTREKMELDINGMERK] = None
    # Gewone wijzigingen blijven stil (sendUpdates=none); alleen _uitnodiging_patch is de toegestane uitnodigingsroute.
    # Google doet dit standaard ook niet, maar hier staat het expliciet, met een test erop.
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(a['id'], safe='')}?sendUpdates=none")
    aangevraagd = body.get("summary")
    if body.get("summary"):
        body["summary"] = canoniek(body["summary"])
    # H1-1, driehoeksoverleg C2, 17-10-2026: elke route loopt hierlangs, ook reeksen en eigen meldingen.
    if "summary" in body and (body["summary"] != a.get("titel") or "titel" not in a):
        alleen_vr = (isinstance(aangevraagd, str) and isinstance(a.get("titel"), str)
                    and (aangevraagd == "VR " + a["titel"] or a["titel"] == "VR " + aangevraagd))
        reden = _titel_patch_reden(a, body["summary"], eigen_rit=eigen_rit,
                                   eigen_zorgverhuis=eigen_zorgverhuis, alleen_vr=alleen_vr,
                                   uit_onderzoek=uit_onderzoek)
        if reden:
            ag.log("titelwijziging", "voorstel", "VOORSTEL: titel niet gewijzigd",
                   f"{_toon(a)} -> {str(body['summary'])[:90]} ({reden})")
            raise TitelVoorstel(reden)
    # een afspraak naar een dag verzetten die een markering afsluit, kan alleen met een ja van Mehdi (FR-83); het eigen
    # spiegelblok van een firma-afspraak volgt zijn afspraak, ook naar zo'n dag (review 27-10-2026)
    if "start" in body and not toch and not (a.get("_merk") or {}).get(FIRMAMERK):
        dag = ((body.get("start") or {}).get("dateTime") or "")[:10]
        m = markering_tegen(body.get("summary") or a.get("titel"), dag,
                           locatie=body.get("location") or a.get("locatie") or "")
        if m:
            raise DagMarkering(f"{dag} staat '{m}': '{(body.get('summary') or a.get('titel') or '')[:60]}' kan die dag niet zonder ja van Mehdi")
    elif "start" in body:
        _ja_stempel(body, ((body.get("start") or {}).get("dateTime") or "")[:10])
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)
    if nieuwe_herinneringen is not None:
        a["_reminders"] = nieuwe_herinneringen
    if eigen_merk_wissen:
        a.setdefault("_merk", {}).pop(VERTREKMELDINGMERK, None)


def _vertrekmelding_zetten(a, minuten, tok):
    """Vervang hoogstens de eigen popup; een gelijke handmatige popup blijft van de eigenaar."""
    if minuten <= 0:
        return False
    bestaand = [dict(ov) for ov in ((a.get("_reminders") or {}).get("overrides") or [])
                if isinstance(ov, dict) and int(ov.get("minutes") or 0) > 0]
    merk = (a.get("_merk") or {}).get(VERTREKMELDINGMERK)
    eigen_index = _eigen_vertrekmelding_index(a, bestaand)
    if eigen_index is not None and bestaand[eigen_index]["minutes"] == minuten and len(bestaand) <= 5:
        return True
    over = list(bestaand)
    if eigen_index is not None:
        over.pop(eigen_index)
    if len(over) > 5:
        raise ValueError("meer dan vijf bestaande herinneringen")
    nieuw = {"method": "popup", "minutes": minuten}
    toegevoegd = nieuw not in over and len(over) < 5
    if toegevoegd:
        over.append(nieuw)
    nieuw_merk = str(minuten) if toegevoegd else None
    if over == bestaand and (merk or None) == nieuw_merk:
        return nieuw in over
    _patch(a, {"reminders": {"useDefault": False, "overrides": over},
               "extendedProperties": {"private": {VERTREKMELDINGMERK: nieuw_merk}}},
           tok, beheerde_vertrekmelding=True)
    if toegevoegd:
        a.setdefault("_merk", {})[VERTREKMELDINGMERK] = nieuw_merk
    else:
        a.setdefault("_merk", {}).pop(VERTREKMELDINGMERK, None)
    return toegevoegd or nieuw in over


def herinneringen_zetten(items, alleen_dag=None):
    """Werkwijze stap 5: een pop-upherinnering op elke komende prospect-afspraak
    (regel in melding_gewenst) die er nog geen heeft: online 5 min, buiten (!!) 30 min.
    Een herinnering die ik zelf eerder op een niet-gewenste afspraak zette (mijn
    handtekening: één pop-up van 10 of 30 min) haal ik weer weg, zodat intern en
    terugkerend stil blijven. Bestaande herinneringen van Mehdi laat ik staan.
    Geeft (gezet, al, weggehaald, fout)."""
    tok = agenda._toegang()
    nu_iso = nu_lokaal().isoformat()
    gezet, al, weg, fout = 0, 0, 0, 0
    for a in items:
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if _voorbij(a["start"], nu_iso) or a.get("kalender", "").startswith("en.be#"):
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
                    print("rit-melding mislukt:", _toon(a), type(e).__name__, file=sys.stderr)
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
            print("herinnering mislukt:", _toon(a), type(e).__name__, file=sys.stderr)
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


def is_calendly(a):
    """Een Calendly-boeking: op een boekingsaccount, door een boekingsaccount gezet, of met de annuleer- en verzetlinks
    van calendly.com in de omschrijving. De titel daarvan verander ik nooit zelf: dat is een voorstel (Codex A09)."""
    return (a.get("kalender") in CALENDLY_ACCOUNTS or (a.get("maker") or "").strip().lower() in CALENDLY_ACCOUNTS
            or "calendly.com" in (a.get("omschrijving") or "").lower())


# Een vergaderlink is een link waarmee je deelneemt. Een annuleer- of verzetlink van Calendly, een Dropbox-, Pipedrive-
# of Maps-link is geen vergaderlink en houdt ZL dus niet weg (Codex A30, 15-10-2026).
VERGADERLINK_RE = re.compile(r"zoom\.us/(?:j|my|w|s)/|meet\.google\.com/|teams\.(?:microsoft|live)\.com/|whereby\.com/|"
                             r"webex\.com/|meet\.jit\.si/|gotomeet(?:ing)?\.com/|app\.gotomeeting\.com/", re.I)


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
    """Door Mehdi zelf gezet en zonder gasten: geen gast van buiten en geen collega als agendagast. Een collega ziet de
    titel en de omschrijving ook (Codex A09, ronde 3)."""
    m = (a.get("maker") or "").lower()
    return (m in ("", WERKAGENDA) and a.get("kalender") != "zoomafspraken@gmail.com" and not a.get("deelnemers")
            and not a.get("_agendagasten"))


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
    # H1-1b, driehoeksoverleg C3, 17-10-2026: twee firma's hebben geen canonieke gekozen firma.
    if info["firma_conflict"]:
        return titel
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
    if loc.startswith("http") or "zoom.us" in loc or VERGADERLINK_RE.search(a.get("omschrijving") or ""):
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
    nu = nu_lokaal().isoformat()
    gedaan, regels = 0, []
    for a in items:
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if a.get("hele_dag") or "T" not in a.get("start", "") or _voorbij(a["start"], nu):
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
            if kandidaat != titel and re.search(r"-B2B\]", kandidaat):
                regels.append(f"{a['start'][:16]} {titel[:50]}: VOORSTEL buiten of online staat nergens: '{kandidaat.replace('-B2B]', '-XB]')[:60]}' "
                              f"(buiten) of '{kandidaat.replace('-B2B]', '-XO]')[:60]}' (online)? Ik schrijf niets tot het vaststaat")
            elif kandidaat != titel:
                if _van_mehdi(a) and not a.get("_terugkerend") and not is_calendly(a):
                    nieuw, uitleg = kandidaat, "codes van twee letters (Mehdi, 02-10-2026)"
                elif not a.get("_terugkerend"):
                    regels.append(f"{a['start'][:16]} {titel[:50]}: VOORSTEL '{kandidaat[:70]}' (twee letters; met gasten verander ik de titel niet)")
        else:
            nieuw, firma, soort, uitleg = titel_voorstel(titel, _online(a))
            if nieuw and not (firma and soort and _van_mehdi(a) and not a.get("_terugkerend") and not is_calendly(a)):
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
        if not a.get("_reeks") or a["_reeks"] in gezien or a.get("_archief") \
                or not mag_schrijven(a.get("kalender", "")):
            continue
        gezien.add(a["_reeks"])
        # H1-1b, driehoeksoverleg C3, 17-10-2026: bekend verbod vraagt geen GET van de reeks.
        if a.get("deelnemers") or is_calendly(a):
            reden = "externe gast" if a.get("deelnemers") else "Calendly-boeking"
            regels.append(f"reeks '{a['titel'][:50]}': VOORSTEL (titel niet gewijzigd; {reden})")
            continue
        try:
            url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='@')}/events/{urllib.parse.quote(a['_reeks'])}"
            reeks = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer " + tok}), timeout=30))
            oud = reeks.get("summary") or ""
            nieuw = re.sub(r"\[LARA\]", "[LA]", oud, flags=re.I) if "[LARA]" in oud.upper() else codes_twee_letters(oud, _online(a))
            if nieuw == oud:
                continue
            reeks_a = _reeks_als_afspraak(a, reeks)
            if not isinstance(reeks_a["maker"], str) or reeks_a["maker"].strip().lower() not in _eigen_accounts():
                # H1-1, driehoeksoverleg C2, 17-10-2026: ook een reeks van een ander wordt zichtbaar als voorstel.
                regels.append(f"reeks '{oud[:50]}': VOORSTEL '{nieuw[:60]}' (door een ander gemaakt)")
                ag.log("titelwijziging", "voorstel", "VOORSTEL: titel niet gewijzigd", regels[-1])
                continue
            if not droog:
                _patch(reeks_a, {"summary": nieuw}, tok)
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
    if re.match(r"\s*(?:VR\s+)?vervalt\b", titel, re.I):
        return titel          # 'vervalt' blijft vooraan, anders herkent de agent de markering niet meer (FR-210)
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
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if a.get("hele_dag") or "T" not in a.get("start", "") or _voorbij(a["start"], nu) \
                or a.get("_archief") or not mag_schrijven(a.get("kalender", "")):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        nieuw = tekens_vooraan(a["titel"])
        if nieuw == a["titel"]:
            continue
        # H1-1b, driehoeksoverleg C3, 17-10-2026: ook hier geen reeks-GET bij bekende weigering.
        if a.get("deelnemers") or is_calendly(a):
            reden = "externe gast" if a.get("deelnemers") else "Calendly-boeking"
            regels.append(f"{a['start'][:16]} {a['titel'][:45]}: VOORSTEL '{nieuw[:60]}' ({reden})")
            continue
        voorgesteld = nieuw
        try:
            if a.get("_reeks"):
                if a["_reeks"] not in reeksen:
                    reeksen.add(a["_reeks"])
                    url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='@')}/events/{urllib.parse.quote(a['_reeks'])}"
                    reeks = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer " + tok}), timeout=30))
                    nieuw_reeks = tekens_vooraan(reeks.get("summary") or "")
                    if nieuw_reeks != (reeks.get("summary") or ""):
                        voorgesteld = nieuw_reeks
                        _patch(_reeks_als_afspraak(a, reeks), {"summary": nieuw_reeks}, tok)
                        regels.append(f"reeks '{(reeks.get('summary') or '')[:50]}' -> '{nieuw_reeks[:60]}'")
                        gedaan += 1
            else:
                _patch(a, {"summary": nieuw}, tok)
                regels.append(f"{a['start'][:16]} '{a['titel'][:50]}' -> '{nieuw[:60]}'")
                gedaan += 1
            a["titel"] = nieuw
        except TitelVoorstel as e:
            regels.append(f"{a['start'][:16]} {a['titel'][:45]}: VOORSTEL '{voorgesteld[:60]}' ({e})")
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
                klant = " ".join(naam)
                # Een testdeal met een invulsjabloon is geen bewijs van de gesprekspartner.
                if re.search(r"\b(?:voornaam\s+achternaam|first\s+name\s+last\s+name)\b", klant, re.I):
                    continue
                uit = (klant, x.get("status") == "won")
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
    if info.get("firma") or info["firma_conflict"] or info["reistijd"] or a.get("hele_dag"):
        return None, ""
    # Een bekende partner op het thuisadres is geen prospect van een willekeurige deal
    # die toevallig hetzelfde adres bevat. De koppeling partner -> firma staat in de master.
    if is_thuis_adres(a.get("locatie") or "") and not info["nummer"]:
        gevonden = []
        for firma, namen in (_gastregels().get("firma_gasten") or {}).items():
            for naam in namen:
                if re.search(r"\b" + re.escape(naam) + r"\b", titel, re.I):
                    gevonden.append((firma, naam))
        if len(gevonden) == 1:
            firma, naam = gevonden[0]
            rest = re.sub(r"\b" + re.escape(naam) + r"\b", "", titel.split(":", 1)[-1],
                          count=1, flags=re.I).strip(" ,:-")
            rest = rest[:1].upper() + rest[1:] if rest else "overleg"
            nieuw = f"Mehdi & {naam}: [{titelcode(firma)}-IN] {rest}"
            return nieuw, f"bekende partner {naam} van {firma}; thuis is geen buitenafspraak"
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
    # Een titel met enkel de activiteit kan uit de unieke adresdeal worden aangevuld.
    # Schreef Mehdi daarnaast een naam/ander inhoudswoord, dan mag een andere
    # persoon uit een deal op hetzelfde adres zijn woorden niet overschrijven.
    eigen_woorden = re.sub(r"^\s*(?:!!\s*)?mehdi\s*[:;,]?\s*", "", titel, flags=re.I)
    for rx, _ in ACTIVITEIT_WOORDEN[firma]:
        eigen_woorden = re.sub(rx, "", eigen_woorden, flags=re.I)
    eigen_woorden = re.sub(r"\b(?:en|met|voor|de|het|een)\b", "", eigen_woorden, flags=re.I)
    if re.search(r"[A-Za-zÀ-ÿ]", eigen_woorden) and not re.search(r"\b" + re.escape(klant) + r"\b", titel, re.I):
        return None, ""
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
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if a.get("hele_dag") or "T" not in a.get("start", "") or _voorbij(a["start"], nu) or a.get("_archief"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if a.get("kalender", "").startswith("en.be#"):
            continue
        nieuw, uitleg = titel_aanvulling(a, projecten)
        nieuw = canoniek(nieuw, _online(a))
        if not nieuw or nieuw == a["titel"]:
            continue
        zelf = (not a.get("deelnemers") and not a.get("_terugkerend") and not is_calendly(a))
        if not zelf:
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: VOORSTEL '{nieuw[:90]}' ({uitleg})")
            continue
        try:
            # De enige gecombineerde VR-oplossing komt uit het herhaalbaar onderzoeksresultaat.
            onderzoek = False
            if a["titel"].startswith("VR ") and not nieuw.startswith("VR "):
                gevonden, _ = titel_uit_onderzoek(a)
                onderzoek = bool(gevonden) and canoniek(gevonden, _online(a)) == nieuw
            _patch(a, {"summary": nieuw}, tok, uit_onderzoek=onderzoek)
            regels.append(f"{a['start'][:16]} '{a['titel'][:45]}' -> '{nieuw[:80]}' ({uitleg})")
            a["titel"] = nieuw
            gedaan += 1
        except TitelVoorstel as e:
            regels.append(f"{a['start'][:16]} {a['titel'][:45]}: VOORSTEL '{nieuw[:90]}' ({e})")
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


def rit_hoort_bij(rit, titel, richting=None, grens=None):
    """Draagt deze rit de titel van deze afspraak in zijn omschrijving ('Reistijd voor: <titel> (..'), ongeacht de code."""
    m = RIT_TITEL_RE.search(rit.get("omschrijving") or "")
    if m and (richting is None or m.group(1) == richting) and titel_sleutel(m.group(2)) == titel_sleutel(titel):
        return True
    if grens is None or richting not in ("voor", "na") or not _handmatige_rit_titel(rit, richting):
        return False
    try:
        rand = rit["einde"] if richting == "voor" else rit["start"]
        return datetime.fromisoformat(rand) == datetime.fromisoformat(grens)
    except (KeyError, TypeError, ValueError):
        return False


def zoom_zetten(items, alleen_dag=None):
    """ZL = zonder link. Een online gesprek met een externe partij zonder link krijgt ZL in de titel
    (zoals !! en ??) en de notitie 'Online. Mehdi stuurt de link naar ...'. Staat er later een link in
    de afspraak, dan gaan ZL en de notitie er weer af. De agent zet zelf GEEN link: Mehdi stuurt die.
    Niet bij bellen, Calendly-boekingen, intern overleg, een taak of terugkerende overleggen.
    Mandaat van Mehdi, 23-09-2026."""
    tok = agenda._toegang()
    nu = nu_lokaal().isoformat()
    gedaan, regels = 0, []
    for a in items:
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if a.get("hele_dag") or "T" not in a.get("start", "") or _voorbij(a["start"], nu):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if a.get("kalender") != WERKAGENDA or a.get("_terugkerend"):
            continue
        titel = a["titel"]
        info = lees_titel(titel)
        if info["reistijd"] or not info.get("firma") or info["soort"] == "IN" or info["buiten"] or info["soort"] in BUITEN_SOORTEN:
            continue
        if is_calendly(a):
            continue                      # werkwijze: niet bij Calendly-boekingen (Codex A09)
        zelf = _van_mehdi(a)              # met gasten of door een ander gezet: alleen een voorstel (werkwijze, Codex A09)
        oms = a.get("omschrijving") or ""
        heeft_link = bool(a.get("_conferentie")) or bool(VERGADERLINK_RE.search(f"{a.get('locatie') or ''} {oms}"))
        if heeft_link:
            if _heeft_zl(titel):
                nieuw = zonder_zl(titel)
                if not zelf:
                    regels.append(f"{a['start'][:16]} {titel[:45]}: VOORSTEL '{nieuw[:60]}' (link staat erin; met gasten verander ik de titel niet)")
                    continue
                try:
                    oms = _volledige_omschrijving(a, tok) if len(oms) >= 1900 else oms
                    schoon = re.sub(r"Online\. Mehdi stuurt de link naar [^\n]*\.\n*", "", oms).strip()
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
        if not zelf:
            regels.append(f"{a['start'][:16]} {titel[:45]}: VOORSTEL '{met_zl(titel)[:60]}' en stuur de link naar {wie} "
                          f"(met gasten verander ik titel en omschrijving niet)")
            continue
        try:
            if "description" in wijzig and len(oms) >= 1900:
                oms = _volledige_omschrijving(a, tok)
                wijzig["description"] = f"Online. Mehdi stuurt de link naar {wie}." + ("\n\n" + oms if oms else "")
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
    if info["firma_conflict"]:
        return ["meer verschillende firmacodes: " + ", ".join(info["firmas"])]
    if info["reistijd"] or a.get("hele_dag"):
        return []
    fouten = []
    if a.get("kalender", "") not in AGENDA_VASTE_KLEUR and not info.get("firma") and not is_zorg_titel(a.get("titel")):
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
    if info.get("firma_conflict"):
        return ""   # H1-1, driehoeksoverleg C2, 17-10-2026: ook een rit met twee firma's behoudt zijn kleur.
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
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
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
            print("kleur mislukt:", _toon(a), type(e).__name__, file=sys.stderr)
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


class _KaartdienstStoring:
    def __bool__(self):
        return False


KAARTDIENST_STORING = _KaartdienstStoring()


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
        # Netwerk-, HTTP-, time-out- en antwoordfouten zijn geen geldig leeg zoekresultaat.
        return KAARTDIENST_STORING


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
    storing = False
    for i, params in enumerate(pogingen):
        uit = _nominatim(params)
        if uit is KAARTDIENST_STORING:
            storing = True
            continue
        if uit:
            if i:
                print(f"adres gevonden via poging {i + 1}: {adres}", file=sys.stderr)
            cache[sleutel] = uit
            return uit
    cache.pop(sleutel, None)   # niet blijvend onthouden dat het mislukte
    return KAARTDIENST_STORING if storing else None


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
# Eén bron voor Lara's schoolvakanties: de officiële Vlaamse kalender in de repo (driehoeksoverleg 27-10-2026, L2). Tot
# dan telde elk hele-dag-blok in de Lara-agenda met 'vakanti' of 'feestdag'. Een fout blok (26/10 tot 1/11, gezet op
# 26-05-2026) liet de Lara-ritten wegvallen; een assistent wiste daarop de vaste Lara-afspraken van die week en Calendly
# boekte een klant op de rit van de zwemles naar huis (FR-210).
SCHOOLVAKANTIES = Path(__file__).resolve().parent / "werkwijze" / "schoolvakanties.json"
SCHOOLVAKANTIE_MARGE_DAGEN = 365    # zo ver zet ik Lara-ritten (RIT_VOORUIT_ALLES); de bron moet minstens zo ver gaan


def schoolvakanties():
    """(dagen, dekking_tot, namen) uit werkwijze/schoolvakanties.json: de vakantie- en feestdagen als ISO-datums, de
    laatste dag die de bron dekt (date) en per dag de naam van de vakantie. None als het bestand ontbreekt, niet klopt
    of de schooljaren niet aansluiten: onbekend is niet 'geen vakantie' (Codex A11)."""
    from datetime import date
    try:
        d = json.loads(SCHOOLVAKANTIES.read_text(encoding="utf-8"))
        jaren = sorted((d.get("schooljaren") or {}).values(), key=lambda j: j["van"])
        if not jaren:
            return None
        dagen, namen, vorig = set(), {}, None
        for j in jaren:
            begin, eind = date.fromisoformat(j["van"]), date.fromisoformat(j["tot"])
            if eind < begin or (vorig and begin != vorig + timedelta(days=1)):
                return None              # een gat tussen twee schooljaren zou als schooldagen tellen
            vorig = eind
            for p in j["vrij"]:
                a, b = date.fromisoformat(p["van"]), date.fromisoformat(p["tot"])
                if b < a or not (begin <= a and b <= eind) or not p.get("naam"):
                    return None
                while a <= b:
                    dagen.add(a.isoformat())
                    namen[a.isoformat()] = p["naam"]
                    a += timedelta(days=1)
        return frozenset(dagen), vorig, namen
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def lara_vakantiedagen():
    """De officiële schoolvakantie- en feestdagen (schoolvakanties()). Op zo'n dag is er geen Lara-ophaling, dus maakt
    de agent geen Lara-rit (mandaat van Mehdi, 22-09-2026). Een blok in de Lara-agenda telt niet meer mee: wijkt het
    af, dan wordt het een vraag (lara_vakantie_afwijkingen). Is de bron niet te lezen, dan None: onbekend is niet 'geen
    vakantie' (Codex A11, zoals FR-94)."""
    sv = schoolvakanties()
    if sv is None:
        return None
    _lara_vrij["dagen"] = sv[0]
    return sv[0]


def schoolvakantie_dekking():
    """De laatste dag die de officiële bron dekt, of None. Een Lara-afspraak daarna krijgt geen rit (niet te toetsen)."""
    sv = schoolvakanties()
    return sv[1] if sv else None


def lara_vervalt(a):
    """Een Lara-afspraak die Mehdi liet vervallen: 'vervalt' vooraan in de titel (en Beschikbaar). Zo wordt een
    ophaalmoment in een vakantie of op een eigen reis gemarkeerd in plaats van gewist (driehoeksoverleg 27-10-2026, L4).
    Daarvoor zet de agent geen rit."""
    return bool(re.match(r"\s*(?:VR\s+)?(?:!!\s*)?vervalt\b", a.get("titel") or "", re.I))


def zonder_vervalt(titel):
    """De titel zonder de markering 'vervalt (...)' vooraan: zo blijft een rit gekoppeld aan zijn afspraak (hertest 14)."""
    return re.sub(r"^\s*(?:VR\s+)?(?:!!\s*)?vervalt\b\s*(?:\([^)]*\))?\s*", "", titel or "", flags=re.I)


def lara_zonder_rit(a, vrij):
    """Een Lara-afspraak die geen rit (meer) vraagt: op een officiële vakantiedag of met 'vervalt' vooraan. Die houdt
    ook geen eigen rit vast: een rit die er nog aan hing, ruimt de agent op (reviewronde 27-10-2026, FR-79 en FR-210)."""
    return lara_vervalt(a) or (a.get("kalender") in AGENDA_VASTE_KLEUR
                               and AGENDA_VASTE_KLEUR[a["kalender"]].get("naam") == "Lara"
                               and vrij is not None and (a.get("start") or "")[:10] in vrij)


# Hele-dag-blokken in de Lara-agenda die een vrije dag aankondigen: alleen om te vergelijken met de officiële bron. Ook
# een pedagogische studiedag of vrije dag van de school wordt zo een vraag; ritten schakelt alleen de bron uit (hertest 16)
LARA_VRIJ_RE = re.compile(r"vakanti|feestdag|studiedag|vrije\s+dag|geen\s+school|schoolvrij|facultatie|brugdag", re.I)


def lara_vakantieblokken():
    """De hele-dag-blokken in de Lara-agenda met 'vakanti' of 'feestdag' in de titel, van vandaag tot 400 dagen
    vooruit: [{id, titel, van, tot}] met tot exclusief (zoals Google), of None als de agenda niet te lezen is. Alleen
    om te vergelijken met de officiële bron; ze bepalen de ritten niet meer (L2)."""
    import urllib.parse
    import urllib.request
    lara = next((k for k, val in AGENDA_VASTE_KLEUR.items() if val.get("naam") == "Lara"), None)
    if not lara:
        return None
    blokken = []
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
                if e.get("status") == "cancelled" or "date" not in (e.get("start") or {}) \
                        or not LARA_VRIJ_RE.search(e.get("summary") or ""):
                    continue
                blokken.append({"id": e.get("id", ""), "titel": e.get("summary") or "",
                                "van": e["start"]["date"], "tot": e["end"]["date"]})
            tok = d.get("nextPageToken")
            if not tok:
                break
    except Exception:  # noqa: BLE001
        return None
    return blokken


def lara_vakantie_afwijkingen(blokken, officieel, vandaag, dekking=None):
    """Pure functie: de blokken uit lara_vakantieblokken() met minstens één schooldag (maandag tot vrijdag, niet in de
    officiële bron) vanaf vandaag. Zo'n blok is een eigen reis, een vrije dag van de school of een fout: de agent plant
    de ritten zoals op een schooldag en vraagt het aan Mehdi (L2). Geeft [{id, titel, van, tot, schooldagen}]."""
    from datetime import date
    uit = []
    for b in blokken or []:
        try:
            a, eind = max(date.fromisoformat(b["van"]), vandaag), date.fromisoformat(b["tot"])
        except (KeyError, TypeError, ValueError):
            continue
        school = []
        if dekking is not None:
            eind = min(eind, dekking + timedelta(days=1))    # na de bron is een dag onbekend, geen schooldag
        while a < eind:
            if a.weekday() < 5 and a.isoformat() not in officieel:
                school.append(a.isoformat())
            a += timedelta(days=1)
        if school:
            uit.append({**b, "schooldagen": school})
    return uit


def lara_vakantieweken(items, namen, vandaag, vooruit=21):
    """Pure functie: per officiële vakantieweek in de komende `vooruit` dagen de vaste Lara-afspraken die er nog staan
    (geen rit, geen hele dag, niet vervallen). Die blijven staan en Bezet tot Mehdi zegt welke vervallen; de agent wist
    niets en past de reeks niet aan (L4). Geeft [{week, naam, van, tot, afspraken: [(start, titel)]}]."""
    from datetime import date
    lara = {k for k, val in AGENDA_VASTE_KLEUR.items() if val.get("naam") == "Lara"}
    grens = vandaag + timedelta(days=vooruit)
    weken = {}
    for a in items or []:
        dag = (a.get("start") or "")[:10]
        if a.get("kalender") not in lara or a.get("hele_dag") or "T" not in (a.get("start") or "") \
                or dag not in namen or lees_titel(a.get("titel") or "")["reistijd"] or lara_vervalt(a):
            continue
        if not (a.get("_reeks") or a.get("_terugkerend")
                or re.search(r"ophal|zwemles|naar huis brengen", a.get("titel") or "", re.I)):
            continue          # een eenmalig feest of uitstap is geen vast ophaalmoment (hertest 17)
        d = date.fromisoformat(dag)
        if not (vandaag <= d <= grens):
            continue
        j, w, _ = d.isocalendar()
        weken.setdefault(f"{j}-W{w:02d}", {"naam": namen[dag], "dagen": set(), "afspraken": [], "ids": [], "kenmerk": {}})
        weken[f"{j}-W{w:02d}"]["afspraken"].append((a["start"][:16], a.get("titel") or ""))
        _id = a.get("id") or a["start"][:16]
        weken[f"{j}-W{w:02d}"]["ids"].append(_id)
        weken[f"{j}-W{w:02d}"]["kenmerk"][_id] = f"{a['start'][:16]}|{a.get('titel') or ''}"
    uit = []
    for wk, v in sorted(weken.items()):
        j, w = int(wk[:4]), int(wk[-2:])
        maandag = date.fromisocalendar(j, w, 1)
        vrij = [maandag + timedelta(days=i) for i in range(7) if (maandag + timedelta(days=i)).isoformat() in namen]
        uit.append({"week": wk, "naam": v["naam"], "van": max(min(vrij), vandaag).isoformat(), "tot": max(vrij).isoformat(),
                    "afspraken": sorted(v["afspraken"]), "ids": sorted(v["ids"]), "kenmerk": v["kenmerk"]})
    return uit


_geen_auto = {"tot": 0.0, "dagen": frozenset()}


def geen_auto_dagen():
    """Dagen waarop Mehdi geen auto heeft. Hij (of een planner) zet er een hele-dag
    marker met 'geen auto' in de titel op de werkagenda. Op zo'n dag kan hij niet naar
    buiten rijden: de agent maakt geen rit en waarschuwt als er toch buiten gepland
    staat. Buiten-boekingen gebeuren sowieso handmatig, niet via Calendly. Mandaat van
    Mehdi, 22-09-2026. Lukt het lezen niet, dan None en niets onthouden (Codex A11, zoals FR-94)."""
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
        return None
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
    # een nieuwe afspraak op een dag die een markering afsluit, kan alleen met een ja van Mehdi (FR-83). Het eigen blok
    # dat een bestaande firma-afspraak spiegelt, is geen nieuwe afspraak: dat moet er juist staan (review 27-10-2026)
    dag = ((body.get("start") or {}).get("dateTime") or "")[:10]
    spiegel = bool(((body.get("extendedProperties") or {}).get("private") or {}).get(FIRMAMERK))
    m = markering_tegen(body.get("summary"), dag, locatie=body.get("location") or "") if not (toch or spiegel) else None
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
    if is_zorgschaduw(x):
        raise SchaduwItem("schaduw van een privé-zorgafspraak")
    import urllib.parse
    import urllib.request
    if not (mag_schrijven(x["kalender"]) and mag_schrijven(doel)):
        raise GeenSchrijfrecht(doel)
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(x['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(x['id'], safe='')}/move?" + urllib.parse.urlencode({"destination": doel, "sendUpdates": "none"}))
    req = urllib.request.Request(url, data=b"", method="POST", headers={"Authorization": f"Bearer {tok}"})
    urllib.request.urlopen(req, timeout=30)


RITMERK = "agendawacht_rit"
VERTREKMERK = "agendawacht_vertrek"
VERTREKMELDINGMERK = "agendawacht_vertrekmelding"
KETENMERK = "agendawacht_keten_vanaf"
RIT_MERKEN_PER_RONDE = 60      # oude ritten krijgen hun merk geleidelijk, zodat de eerste ronde niet uitloopt


def _nieuwe_rit():
    """Een eigen ID en een merk met datzelfde ID voor elke rit die ik maak. Tekst kan iedereen kopiëren; een kopie in
    Google krijgt altijd een ander ID, dus merk en ID kloppen dan niet meer (Codex A10, 15-10-2026)."""
    import uuid
    rid = "rit" + uuid.uuid4().hex          # base32hex: a-v en 0-9, zoals Google vraagt
    return {"id": rid, "extendedProperties": {"private": {RITMERK: rid}}}


def _rit_tekst(x):
    """Ziet eruit als mijn rit: het autootje vooraan en mijn uitleg (Reistijd voor/na ... OSRM) in de omschrijving."""
    oms = x.get("omschrijving") or ""
    return ((x.get("titel") or "").lstrip().startswith("\U0001F697") and "OSRM" in oms
            and ("Reistijd voor:" in oms or "Reistijd na:" in oms))


def _handmatige_rit_titel(x, richting):
    """Een menselijke rit blijft eigendom van de maker; richting en grensuur bepalen waar hij bij hoort."""
    titel = (x.get("titel") or "").strip()
    if _rit_tekst(x):
        return False
    rijden = bool(re.match(r"^(?:🚗\s*)?Rijden naar\s+\S", titel, re.I))
    heen = bool(re.match(r"^🚗\s*Reistijd\s*→\s*\S", titel, re.I))
    terug = bool(re.match(r"^(?:🚗\s*)?Reistijd\s*←\s*\S", titel, re.I))
    return (rijden or heen) if richting == "voor" else (rijden or terug)


def _afspraak_van_rit(x, items, s0, e0):
    """De afspraken waar deze rit volgens zijn omschrijving en zijn tijdstip bij hoort: een heenrit eindigt op het begin,
    een terugrit begint op het einde, en 'Reistijd voor/na: <titel>' noemt de afspraak."""
    richting = "voor" if "Reistijd voor:" in (x.get("omschrijving") or "") else "na"
    uit = []
    for y in items:
        if "T" not in (y.get("start") or "") or lees_titel(y.get("titel") or "")["reistijd"]:
            continue
        try:
            t = datetime.fromisoformat(y["start"] if richting == "voor" else y["einde"])
        except (KeyError, ValueError):
            continue
        if y.get("kalender") == x.get("kalender") and t == (e0 if richting == "voor" else s0) and rit_hoort_bij(x, y["titel"], richting):
            uit.append(y)
    return uit


def is_eigen_rit(x):
    """Een ritblok dat de agent zelf maakte: mijn tekst én mijn merk met het eigen ID van het blok. Alleen zo'n blok
    mag hij ooit weghalen of verhuizen. Tot 15-10-2026 volstond de tekst, en een gekopieerd ritblok kon zo verdwijnen
    (Codex A10). Een oude rit zonder merk wordt niet bijgewerkt: eerst krijgt hij het merk via de gecontroleerde
    overgang, als hij aantoonbaar aan precies één afspraak hangt."""
    return _rit_tekst(x) and bool(x.get("id")) and (x.get("_merk") or {}).get(RITMERK) == x.get("id")


def _rit_vertrek(x):
    """Echt laatste vertrek van een eigen rit, uit het Google-merk en binnen de blokgrenzen.

    Bij oude en handmatige ritten blijft het blokbegin het enige bekende vertrekmoment.
    """
    begin = datetime.fromisoformat(x["start"])
    if is_eigen_rit(x):
        try:
            vertrek = datetime.fromisoformat((x.get("_merk") or {}).get(VERTREKMERK) or "")
            einde = datetime.fromisoformat(x["einde"])
            if begin <= vertrek <= einde:
                return vertrek
        except (ValueError, TypeError, KeyError):
            pass
    return begin


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
              "zonder_tijd": f"VR Agendawacht: uitnodiging zonder uur: {a['bron_onderwerp'][:70]}",
              "zorg_open": f"VR Agendawacht: zorgafspraak uit mail, {a.get('detail') or 'nog niet volledig'}: {uur} {a['titel'][:40]}"}
    vraag = {"zonder_tijd": "zeg of het een afspraak wordt en wanneer. Ik zet zelf niets.",
             "ontbreekt": "zeg of ik deze afspraak in je agenda zet, of dat ze niet doorgaat. Ik zet zelf niets.",
             "zorg_open": "zeg wat ontbreekt (eindtijd, plaats of voor wie), of laat het staan tot de praktijk het bevestigt. "
                          "Ik zet het blok pas als het vaststaat en verzin geen duur."
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
    gekoppelde_zorg_k = {MA.sleutel_kort({"sleutel": (x.get("_merk") or {}).get(ZORGMERK)}) for x in bestaande
                         if x.get("kalender") == PRIVE_AGENDA and not x.get("hele_dag")
                         and (x.get("_merk") or {}).get(ZORGMERK)}
    gekoppelde_zorg_k |= {MA.sleutel_kort(a) for a in res
                          if a.get("soort") == "zorg" and a.get("status") in ("gekoppeld", "gezet")}
    open_ = {MA.sleutel_kort(a): a for a in res if a["status"] in MA.VRAAG_STATUSSEN
             and MA.sleutel_kort(a) not in gekoppelde_zorg_k
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
        # ook een zorgmail zonder datum (een annulering zonder tijd) krijgt een keer een vraag (Codex A03)
        zonder = a["status"] == "zonder_tijd" or (a["status"] == "zorg_open" and not a.get("start"))
        if (not zonder or MA.sleutel_kort(a) in gekoppelde_zorg_k or a.get("melding")
                or (a.get("bron_ontvangen") or "")[:10] < (nu - timedelta(days=MAIL_VOORUIT_DAGEN)).date().isoformat()):
            continue
        k = "z:" + MA.sleutel_kort(a)
        try:
            if k not in er:
                _insert(PRIVE_AGENDA, _mail_melding_body(a, k, vandaag), tok)
            MA.melding_zet(a["sleutel"], vandaag)
            regels.append(f"uitnodiging zonder uur: vraag gezet ({a['bron_mailbox']})")
        except Exception as e:  # noqa: BLE001
            regels.append(f"uitnodiging zonder uur: vraag niet gezet ({type(e).__name__})")
    # Afronden alleen op bewijs: de afspraak staat nu in de agenda, is geannuleerd of voorbij. Een vraag die alleen buiten
    # het venster van 14 dagen viel, blijft open; verschoof haar afspraak, dan volgt de melding (nacontrole v1.3, R4).
    per_k = {MA.sleutel_kort(a): a for a in res}
    redenen = {"gekoppeld": "de afspraak staat nu in de agenda", "gezet": "de afspraak staat nu in de agenda",
               "geannuleerd": "de afspraak is geannuleerd", "voorbij": "de afspraak is voorbij"}
    for k, x in er.items():
        basis_k = k[2:] if k.startswith("z:") else k
        if basis_k in gekoppelde_zorg_k:
            try:
                if _eigen_melding_opgelost(x, k, tok, nu, "de afspraak staat nu in de agenda"):
                    regels.append(f"{x['start'][:10]} melding op opgelost gezet: de afspraak staat nu in de agenda")
            except Exception as e:  # noqa: BLE001
                regels.append(f"{x['start'][:10]} melding niet bijgewerkt ({type(e).__name__})")
            continue
        if k in open_ or k.startswith("z:"):
            continue
        a = per_k.get(k)
        try:
            if a is None:
                continue                                   # onbekend in het register: niets beweren, niets afronden
            if a["status"] in MA.VRAAG_STATUSSEN:
                if a["start"] and (x.get("start") or "")[:10] != a["start"][:10]:
                    body = _mail_melding_body(a, k, a["start"][:10])
                    _patch(x, {k2: body[k2] for k2 in ("summary", "start", "end", "description")}, tok)
                    regels.append(f"{a['start'][:16]} melding bijgewerkt buiten het venster ({a['status']}, blijft open)")
                continue
            if a["status"] in redenen and _eigen_melding_opgelost(x, k, tok, nu, redenen[a["status"]]):
                regels.append(f"{x['start'][:10]} melding op opgelost gezet: {redenen[a['status']]}")
        except Exception as e:  # noqa: BLE001
            regels.append(f"{x['start'][:10]} melding niet bijgewerkt ({type(e).__name__})")
    return regels


def _eigen_melding_opgelost(x, k, tok, nu, reden="opgelost", vrij=False):
    """Zet alleen een eigen mailmelding (merk van de agent, privé-agenda) op 'Opgelost'. Wissen doet de agent niet.
    Met vrij=True wordt het blok ook Beschikbaar: een opgelost Bezet blok houdt geen uur meer vast (Codex-hertest 3, 13)."""
    if x.get("kalender") != PRIVE_AGENDA or (x.get("_merk") or {}).get(MAILMERK) != k or not x.get("id"):
        return False
    titel = re.sub(r"^VR Agendawacht:\s*", "", x.get("titel") or "")
    nieuwe_titel = f"Opgelost: {titel}"[:200]
    nieuwe_oms = f"Opgelost op {nu:%d-%m-%Y %H:%M}: {reden}. Je mag deze melding weghalen.\n\n" + (x.get("omschrijving") or "")
    nieuwe_merk = {**(x.get("_merk") or {}), MAILMERK: f"opgelost:{k}"}
    _patch(x, {"summary": nieuwe_titel,
               "description": nieuwe_oms,
               "extendedProperties": {"private": nieuwe_merk},
               **({"transparency": "transparent"} if vrij else {})}, tok)
    x["titel"] = nieuwe_titel
    x["omschrijving"] = nieuwe_oms
    x["_merk"] = nieuwe_merk
    return True


# Lara en de schoolvakanties (driehoeksoverleg 27-10-2026, L2 tot L4; FR-210). Wat niet klopt met de officiële kalender,
# en elke vakantieweek met vaste Lara-afspraken, wordt een vraag in de privé-agenda (alleen Mehdi ziet die; Leen ziet de
# Lara-agenda). De vraag draagt het mailmerk (zodat de bestaande eigendomscontrole ze als eigen melding kent) en een
# eigen Lara-sleutel. De agent wist nooit een Lara-afspraak en past geen reeks aan: wat vervalt, markeert Claude 1 na
# Mehdi's ja met 'vervalt (vakantie)' vooraan en Beschikbaar.
LARAMERK = "agendawacht_lara"
LARA_INHOUD = "agendawacht_lara_inhoud"     # vingerafdruk van de tekst: een vraag volgt haar inhoud (reviewronde)
LARA_VRAAG_VOORUIT = 120          # dagen vooruit voor een afwijkend blok; een vakantieweek: 21 dagen
LARA_MARKEREN = ("Vervalt een ophaalmoment, laat het dan markeren met 'vervalt (vakantie)' vooraan en Beschikbaar. "
                 "Wissen doe ik nooit.")


def _lara_mailk(k):
    return hashlib.sha256(f"lara:{k}".encode()).hexdigest()[:16]


def _lara_body(k, titel, van, tot, tekst):
    """Een hele-dag-vraag in de privé-agenda van van tot en met tot (ISO-datums), Beschikbaar, zonder herinnering."""
    from datetime import date as _d  # noqa: PLC0415
    return {"summary": titel[:200], "start": {"date": van},
            "end": {"date": (_d.fromisoformat(tot) + timedelta(days=1)).isoformat()},
            "transparency": "transparent", "reminders": {"useDefault": False, "overrides": []},
            "description": tekst[:1900],
            "extendedProperties": {"private": {MAILMERK: _lara_mailk(k), LARAMERK: k,
                                               LARA_INHOUD: hashlib.sha256(tekst.encode()).hexdigest()[:12]}}}


def _ddmm(dag):
    return f"{dag[8:10]}/{dag[5:7]}"


def lara_afwijking_body(b, vandaag):
    from datetime import date as _d  # noqa: PLC0415
    k = f"afwijking:{b['id']}"
    van = max(b["van"], vandaag.isoformat())
    tot = (_d.fromisoformat(b["tot"]) - timedelta(days=1)).isoformat()
    tekst = (f"Agendawacht vraagt: is dit een eigen reis of een vrije dag van de school? Volgens de officiële kalender "
             f"(vlaanderen.be) zijn {', '.join(_ddmm(d) for d in b['schooldagen'][:10])} schooldagen. Ik plan de ophaalritten "
             f"zoals op een schooldag tot jij beslist. {LARA_MARKEREN}\n\n"
             f"Blok in de agenda Lara: '{b['titel'][:80]}', {_ddmm(b['van'])} tot en met {_ddmm(tot)}.")
    return k, _lara_body(k, f"VR Agendawacht: Lara-blok valt niet in de officiële schoolvakantie ({_ddmm(b['van'])} tot "
                            f"{_ddmm(tot)})", van, tot, tekst)


def lara_week_body(w):
    k = f"week:{w['week']}"
    lijst = "\n".join(f"- {_ddmm(s[:10])} {s[11:16]} {t[:70]}" for s, t in w["afspraken"][:15])
    tekst = (f"Agendawacht vraagt: welke vaste Lara-afspraken vervallen in de {w['naam']} ({_ddmm(w['van'])} tot "
             f"{_ddmm(w['tot'])})? Ze blijven staan en Bezet, zodat Calendly er niet over boekt. {LARA_MARKEREN}\n\n{lijst}")
    return k, _lara_body(k, f"VR Agendawacht: {w['naam']} Lara, ophaalmomenten blijven Bezet tot jij zegt welke vervallen",
                         w["van"], w["tot"], tekst)


LARA_VRAGEN = os.path.expanduser("~/appportal/mijnagents-data/agenda-lara-vragen.json")


def _lara_vragen_lezen():
    try:
        with open(LARA_VRAGEN, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _lara_vragen_bewaren(d):
    os.makedirs(os.path.dirname(LARA_VRAGEN), exist_ok=True)
    tmp = f"{LARA_VRAGEN}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=0)
    os.replace(tmp, LARA_VRAGEN)


def _prive_item_lezen(eid, tok):
    """Een item uit de privé-agenda op id, in de vorm van agenda.afspraken(), of None als het weg is. Zo vindt de agent
    een eigen vraag terug die buiten het leesvenster van de ronde valt (Codex-controle 27-10-2026, punt 3)."""
    import urllib.error  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(PRIVE_AGENDA, safe='')}/events/"
           f"{urllib.parse.quote(eid, safe='')}")
    try:
        ev = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"}),
                                              timeout=30))
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return None
        raise
    if ev.get("status") == "cancelled":
        return None
    s, e_ = ev.get("start") or {}, ev.get("end") or {}
    return {"kalender": PRIVE_AGENDA, "id": ev.get("id", ""), "titel": ev.get("summary", ""),
            "start": s.get("dateTime") or s.get("date", ""), "einde": e_.get("dateTime") or e_.get("date", ""),
            "hele_dag": "date" in s and "dateTime" not in s, "omschrijving": (ev.get("description") or "")[:2000],
            "deelnemers": [a.get("email", "") for a in ev.get("attendees", []) if a.get("email")],
            "_agendagasten": [], "maker": (ev.get("creator") or {}).get("email", ""),
            "_merk": (ev.get("extendedProperties") or {}).get("private") or {}, "_reminders": ev.get("reminders") or {}}


def lara_meldingen(afwijkingen, weken, bestaande, tok, nu=None):
    """Zet of werkt bij: een vraag per afwijkend Lara-blok en per vakantieweek met vaste Lara-afspraken. Elke vraag
    wordt een keer gesteld: het register (LARA_VRAGEN) onthoudt ze, ook als Mehdi de vraag weghaalt of beantwoordt
    terwijl het blok blijft staan (een echte reis); zo vraagt de agent niet elke ronde opnieuw (Codex-controle
    27-10-2026, punt 2). Wat niet meer geldt, krijgt 'Opgelost' (zoals een mailmelding), ook buiten het leesvenster;
    wissen doet de agent niet. Alleen aanroepen na een volledige lezing. Geeft regels zonder Lara-titels (privé)."""
    nu = nu or nu_lokaal()
    gewenst = dict([lara_afwijking_body(b, nu.date()) for b in afwijkingen] + [lara_week_body(w) for w in weken])
    weekinhoud = {f"week:{w['week']}": w.get("ids") or [s_ for s_, _ in w["afspraken"]] for w in weken}
    weekkenmerk = {f"week:{w['week']}": w.get("kenmerk") or {} for w in weken}
    reg = _lara_vragen_lezen()
    er = {(x.get("_merk") or {}).get(LARAMERK): x for x in bestaande
          if x.get("kalender") == PRIVE_AGENDA and (x.get("_merk") or {}).get(LARAMERK)
          and not str((x.get("_merk") or {}).get(MAILMERK, "")).startswith("opgelost:")}
    regels, gewijzigd = [], False
    for k, body in gewenst.items():
        x = er.get(k)
        soort = k.split(":", 1)[0]
        try:
            inhoud = body["extendedProperties"]["private"][LARA_INHOUD]
            # een week krijgt alleen opnieuw een vraag (of een bijgewerkte) als er een ophaalmoment bijkomt dat nog niet
            # gevraagd was; een voorbije afspraak die uit de lijst valt, telt niet (hertest 14 tot 16)
            sleutels = sorted(set(weekinhoud.get(k) or []))      # id van de afspraak: een titelwijziging is niets nieuws
            nieuw_bij = bool(set(sleutels) - set((reg.get(k) or {}).get("afspraken") or []))
            # een komende afspraak met dezelfde id die van uur of titel veranderde: de vraag bijwerken, niet opnieuw vragen
            oud_km = (reg.get(k) or {}).get("kenmerk") or {}
            km = weekkenmerk.get(k) or {}
            vandaag_s = nu.date().isoformat()
            # ook bijwerken als een nog komend moment verdwijnt (vervalt of weg) of terugkomt; het gewone verstrijken van
            # een afspraak telt niet (hertest 19)
            veranderd = (any(i in oud_km and oud_km[i] != v_ for i, v_ in km.items())
                         or any(i not in km and v_[:10] >= vandaag_s for i, v_ in oud_km.items())
                         or any(i not in oud_km for i in km if i in set((reg.get(k) or {}).get("afspraken") or [])))
            heropen = k.startswith("week:") and k in reg and nieuw_bij
            if x is None and (k not in reg or heropen):
                n = _insert(PRIVE_AGENDA, body, tok) or {}
                reg[k] = {"gevraagd": nu.date().isoformat(), "id": n.get("id", ""), "open": True, "inhoud": inhoud,
                          "afspraken": sorted(set(sleutels) | set((reg.get(k) or {}).get("afspraken") or [])),
                          "kenmerk": dict(km)}
                gewijzigd = True
                regels.append(f"{body['start']['date']} Lara-vraag gezet ({soort})")
            elif x is not None and ((x.get("titel") or "") != body["summary"]
                                    or (k.startswith("week:") and (nieuw_bij or veranderd))
                                    or (k.startswith("afwijking:") and (x.get("start") or "")[:10] != body["start"]["date"])):
                _patch(x, {k2: body[k2] for k2 in ("summary", "start", "end", "description", "extendedProperties")}, tok)
                if k in reg:
                    reg[k] = {**reg[k], "inhoud": inhoud,
                              "afspraken": sorted(set(sleutels) | set(reg[k].get("afspraken") or [])),
                              "kenmerk": dict(km)}
                    gewijzigd = True
                regels.append(f"{body['start']['date']} Lara-vraag bijgewerkt ({soort})")
        except Exception as e:  # noqa: BLE001
            regels.append(f"{body['start']['date']} Lara-vraag niet gezet ({soort}, {type(e).__name__})")
    for k, r in list(reg.items()):
        if k in gewenst or not r.get("open") or not (k.startswith("afwijking:") or k.startswith("week:")):
            continue          # een vraag over een gewiste afspraak (agenda_signaal) rondt Mehdi zelf af
        reden = ("het blok wijkt niet meer af van de officiële kalender" if k.startswith("afwijking:")
                 else "de vakantieweek is voorbij of er staat geen vaste Lara-afspraak meer open")
        try:
            x = er.get(k) or (_prive_item_lezen(r["id"], tok) if r.get("id") else None)
            if x is not None and (x.get("_merk") or {}).get(LARAMERK) == k \
                    and not str((x.get("_merk") or {}).get(MAILMERK, "")).startswith("opgelost:"):
                if not _eigen_melding_opgelost(x, (x.get("_merk") or {}).get(MAILMERK), tok, nu, reden):
                    continue
                regels.append(f"{(x.get('start') or '')[:10]} Lara-vraag op opgelost gezet")
            reg[k] = {**r, "open": False, "afgerond": nu.date().isoformat()}
            gewijzigd = True
        except Exception as e:  # noqa: BLE001
            regels.append(f"{r.get('gevraagd', '')} Lara-vraag niet bijgewerkt ({type(e).__name__})")
    grens = (nu.date() - timedelta(days=400)).isoformat()
    for k in [k for k, r in reg.items() if not r.get("open") and (r.get("afgerond") or r.get("gevraagd", "")) < grens]:
        reg.pop(k)
        gewijzigd = True
    if gewijzigd:
        _lara_vragen_bewaren(reg)
    return regels


def lara_vakantie_stap(rit_items, vandaag):
    """De Lara-stap van de volledige ronde: afwijkende blokken en vakantieweken als vraag in de privé-agenda. Geeft
    noden (vaste tekst, geen teller, geen Lara-titel: N10 en privé). Alleen op een volledige lezing (Codex A15, A17)."""
    noden = []
    sv = schoolvakanties()
    if sv is None:
        return [{"tekst": "De officiële schoolvakanties (werkwijze/schoolvakanties.json) zijn niet te lezen: geen Lara-ritten",
                 "wie": "claude"}]
    officieel, dekking, namen = sv
    nu = nu_lokaal()
    if dekking < nu.date() + timedelta(days=SCHOOLVAKANTIE_MARGE_DAGEN):
        noden.append({"tekst": "De officiële schoolvakanties van het volgende schooljaar ontbreken in "
                               "werkwijze/schoolvakanties.json; overnemen van vlaanderen.be", "wie": "claude"})
    lara = {k for k, val in AGENDA_VASTE_KLEUR.items() if val.get("naam") == "Lara"}
    if VERRE_FOUT or PRIVE_AGENDA in ONGELEZEN or lara & ONGELEZEN:
        return noden                 # halve lezing: geen vraag zetten of afronden, anders komt er een dubbel
    blokken = lara_vakantieblokken()
    if blokken is None:
        return noden + [{"tekst": "De Lara-agenda is niet te lezen: afwijkende vakantieblokken niet nagekeken", "wie": "claude"}]
    grens = (nu.date() + timedelta(days=LARA_VRAAG_VOORUIT)).isoformat()
    afw = [b for b in lara_vakantie_afwijkingen(blokken, officieel, nu.date(), dekking) if b["van"] <= grens]
    weken = lara_vakantieweken(rit_items, namen, nu.date())
    try:
        regels = lara_meldingen(afw, weken, rit_items, agenda._toegang(), nu)
    except Exception as e:  # noqa: BLE001
        return noden + [{"tekst": f"Lara-vragen in de privé-agenda niet gezet ({type(e).__name__})", "wie": "claude"}]
    ag.log(f"dag {vandaag}", "schrijf", f"Lara en schoolvakanties: {len(afw)} afwijkend blok, {len(weken)} vakantieweek",
           "\n".join(regels))
    if any("niet gezet" in r or "niet bijgewerkt" in r for r in regels):
        noden.append({"tekst": "Een Lara-vraag in de privé-agenda is niet gezet of niet bijgewerkt", "wie": "claude"})
    return noden


def _lara_gewist_body(dag, uur, titel, sleutel, dagen):
    k = f"gewist:{sleutel}"
    dagen = sorted(set(dagen or [dag]))
    waar = (f"op {_ddmm(dagen[0])} is een vaste Lara-afspraak{(' van ' + uur) if uur else ''}" if len(dagen) == 1 else
            f"op {', '.join(_ddmm(d) for d in dagen[:10])}{' en later' if len(dagen) > 10 else ''} zijn vaste "
            f"Lara-afspraken van dezelfde reeks")
    tekst = (f"Agendawacht vraagt: {waar} uit de agenda gehaald, maar volgens de officiële kalender (vlaanderen.be) zijn "
             f"het schooldagen. Klopt dat? Zo niet, laat Claude 1 ze terugzetten. {LARA_MARKEREN}\n\n"
             f"Afspraak: {titel[:80] or '(titel onbekend)'}.")
    return _lara_body(k, f"VR Agendawacht: vaste Lara-afspraak gewist op een schooldag ({_ddmm(dagen[0])})",
                      dagen[0], dagen[0], tekst)


def lara_gewist_melden(dag, uur, titel, sleutel, tok, dagen=None):
    """Een vaste Lara-afspraak werd gewist op een officiële schooldag (agenda_signaal ziet dat, ook als een assistent
    buiten Claude Code het deed): een vraag in de privé-agenda op de eerste dag. Een hele reeks geeft één vraag met de
    lijst van de dagen. De agent zet zelf niets terug (L3). Geeft het id van de vraag."""
    n = _insert(PRIVE_AGENDA, _lara_gewist_body(dag, uur, titel, sleutel, dagen), tok) or {}
    return n.get("id") or ""


def lara_gewist_bijwerken(eid, uur, titel, sleutel, tok, dagen):
    """Vult de bestaande vraag over een gewiste reeks aan met dagen die in een latere ronde geschrapt werden, in plaats
    van een tweede vraag (Codex-hertest 27-10-2026, punt 1). False als de vraag er niet meer is of niet van de agent."""
    x = _prive_item_lezen(eid, tok) if eid else None
    if x is None or (x.get("_merk") or {}).get(LARAMERK) != f"gewist:{sleutel}" \
            or str((x.get("_merk") or {}).get(MAILMERK, "")).startswith("opgelost:") \
            or not (x.get("titel") or "").startswith("VR Agendawacht:"):
        return False          # weg, niet van mij, of al afgerond: dan een nieuwe vraag (reviewronde)
    body = _lara_gewist_body(min(dagen), uur, titel, sleutel, dagen)
    _patch(x, {k2: body[k2] for k2 in ("summary", "start", "end", "description")}, tok)
    return True


# Firma-agenda's van collega's (driehoeksoverleg 27-10-2026, Z1 tot Z7). Mehdi verbergt ze in zijn weergave; hij wil
# alleen zien wat hij moet doen of waar hij bij moet zijn. De agent leest ze alleen mee (werkwijze/agenda-taken.json,
# 'firma_meelezen'): een afspraak die Mehdi aangaat ('Mehdi: ...' vooraan), krijgt Mehdi als stille gast, zonder mail,
# zodat ze op zijn werkagenda verschijnt. Verder schrijft de agent er niets: mag_schrijven() kent deze agenda's niet.
MEHDI_VOORAAN = re.compile(r"^\W*(?:VR\s+)?(?:!+\s*)?Mehdi\b[^:\n]{0,60}:", re.I)
FIRMAMERK = "agendawacht_firma"
FIRMA_VRAGEN = os.path.expanduser("~/appportal/mijnagents-data/agenda-firma-vragen.json")
FIRMA_VOORUIT_DAGEN = 365          # zo ver als de ritten: een afspraak over drie weken mag niet ontbreken (Codex, punt 1)
FIRMA_VANGNET_DAGEN = 7


def firma_meelezen():
    """[(adres, naam)] van de firma-agenda's die de agent alleen meeleest. Geen kopie in de code (Z1)."""
    try:
        d = json.loads((Path(__file__).resolve().parent / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
        return [(a["adres"], a.get("naam") or a["adres"]) for a in d.get("firma_meelezen") or [] if a.get("adres")]
    except (OSError, ValueError, KeyError, TypeError):
        return []


FIRMA_SLOT = os.path.expanduser("~/appportal/mijnagents-data/agenda-firma.lock")
FIRMA_NODEN = os.path.expanduser("~/appportal/mijnagents-data/agenda-firma-noden.json")


def _firma_buitenblok(a, fysiek):
    """Mijn open Bezet blok voor een verborgen firma-afspraak op een echt adres: voor de ritten een buitenafspraak, ook al
    draagt het een algemene titel (Codex-hertest 24)."""
    mk = a.get("_merk") or {}
    return bool(fysiek and mk.get(FIRMAMERK) and not str(mk.get(MAILMERK, "")).startswith("opgelost:")
                and not a.get("_vrij") and "T" in (a.get("start") or "") and a.get("kalender") == PRIVE_AGENDA)


FIRMA_BLOK_VERANDERD = False     # zette of verzette deze ronde een Bezet blok? Dan het belrooster meteen bijwerken


def firma_kleurronde(vandaag):
    """De firmacontrole in de kleurronde. De noden gaan daar niet naar het bord (dat zet de volledige ronde, declaratief);
    verandert wat er mis is, dan komt het in het werkverslag, zodat Mehdi het ook in het weekend ziet (overleg P8)."""
    teksten = sorted(n["tekst"] for n in firma_stap(vandaag))
    if FIRMA_BLOK_VERANDERD:
        # een nieuw of verzet Bezet blok in het weekend of 's avonds: het belrooster meteen bijwerken, niet pas in de
        # volgende volledige ronde (Codex-hertest 24)
        try:
            rooster = rooster_maken([x for x in afspraken(-1, 8) if not x.get("fout")], archief_afspraken(-1, 8), vandaag, [])
            bellen.rooster_schrijven(rooster)
        except Exception as e:  # noqa: BLE001
            teksten.append(f"Belrooster niet bijgewerkt na een firmablok ({type(e).__name__})")
    try:
        with open(FIRMA_NODEN, encoding="utf-8") as f:
            vorige = json.load(f)
    except (OSError, ValueError):
        vorige = []
    if teksten != vorige:
        ag.log(f"dag {vandaag}", "bevinding", "firma-agenda's: " + ("; ".join(teksten) if teksten else "weer in orde"))
        os.makedirs(os.path.dirname(FIRMA_NODEN), exist_ok=True)
        with open(FIRMA_NODEN, "w", encoding="utf-8") as f:
            json.dump(teksten, f, ensure_ascii=False)
    return teksten


def verborgen_schrijfagendas(zicht):
    """De agenda's waarop de agent zelf ritten en vragen zet (KALENDERS, zonder de feestdagen) en die Mehdi in zijn
    weergave verborgen heeft: daar zou hij een eigen rit missen. Alleen de firma-agenda's van collega's mogen verborgen
    zijn (overleg P1, Codex-hertest 3, punt 12). Een agenda die niet in Mehdi's lijst staat, ziet hij evenmin."""
    return sorted(n.split("(")[0].strip() for k, n in KALENDERS.items() if "#holiday" not in k and zicht.get(k) is not True)


def _gast_status(ev):
    """Mehdi's antwoord als gast ('accepted', 'declined', ...), of None als hij geen gast is."""
    return next(((g.get("responseStatus") or "") for g in ev.get("attendees") or []
                 if (g.get("email") or "").lower() == WERKAGENDA), None)


def _gast_mehdi(ev):
    return _gast_status(ev) is not None


def _tijd(e, veld):
    return (e.get(veld) or {}).get("dateTime") or (e.get(veld) or {}).get("date") or ""


_KAL_TZ = {}          # tijdzone per firma-agenda, gelezen met haar afspraken


def _naar_brussel(e, kal_tz=None):
    """Een firma-afspraak met haar tijden in Brusselse tijd. Google geeft de tijd in de tijdzone van de bronagenda
    (Suriname): 21:30 daar is 01:30 de dag erna in Brussel. Datum en uur van een vraag volgen Brussel (Codex-hertest 15).
    Een tijd zonder offset geldt in haar eigen timeZone, anders in die van de agenda (hertest 16, 17); is geen van beide
    bekend, dan krijgt de afspraak '_tijd_onzeker' en komt er geen Bezet blok. Een hele dag blijft haar datum."""
    if not isinstance(e, dict):
        return e
    uit = dict(e)
    for veld in ("start", "end", "originalStartTime"):
        t = (e.get(veld) or {}).get("dateTime")
        if t:
            try:
                d = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if d.tzinfo is None:
                    tz = (e.get(veld) or {}).get("timeZone") or kal_tz
                    if not tz:
                        uit["_tijd_onzeker"] = True
                        continue
                    d = d.replace(tzinfo=ZoneInfo(tz))
                uit[veld] = {"dateTime": d.astimezone(TIJDZONE).isoformat()}
            except (ValueError, KeyError):
                uit["_tijd_onzeker"] = True
    return uit


def _google(url, tok, data=None, methode=None, kop=None):
    import urllib.request  # noqa: PLC0415
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, method=methode,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json", **(kop or {})})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _lijst_alles(kal, q, tok):
    """Alle items van een events-lijst, over alle pagina's: Google kan een lege pagina met een volgende token geven."""
    import urllib.parse  # noqa: PLC0415
    uit, pagina = [], None
    while True:
        qq = dict(q, **({"pageToken": pagina} if pagina else {}))
        d = _google(f"{agenda.API}/calendars/{urllib.parse.quote(kal, safe='')}/events?" + urllib.parse.urlencode(qq), tok)
        uit += d.get("items", [])
        pagina = d.get("nextPageToken")
        if not pagina:
            return uit


def firma_afspraken(tok, nu=None, dagen=FIRMA_VOORUIT_DAGEN):
    """De komende afspraken op de firma-agenda's, over alle pagina's, als ruwe Google-items met 'kalender' erbij, en de
    adressen van de agenda's die niet volledig te lezen waren. Een onleesbare agenda stopt de andere niet; van haar komt
    niets in de lijst, dus geen gast en geen vangnet op een halve lezing (Codex, punt 4; hertest 3, punt 17)."""
    nu = nu or nu_lokaal()
    uit, onleesbaar = [], []
    for adres, naam in firma_meelezen():
        q = {"timeMin": nu.isoformat(), "timeMax": (nu + timedelta(days=dagen)).isoformat(), "singleEvents": "true",
             "maxResults": "2500"}
        try:
            items = _lijst_alles(adres, q, tok)
        except Exception:  # noqa: BLE001
            onleesbaar.append(adres)
            continue
        if adres not in _KAL_TZ:
            try:
                import urllib.parse  # noqa: PLC0415
                _KAL_TZ[adres] = _google(f"{agenda.API}/calendars/{urllib.parse.quote(adres, safe='')}?fields=timeZone",
                                         tok).get("timeZone")
            except Exception:  # noqa: BLE001
                _KAL_TZ[adres] = None
        uit += [{**_naar_brussel(e, _KAL_TZ.get(adres)), "kalender": adres, "_agendanaam": naam}
                for e in items if e.get("status") != "cancelled"]
    return uit, onleesbaar


GASTVELDEN = ("email", "displayName", "optional", "responseStatus", "comment", "additionalGuests", "resource")


class _BlijftVeranderen(RuntimeError):
    """Drie keer na elkaar een 412: de laatst gelezen afspraak gaat mee naar het vangnet (Codex-hertest 3, punt 16)."""

    def __init__(self, vers):
        super().__init__("afspraak bleef veranderen (412)")
        self.vers = vers


def _gast_erbij(kal, eid, tok, pogingen=3):
    """Zet alleen Mehdi erbij als gast, zonder mail (sendUpdates=none). Ik lees de afspraak vlak ervoor opnieuw, behoud
    alle schrijfbare velden van de bestaande gasten (Google vervangt de hele lijst) en schrijf met If-Match op de etag,
    zodat een wijziging van een collega intussen nooit overschreven wordt (Codex, punt 2). De body draagt alleen
    'attendees'. Bij een 412 lees ik opnieuw en probeer ik nog eens. Geeft het teruggelezen item, of None als de
    afspraak intussen geschrapt is of niet meer voor Mehdi."""
    import urllib.error  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415
    url = f"{agenda.API}/calendars/{urllib.parse.quote(kal, safe='')}/events/{urllib.parse.quote(eid, safe='')}"
    for _ in range(pogingen):
        vers = _google(url, tok)
        if _gast_mehdi(vers):
            return vers
        if vers.get("status") == "cancelled" or not MEHDI_VOORAAN.match(vers.get("summary") or ""):
            return None                 # intussen geschrapt of niet meer voor Mehdi: niets doen (Codex-hertest, punt 8)
        gasten = [{k: v for k, v in g.items() if k in GASTVELDEN} for g in vers.get("attendees") or []]
        body = {"attendees": gasten + [{"email": WERKAGENDA, "responseStatus": "needsAction"}]}
        try:
            return _google(url + "?sendUpdates=none", tok, body, "PATCH", {"If-Match": vers.get("etag") or "*"})
        except urllib.error.HTTPError as e:
            if e.code != 412:
                raise                   # een collega veranderde de afspraak intussen: opnieuw lezen en beoordelen
    raise _BlijftVeranderen(vers)


def _op_werkagenda(ev, tok):
    """Staat de afspraak zichtbaar op Mehdi's werkagenda? Ik zoek ze in de gewone lijst van zijn werkagenda op haar
    iCalUID: een verborgen uitnodiging staat daar niet in (showHiddenInvitations staat standaard uit), een geslaagde
    get op het id bewijst dat niet (Codex, punt 3)."""
    uid = ev.get("iCalUID")
    start = _tijd(ev, "start")
    if not uid or not start:
        return False
    # alle keren van een reeks delen de iCalUID: ik zoek deze ene keer, op haar eigen begin (Codex-hertest, punt 7)
    van = datetime.fromisoformat(start if "T" in start else start + "T00:00:00+00:00")
    q = {"iCalUID": uid, "singleEvents": "true", "showDeleted": "false", "maxResults": "250",
         "timeMin": (van - timedelta(minutes=1)).isoformat(), "timeMax": (van + timedelta(minutes=1)).isoformat()}
    orig = _tijd(ev, "originalStartTime")
    for x in _lijst_alles(WERKAGENDA, q, tok):
        xs, xo = _tijd(x, "start"), _tijd(x, "originalStartTime")
        if x.get("status") == "cancelled" or not xs:
            continue
        if datetime.fromisoformat(xs if "T" in xs else xs + "T00:00:00+00:00") != van:
            continue
        # twee verplaatste keren van dezelfde reeks kunnen op hetzelfde uur vallen: de oorspronkelijke tijd beslist (punt 7)
        if orig and (not xo or datetime.fromisoformat(xo if "T" in xo else xo + "T00:00:00+00:00")
                     != datetime.fromisoformat(orig if "T" in orig else orig + "T00:00:00+00:00")):
            continue
        return True
    return False


def firma_gasten(evs, tok, onleesbaar=()):
    """Z2: elke komende keer op een firma-agenda met 'Mehdi: ...' vooraan krijgt Mehdi als stille gast, en ik lees na
    dat ze zichtbaar op zijn werkagenda staat. Alleen keren, nooit de moederreeks: zo kan een keer van een collega,
    ook buiten het leesvenster, nooit mee (Codex-hertest 3, punt 11); een keer die later in het venster komt, krijgt de
    gast in een latere ronde. Een afspraak waar Mehdi al gast is, welke titel ook en niet afgewezen, krijgt dezelfde
    zichtbaarheidscontrole (punt 14). Na een fout lees ik de afspraak opnieuw en beslist alleen wat er nu staat: het
    vangnet krijgt nooit een oude tijd (Codex-hertest 5, punt 1). Geeft (regels, niet_zichtbaar, onzeker, opnieuw):
    onzeker zijn de sleutels die niet te beoordelen waren (het vangnet laat die staan), opnieuw is waar als een
    afspraak tijdens de controle verdween (een collega verzette de reeks): dan leest firma_stap de agenda opnieuw."""
    regels, niet_zichtbaar, opnieuw = [], [], False
    evs, onzeker, twijfel = _firma_kopieen_kiezen(evs, onleesbaar)
    onzeker |= set(twijfel)             # een gastkopie zonder organisator: geen gast en geen blok (het vangnet vraagt)
    gezien = set()
    for ev in evs:
        voor_mehdi = bool(MEHDI_VOORAAN.match(ev.get("summary") or ""))
        status = _gast_status(ev)
        if status == "declined" or (not voor_mehdi and status is None):
            continue
        if _firma_uid(ev) in gezien:
            continue                    # dezelfde afspraak op een tweede firma-agenda (een gastkopie): een keer (review)
        gezien.add(_firma_uid(ev))
        vers_gezet = False
        try:
            if status is None:
                terug = _gast_erbij(ev["kalender"], ev["id"], tok)
                if terug is None:
                    regels.append(f"afspraak op {ev['_agendanaam']} intussen geschrapt of niet meer voor Mehdi")
                    continue
                if not _gast_mehdi(terug):
                    raise RuntimeError("gast niet teruggelezen")
                if _gast_status(terug) == "declined":
                    continue            # intussen door Mehdi zelf afgewezen: niets te tonen
                # de teruggelezen afspraak beslist: een collega kan intussen het uur verzet hebben (Codex-hertest 4, punt 1)
                ev = {**ev, **{k: v for k, v in _naar_brussel(terug, _KAL_TZ.get(ev["kalender"])).items()
                               if k in ("summary", "start", "end", "description", "originalStartTime", "iCalUID",
                                        "_tijd_onzeker")}}
                regels.append(f"{_tijd(ev, 'start')[:16]} gast gezet op {ev['_agendanaam']}")
                vers_gezet = True
            if not _op_werkagenda(ev, tok):
                if vers_gezet:
                    # net gezet: Google kan de kopie op de werkagenda even later tonen. Pas de volgende ronde, met Mehdi
                    # al als gast, beslist of ze verborgen blijft; zo komt er geen blok voor een paar seconden (review)
                    onzeker.add(_firma_sleutel(ev))
                else:
                    uitslag = _firma_beoordelen(ev, tok)    # vlak voor het blok: alleen wat er nu staat (hertest 6, 2)
                    if uitslag[0] == "blok":
                        niet_zichtbaar.append(uitslag[1])
                    elif uitslag[0] == "onzeker":
                        onzeker.add(_firma_sleutel(ev))
                    elif uitslag[0] == "weg":
                        opnieuw = True
        except Exception as e:  # noqa: BLE001
            regels.append(f"gast niet gezet op {ev.get('_agendanaam')} ("
                          + ("de afspraak bleef veranderen" if isinstance(e, _BlijftVeranderen) else type(e).__name__) + ")")
            uitslag = _firma_beoordelen(ev, tok)
            if uitslag[0] == "blok":
                niet_zichtbaar.append(uitslag[1])
            elif uitslag[0] == "onzeker":
                onzeker.add(_firma_sleutel(ev))
            elif uitslag[0] == "weg":
                opnieuw = True          # verdwenen of geschrapt: de agenda opnieuw lezen, de nieuwe keren tellen
    return regels, niet_zichtbaar, onzeker, opnieuw


def _utc(t):
    """Een tijd als UTC-tekst, zodat twee agenda's in een andere tijdzone (Suriname, Brussel) dezelfde keer geven."""
    if "T" not in (t or ""):
        return t or ""
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%MZ")
    except ValueError:
        return t


def _firma_sleutel(e):
    """De identiteit van een firma-afspraak, voor ontdubbeling, register en blok: haar iCalUID en, bij een keer van een
    reeks, de oorspronkelijke tijd in UTC. Niet de agenda en niet het Google-id: dat is alleen binnen een agenda uniek,
    en een kopie op een tweede firma-agenda kan een ander id hebben (Codex-hertest 9 en 10). Een verschoven afspraak
    houdt zo haar sleutel, en elke leesbare kopie werkt hetzelfde blok bij."""
    return f"firma|{e.get('iCalUID') or e.get('id')}|{_utc(_tijd(e, 'originalStartTime'))}"


def _firma_kopieen_kiezen(evs, onleesbaar=()):
    """Een afspraak kan op twee firma-agenda's staan (de ene nodigt de andere uit), of alleen als gastkopie (de
    organisator is iemand anders). Alleen de kopie op de agenda van de organisator bepaalt het uur: een gast kan de tijd
    op zijn eigen kopie wijzigen (Codex-hertest 11 tot 13). Geeft (gekozen, onzeker, twijfel):
    - gekozen: de kopie van de organisator, die gewoon verwerkt wordt;
    - onzeker: de organisator is een firma-agenda die nu niet te lezen is; er verandert niets (die nood bestaat al);
    - twijfel: geen kopie van de organisator te lezen; geen gast en geen Bezet blok, wel een zichtbare vraag dat het
      uur niet zeker is ({sleutel: kopieën})."""
    stuk = {a.lower() for a in onleesbaar or ()}
    groepen = {}
    for e in evs or []:
        groepen.setdefault(_firma_sleutel(e), []).append(e)
    gekozen, onzeker, twijfel = [], set(), {}
    eigen = {a.lower() for a in KALENDERS} | _eigen_accounts()
    for k, kopieen in groepen.items():
        if {((e.get("organizer") or {}).get("email") or "").lower() for e in kopieen} & eigen:
            continue                    # Mehdi's eigen afspraak met een firma-agenda als gast: staat al bij hem (review 2)
        org = [e for e in kopieen if ((e.get("organizer") or {}).get("email") or "").lower() == (e.get("kalender") or "").lower()
               and not e.get("_tijd_onzeker")]
        if org:
            gekozen.append(org[0])      # een zekere kopie van de organisator beslist altijd (Codex-hertest 18)
        elif {((e.get("organizer") or {}).get("email") or "").lower() for e in kopieen} & stuk:
            onzeker.add(k)              # organisator onleesbaar: niets veranderen, ook een bestaand blok niet (hertest 23)
        elif any(e.get("_tijd_onzeker") for e in kopieen):
            twijfel[k] = kopieen        # tijdzone onbekend: nooit een blok op een gok (Codex-hertest 17)
        else:
            twijfel[k] = kopieen
    return gekozen, onzeker, twijfel


def _firma_uid(e):
    """Dezelfde afspraak op twee firma-agenda's (de ene nodigt de andere uit): dezelfde sleutel."""
    return _firma_sleutel(e)


_FIRMA_ADRESSEN = None
_FIRMA_UIDS = None          # iCalUID's van de firma-agenda's, eenmaal per proces gelezen; False als dat niet lukte


def _firma_uids():
    """De iCalUID's van alle afspraken op de firma-agenda's (een jaar vooruit, een dag terug), eenmaal per proces.
    False als een firma-agenda niet te lezen was: dan weet ik niet welke kopie van een collega is."""
    global _FIRMA_UIDS
    if _FIRMA_UIDS is None:
        try:
            tok = agenda._toegang()
            # een dag terug tot twee dagen voorbij het rittenvenster (verre_afspraken): Google laat weg wat op of na
            # timeMax begint, en het grensuur mag niet ontbreken (Codex-hertest 8)
            evs, onleesbaar = firma_afspraken(tok, nu_lokaal() - timedelta(days=1), FIRMA_VOORUIT_DAGEN + 3)
            _FIRMA_UIDS = False if onleesbaar else {e.get("iCalUID") for e in evs if e.get("iCalUID")}
        except Exception:  # noqa: BLE001
            _FIRMA_UIDS = False
    return _FIRMA_UIDS


def _firma_kopie(a):
    """Is dit item op Mehdi's werkagenda de gastkopie van een afspraak op een firma-agenda? Daarop schrijft de agent
    niets: geen telefoon, kleur, herinnering, titel of vraag. Het is de afspraak van een collega (review en
    Codex-hertest 6, 27-10-2026). Herkend aan de organisator (de firma-agenda) of aan dezelfde afspraak (iCalUID) op een
    firma-agenda, ook als een collega de organisator is (Codex-hertest 7). Een eigen afspraak van Mehdi, met een
    firma-agenda als gast, blijft van hem. Is een firma-agenda niet te lezen, dan telt elke afspraak die Mehdi niet zelf
    organiseerde als kopie: liever een ronde geen kleur dan een schrijfactie op andermans afspraak. Een rit ernaartoe
    is wel van Mehdi en staat apart."""
    global _FIRMA_ADRESSEN
    if a.get("_organisator_zelf") is True or "_organisator" not in a:
        return False                    # van Mehdi zelf, of een eigen hulpblok zonder Google-organisator
    if _FIRMA_ADRESSEN is None:
        _FIRMA_ADRESSEN = {adres.strip().lower() for adres, _ in firma_meelezen()}
    if (a.get("_organisator") or "").strip().lower() in _FIRMA_ADRESSEN:
        return True
    uids = _firma_uids()
    if uids is False:
        return True
    return bool(a.get("_ical")) and a["_ical"] in uids


def _firma_beoordelen(ev, tok):
    """Lees de afspraak opnieuw en beslis op wat er nu staat, vlak voor een blok (Codex-hertest 5 en 6):
    ('blok', actueel), ('weg', None), ('onzeker', None) of ('niets', None)."""
    nu_ev = _firma_actueel(ev, tok)
    if nu_ev is None:
        return "onzeker", None
    if nu_ev is False:
        return "weg", None
    st = _gast_status(nu_ev)
    if st is None:                      # geen gast: dan staat ze zeker niet op zijn werkagenda
        return ("blok", nu_ev) if MEHDI_VOORAAN.match(nu_ev.get("summary") or "") else ("niets", None)
    if st == "declined":
        return "niets", None
    try:
        return ("niets", None) if _op_werkagenda(nu_ev, tok) else ("blok", nu_ev)
    except Exception:  # noqa: BLE001
        return "onzeker", None          # werkagenda niet te lezen: niets veranderen (review)


def _firma_actueel(ev, tok):
    """De afspraak zoals ze nu op de firma-agenda staat (met 'kalender' en agendanaam), False als ze weg of geschrapt
    is, None als ze niet te lezen is."""
    import urllib.error  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415
    try:
        x = _google(f"{agenda.API}/calendars/{urllib.parse.quote(ev['kalender'], safe='')}/events/"
                    f"{urllib.parse.quote(ev['id'], safe='')}", tok)
    except urllib.error.HTTPError as e:
        return False if e.code in (404, 410) else None
    except Exception:  # noqa: BLE001
        return None
    if x.get("status") == "cancelled":
        return False
    return {**_naar_brussel(x, _KAL_TZ.get(ev["kalender"])), "kalender": ev["kalender"], "_agendanaam": ev.get("_agendanaam")}


def _prive_vraag_id(k, tok):
    """Het id van een open vraag met dit firmamerk in de privé-agenda, of ''. Zo zet een ronde na een time-out geen
    tweede (punt 5); een opgeloste vraag telt niet, die houdt een nieuwe niet tegen (Codex-hertest 3, punt 13)."""
    q = {"privateExtendedProperty": f"{FIRMAMERK}={k}", "showDeleted": "false", "maxResults": "50"}
    for x in _lijst_alles(PRIVE_AGENDA, q, tok):        # alle pagina's (Codex-hertest, punt 9)
        merk = ((x.get("extendedProperties") or {}).get("private") or {})
        if x.get("status") != "cancelled" and not str(merk.get(MAILMERK, "")).startswith("opgelost:"):
            return x.get("id") or ""
    return ""


def _firma_vragen_lezen():
    try:
        with open(FIRMA_VRAGEN, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _tz_bekend(t):
    """Heeft deze tijd een offset (of is het een hele dag)?"""
    if "T" not in (t or ""):
        return True
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _firma_vraag_body(k, e, start, sterk):
    """De vraag in de privé-agenda. Een afspraak voor Mehdi die niet doorkwam (sterk) wordt een Bezet blok op haar eigen
    tijd, zodat Calendly er niet over boekt (Codex-hertest 2, punt 10): op haar uur, of over haar hele dag(en) als ze
    geen uur heeft (hertest 3, punt 10). Een afspraak die Mehdi alleen noemt: een vraag voor de hele dag op Beschikbaar."""
    dag = start[:10]
    eind = _tijd(e, "end")
    volgende = (datetime.fromisoformat(dag) + timedelta(days=1)).date().isoformat()
    merk = {"private": {MAILMERK: hashlib.sha256(f"firma:{k}".encode()).hexdigest()[:16], FIRMAMERK: k}}
    if sterk is None:
        # twijfel: alleen gastkopieën, het uur van de organisator is niet te lezen (Codex-hertest 13)
        waar = "; ".join(f"op {n}: {_ddmm((t or '')[:10])}" + (f" om {t[11:16]}" if "T" in (t or "") else " (hele dag)")
                         for n, t, _ in e.get("_kopieen") or [])
        org = (e.get("organizer") or {}).get("email") or "de organisator"
        tekst = (f"Agendawacht vraagt: '{(e.get('summary') or '')[:80]}' staat {waar}, maar de agenda van de organisator "
                 f"({org}) kan ik niet lezen. Het uur is dus niet zeker; ik zet er geen blok voor. Kijk het na bij de "
                 "organisator.")
        laatste = (eind or start)[:10]
        tot = laatste if "T" not in eind and laatste > dag else \
            (datetime.fromisoformat(laatste) + timedelta(days=1)).date().isoformat()
        if e.get("_tijd_onzeker") or any(not _tz_bekend(t) for _, t, _ in e.get("_kopieen") or []):
            # tijdzone onbekend: de echte Brusselse dag kan een dag vroeger of later zijn; de vraag dekt ze (hertest 20)
            dag = (datetime.fromisoformat(dag) - timedelta(days=1)).date().isoformat()
            tot = max(tot, (datetime.fromisoformat(laatste) + timedelta(days=2)).date().isoformat())
        return {"summary": f"VR Agendawacht: firma-afspraak voor jou, uur niet zeker ({_ddmm(dag)})"[:200],
                "start": {"date": dag}, "end": {"date": max(tot, volgende)}, "transparency": "transparent",
                "reminders": {"useDefault": False, "overrides": []}, "description": tekst, "extendedProperties": merk}
    tekst = (f"Agendawacht vraagt: op de agenda {e.get('_agendanaam')} staat '{(e.get('summary') or '')[:80]}' op "
             f"{_ddmm(dag)}{(' om ' + start[11:16]) if 'T' in start else ''}, en die "
             + ("is voor jou maar komt niet op je werkagenda (instelling van Google). Dit blok houdt de tijd bezet tot het "
                "opgelost is." if sterk else "lijkt jou aan te gaan, maar ze staat niet op je werkagenda. Moet jij erbij zijn? "
                "Zeg het, dan komt ze erop; anders laat je deze vraag weg."))
    if sterk and "T" in start and "T" in eind:
        tijd = {"start": {"dateTime": start}, "end": {"dateTime": eind}, "location": e.get("location") or "",
                # een eigen herinnering: ook in het weekend, voor de volledige ronde een oproep plant (Codex-hertest 24)
                "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 15}]}}
    elif sterk:
        tijd = {"start": {"date": dag}, "end": {"date": eind[:10] if eind[:10] > dag else volgende}}
    else:
        tijd = {"start": {"date": dag}, "end": {"date": volgende}}
    titel = ("VR Agendawacht: firma-afspraak voor jou, niet op je werkagenda" if sterk
             else "VR Agendawacht: firma-afspraak die jou lijkt aan te gaan")
    return {"summary": f"{titel} ({_ddmm(dag)})"[:200], "reminders": {"useDefault": False, "overrides": []}, **tijd,
            "transparency": "opaque" if sterk else "transparent", "description": tekst, "extendedProperties": merk}


def _einde_voorbij(t, nu):
    """Is dit einde voorbij? Een datum (hele dag) telt exclusief, zoals bij Google; leeg telt niet als voorbij. Een
    eigen naam: _voorbij() verderop gaat over een begin en telt leeg als voorbij."""
    if not t:
        return False
    if "T" not in t:
        return t[:10] <= nu.date().isoformat()
    try:
        return datetime.fromisoformat(t) <= nu
    except (TypeError, ValueError):
        return False


def _tijd_patch(t):
    """Een begin of einde voor een PATCH: Google voegt velden samen, dus het andere soort tijd wordt expliciet leeg."""
    return {"date": t["date"], "dateTime": None} if "date" in t else {"dateTime": t["dateTime"], "date": None}


def _firma_blok_open(x, k):
    """Is dit privé-item mijn open vraag voor deze firma-afspraak? Herkend aan merk en maker, niet aan de titel: Mehdi
    mag het blok hernoemen, het blijft het blok van die afspraak (review 2)."""
    mk = (x or {}).get("_merk") or {}
    return (x is not None and mk.get(FIRMAMERK) == k and not str(mk.get(MAILMERK, "")).startswith("opgelost:")
            and (x.get("maker") or WERKAGENDA).strip().lower() in _eigen_accounts())


def _firma_blok_bijzetten(x, k, e, start, sterk, tok):
    """Zet mijn eigen blok op de huidige tijd, soort en plaats van zijn afspraak (zelfde item, zelfde merk). Hernoemde
    Mehdi het, dan blijven zijn titel en tekst staan en verandert alleen de tijd, de status en de plaats."""
    body = _firma_vraag_body(k, e, start, sterk)
    nieuw = {"transparency": body["transparency"], "start": _tijd_patch(body["start"]), "end": _tijd_patch(body["end"]),
             "location": body.get("location", "")}
    if (x.get("titel") or "").startswith("VR Agendawacht:"):
        nieuw.update(summary=body["summary"], description=body["description"])
    _patch(x, nieuw, tok)


def _firma_tweede_afwijking(k, r, e, start, tok):
    """Het Bezet blok verdween of verschoof opnieuw na mijn herstel: ik zet het niet nog eens (Mehdi beslist), maar ik
    leg het hem een keer zichtbaar voor, als vraag op Beschikbaar in zijn privé-agenda (Codex-hertest 23)."""
    if r.get("tweede_gemeld"):
        return ""
    dag = start[:10]
    volgende = (datetime.fromisoformat(dag) + timedelta(days=1)).date().isoformat()
    body = {"summary": f"VR Agendawacht: Bezet blok voor een firma-afspraak weg ({_ddmm(dag)})"[:200],
            "start": {"date": dag}, "end": {"date": volgende}, "transparency": "transparent",
            "reminders": {"useDefault": False, "overrides": []},
            "description": (f"Agendawacht vraagt: '{(e.get('summary') or '')[:80]}' staat nog op {e.get('_agendanaam')} op "
                            f"{_ddmm(dag)}{(' om ' + start[11:16]) if 'T' in start else ''}. Het Bezet blok ervoor is weer weg of "
                            "verzet; ik zet het niet opnieuw. Calendly kan dat uur nu boeken. Klopt dat? Anders zet je het blok "
                            "terug of laat je het me weten."),
            "extendedProperties": {"private": {MAILMERK: hashlib.sha256(f"firma-weg:{k}".encode()).hexdigest()[:16],
                                               FIRMAMERK: f"{k}|weg"}}}
    _insert(PRIVE_AGENDA, body, tok)
    r["tweede_gemeld"] = True
    return f"{dag} Bezet blok voor een firma-afspraak opnieuw weg of verzet: Mehdi een keer gevraagd"


def _firma_blok_nakijken(k, r, g, tok):
    """De afspraak veranderde niet, maar staat mijn Bezet blok er nog zoals het hoort? Verdwenen, verschoven of op
    Beschikbaar gezet: een keer herstellen, zodat Calendly niet over de verborgen afspraak boekt (Codex-hertest 22). Ik
    blijf het nakijken: gebeurt het opnieuw, dan zet ik het niet nog eens maar vraag ik het Mehdi een keer zichtbaar
    (hertest 23). Werkt r bij en geeft een regel, of ''."""
    e, sterk, start, einde, _ = g
    import urllib.parse  # noqa: PLC0415
    x = _prive_item_lezen(r["id"], tok) if r.get("id") else None    # None: echt weg; een leesfout gooit (dan niets doen)
    if x is None:
        if r.get("hersteld"):
            return _firma_tweede_afwijking(k, r, e, start, tok)
        n = _insert(PRIVE_AGENDA, _firma_vraag_body(k, e, start, sterk), tok) or {}
        r.update(id=n.get("id", ""), hersteld=True)
        return f"{start[:10]} Bezet blok voor een firma-afspraak was weg: een keer opnieuw gezet"
    mk = x.get("_merk") or {}
    if mk.get(FIRMAMERK) != k or str(mk.get(MAILMERK, "")).startswith("opgelost:") or not _firma_blok_open(x, k):
        return ""                       # door Mehdi afgerond of niet meer van mij: niets doen
    raw = _google(f"{agenda.API}/calendars/{urllib.parse.quote(PRIVE_AGENDA, safe='')}/events/"
                  f"{urllib.parse.quote(r['id'], safe='')}?fields=transparency", tok)
    goed = (_utc(x.get("start")) == _utc(start) and _utc(x.get("einde")) == _utc(einde)
            and raw.get("transparency", "opaque") != "transparent")
    if goed:
        return ""
    if r.get("hersteld"):
        return _firma_tweede_afwijking(k, r, e, start, tok)
    _firma_blok_bijzetten(x, k, e, start, sterk, tok)
    r["hersteld"] = True
    return f"{start[:10]} Bezet blok voor een firma-afspraak was verschoven of Beschikbaar: een keer hersteld"


def firma_vangnet(evs, niet_zichtbaar, tok, nu=None, onleesbaar=(), onzeker=()):
    """Z3: wat op een firma-agenda Mehdi aangaat maar niet op zijn werkagenda staat, wordt eenmaal een vraag in de
    privé-agenda: een afspraak voor Mehdi die niet doorkwam (een Bezet blok, tot FIRMA_VOORUIT_DAGEN vooruit), of een
    afspraak die Mehdi in titel of omschrijving noemt zonder hem als gast (de komende FIRMA_VANGNET_DAGEN). Het blok
    volgt zijn afspraak: verschuift die (begin of einde), dan schuift het blok mee; verdwijnt ze of komt ze nu wel door,
    dan 'Opgelost' en Beschikbaar (Codex-hertest 3, punt 13). Van een onleesbare agenda blijft alles staan (punt 17)."""
    nu = nu or nu_lokaal()
    vandaag = nu.date().isoformat()
    zwak_grens = (nu + timedelta(days=FIRMA_VANGNET_DAGEN)).isoformat()
    reg = _firma_vragen_lezen()
    kand, gezien = {}, set()
    for e in niet_zichtbaar:
        if _firma_uid(e) not in gezien:   # dezelfde afspraak op twee firma-agenda's: een blok (review 27-10-2026)
            gezien.add(_firma_uid(e))
            if e.get("_tijd_onzeker"):
                # bij het herlezen bleek de tijd onzeker (geen offset, geen tijdzone): de vraag, nooit een blok (hertest 19)
                lijst = [(e.get("_agendanaam"), _tijd(e, "start"), _tijd(e, "end"))]
                kand[_firma_sleutel(e)] = (dict(e, _kopieen=lijst, _alleen_noemt=False,
                                                _vinger=hashlib.sha256(json.dumps(lijst).encode()).hexdigest()[:12]), None)
            else:
                kand[_firma_sleutel(e)] = (e, True)
    gekozen, onz2, twijfel = _firma_kopieen_kiezen(evs, onleesbaar)
    onzeker = (set(onzeker) | onz2) - set(twijfel)
    for k, kopieen in twijfel.items():
        # geen kopie van de organisator: een zichtbare vraag, nooit een blok op een uur dat niet zeker is (hertest 13).
        # Afgewezen: niets. Is Mehdi gast en staat zijn eigen uitnodiging (met het uur van de organisator) zichtbaar op
        # zijn werkagenda, dan is er niets te vragen (review 2); een leesfout: onzeker
        if any(_gast_status(e) == "declined" for e in kopieen):
            continue
        gast = [e for e in kopieen if _gast_status(e) is not None and not e.get("_tijd_onzeker")]
        if gast:                        # met een onzekere tijd kan ik niet zoeken: dan meteen de vraag (hertest 18)
            try:
                if _op_werkagenda(gast[0], tok):
                    continue
            except Exception:  # noqa: BLE001
                onzeker.add(k)
                continue
        voor = any(MEHDI_VOORAAN.match(e.get("summary") or "") or _gast_status(e) not in (None, "declined") for e in kopieen)
        noemt = any(re.search(r"\bMehdi\b", f"{e.get('summary') or ''} {e.get('description') or ''}", re.I) for e in kopieen)
        if voor or noemt:
            # de vraag dekt elke mogelijke datum, van de vroegste tot de laatste kopie, en noemt per kopie datum en uur;
            # verandert een kopie, dan verandert haar vingerafdruk en wordt de vraag bijgewerkt (Codex-hertest 14)
            kop = sorted(kopieen, key=lambda c: _utc(_tijd(c, "start")))
            laatste = max(kopieen, key=lambda c: _utc(_tijd(c, "end")) or _tijd(c, "end"))
            lijst = [(c.get("_agendanaam"), _tijd(c, "start"), _tijd(c, "end")) for c in kop]
            e = dict(kop[0], start=kop[0].get("start"), end=laatste.get("end"), _kopieen=lijst, _alleen_noemt=not voor,
                     _vinger=hashlib.sha256(json.dumps(lijst).encode()).hexdigest()[:12])
            kand[k] = (e, None)
    for e in gekozen:
        tekst = f"{e.get('summary') or ''} {e.get('description') or ''}"
        if re.search(r"\bMehdi\b", tekst, re.I) and not MEHDI_VOORAAN.match(e.get("summary") or "") and not _gast_mehdi(e) \
                and _firma_uid(e) not in gezien:
            gezien.add(_firma_uid(e))
            kand[_firma_sleutel(e)] = (e, False)
    gewenst = {}
    for k, (e, sterk) in kand.items():
        start = _tijd(e, "start")
        # een afspraak die al begon maar nog loopt (meerdaags), telt nog mee (Codex-hertest 4, punt 2)
        zwak = sterk is False or (sterk is None and e.get("_alleen_noemt"))
        if not start or _einde_voorbij(_tijd(e, "end"), nu) or (zwak and start > zwak_grens):
            continue
        # een Bezet blok volgt ook de plaats van zijn afspraak: een nieuw adres werkt het blok bij (Codex-hertest 21)
        vinger = e.get("_vinger") or (hashlib.sha256((e.get("location") or "").encode()).hexdigest()[:12]
                                      if sterk and (e.get("location") or "") else "")
        gewenst[k] = (e, sterk, start, _tijd(e, "end"), vinger)
    regels, gewijzigd = [], False
    gelezen = {_firma_sleutel(e) for e in evs or []}
    for k, r in list(reg.items()):
        g = gewenst.get(k)
        # een onleesbare agenda houdt alleen tegen wat geen leesbare kopie heeft: een leesbare kopie beslist (hertest 10)
        if k in onzeker or (not g and r.get("kalender") in onleesbaar and k not in gelezen):
            continue                    # een halve lezing rondt niets af en verschuift niets (Codex-hertest 3, punt 17)
        # schuift de afspraak naar later, dan volgt het blok meteen, ook als het oude uur al voorbij is (hertest 5, 2)
        if not g and (_einde_voorbij(r.get("einde"), nu) or (not r.get("einde") and r.get("dag", "") < vandaag)):
            reg.pop(k)                  # de afspraak is helemaal voorbij: alleen uit het register (Codex-hertest 4, punt 2)
            gewijzigd = True
            continue
        if g and (g[1], g[2], g[3], g[4]) == (r.get("sterk"), r.get("start"), r.get("einde"), r.get("vinger", "")):
            if g[1] is True:
                try:
                    regel = _firma_blok_nakijken(k, r, g, tok)
                    if regel:
                        regels.append(regel)
                        gewijzigd = True
                except Exception as ex:  # noqa: BLE001
                    regels.append(f"{r.get('dag')} Bezet blok niet nagekeken ({type(ex).__name__})")
            continue
        try:
            x = _prive_item_lezen(r["id"], tok) if r.get("id") else None
            mk = (x or {}).get("_merk") or {}
            open_ = _firma_blok_open(x, k)
            if g and open_:
                e, sterk, start, einde, vinger = g
                _firma_blok_bijzetten(x, k, e, start, sterk, tok)
                reg[k] = {**r, "dag": start[:10], "start": start, "einde": einde, "sterk": sterk, "kalender": e["kalender"],
                          "vinger": vinger}
                regels.append(f"{start[:10]} vraag over een firma-afspraak mee verschoven met de afspraak")
            else:
                if open_ and not (x.get("titel") or "").startswith("VR Agendawacht:"):
                    # hernoemd door Mehdi: zijn titel blijft, het blok wordt opgelost, Beschikbaar en een hele dag
                    d0 = (x.get("start") or "")[:10]
                    d1 = (datetime.fromisoformat(d0) + timedelta(days=1)).date().isoformat() if d0 else d0
                    _patch(x, {"extendedProperties": {"private": {**mk, MAILMERK: f"opgelost:{mk.get(MAILMERK)}"}},
                               "transparency": "transparent",
                               **({"start": _tijd_patch({"date": d0}), "end": _tijd_patch({"date": d1})} if d0 else {})}, tok)
                    regels.append(f"{r.get('dag')} hernoemd blok voor een firma-afspraak opgelost en Beschikbaar gezet")
                elif open_:
                    _eigen_melding_opgelost(x, mk.get(MAILMERK), tok, nu,
                                            "de firma-afspraak verdween of staat nu op je werkagenda", vrij=True)
                    if not x.get("hele_dag") and "T" in (x.get("start") or ""):
                        # een opgelost blok met een uur kreeg anders nog een oproep (belrooster) en telde als botsing
                        d0 = x["start"][:10]
                        d1 = (datetime.fromisoformat(d0) + timedelta(days=1)).date().isoformat()
                        _patch(x, {"start": _tijd_patch({"date": d0}), "end": _tijd_patch({"date": d1})}, tok)
                    regels.append(f"{r.get('dag')} vraag over een firma-afspraak op opgelost en Beschikbaar gezet")
                reg.pop(k)              # weg of al afgerond: staat de afspraak er nog, dan volgt hieronder een nieuwe vraag
            gewijzigd = True
        except Exception as ex:  # noqa: BLE001
            regels.append(f"{r.get('dag')} vraag niet bijgewerkt ({type(ex).__name__})")
    for k, (e, sterk, start, einde, vinger) in gewenst.items():
        if k in reg or k in onzeker:
            continue
        dag = start[:10]
        try:
            bestaand = _prive_vraag_id(k, tok)
            x = _prive_item_lezen(bestaand, tok) if bestaand else None
            if bestaand and _firma_blok_open(x, k):
                # de vraag stond er al (na een time-out of een opgeruimd register): meteen op de juiste tijd (hertest 5, 2)
                _firma_blok_bijzetten(x, k, e, start, sterk, tok)
                reg[k] = {"gevraagd": vandaag, "dag": dag, "start": start, "einde": einde, "sterk": sterk, "id": bestaand,
                          "kalender": e["kalender"], "vinger": vinger}
                regels.append(f"{dag} bestaande vraag over een firma-afspraak op de juiste tijd gezet")
            elif bestaand:
                # niet terug te lezen: opnemen zonder tijd, zodat de volgende ronde het blok bijzet en er geen tweede komt
                reg[k] = {"gevraagd": vandaag, "dag": dag, "start": "", "einde": "", "sterk": sterk, "id": bestaand,
                          "kalender": e["kalender"]}
            else:
                n = _insert(PRIVE_AGENDA, _firma_vraag_body(k, e, start, sterk), tok) or {}
                reg[k] = {"gevraagd": vandaag, "dag": dag, "start": start, "einde": einde, "sterk": sterk,
                          "id": n.get("id", ""), "kalender": e["kalender"], "vinger": vinger}
                regels.append(f"{dag} vraag gezet: firma-afspraak " + ("voor Mehdi die niet doorkwam" if sterk else
                                                                     "met een uur dat niet zeker is" if sterk is None
                                                                     else "die Mehdi noemt"))
            gewijzigd = True
        except Exception as ex:  # noqa: BLE001
            regels.append(f"{dag} vraag niet gezet ({type(ex).__name__})")
    if gewijzigd:
        os.makedirs(os.path.dirname(FIRMA_VRAGEN), exist_ok=True)
        tmp = f"{FIRMA_VRAGEN}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=0)
        os.replace(tmp, FIRMA_VRAGEN)
    return regels


def firma_stap(vandaag):
    """De firma-stap (Z1 tot Z3): in de volledige ronde en in de kleurronde (om :17 en :47, elke dag, ook in het
    weekend), zodat een nieuwe afspraak geen werkdag wacht (Codex-hertest 3, punt 15). Een eigen slot: nooit twee
    tegelijk. Geeft noden met een vaste tekst, zonder teller (N10)."""
    import fcntl  # noqa: PLC0415
    noden = []
    try:
        verborgen = verborgen_schrijfagendas(agenda.zichtbaarheid())
    except Exception as e:  # noqa: BLE001
        verborgen = []
        noden.append({"tekst": f"Zichtbaarheid van de agenda's niet te lezen ({type(e).__name__})", "wie": "claude"})
    if verborgen:
        noden.append({"tekst": "Verborgen in je Google Agenda, maar de Agendawacht zet daar ritten: "
                               + ", ".join(verborgen) + ". Zet het vinkje terug.", "wie": "mehdi"})
    if not firma_meelezen():
        return noden
    os.makedirs(os.path.dirname(FIRMA_SLOT), exist_ok=True)
    with open(FIRMA_SLOT, "w", encoding="utf-8") as slot:
        try:
            fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return noden                # een andere ronde is er al mee bezig
        tok = agenda._toegang()
        evs, onleesbaar = firma_afspraken(tok)
        gregels, niet_zichtbaar, onzeker, opnieuw = firma_gasten(evs, tok, onleesbaar)
        if opnieuw:                     # een collega verzette een reeks tijdens de controle: de nieuwe keren lezen (hertest 5)
            evs, onleesbaar = firma_afspraken(tok)
            g2, niet_zichtbaar, onzeker, _ = firma_gasten(evs, tok, onleesbaar)
            gregels += g2
        vregels = firma_vangnet(evs, niet_zichtbaar, tok, onleesbaar=onleesbaar, onzeker=onzeker)
    global FIRMA_BLOK_VERANDERD
    FIRMA_BLOK_VERANDERD = any(("voor Mehdi die niet doorkwam" in r or "mee verschoven" in r or "opnieuw gezet" in r
                                or "hersteld" in r) for r in vregels)
    if gregels or vregels:
        ag.log(f"dag {vandaag}", "schrijf", "firma-agenda's: Mehdi als stille gast waar het hem aangaat",
               "\n".join(gregels + vregels))
    namen = dict(firma_meelezen())
    if onleesbaar:
        noden.append({"tekst": "Firma-agenda niet te lezen: " + ", ".join(namen.get(a, a) for a in onleesbaar)
                               + "; afspraken voor Mehdi daarin niet nagekeken", "wie": "claude"})
    if any("niet gezet" in r or "niet bijgewerkt" in r for r in gregels + vregels):
        noden.append({"tekst": "Een gast of vraag voor een firma-afspraak is niet gezet; zie het werkverslag", "wie": "claude"})
    return noden


# Zorgafspraken uit mail ('Opdracht voor Claude - kine en tandarts in de privéagenda' v1.0, 14-10-2026). Een smalle
# uitzondering op 'uit mail zet ik niets': een bevestigde afspraak voor Mehdi bij een beheerde persoonlijke zorgpraktijk
# (profielen in het privéregister, nooit in git) wordt een echt blok in de privé-agenda: begin en einde uit de mail,
# Bezet, de gewone herinnering voor buiten en daarna de gewone ritten. Het is een bestaand consult overnemen, geen nieuwe
# boeking bij de praktijk: geen gasten, geen mail, niets verstuurd. Wat al in een agenda staat, wordt gekoppeld (geen
# tweede item); een kine- of tandartsitem op de werkagenda verhuist naar privé met behoud van zijn Google-ID. Een
# onbekende eindtijd, een andere patiënt of een onzekere wijziging blijft een open punt. Voorbij wordt nooit
# teruggeboekt. Niets wordt gewist.
ZORGMERK = "agendawacht_zorg"
ZORGPLAATSMERK = "agendawacht_zorgplaats"
ZORGPLAATSZIN = "Adres uit het geverifieerde zorgprofiel (Agendawacht, {dag})"
ZORG_SCHADUW_IDS = set()  # alleen voor deze ronde; op een collega-item wordt niets geschreven


class SchaduwItem(PermissionError):
    """Een dubbel werkitem mag door geen schrijfroute worden aangepast of verhuisd."""


def is_zorgschaduw(a):
    return bool(a.get("_zorg_schaduw") or (a.get("kalender"), a.get("id")) in ZORG_SCHADUW_IDS)


def _zorg_soort_titel(titel):
    t = titel or ""
    if re.search(r"\bkine\b|kinesi|kinésit", t, re.I):
        return "kine"
    if re.search(r"tandarts|mondhygi|dentist", t, re.I):
        return "tandarts"
    return "huisarts" if re.search(r"\bhuisarts\b", t, re.I) else ""


def _zorg_item_profiel(a, profielen, nu):
    import mail_afspraken as MA  # noqa: PLC0415
    merk = a.get("_merk") or {}
    sleutel = merk.get(ZORGMERK) or ""
    pid = sleutel.split("|", 2)[1] if sleutel.startswith("zorg|") and sleutel.count("|") >= 2 else ""
    pid = pid or (merk.get(ZORGPLAATSMERK) or "").split(":", 1)[0]
    if pid:
        return next((p for p in profielen if p.get("id") == pid), None)
    kandidaten = _zorg_profiel_kandidaten(a, profielen, nu)
    tekst = MA._naam_plat(" ".join(str(a.get(k) or "") for k in ("titel", "omschrijving")))
    bewezen = [p for p in kandidaten if any(
        naam and len(MA._naam_plat(naam)) >= 5 and MA._naam_plat(naam) in tekst
        for naam in [p.get("naam"), *(p.get("praktijknamen") or []), *(p.get("behandelaars") or {})])
        or any(MA.zorg_plaats_gelijk(a.get("locatie"), loc) for loc in
               [p.get("adres"), *(p.get("locaties") or [])])]
    return bewezen[0] if len(bewezen) == 1 else None


def markeer_zorgschaduwen(items, profielen=None, nu=None):
    """Vind een dubbel werkitem bij een gemerkt of door ons verhuisd privé-item. De markering leeft alleen in geheugen."""
    import mail_afspraken as MA  # noqa: PLC0415
    nu = nu or nu_lokaal()
    profielen = MA.zorgprofielen() if profielen is None else profielen
    ZORG_SCHADUW_IDS.clear()
    for x in items:
        x.pop("_zorg_schaduw", None)
    bronnen = [x for x in items if x.get("kalender") == PRIVE_AGENDA and x.get("id")
               and _zorg_soort_titel(x.get("titel")) and
               ((x.get("_merk") or {}).get(ZORGMERK) or (x.get("_merk") or {}).get(ZORGPLAATSMERK)
                or "Van de werkagenda naar privé verhuisd door de Agendawacht" in (x.get("omschrijving") or ""))]
    bronnen.sort(key=lambda x: (0 if (x.get("_merk") or {}).get(ZORGMERK) else
                                1 if (x.get("_merk") or {}).get(ZORGPLAATSMERK) else 2,
                                x.get("start") or "", x["id"]))
    noden, gezien = [], set()
    for prive in bronnen:
        soort = _zorg_soort_titel(prive.get("titel"))
        bronprofiel = _zorg_item_profiel(prive, profielen, nu)
        for werk in items:
            if (werk is prive or is_zorgschaduw(werk) or werk.get("kalender") in PRIVE_KALENDERS or not werk.get("id")
                    or werk.get("hele_dag") or _zorg_soort_titel(werk.get("titel")) != soort
                    or not is_zorg_titel(werk.get("titel"))):
                continue
            try:
                dichtbij = abs((datetime.fromisoformat(werk["start"]) - datetime.fromisoformat(prive["start"])).total_seconds()) <= 900
            except (KeyError, TypeError, ValueError):
                continue
            if not dichtbij:
                continue
            werkprofiel = _zorg_item_profiel(werk, profielen, nu)
            zelfde_profiel = bool(bronprofiel and werkprofiel and bronprofiel["id"] == werkprofiel["id"])
            zelfde_plaats = MA.zorg_plaats_gelijk(prive.get("locatie"), werk.get("locatie"))
            if not (zelfde_profiel or zelfde_plaats):
                continue
            werk["_zorg_schaduw"] = f"{PRIVE_AGENDA}|{prive['id']}"
            ZORG_SCHADUW_IDS.add((werk["kalender"], werk["id"]))
            sleutel = (prive["kalender"], prive["id"])
            if sleutel not in gezien:
                gezien.add(sleutel)
                try:
                    dag = datetime.fromisoformat(prive["start"]).astimezone(TIJDZONE).strftime("%d-%m %H:%M")
                except (KeyError, TypeError, ValueError):
                    continue
                noden.append({"tekst": f"Dubbele zorgafspraak op {dag}: een collega zette ze ook op de werkagenda. "
                                        "Zal ik die verwijderen? (antwoord aan Claude)", "wie": "mehdi"})
    return noden


def _zorg_huisbezoek(a, profielen=None, nu=None):
    woorden = bool(re.search(r"\b(huisbezoek|aan[-\s]+huis|thuis)\b",
                            " ".join(str(a.get(k) or "") for k in ("titel", "omschrijving", "locatie")), re.I))
    return woorden and not _zorg_profiel_nooit_aan_huis(a, profielen, nu)


def _zorg_profielmerk(p):
    adres = " ".join((p.get("adres") or "").casefold().split())
    return f"{p['id']}:{hashlib.sha256(adres.encode()).hexdigest()[:16]}"


def _zorgplaats_merk_klopt(a):
    merk = (a.get("_merk") or {}).get(ZORGPLAATSMERK) or ""
    adres = " ".join((a.get("locatie") or "").casefold().split())
    return bool(merk and adres and merk.rpartition(":")[2] == hashlib.sha256(adres.encode()).hexdigest()[:16])


def _zorg_profiel_kandidaten(a, profielen, nu):
    """Alleen geverifieerde profielen van de zorgsoort en de genoemde patiënt."""
    import mail_afspraken as MA  # noqa: PLC0415
    t = a.get("titel") or ""
    soort = _zorg_soort_titel(t)

    def geverifieerd(p):
        try:
            return datetime.fromisoformat(str(p.get("geverifieerd") or "")).date() <= nu.date()
        except ValueError:
            return False

    kandidaten = [p for p in profielen if p.get("soort") == soort and p.get("id") and geverifieerd(p)
                  and p.get("bewijs") and any(MA.zorg_locatie_is_adres(loc) for loc in
                                             [p.get("adres"), *(p.get("locaties") or [])]) and p.get("patienten")]
    expliciet = re.search(r"\b(?:pati[eë]nt|patient)\s*:\s*([^\n,;.]+)",
                         " ".join(str(a.get(k) or "") for k in ("titel", "omschrijving")), re.I)
    if expliciet:
        naam = MA._plat_tekst(expliciet.group(1))
        kandidaten = [p for p in kandidaten if naam in {MA._plat_tekst(n) for n in p.get("patienten") or []}]
    return kandidaten


def _zorg_genoemde_praktijk(a, kandidaten):
    """(profiel, expliciet): een genoemde praktijk of straat moet bij precies een kandidaat horen."""
    import mail_afspraken as MA  # noqa: PLC0415
    velden = (a.get("titel") or "", a.get("omschrijving") or "")

    def bij_naam(tekst):
        plat = MA._plat_tekst(tekst)
        return [p for p in kandidaten if any(
            re.search(r"(?<!\w)" + re.escape(MA._plat_tekst(naam)) + r"(?!\w)", plat)
            for naam in (p.get("naam"), *(p.get("praktijknamen") or []))
            if naam and len(MA._plat_tekst(naam)) >= 5)]

    verwijzingen = []
    for tekst in velden:
        # Alleen een benoemde praktijk; een generieke zin als 'bij de tandarts' is geen naam.
        for m in re.finditer(r"(?i:\b(?:bij|praktijk|kinesist)\s+)[A-ZÀ-Ý][^\n,;.!?]{0,70}", tekst):
            gevonden = bij_naam(m.group())
            if len(gevonden) != 1:
                return None, True
            verwijzingen.append(gevonden[0]["id"])
        # Een uitgeschreven straat met huisnummer is eveneens een expliciete plaats.
        for m in re.finditer(r"\b(?:[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'-]*\s+){0,3}"
                             r"[A-Za-zÀ-ÿ]+(?:straat|laan|weg|dreef|plein|lei|kaai|baan|hof|steeg|markt|rue|avenue)"
                             r"\s+\d{1,4}[A-Za-z]?\b", tekst, re.I):
            genoemd = _plat_adres(m.group())
            gevonden = [p for p in kandidaten if re.search(
                r"(?<!\w)" + re.escape(_plat_adres((p.get("adres") or "").split(",", 1)[0])) + r"(?!\w)", genoemd)]
            if len(gevonden) != 1:
                return None, True
            verwijzingen.append(gevonden[0]["id"])

    # Ook een volledige profielnaam zonder voorzetsel is een ondubbelzinnige aanwijzing.
    alle_namen = bij_naam(" ".join(velden))
    verwijzingen.extend(p["id"] for p in alle_namen)
    if not verwijzingen:
        return None, False
    if len(set(verwijzingen)) != 1:
        return None, True
    return next((p for p in kandidaten if p["id"] == verwijzingen[0]), None), True


def _zorg_bronprofiel(a, kandidaten):
    """Kies een profiel uit een zorgmailmerk, een eigen plaatsmerk of de enige geverifieerde kandidaat."""
    expliciet, genoemd = _zorg_genoemde_praktijk(a, kandidaten)
    if genoemd and expliciet is None:
        return None
    merk = a.get("_merk") or {}
    zorgmerk = merk.get(ZORGMERK) or ""
    if zorgmerk:
        pid = zorgmerk.split("|", 2)[1] if zorgmerk.startswith("zorg|") and zorgmerk.count("|") >= 2 else ""
        return next((p for p in kandidaten if p["id"] == pid and (not genoemd or p["id"] == expliciet["id"])), None)
    plaatsmerk = merk.get(ZORGPLAATSMERK) or ""
    if plaatsmerk:
        return next((p for p in kandidaten if _zorg_profielmerk(p) == plaatsmerk
                     and (not genoemd or p["id"] == expliciet["id"])), None)
    if genoemd:
        return expliciet
    return kandidaten[0] if len(kandidaten) == 1 else None


def _zorg_profiel_nooit_aan_huis(a, profielen=None, nu=None):
    """Vrije tekst bewijst nooit welke praktijk de afspraak heeft."""
    if not is_zorg_titel(a.get("titel")):
        return False
    if profielen is None:
        import mail_afspraken as MA  # noqa: PLC0415
        profielen = MA.zorgprofielen()
    kandidaten = _zorg_profiel_kandidaten(a, profielen, nu or nu_lokaal())
    p = _zorg_bronprofiel(a, kandidaten)
    merk = a.get("_merk") or {}
    # Een vrije naam bewijst bij meerdere kandidaten nog niet dat deze afspraak nooit aan huis is.
    bewezen = len(kandidaten) == 1 or merk.get(ZORGMERK) or merk.get(ZORGPLAATSMERK)
    return p is not None and bool(bewezen) and p.get("aan_huis") is False


def _zorg_profiel_kiezen(a, profielen, nu):
    """Een gecontroleerd profiel en een eigen patiënt; vrije omschrijving bewijst nooit de herkomst van de plaats."""
    if not (a.get("kalender") == PRIVE_AGENDA and a.get("id") and is_zorg_titel(a.get("titel"))
            and not lees_titel(a.get("titel") or "")["reistijd"]    # een ritblok "Reistijd -> Tandarts" is geen consult
            and _toekomst(a.get("start"), nu) and not a.get("hele_dag")
            and not a.get("deelnemers") and not a.get("_agendagasten")
            and not a.get("_terugkerend") and not a.get("_reeks")
            and a.get("_organisator_zelf") is True
            and (a.get("maker") or "").strip().lower() in _eigen_accounts()):
        return None
    kandidaten = _zorg_profiel_kandidaten(a, profielen, nu)
    if _zorg_huisbezoek(a, profielen, nu):
        return None
    bronprofiel = _zorg_bronprofiel(a, kandidaten)
    if bronprofiel and bronprofiel.get("adres"):
        return bronprofiel
    return None


def zorg_profielplaatsen_zetten(items, tok, nu=None, profielen=None):
    """Vult een ontbrekende privé-zorgplaats uit precies één geverifieerd profiel, met verborgen herkomstbewijs."""
    import mail_afspraken as MA  # noqa: PLC0415
    nu = nu or nu_lokaal()
    profielen = MA.zorgprofielen() if profielen is None else profielen
    gezet, open_ = 0, []
    for a in items:
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if not _toekomst(a.get("start"), nu) or a.get("kalender") != PRIVE_AGENDA or not is_zorg_titel(a.get("titel")):
            continue
        p = _zorg_profiel_kiezen(a, profielen, nu)
        if not p:
            continue                         # de adresvraag loopt via vragen_in_agenda; nooit een profiel raden
        locatie = (a.get("locatie") or "").strip()
        if locatie and not (_huisbezoek_locatie(locatie) and _zorg_profiel_nooit_aan_huis(a, profielen, nu)):
            continue                         # een handmatige fysieke plaats blijft staan
        merk = _zorg_profielmerk(p)
        try:
            oms = a.get("omschrijving") or ""
            if len(oms) >= 1900:
                oms = _volledige_omschrijving(a, tok)
            zin = ZORGPLAATSZIN.format(dag=nu.strftime("%d-%m-%Y"))
            body = {"location": p["adres"], "description": (oms.rstrip() + "\n\n" + zin).strip(),
                    "extendedProperties": {"private": {**(a.get("_merk") or {}), ZORGPLAATSMERK: merk}}}
            _patch(a, body, tok)
            e = _lees_event(a["kalender"], a["id"], tok)
            if not e or (e.get("location") or "") != p["adres"] or zin not in (e.get("description") or "") \
                    or ((e.get("extendedProperties") or {}).get("private") or {}).get(ZORGPLAATSMERK) != merk:
                open_.append(f"{a['id']}: profielplaats niet teruggelezen")
                continue
            a["locatie"], a["omschrijving"], a["_merk"] = p["adres"], body["description"], body["extendedProperties"]["private"]
            gezet += 1
        except Exception as ex:  # noqa: BLE001
            open_.append(f"{a['id']}: profielplaats niet gezet ({type(ex).__name__})")
    return gezet, open_


def _mailbron_zorg_afhankelijk(mailbox, items, nu=None):
    """De persoonlijke postbron kan nog een bevestiging of wijziging voor een nabij consult bevatten."""
    import mail_afspraken as MA  # noqa: PLC0415
    if mailbox not in MA.PRIVE:
        return False
    nu = nu or nu_lokaal()
    return any(a.get("kalender") in (WERKAGENDA, PRIVE_AGENDA) and is_zorg_titel(a.get("titel"))
               and _toekomst(a.get("start"), nu)
               and datetime.fromisoformat(a["start"]) <= nu + timedelta(hours=24)
               for a in items if "T" in (a.get("start") or ""))


def _verplaats_naar(x, doel, tok):
    """Verhuist een afspraak naar een andere agenda met behoud van haar Google-ID (events.move)."""
    if is_zorgschaduw(x):
        raise SchaduwItem("schaduw van een privé-zorgafspraak")
    _verplaats(x, doel, tok)


def _lees_event(kal, eid, tok):
    """De afspraak zoals Google ze bewaarde, of None."""
    import urllib.parse
    import urllib.request
    url = f"{agenda.API}/calendars/{urllib.parse.quote(kal, safe='')}/events/{urllib.parse.quote(eid or '', safe='')}"
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"}), timeout=30))
    except Exception:  # noqa: BLE001
        return None


def _zelfde_tijd(a, b):
    try:
        return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()) <= 60
    except (TypeError, ValueError):
        return False


def _zorg_body(a, z, profiel):
    """Het blok voor een bevestigde zorgafspraak: titel '!! [PR] Kine - Naam', plaats, begin en einde uit de mail,
    Bezet, de herinnering voor buiten, bron in de omschrijving (alleen Mehdi ziet de privé-agenda), merk."""
    import mail_afspraken as MA  # noqa: PLC0415
    beh = z.get("behandelaar") or ""
    kop = ", ".join(x for x in (profiel.get("naam", ""), profiel.get("adres", ""),
                                f"tel. {profiel['telefoon']}" if profiel.get("telefoon") else "") if x)
    return {"summary": canoniek(f"!! [PRIVE] {MA.zorg_rol(z, profiel)}" + (f" - {beh}" if beh else "")),
            "location": a.get("locatie") or "",          # alleen uit de mail (Codex A04)
            "start": {"dateTime": a["start"], "timeZone": "Europe/Brussels"},
            "end": {"dateTime": a["einde"], "timeZone": "Europe/Brussels"},
            "transparency": "opaque",
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": BUITEN_MIN}]},
            "description": "\n".join([kop,
                                      "Bevestigde zorgafspraak uit mail, door de Agendawacht in de privé-agenda gezet. Geen nieuwe "
                                      "boeking bij de praktijk: wijzigen of afzeggen gebeurt bij de praktijk zelf.",
                                      f"Bron: {a['bron_mailbox']}, '{a['bron_onderwerp']}', ontvangen "
                                      f"{(a.get('bron_ontvangen') or '')[:16].replace('T', ' ')}, Message-ID {a['bron_message_id']}."]),
            "extendedProperties": {"private": {ZORGMERK: a["sleutel"]}}}


def _zorg_teruglezen(kal, eid, body, tok, gelezen=None):
    """Leest het blok terug: pas als begin, einde, Bezet, plaats, 'geen gasten', titel, herinnering en ons merk kloppen,
    heet het gezet (Codex A07, ronde 3: titel, herinnering en merk werden niet teruggelezen)."""
    e = _lees_event(kal, eid, tok)
    if gelezen is not None:
        gelezen["event"] = e
    if not e:
        return "niet terug te lezen"
    fout = []
    if not _zelfde_tijd((e.get("start") or {}).get("dateTime"), body["start"]["dateTime"]):
        fout.append("begin")
    if not _zelfde_tijd((e.get("end") or {}).get("dateTime"), body["end"]["dateTime"]):
        fout.append("einde")
    if (e.get("transparency") or "opaque") != "opaque":
        fout.append("niet Bezet")
    if e.get("attendees"):
        fout.append("gasten")
    if body.get("location") and (e.get("location") or "") != body["location"]:
        fout.append("plaats")
    if body.get("summary") and (e.get("summary") or "") != body["summary"]:
        fout.append("titel")
    if "reminders" in body and (e.get("reminders") or {}) != body["reminders"]:
        fout.append("herinnering")
    merk = ((body.get("extendedProperties") or {}).get("private") or {}).get(ZORGMERK)
    if merk and ((e.get("extendedProperties") or {}).get("private") or {}).get(ZORGMERK) != merk:
        fout.append("merk")
    return ", ".join(fout)


def _zorg_nalezen(kal, eid, tok, start=None, einde=None, merk=None, plaats=None, titel_pr=False, weg_van=None):
    """Leest na elke schrijfactie van de zorgstap terug wat Google bewaarde (Codex A07): staat het item op de juiste
    agenda, kloppen begin, einde, merk en plaats, draagt het [PR] zonder VR of vraag, geen gasten, en staat het niet
    meer op de agenda waar het vandaan kwam. Geeft de problemen, of '' als alles klopt."""
    e = _lees_event(kal, eid, tok)
    if not e or e.get("status") == "cancelled":
        return f"niet terug te vinden op {kal[:24]}"
    fout = []
    if start and not _zelfde_tijd((e.get("start") or {}).get("dateTime"), start):
        fout.append("begin")
    if einde and not _zelfde_tijd((e.get("end") or {}).get("dateTime"), einde):
        fout.append("einde")
    if merk and ((e.get("extendedProperties") or {}).get("private") or {}).get(ZORGMERK) != merk:
        fout.append("merk")
    if plaats and (e.get("location") or "") != plaats:
        fout.append("plaats")
    if titel_pr:
        t = e.get("summary") or ""
        if "[PR]" not in t or t.startswith("VR") or "Agendawacht vraagt" in (e.get("description") or ""):
            fout.append("titel of vraag")
    if e.get("attendees"):
        fout.append("gasten")
    if weg_van:
        oud = _lees_event(weg_van, eid, tok)
        if oud and oud.get("status") != "cancelled":
            fout.append(f"staat nog op {weg_van[:24]}")
    return ", ".join(fout)


def _voorbij(start, nu=None):
    """Ligt dit begin voor nu? Echte tijdstippen met tijdzone, nooit tekst: de VM draait op UTC, Google geeft Brusselse
    tijd, en in de nacht van de wintertijd ligt 02:15+01:00 na 02:30+02:00 (Codex A22, 15-10-2026). Een hele dag telt
    per datum in Brussel. Onleesbaar telt als voorbij: dan schrijf ik er niets aan."""
    nu = nu or nu_lokaal()
    try:
        nu = datetime.fromisoformat(nu) if isinstance(nu, str) else nu
        if "T" not in start:
            return start < nu.astimezone(TIJDZONE).date().isoformat()
        return datetime.fromisoformat(start) < nu
    except (TypeError, ValueError):
        return True


def _toekomst(start, nu):
    try:
        return datetime.fromisoformat(start) > nu
    except (TypeError, ValueError):
        return False


def zorg_afspraken_zetten(res, items, tok, nu=None, bijwerken_items=False):
    """Zet, koppelt, volgt of verhuist zorgafspraken (zie hierboven). Werkt de status en het Google-ID in res bij, zodat
    het register ze bewaart en de gewone mailmelding geen tweede vraag zet. Geeft tellingen, 'bord' (zonder namen,
    praktijk of plaats) en 'prive' (details, alleen voor Mehdi)."""
    import mail_afspraken as MA  # noqa: PLC0415
    nu = nu or nu_lokaal()
    profielen = {p["id"]: p for p in MA.zorgprofielen()}
    schaduw_noden = markeer_zorgschaduwen(items, list(profielen.values()), nu)
    st = {"gezet": 0, "gekoppeld": 0, "verhuisd": 0, "verzet": 0, "open": 0, "voorbij": 0, "wacht": 0,
          "fout": 0, "prive": [], "noden": list(schaduw_noden)}
    per_id = {(x.get("kalender"), x.get("id")): x for x in items}
    werk_gelinkt = {}
    for a in res:
        if a.get("soort") != "zorg":
            continue
        z = MA._zorg_json(a)
        profiel = profielen.get(z.get("praktijk"), {})
        toekomst = _toekomst(a.get("start"), nu)
        wat = f"{(a.get('start') or '?')[:16].replace('T', ' ')} {a.get('titel', '')}"
        if profiel.get("soort") == "huisarts" and z.get("mehdi") and toekomst and not a.get("geannuleerd") \
                and z.get("gebeurtenis") not in ("aanvraag", "onbekend"):
            begint = datetime.fromisoformat(a["start"]).astimezone(TIJDZONE)
            nu_lokaal_ = nu.astimezone(TIJDZONE)
            if begint.date() == nu_lokaal_.date() or begint <= nu_lokaal_ + timedelta(hours=6):
                wanneer = "vandaag" if begint.date() == nu_lokaal_.date() else "binnen zes uur"
                st["noden"].append({"tekst": f"Huisartsafspraak {wanneer} op {begint:%d-%m %H:%M}: "
                                             "kijk in je privé-agenda.", "wie": "mehdi"})
        if a["status"] == "ontbreekt" and toekomst and a.get("einde"):
            body = _zorg_body(a, z, profiel)
            try:
                e = _insert(PRIVE_AGENDA, body, tok)
            except DagMarkering as ex:
                st["open"] += 1
                st["prive"].append(f"{wat}: niet gezet, de dag is afgesloten ({str(ex)[:80]}); beslist Mehdi")
                continue
            except Exception as ex:  # noqa: BLE001
                st["fout"] += 1
                st["prive"].append(f"{wat}: niet gezet ({type(ex).__name__})")
                continue
            gelezen = {}
            probleem = _zorg_teruglezen(PRIVE_AGENDA, e.get("id"), body, tok, gelezen)
            a["google"] = f"{PRIVE_AGENDA}|{e.get('id')}"
            if probleem:
                a["status"], a["detail"] = "afwijkend", f"teruglezen: {probleem}"
                st["fout"] += 1
                st["prive"].append(f"{wat}: gezet maar het teruglezen klopt niet ({probleem})")
            else:
                a["status"] = "gezet"
                st["gezet"] += 1
                st["prive"].append(f"{wat}: blok gezet in de privé-agenda ({e.get('id')}), teruggelezen")
                if bijwerken_items and z.get("mehdi") is True and (PRIVE_AGENDA, e.get("id")) not in per_id:
                    # De hoofdronde gebruikte al een agenda-momentopname. Geef het teruggelezen nieuwe blok
                    # direct aan Z1 en de ritten door; anders mist een mail zonder bruikbare plaats deze ronde.
                    terug = gelezen["event"]
                    nieuw = {"kalender": PRIVE_AGENDA, "id": e["id"], "titel": terug.get("summary") or body["summary"],
                             "start": (terug.get("start") or {}).get("dateTime") or a["start"],
                             "einde": (terug.get("end") or {}).get("dateTime") or a["einde"],
                             "hele_dag": False, "locatie": terug.get("location") or "",
                             "omschrijving": (terug.get("description") or body["description"])[:2000],
                             "maker": (terug.get("creator") or {}).get("email") or PRIVE_AGENDA,
                             "_organisator_zelf": (terug.get("organizer") or {}).get("self", True) is True,
                             "deelnemers": [], "_agendagasten": [],
                             "_terugkerend": bool(terug.get("recurringEventId")), "_reeks": terug.get("recurringEventId") or "",
                             "_merk": (terug.get("extendedProperties") or {}).get("private") or {}}
                    items.append(nieuw)
                    per_id[(PRIVE_AGENDA, e["id"])] = nieuw
        elif a["status"] == "gekoppeld":
            st["gekoppeld"] += 1
            kal, _, eid = (a.get("google") or "").partition("|")
            x = per_id.get((kal, eid))
            if x and is_zorgschaduw(x):
                bronkal, _, bronid = x["_zorg_schaduw"].partition("|")
                bron = per_id.get((bronkal, bronid))
                if bron:
                    kal, eid, x = bronkal, bronid, bron
                    a["google"] = f"{kal}|{eid}"
                else:
                    st["open"] += 1
                    st["prive"].append(f"{wat}: schaduw zonder teruggelezen privébron; niets gewijzigd")
                    continue
            if x and MA._ander_zorgitem(x, a):
                # het item draagt het merk of de uitnodiging van een andere afspraak: nooit verhuizen of overschrijven
                # (Codex A02, ronde 4 en 6)
                st["fout"] += 1
                st["prive"].append(f"{wat}: het gekoppelde item hoort bij een andere afspraak of uitnodiging, niets gewijzigd")
            elif kal == WERKAGENDA and toekomst:
                werk_gelinkt[eid] = (a, z, profiel)
            elif (x and (x.get("_merk") or {}).get(ZORGMERK) not in (None, "", a["sleutel"])):
                # het item draagt het merk van een andere zorgafspraak: nooit overschrijven (Codex A02, ronde 4)
                st["fout"] += 1
                st["prive"].append(f"{wat}: het gekoppelde item draagt het merk van een andere zorgafspraak, niets gewijzigd")
            elif kal == PRIVE_AGENDA and toekomst and x:
                plaats = (x.get("locatie") or "").strip()
                mailplaats = a.get("locatie") if MA.zorg_locatie_is_adres(a.get("locatie")) else ""
                profielmerk = (x.get("_merk") or {}).get(ZORGPLAATSMERK)
                gemerkt = _zorgplaats_merk_klopt(x)
                if mailplaats and plaats and not MA.zorg_plaats_gelijk(plaats, mailplaats) and not gemerkt:
                    st["open"] += 1
                    a["status"], a["detail"] = "zorg_open", "plaats in mail wijkt af van handmatig gezette plaats"
                    st["prive"].append(f"{wat}: mailplaats wijkt af van de handmatige plaats; open punt, niets gewijzigd")
                    continue
                # Mail heeft voorrang op een aantoonbaar door ons ingevulde profielplaats. Bij gelijke plaats is de
                # mail daarna de bron; het profielmerk verdwijnt. Een afwijkende handmatige plaats blijft staan.
                privaat = {**(x.get("_merk") or {}), ZORGMERK: a["sleutel"]}
                if profielmerk and (gemerkt or not plaats):
                    privaat[ZORGPLAATSMERK] = None
                body = {"extendedProperties": {"private": privaat}}
                if mailplaats and (not plaats or (gemerkt and not MA.zorg_plaats_gelijk(plaats, mailplaats))):
                    body["location"] = mailplaats
                if ((x.get("_merk") or {}).get(ZORGMERK) == a["sleutel"] and "location" not in body
                        and not (profielmerk and (gemerkt or not plaats))):
                    continue
                try:
                    _patch(x, body, tok)
                    probleem = _zorg_nalezen(PRIVE_AGENDA, eid, tok, merk=a["sleutel"], plaats=body.get("location"))
                    if profielmerk and (gemerkt or not plaats):
                        terug = _lees_event(PRIVE_AGENDA, eid, tok)
                        if ((terug or {}).get("extendedProperties") or {}).get("private", {}).get(ZORGPLAATSMERK):
                            probleem = (probleem + ", profielmerk").strip(", ")
                    if probleem:
                        st["fout"] += 1
                        st["prive"].append(f"{wat}: koppelmerk gezet maar het teruglezen klopt niet ({probleem})")
                    else:
                        x["_merk"] = {k: v for k, v in privaat.items() if v is not None}
                        if "location" in body:
                            x["locatie"] = body["location"]
                except Exception as ex:  # noqa: BLE001
                    st["fout"] += 1
                    st["prive"].append(f"{wat}: koppelmerk niet gezet ({type(ex).__name__})")
            st["prive"].append(f"{wat}: staat al in de agenda ({kal[:24]}, {eid}); geen tweede item")
        elif a["status"] == "afwijkend" and toekomst and a.get("google"):
            kal, _, eid = a["google"].partition("|")
            x = per_id.get((kal, eid))
            hist = (z.get("historie") or [])
            if x and MA._ander_zorgitem(x, a):
                # het item draagt intussen het merk of de uitnodiging van een andere afspraak: nooit wijzigen (A02, ronde 5)
                st["open"] += 1
                st["prive"].append(f"{wat}: het item op het oude uur hoort bij een andere afspraak, niets verzet; open punt")
            elif x and hist and hist[-1].get("naar") == a["start"] and not x.get("hele_dag"):
                einde = a.get("einde")
                notitie = ""
                if not einde:
                    # Hetzelfde consult op een nieuw uur: het blok verhuist mee en houdt zijn lengte; dat het einde niet in
                    # de mail stond, staat erbij (Codex A04, deels: een blok op het oude uur laten staan is erger)
                    duur = datetime.fromisoformat(x["einde"]) - datetime.fromisoformat(x["start"])
                    einde = (datetime.fromisoformat(a["start"]) + duur).isoformat()
                    notitie = " Het einde stond niet in de mail: de oude duur is behouden."
                try:
                    _patch(x, {"start": {"dateTime": a["start"], "timeZone": "Europe/Brussels"},
                               "end": {"dateTime": einde, "timeZone": "Europe/Brussels"},
                               "description": ((x.get("omschrijving") or "").rstrip() + f"\n\nVerzet van {hist[-1]['van'][:16].replace('T', ' ')} "
                                               f"naar {a['start'][:16].replace('T', ' ')} volgens mail {hist[-1].get('bron', '')}.{notitie}").strip()}, tok)
                    probleem = _zorg_nalezen(kal, eid, tok, start=a["start"], einde=einde)
                    if probleem:
                        st["fout"] += 1
                        st["prive"].append(f"{wat}: verzet maar het teruglezen klopt niet ({probleem})")
                    else:
                        a["status"] = "gezet"
                        st["verzet"] += 1
                        st["prive"].append(f"{wat}: verzet van {hist[-1]['van'][:16]} (zelfde item {eid}), teruggelezen{notitie}")
                except Exception as ex:  # noqa: BLE001
                    st["fout"] += 1
                    st["prive"].append(f"{wat}: verzetten mislukt ({type(ex).__name__})")
            else:
                st["open"] += 1
                st["prive"].append(f"{wat}: agenda en mail verschillen ({a.get('detail')}); niets veranderd op een gok")
        elif a["status"] == "zorg_open":
            st["open"] += 1
            st["prive"].append(f"{wat}: open punt ({a.get('detail')})")
        elif a["status"] == "voorbij":
            st["voorbij"] += 1
            st["prive"].append(f"{wat}: voorbij, {a.get('detail') or 'historisch'}; niets teruggeboekt")
        elif a["status"] == "zorg_wacht":
            st["wacht"] += 1
    # Een eigen zorgitem op werk hoort privé; een dubbel collega-item blijft als schaduw staan.
    for x in items:
        # nooit verhuizen: een afspraak met gasten (van buiten of collega's), een reeks of een hele dag (Codex A02)
        if x.get("kalender") != WERKAGENDA or is_zorgschaduw(x) or x.get("hele_dag") or x.get("deelnemers") or x.get("_agendagasten") \
                or x.get("_terugkerend") or not x.get("id"):
            continue
        if not (is_zorg_titel(x.get("titel")) or x["id"] in werk_gelinkt) or not _toekomst(x.get("start"), nu):
            continue
        gekoppeld = werk_gelinkt.get(x["id"])
        if gekoppeld:
            body = _zorg_body(gekoppeld[0], gekoppeld[1], gekoppeld[2])
            body = {k: body[k] for k in ("summary", "location", "extendedProperties")}
            if (x.get("locatie") or "").strip() and body["location"] and not MA.zorg_plaats_gelijk(x["locatie"], body["location"]) \
                    and not _zorgplaats_merk_klopt(x):
                body["location"] = x["locatie"]
                gekoppeld[0]["status"] = "zorg_open"
                gekoppeld[0]["detail"] = "plaats in mail wijkt af van handmatig gezette plaats"
                st["open"] += 1
                st["prive"].append(f"{x['start'][:16]}: mailplaats wijkt af van handmatige plaats; open punt")
            elif (x.get("locatie") or "").strip() and not body["location"]:
                body["location"] = x["locatie"]
            notitie = "Van de werkagenda naar privé verhuisd door de Agendawacht: persoonlijke zorg, geen zakelijke afspraak."
        else:
            t = re.sub(r"^\s*((VR|ZL|!!|\?\?)\s+)+", "", x.get("titel") or "")
            t = re.sub(r"\bmehdi\b\s*:?", "", t, flags=re.I).strip(" :-,")
            body = {"summary": canoniek(f"!! [PRIVE] {t[:1].upper() + t[1:]}")}
            notitie = ("Van de werkagenda naar privé verhuisd door de Agendawacht: persoonlijke zorg, geen zakelijke afspraak. "
                       "Behandelaar en praktijk zijn nog niet door een bronmail bevestigd; de herinnering van de praktijk komt "
                       "meestal de dag ervoor en wordt dan aan dit item gekoppeld.")
        oms = "\n".join(r for r in (x.get("omschrijving") or "").splitlines() if not r.startswith("Agendawacht vraagt:")).strip()
        body["description"] = (oms + "\n\n" + notitie).strip()
        verhuisd_item = dict(x, kalender=PRIVE_AGENDA, _titel_bronkalender=x["kalender"])
        reden = _titel_patch_reden(verhuisd_item, canoniek(body["summary"]), eigen_zorgverhuis=True)
        if reden:
            st["open"] += 1
            st["prive"].append(f"{x['start'][:16]}: VOORSTEL zorgafspraak naar privé te verhuizen ({reden})")
            continue
        try:
            _verplaats_naar(x, PRIVE_AGENDA, tok)
            _patch(verhuisd_item, body, tok, eigen_zorgverhuis=True)
            probleem = _zorg_nalezen(PRIVE_AGENDA, x["id"], tok, titel_pr=True, weg_van=WERKAGENDA,
                                     merk=(body.get("extendedProperties") or {}).get("private", {}).get(ZORGMERK))
            if probleem:
                st["fout"] += 1
                st["prive"].append(f"{x['start'][:16]} verhuisd maar het teruglezen klopt niet ({probleem})")
                continue
            st["verhuisd"] += 1
            if bijwerken_items:
                # De volledige ronde gebruikt dezelfde itemlijst voor reistijd; het doel is pas na teruglezen zeker.
                x["kalender"], x["titel"], x["omschrijving"] = PRIVE_AGENDA, body["summary"], body["description"]
                if "location" in body:
                    x["locatie"] = body["location"]
                if "extendedProperties" in body:
                    x["_merk"] = body["extendedProperties"]["private"]
            st["prive"].append(f"{x['start'][:16].replace('T', ' ')} {x.get('titel', '')[:40]}: van werk naar privé ({x['id']}), "
                               f"nu '{body['summary']}', teruggelezen")
        except Exception as ex:  # noqa: BLE001
            st["fout"] += 1
            st["prive"].append(f"{x['start'][:16]} verhuizen naar privé mislukt ({type(ex).__name__})")
    gekoppelde_zorg_k = {MA.sleutel_kort({"sleutel": (x.get("_merk") or {}).get(ZORGMERK)}) for x in items
                         if x.get("kalender") == PRIVE_AGENDA and not x.get("hele_dag")
                         and (x.get("_merk") or {}).get(ZORGMERK)}
    gekoppelde_zorg_k |= {MA.sleutel_kort(a) for a in res
                          if a.get("soort") == "zorg" and a.get("status") in ("gekoppeld", "gezet")}
    for x in items:
        k_merk = (x.get("_merk") or {}).get(MAILMERK) or ""
        if x.get("kalender") != PRIVE_AGENDA or not k_merk or k_merk.startswith("opgelost:"):
            continue
        basis_k = k_merk[2:] if k_merk.startswith("z:") else k_merk
        if basis_k in gekoppelde_zorg_k:
            try:
                if _eigen_melding_opgelost(x, k_merk, tok, nu, "de afspraak staat nu in de agenda"):
                    st["prive"].append(f"{(x.get('start') or '')[:10]} melding op opgelost gezet: de afspraak staat nu in de agenda")
            except Exception as ex:  # noqa: BLE001
                st["fout"] += 1
                st["prive"].append(f"{(x.get('start') or '')[:10]} melding niet op opgelost gezet ({type(ex).__name__})")
    profiel_gezet, profiel_open = zorg_profielplaatsen_zetten(items, tok, nu, list(profielen.values()))
    st["profielplaats"] = profiel_gezet
    st["fout"] += len(profiel_open)
    st["prive"].extend(profiel_open)
    st["bord"] = [f"zorg uit mail: {st['gezet']} blok(ken) gezet, {st['gekoppeld']} al in de agenda, {st['verhuisd']} van werk "
                  f"naar privé, {st['verzet']} verzet, {st['open']} open punt(en), {st['wacht']} wacht op bevestiging, "
                  f"{st['voorbij']} voorbij zonder item (historisch), {st['profielplaats']} profielplaatsen, {st['fout']} mislukt"]
    return st


# Agendagasten (Mehdi, 03-10-2026: "een systeem waarbij je iemand kunt toevoegen ... zodat het gewoon op hun agenda
# verschijnt ... dan hoef ik niet handmatig mails te ontvangen"). Collega's en partners met een agenda-adres op
# organisatie.globaal.be (kern.persoon.email_agenda) staan als gast op de afspraken waar ze bij horen. Gewone wijzigingen
# blijven stil. Sinds 18-10-2026 krijgt de toegestane partner eenmalig een uitnodiging voor een afspraak ter plaatse.
# Wie erbij hoort:
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


UITNODIGMERK = "agendawacht_uitgenodigd"
_TITELADRES = re.compile(r",\s*[^,]+\s+\d+[A-Za-z]?\s*,\s*\d{4}\s+[^,]+")
_VIRTUELE_PLAATS = re.compile(r"https?://|www\.|\b(?:zoom|teams|online|videogesprek|videovergadering|google meet)\b", re.I)


def _ter_plaatse_voor_uitnodiging(a):
    """Alleen een bewezen fysieke afspraak. Een buitencode zonder enig adres is onvoldoende."""
    info = lees_titel(a.get("titel") or "")
    if (is_prive(a) or info["reistijd"] or info["soort"] in EXTERN_ONLINE + ("IN",)
            or a.get("_conferentie") or _online(a) is True):
        return False
    buiten = info["buiten"] or info["soort"] in BUITEN_SOORTEN
    plaats = (a.get("locatie") or "").strip()
    if plaats:
        return (not _VIRTUELE_PLAATS.search(plaats) and not VERGADERLINK_RE.search(plaats)
                and (buiten or bool(re.search(r"\d", plaats))))
    return bool(buiten and _TITELADRES.search(a.get("titel") or ""))


DUURMERK = "agendawacht_duur"


def _duurregel():
    """Lees de duur uit de master; bij een onleesbare regel verandert er geen afspraak."""
    try:
        regel = json.loads((Path(__file__).resolve().parent / "werkwijze" / "agenda-taken.json")
                           .read_text(encoding="utf-8"))["duur_ter_plaatse"]
        minuten = int(regel["minuten"])
        woorden = regel["trefwoorden"]
        if minuten > 0 and isinstance(woorden, list) and all(isinstance(w, str) and w for w in woorden):
            return minuten, re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in woorden) + r")", re.I)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None, None


def _duur_doel(a, minuten, patroon):
    """Woordbegin in titel, locatie of omschrijving, uitsluitend bij een bewezen afspraak ter plaatse."""
    if (not minuten or not patroon or a.get("hele_dag") or a.get("fout") or a.get("_archief")
            or "T" not in (a.get("start") or "") or "T" not in (a.get("einde") or "")
            or not _ter_plaatse_voor_uitnodiging(a)):
        return None
    if not patroon.search(" ".join(str(a.get(k) or "") for k in ("titel", "locatie", "omschrijving"))):
        return None
    try:
        begin, einde = datetime.fromisoformat(a["start"]), datetime.fromisoformat(a["einde"])
        return begin + timedelta(minutes=minuten) if 0 < (einde - begin).total_seconds() < minuten * 60 else None
    except (ValueError, TypeError):
        return None


def _duur_botsing(a, items, doel):
    """Kijk alleen naar het verlengde stuk. Eigen gemerkte ritten rekent reistijd_zetten opnieuw."""
    einde = datetime.fromisoformat(a["einde"])
    dag = einde.date()
    while datetime.combine(dag, datetime.min.time(), tzinfo=einde.tzinfo) < doel:
        marker = markering_tegen(a["titel"], dag.isoformat(), markeringen_uit(items, dag.isoformat()),
                                 locatie=a.get("locatie") or "")
        if marker:
            return f"dagmarkering '{marker}'"
        dag += timedelta(days=1)
    for x in items:
        if (x is a or (x.get("kalender"), x.get("id")) == (a.get("kalender"), a.get("id"))
                or x.get("fout") or x.get("hele_dag") or is_eigen_rit(x)
                or "T" not in (x.get("start") or "") or "T" not in (x.get("einde") or "")):
            continue
        try:
            if datetime.fromisoformat(x["start"]) < doel and einde < datetime.fromisoformat(x["einde"]):
                return f"andere afspraak om {x['start'][11:16]}"
        except (ValueError, TypeError):
            continue
    return ""


def _duur_vr_mogelijk(a):
    """Een duurvraag mag alleen via de bestaande, bewezen titelroute in de afspraak komen."""
    titel = a.get("titel") or ""
    nieuw = titel[3:] if titel.startswith("VR ") else "VR " + titel
    if not (a.get("kalender") == WERKAGENDA and _van_mehdi(a) and not a.get("_reeks")
            and not a.get("_terugkerend") and not a.get("_archief")
            and not _titel_patch_reden(a, nieuw, alleen_vr=True)):
        return False
    try:
        return mag_schrijven(a["kalender"])
    except Exception:  # noqa: BLE001
        return False


def duur_ter_plaatse_zetten(items, tok=None, nu=None):
    """Verleng eigen werkafspraken over barsten of scheuren tot twee uur en lees elke wijziging terug.

    Een botsing wordt via _vastgelopen een VR-vraag. Zonder titelrecht komt de bevinding in het werkverslag.
    Geeft (aantal teruggelezen wijzigingen, bevindingen).
    """
    nu = nu or nu_lokaal()
    minuten, patroon = _duurregel()
    if not minuten:
        return 0, ["Duur ter plaatse: masterregel niet leesbaar; geen afspraak gewijzigd"]
    gezet, regels = 0, []
    for a in items:
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        doel = _duur_doel(a, minuten, patroon)
        if not doel or (a.get("_merk") or {}).get(DUURMERK) == str(minuten):
            continue
        begin = datetime.fromisoformat(a["start"])
        if begin <= nu:
            continue
        tekst = (f"Barsten en scheuren ter plaatse: 2 uur voorzien, nu "
                 f"{int((datetime.fromisoformat(a['einde']) - begin).total_seconds() // 60)} min; "
                 f"verleng tot {doel:%H:%M}")
        eigen = (a.get("kalender") == WERKAGENDA and _van_mehdi(a) and not a.get("_reeks")
                 and not a.get("_terugkerend") and not is_calendly(a))
        if not eigen:
            regels.append(f"{a['start'][:16]} {_toon(a, 45)}: NOOD: {tekst}; gasten, maker, agenda of reeks laten geen eigen verlenging toe")
            continue
        botsing = _duur_botsing(a, items, doel)
        if botsing:
            label = "VRAAG" if _duur_vr_mogelijk(a) else "NOOD"
            regels.append(f"{a['start'][:16]} {_toon(a, 45)}: {label}: {tekst} ({botsing})")
            continue
        try:
            tok = tok or agenda._toegang()
            if not mag_schrijven(a["kalender"]):
                raise GeenSchrijfrecht(a["kalender"])
            vers = _event(a, tok)
            ev_begin = (vers.get("start") or {}).get("dateTime")
            ev_einde = (vers.get("end") or {}).get("dateTime")
            privaat = ((vers.get("extendedProperties") or {}).get("private") or {})
            if privaat.get(DUURMERK) == str(minuten):
                a["_merk"] = privaat
                continue
            if vers.get("status") == "cancelled":
                continue
            if not _zelfde_tijd(ev_begin, a["start"]) or not _zelfde_tijd(ev_einde, a["einde"]):
                # Een andere schrijver was sneller. Bewaar de verse duur zodat de vraagroute geen oud uur gebruikt.
                if _zelfde_tijd(ev_begin, a["start"]) and ev_einde:
                    a["einde"] = ev_einde
                    a["_merk"] = privaat
                    a["omschrijving"] = vers.get("description") or ""
                    if datetime.fromisoformat(ev_einde) >= doel:
                        continue
                regels.append(f"{a['start'][:16]} {_toon(a, 45)}: NOOD: afspraak intussen verzet; duur opnieuw nakijken")
                continue
            if vers.get("attendees") or vers.get("recurringEventId"):
                regels.append(f"{a['start'][:16]} {_toon(a, 45)}: NOOD: {tekst}; intussen gasten of een reeks")
                continue
            oms = vers.get("description") or ""
            zin = f"Duur 2 uur: vaste regel van Mehdi voor barsten en scheuren ter plaatse (Agendawacht, {nu:%d-%m-%Y})"
            if not any(r.startswith("Duur 2 uur: vaste regel van Mehdi voor barsten en scheuren ter plaatse")
                       for r in oms.splitlines()):
                oms = oms.rstrip() + ("\n" if oms.strip() else "") + zin
            _patch(a, {"end": {"dateTime": doel.isoformat()}, "description": oms,
                       "extendedProperties": {"private": {**privaat, DUURMERK: str(minuten)}}}, tok)
            terug = _event(a, tok)
            terug_einde = (terug.get("end") or {}).get("dateTime")
            terug_privaat = ((terug.get("extendedProperties") or {}).get("private") or {})
            if (not _zelfde_tijd(terug_einde, doel.isoformat()) or terug_privaat.get(DUURMERK) != str(minuten)
                    or zin not in (terug.get("description") or "")):
                raise RuntimeError("verlenging niet bevestigd bij teruglezen")
            a["einde"] = terug_einde
            a["omschrijving"] = terug.get("description") or ""
            a["_merk"] = terug_privaat
            gezet += 1
        except Exception as e:  # noqa: BLE001
            regels.append(f"{a['start'][:16]} {_toon(a, 45)}: NOOD: {tekst}; verlengen mislukt ({type(e).__name__})")
    return gezet, regels


class AndereUitnodigingsgast(ValueError):
    """De mailpatch zou ook een niet-toegestane gast bereiken."""


def _uitnodiging_alleen_partner(attendees, toegestaan):
    """Ook een resource zonder adres is een andere gast; organisator en Mehdi zelf tellen niet mee."""
    for gast in attendees or []:
        if not isinstance(gast, dict) or gast.get("resource"):
            return False
        adres = (gast.get("email") or "").strip().lower()
        if not (gast.get("self") or gast.get("organizer") or adres == WERKAGENDA.lower()
                or adres in toegestaan):
            return False
    return True


def _uitnodiging_patch(a, body, tok):
    """Enige mailroute: de toegestane gast op een eigen, komende fysieke afspraak uitnodigen."""
    if is_zorgschaduw(a):
        raise SchaduwItem("schaduw van een privé-zorgafspraak")
    import urllib.parse
    import urllib.request
    adres = ((body.get("extendedProperties") or {}).get("private") or {}).get(UITNODIGMERK)
    toegestaan = {e.lower() for e in _gastregels().get("uitnodigen_ter_plaatse") or []}
    if not _uitnodiging_alleen_partner(body.get("attendees"), toegestaan):
        raise AndereUitnodigingsgast("andere gasten in uitnodigingsbody")
    gasten = {(g.get("email") or "").strip().lower() for g in body.get("attendees") or []}
    if (a.get("kalender") != WERKAGENDA or not a.get("_organisator_zelf") or a.get("_reeks")
            or a.get("hele_dag") or _voorbij(a.get("start") or "", nu_lokaal().isoformat())
            or not _ter_plaatse_voor_uitnodiging(a) or adres not in toegestaan or adres not in gasten):
        raise ValueError("geen toegestane uitnodiging ter plaatse")
    if not mag_schrijven(a["kalender"]):
        raise GeenSchrijfrecht(a["kalender"])
    # Een collega of klant kan tussen het maken van de body en deze PATCH zijn toegevoegd.
    vers = _event(a, tok)
    verse_gasten = vers.get("attendees") or []
    if not _uitnodiging_alleen_partner(verse_gasten, toegestaan):
        raise AndereUitnodigingsgast("andere gasten in vers event")
    if adres not in {(g.get("email") or "").strip().lower() for g in verse_gasten}:
        raise ValueError("toegestane gast ontbreekt in vers event")
    url = (f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/"
           f"{urllib.parse.quote(a['id'], safe='')}?sendUpdates=all")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)


def agendagasten_zetten(items, tok=None, nu=None):
    """Zet ontbrekende agendagasten op komende afspraken op de werkagenda die Mehdi zelf organiseert, een reeks in de
    reeks zelf. Bestaande gasten blijven staan; alleen de toegestane partner krijgt eenmaal een uitnodiging ter plaatse.
    Na schrijven worden gast en uitnodigingsmerk teruggelezen. Geeft regels."""
    mensen = organisatie.agenda_adressen() or {}
    regels_ = _gastregels()
    if not mensen and not regels_.get("uitnodigen_ter_plaatse"):
        return []
    nu_iso = (nu or nu_lokaal()).isoformat()
    uit, reeksen, voorgestelde_reeksen = [], {}, set()
    for a in items:
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if (is_zorgschaduw(a) or a.get("hele_dag") or a.get("fout") or a.get("_archief") or "T" not in a.get("start", "")
                or _voorbij(a["start"], nu_iso) or not a.get("_organisator_zelf")
                or a.get("kalender") != WERKAGENDA or lees_titel(a["titel"])["reistijd"]):
            continue
        gewenst = agendagasten_voor(a["titel"], regels_, mensen)
        ontbreekt = gewenst - set(a.get("_agendagasten") or [])
        mag_uitnodigen = _ter_plaatse_voor_uitnodiging(a)
        uitnodig_adressen = {e.lower() for e in regels_.get("uitnodigen_ter_plaatse") or []}
        gasten_in_overzicht = set(a.get("_agendagasten") or []) | {
            e.lower() for e in a.get("deelnemers") or []}
        uitnodig_kandidaten = uitnodig_adressen & (gasten_in_overzicht | gewenst)
        uitnodig_kandidaten.discard((a.get("_merk") or {}).get(UITNODIGMERK))
        if not ontbreekt and not (mag_uitnodigen and uitnodig_kandidaten):
            continue
        hier = {"kalender": a["kalender"], "id": a["id"], "titel": a["titel"]}
        try:
            tok = tok or agenda._toegang()
            doelen = []
            if a.get("_reeks") and ontbreekt:
                # De reeks krijgt alleen wie in de titel van de reeks zelf staat. Een naam die alleen in de titel van
                # deze ene keer staat, komt alleen op deze keer, niet op alle weken (Codex A18, 15-10-2026).
                if a["_reeks"] not in reeksen:
                    reeks = {"kalender": a["kalender"], "id": a["_reeks"], "titel": a["titel"]}
                    reeksen[a["_reeks"]] = agendagasten_voor(_event(reeks, tok).get("summary") or "", regels_, mensen)
                    if reeksen[a["_reeks"]] & ontbreekt:
                        doelen.append((reeks, reeksen[a["_reeks"]] & ontbreekt, " (de hele reeks)"))
                if ontbreekt - reeksen[a["_reeks"]]:
                    doelen.append((hier, ontbreekt - reeksen[a["_reeks"]], " (alleen deze keer)"))
            elif ontbreekt:
                doelen.append((hier, ontbreekt, ""))
            for doel, nodig, waar in doelen:
                bestaand = _event(doel, tok).get("attendees") or []
                erbij = sorted(nodig - {(g.get("email") or "").lower() for g in bestaand})
                if not erbij:
                    continue
                _patch(doel, {"attendees": bestaand + [{"email": e} for e in erbij]}, tok)
                terug = {(g.get("email") or "").lower() for g in (_event(doel, tok).get("attendees") or [])}
                wie = ", ".join(mensen[e].get("voornaam") or e for e in erbij)
                if set(erbij) <= terug:
                    uit.append(f"{a['start'][:16]} {_toon(a, 45)}: {wie} als gast gezet, zonder mail{waar}")
                else:
                    uit.append(f"{a['start'][:16]} {_toon(a, 45)}: {wie} niet teruggevonden na het zetten")
            if mag_uitnodigen and uitnodig_kandidaten:
                vers = _event(hier, tok)
                gasten = {(g.get("email") or "").lower() for g in vers.get("attendees") or []}
                kandidaten = uitnodig_adressen & (gasten | gewenst)
                if a.get("_reeks"):
                    if kandidaten and a["_reeks"] not in voorgestelde_reeksen:
                        uit.append(f"{a['start'][:16]} {_toon(a, 45)}: VOORSTEL: uitnodiging voor partner in een reeks; "
                                   "de reeks blijft zonder mail")
                        voorgestelde_reeksen.add(a["_reeks"])
                    continue
                privaat = ((vers.get("extendedProperties") or {}).get("private") or {})
                for adres in sorted(uitnodig_adressen & gasten):
                    if privaat.get(UITNODIGMERK) == adres:
                        continue
                    if privaat.get(UITNODIGMERK):
                        uit.append(f"{a['start'][:16]} {_toon(a, 45)}: ander uitnodigingsmerk; geen tweede uitnodiging")
                        continue
                    voorstel = (f"{a['start'][:16]} {_toon(a, 45)}: VOORSTEL: Catalin staat erop zonder mail: "
                                 "er staan andere gasten op; stuur de uitnodiging met de hand")
                    if not _uitnodiging_alleen_partner(vers.get("attendees"), uitnodig_adressen):
                        uit.append(voorstel)
                        continue
                    body = {"attendees": vers.get("attendees") or [],
                            "extendedProperties": {"private": {**privaat, UITNODIGMERK: adres}}}
                    try:
                        _uitnodiging_patch(a, body, tok)
                    except AndereUitnodigingsgast:
                        uit.append(voorstel)
                        continue
                    terug = _event(hier, tok)
                    terug_gasten = {(g.get("email") or "").lower() for g in terug.get("attendees") or []}
                    terug_merk = ((terug.get("extendedProperties") or {}).get("private") or {}).get(UITNODIGMERK)
                    wie = mensen.get(adres, {}).get("voornaam") or adres
                    if adres in terug_gasten and terug_merk == adres:
                        uit.append(f"{a['start'][:16]} {_toon(a, 45)}: uitnodiging aan {wie}, gast en merk teruggelezen")
                    else:
                        uit.append(f"{a['start'][:16]} {_toon(a, 45)}: uitnodiging aan {wie} niet bevestigd bij teruglezen")
        except Exception as e:  # noqa: BLE001
            uit.append(f"{a['start'][:16]} {_toon(a, 45)}: agendagast of uitnodiging mislukt ({type(e).__name__})")
    return uit


def reistijd_zetten(items, alleen_dag=None, nu=None, niet_op_kaart=None):
    """Werkwijze: elke komende afspraak buiten (!!, of PB/KB met een adres) krijgt een
    blok 'Reistijd -> plaats' ervoor en 'Reistijd <- plaats' erna, met de rijtijd
    vanaf thuis (of de vorige buitenafspraak van die dag) plus buffer, rood, op
    dezelfde agenda. Een handmatige rit op een gelezen agenda telt op het grensuur mee. Bestaat er al een ritblok,
    dan niets. De afspraak zelf krijgt een herinnering op het vertrekmoment plus 5.
    Geeft (gemaakt, al, geen_adres, fout, regels); niet_op_kaart ontvangt de
    afspraak-identiteiten waarvan coord() de bestemming niet vond."""
    from datetime import timedelta
    tok = agenda._toegang()
    cache = _cache_laden()
    thuis = coord(THUIS, cache)
    nu = nu or nu_lokaal()
    markeer_zorgschaduwen(items, nu=nu)
    if niet_op_kaart is not None:
        niet_op_kaart.clear()
    gemaakt, al, geen_adres, fout, regels = 0, 0, 0, 0, []
    reistijden = [x for x in items if lees_titel(x["titel"])["reistijd"]]
    projecten = projectadressen.index()

    def handmatige_rit_bij(a, richting):
        grens = a["start"] if richting == "voor" else a["einde"]
        grenzen = {grens}
        bron = f"{a.get('kalender')}|{a.get('id')}"
        grenzen.update(x["start"] if richting == "voor" else x["einde"] for x in items
                       if x.get("_zorg_schaduw") == bron)
        return next((x for x in reistijden if _handmatige_rit_titel(x, richting)
                     and any(rit_hoort_bij(x, a["titel"], richting, rand) for rand in grenzen)), None)

    def alternatieve_adressen(a, info):
        """Bekende bronnen in vaste volgorde, zonder de handmatig ingevulde plaats te wijzigen."""
        project = projecten.get(info["nummer"]) if info["nummer"] else None
        if project and _bruikbare_locatie(project.get("adres")):
            yield project["adres"], "projectmap"
        try:
            gevonden, naam = plek_zoeken((a.get("titel") or "") + " " + (a.get("omschrijving") or ""))
            if gevonden and _bruikbare_locatie(gevonden):
                yield gevonden, f"locatiesysteem ({naam})"
        except Exception:  # noqa: BLE001
            pass
        try:
            woord, vp = vaste_plek(a.get("titel") or "")
            if vp and _bruikbare_locatie(vp.get("adres")):
                yield vp["adres"], f"vaste plek ({woord})"
        except Exception:  # noqa: BLE001
            pass

    buiten = []
    begonnen = set()      # buitenafspraken van vandaag die al begonnen zijn: vertrekpunt, geen eigen ritten meer (FR-97)
    vrij = lara_vakantiedagen()
    dekking = schoolvakantie_dekking() if vrij is not None else None
    zonder_auto = geen_auto_dagen()
    if vrij is None:
        regels.append("Lara-vakanties niet te lezen: deze ronde geen Lara-ritten (onbekend is niet 'geen vakantie')")
    if zonder_auto is None:
        regels.append("dagen zonder auto niet te lezen: deze ronde geen nieuwe ritten naar buiten")
    for a in items:
        if is_zorgschaduw(a) or a.get("hele_dag") or a.get("kalender", "").startswith("en.be#"):
            continue
        adres = a.get("locatie") or ""
        if is_thuis_adres(adres) or _afspraak_is_huisbezoek(a, nu=nu):
            # Ook bij een onleesbare grendel of een dag zonder auto is thuis geen buitenrit.
            continue
        is_lara = a.get("kalender") in AGENDA_VASTE_KLEUR and AGENDA_VASTE_KLEUR[a["kalender"]].get("naam") == "Lara"
        # na de laatste dag van de officiële bron is een schooldag niet te toetsen: zoals een onleesbare bron (L2)
        buiten_bron = is_lara and dekking is not None and a.get("start", "")[:10] > dekking.isoformat()
        if zonder_auto is None or (is_lara and (vrij is None or buiten_bron)):
            # de grendelbron is onbekend: geen rit, ook geen gok (Codex A11). Elke getroffen komende buitenafspraak staat
            # apart in de meldingen, niet alleen in een algemene logregel (ronde 3)
            _li = lees_titel(a["titel"])
            if "T" in a.get("start", "") and not _li["reistijd"] and (_li["buiten"] or _li["soort"] in BUITEN_SOORTEN) \
                    and not _voorbij(a["start"], nu) and (not alleen_dag or a["start"][:10] == alleen_dag) \
                    and not any(x.get("kalender") == a.get("kalender") and _zelfde_tijd(x.get("einde"), a["start"])
                                and rit_hoort_bij(x, a["titel"], "voor") for x in reistijden):
                # alleen de gevraagde dag, en niet als er op dezelfde agenda al een heenrit eindigt op het begin van deze
                # afspraak (Codex A11, ronde 4 tot 6)
                regels.append(f"{a['start'][:16]} {_toon(a, 50)}: geen rit, "
                              + ("schoolvakanties van dat schooljaar nog niet in de bron" if buiten_bron and vrij is not None
                                 else "grendelbron niet te lezen"))
            continue
        # Tijdens een officiële schoolvakantie of feestdag haalt Mehdi Lara niet op: geen rit voor een afspraak op de
        # agenda van Lara op zo'n dag (mandaat van Mehdi, 22-09-2026). Een ophaalmoment dat Mehdi liet vervallen
        # ('vervalt' vooraan, L4) krijgt ook geen rit.
        if lara_zonder_rit(a, vrij):
            continue
        info = lees_titel(a["titel"])
        if info["firma_conflict"]:
            continue          # H1-1, driehoeksoverleg C2, 17-10-2026: geen rit uit een dubbelzinnige firma.
        # Geen auto die dag: geen rit. Staat er toch een buitenafspraak, dan is dat een
        # waarschuwing (collega die het vergat), geen gewone rit. Mandaat van Mehdi, 22-09-2026.
        if a.get("start", "")[:10] in zonder_auto and not lees_titel(a["titel"])["reistijd"]:
            if info["buiten"] or info["soort"] in BUITEN_SOORTEN:
                regels.append(f"{a['start'][:16]} {_toon(a, 50)}: BUITEN op een dag zonder auto (door {maker(a)})")
            continue
        fysiek = _bruikbare_locatie(adres)
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
        if info["reistijd"] or not (info["buiten"] or info["soort"] in BUITEN_SOORTEN or _firma_buitenblok(a, fysiek)):
            continue
        a["_bron_adres"] = bron_adres
        if fysiek and bron_adres == "agenda" and info["nummer"] in projecten:
            g = projecten[info["nummer"]]["gemeente"].lower()
            if g and g not in adres.lower():
                regels.append(f"{a['start'][:16]} {_toon(a, 50)}: adres in agenda ({adres[:35]}) wijkt af van projectmap {info['nummer']} ({projecten[info['nummer']]['adres'][:35]})")
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
                regels.append(f"{a['start'][:16]} {_toon(a, 45)}: projectadres in de afspraak gezet ({adres[:40]})")
            except Exception as e:  # noqa: BLE001
                regels.append(f"{a['start'][:16]} {_toon(a, 45)}: projectadres niet gezet ({type(e).__name__})")
        doel = coord(adres, cache) if fysiek else None
        kaartstoring = doel is KAARTDIENST_STORING or thuis is KAARTDIENST_STORING
        if doel is None and bron_adres == "agenda" and (a.get("locatie") or "").strip():
            for alternatief, bron in alternatieve_adressen(a, info):
                if alternatief == adres:
                    continue
                gevonden = coord(alternatief, cache)
                if gevonden is KAARTDIENST_STORING:
                    kaartstoring = True
                elif gevonden:
                    adres, doel = alternatief, gevonden
                    bron_adres = f"{bron} (plaats in de agenda niet op de kaart)"
                    a["_bron_adres"] = bron_adres
                    regels.append(f"{a['start'][:16]} {_toon(a, 45)}: agenda-plaats niet op de kaart; "
                                  f"rit via {bron}")
                    break
        buiten.append((start, einde, a, info, adres, fysiek, doel, kaartstoring))
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
            if is_zorgschaduw(x) or "T" not in x.get("start", "") or x.get("hele_dag"):
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
        if is_zorgschaduw(x) or "T" not in x.get("start", "") or x.get("hele_dag"):
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

    def rijdend_toegestaan(x):
        """Een intern overleg op een werkagenda zonder fysieke plek mag tijdens het rijden (mandaat Mehdi 23-09-2026);
        het houdt een ketenrit dus niet tegen. Lara en privé tellen altijd als echte afspraak."""
        ix = lees_titel(x.get("titel") or "")
        plek = (x.get("locatie") or "").strip().lower()
        return (ix["soort"] == "IN" and not ix["buiten"] and not ix["reistijd"]
                and x.get("kalender") not in PRIVE_KALENDERS and (not plek or plek.startswith("http")))

    def keten_tussen_eindes(grens, aankomst, doel, rijdend_vrij=False):
        """Eindes van echte getimede afspraken tussen de vorige buitenplek en de volgende aankomst. Met rijdend_vrij
        tellen interne overleggen die tijdens het rijden mogen niet mee."""
        uit = []
        for x in items:
            if (x is doel or is_zorgschaduw(x) or x.get("hele_dag") or is_eigen_rit(x) or bellen.afgezegd(x)
                    or lara_vervalt(x) or "T" not in x.get("start", "") or "T" not in x.get("einde", "")
                    or (rijdend_vrij and rijdend_toegestaan(x))):
                continue
            try:
                xs, xe = datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["einde"])
            except (ValueError, TypeError):
                continue
            if xe > nu and grens < xe and xs < aankomst:
                uit.append(xe)
        return uit

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
                regels.append(f"{a_['start'][:16]} {_toon(a_, 40)}: er staat al een rit naar huis, die telt")
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
                    c1 = rij[i][6] if rij[i][5] else None
                    c2 = rij[i + 1][6] if rij[i + 1][5] else None
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
                    regels.append(f"{a_['start'][:16]} {_toon(a_, 40)}: geen tijd om tussendoor naar huis te gaan, "
                                  f"rechtstreeks naar {_toon(a_volgend, 30)}")
                    bureau = None
            naar_huis_na[sleutel_] = bool(bureau)
            if bureau:
                regels.append(f"{a_['start'][:16]} {_toon(a_, 40)}: VRAAG om {bureau['start'][11:16]} "
                              f"'{_toon(bureau, 30)}' achter het bureau, om {a_volgend['start'][11:16]} weer buiten. "
                              f"Ik reken dat je tussendoor naar huis gaat. Klopt dat, of doe je het vanuit de auto?")

    afspraak_per_sleutel = {(x["kalender"], x.get("id"), x["start"]): x for x in items if "T" in (x.get("start") or "")}
    for start, einde, a, info, adres, fysiek, doel, kaartstoring in buiten:
        dag = a["start"][:10]
        sleutel = (a["kalender"], a.get("id"), a["start"])
        vorige = vorige_per_dag.get(dag)
        bron_adres = a.get("_bron_adres") or "agenda"
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
                regels.append(f"{a['start'][:16]} {_toon(a, 50)}: geen adres, geen reistijd")
            zonder_plek()
            continue
        if not (doel and thuis):
            geen_adres += 1
            if kaartstoring:
                regels.append(f"{a['start'][:16]} {_toon(a, 50)}: kaartdienst niet beschikbaar; volgende ronde opnieuw")
            else:
                regels.append(f"{a['start'][:16]} {_toon(a, 50)}: adres niet gevonden ({adres[:40]})")
            if doel is None and not kaartstoring and start > nu and niet_op_kaart is not None:
                niet_op_kaart.add((a.get("kalender"), a.get("id"), a.get("start")))
            zonder_plek()
            continue
        vorige_einde = None   # gezet als hij rechtstreeks van de vorige afspraak komt
        vorige_a = None
        if vorige is None or naar_huis_na.get(vorige[0]):
            vertrek_van, van_adres = thuis, THUIS
        elif vorige[1] is None:
            vertrek_van, van_adres = thuis, THUIS
            regels.append(f"{a['start'][:16]} {_toon(a, 40)}: VRAAG de vorige buitenafspraak heeft geen adres, "
                          f"ik reken de rit vanaf thuis")
        else:
            vertrek_van, van_adres, vorige_einde = vorige[1], vorige[2], vorige[3]
            vorige_a = afspraak_per_sleutel.get(vorige[0])
        keten_einde = vorige_einde  # onveranderlijke grens, ook als er tussendoor een extern gesprek is
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
                    regels.append(f"{a['start'][:16]} {_toon(a, 40)}: geen terugrit, "
                                  f"'{_toon(x, 30)}' gaat zelf naar huis")
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
            handmatig = handmatige_rit_bij(a, "voor")
            if handmatig:
                return handmatig
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
            handmatig = handmatige_rit_bij(a, "na")
            if handmatig:
                return handmatig
            for x in reistijden:
                if x["kalender"] == a["kalender"] and "T" in x["start"] and datetime.fromisoformat(x["start"]) in vertrekken:
                    return x
            for x in reistijden:
                if (x["kalender"] == a["kalender"] and "T" in x["start"] and not _mijn(x)
                        and einde <= datetime.fromisoformat(x["start"]) <= einde + timedelta(hours=3)):
                    return x
            return None
        bestaand_heen = heenblok()
        keten_gat = False
        if keten_einde and is_eigen_rit(bestaand_heen or {}):
            merk = bestaand_heen.get("_merk") or {}
            try:
                echt_vertrek = datetime.fromisoformat(merk[VERTREKMERK])
            except (KeyError, ValueError, TypeError):
                echt_vertrek = None
            grenzen = keten_tussen_eindes(keten_einde, datetime.fromisoformat(bestaand_heen["einde"]), a)
            gewenst_begin = max([keten_einde] + [e for e in grenzen if echt_vertrek and e <= echt_vertrek])
            grenzen = keten_tussen_eindes(keten_einde, datetime.fromisoformat(bestaand_heen["einde"]), a,
                                          rijdend_vrij=True)
            keten_gat = (datetime.fromisoformat(bestaand_heen["start"]) != gewenst_begin
                         or merk.get(KETENMERK) != keten_einde.isoformat()
                         or not echt_vertrek
                         or not (datetime.fromisoformat(bestaand_heen["start"]) <= echt_vertrek
                                 <= datetime.fromisoformat(bestaand_heen["einde"]))
                         or any(e > echt_vertrek for e in grenzen))
        if (bestaand_heen and (terugblok() or not is_laatste) and not keten_gat
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
            regels.append(f"{a['start'][:16]} {_toon(a, 50)}: rijtijd niet berekend ({type(e).__name__})")
            continue
        plaats = ritlabel(adres, van_adres)
        van_plaats = ritlabel(van_adres, adres)
        # Bij een krappe overgang komt de rit op tijd aan. Een eigen verschuifbare vorige
        # afspraak krijgt een vertrekvraag; bij twee vaste afspraken volgt een nood.
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
            regels.append(f"{a['start'][:16]} {_toon(a, 40)}: LET OP, extern gesprek "
                          f"'{_toon(lopend[0][2], 30)}' loopt nog bij vertrek; rijdend kan dat niet")
        if reden_aankomst:
            regels.append(f"{a['start'][:16]} {_toon(a, 40)}: aankomst {aankomst:%H:%M} in plaats van "
                          f"{start:%H:%M}, want '{_toon(reden_aankomst, 30)}' doe je geparkeerd, niet rijdend")
        rit_start = aankomst - timedelta(minutes=heen)
        tussen_eindes = keten_tussen_eindes(keten_einde, aankomst, a) if keten_einde else []
        if keten_einde:
            # Een afspraak die na het geplande vertrek eindigt, gaat door de bestaande TE KRAP-route.
            later = [e for e in keten_tussen_eindes(keten_einde, aankomst, a, rijdend_vrij=True) if e > rit_start]
            if later:
                vorige_einde = max([e for e in [vorige_einde] if e] + later)
                if vorige_einde != keten_einde:
                    tussen_a = next((x for x in items if x is not a and not is_zorgschaduw(x) and not x.get("hele_dag")
                                     and not is_eigen_rit(x) and not bellen.afgezegd(x) and not rijdend_toegestaan(x)
                                     and "T" in (x.get("einde") or "")
                                     and datetime.fromisoformat(x["einde"]) == vorige_einde), None)
                    if tussen_a is not None:
                        vorige_a = tussen_a
        te_krap = False
        if vorige_einde and rit_start < vorige_einde:
            ruimte = (aankomst - vorige_einde).total_seconds() / 60
            if ruimte < heen - BUFFER_MIN:
                # Een rit eindigt nooit na het begin van de afspraak waarvoor hij rijdt: vertrek wordt op tijd gepland.
                te_krap = True
                rijden = max(heen - BUFFER_MIN, 5) if heen > BUFFER_MIN else heen
                vorige_naam = re.sub(r"^\s*VR\s+", "", _toon(vorige_a, 40)) if vorige_a else "vorige afspraak"
                volgende_naam = re.sub(r"^\s*VR\s+", "", _toon(a, 40))
                if vorige_a and not _is_vaste_afspraak(vorige_a) and _duur_vr_mogelijk(vorige_a) and _is_vaste_afspraak(a):
                    vorige_a["_te_krap_vr"] = (a, rit_start, rijden, start)
                    regels.append(f"{a['start'][:16]} {_toon(a, 40)}: VRAAG: vertrek om {rit_start:%H:%M} bij "
                                  f"{vorige_naam} voor {volgende_naam}; korter maken of de volgende verzetten?")
                else:
                    regels.append(f"{a['start'][:16]} {_toon(a, 40)}: NOOD: TE KRAP: kies welke afspraak schuift "
                                  f"({vorige_naam} tot {vorige_einde:%H:%M}, vertrek {rit_start:%H:%M} voor {volgende_naam}, "
                                  f"rijden duurt {rijden} min, er is {ruimte:.0f} min)")
            else:
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
            # Een ketenblok omvat ook wachttijd; alleen vanaf het gemerkte vertrek is er rijtijd.
            heen = int((datetime.fromisoformat(_x["einde"]) - _rit_vertrek(_x)).total_seconds() // 60)
            fh = "live"
            rit_start = aankomst - timedelta(minutes=heen)
            if vorige_einde and not te_krap and rit_start < vorige_einde:
                rit_start = vorige_einde
        laatste_vertrek = rit_start
        keten_einde_merk = keten_einde if not te_krap else None
        blok_start = (max([keten_einde] + [e for e in tussen_eindes if e <= laatste_vertrek])
                      if keten_einde_merk and keten_einde < laatste_vertrek else rit_start)
        wacht_min = int((laatste_vertrek - blok_start).total_seconds() // 60)
        vertrek_min = int((start - laatste_vertrek).total_seconds() // 60)
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
                regels.append(f"{a['start'][:16]} {_toon(a, 40)}: vertrek naar huis pas {terug_start:%H:%M}, "
                              f"eerst een extern gesprek geparkeerd")

        def bijwerken(x, s, e, tekst, titel, melding=None, vertrek=None, keten_vanaf=None):
            """Een blok dat ik zelf maakte, pas ik aan als de rijtijd meer dan 10 min verschilt,
            en altijd als titel of kleur niet meer klopt met de afspraak waarvoor ik rijd."""
            if not is_eigen_rit(x):
                return False
            oud_vertrek = _rit_vertrek(x) if vertrek else datetime.fromisoformat(x["start"])
            duur_oud = (datetime.fromisoformat(x["einde"]) - oud_vertrek).total_seconds() / 60
            wijzig = {}
            begint_te_vroeg = (bool(vorige_einde) and not te_krap and datetime.fromisoformat(x["start"]) < vorige_einde
                                and not (keten_vanaf and datetime.fromisoformat(x["start"]) == keten_vanaf))
            doel_duur = (e - (vertrek or s)).total_seconds() / 60
            keten_begin_fout = keten_vanaf is not None and datetime.fromisoformat(x["start"]) != s
            if (abs(duur_oud - doel_duur) >= 10 or datetime.fromisoformat(x["einde"]) != e
                    or begint_te_vroeg or keten_begin_fout):
                wijzig.update({"start": {"dateTime": s.isoformat()}, "end": {"dateTime": e.isoformat()}, "description": tekst})
            if x.get("titel") != titel:
                wijzig["summary"] = titel
            if tekst != (x.get("omschrijving") or ""):
                wijzig["description"] = tekst
            if (x.get("_kleur") or "") != rit_kleur.get("colorId", ""):
                wijzig["colorId"] = rit_kleur.get("colorId") or None
            r = x.get("_reminders") or {}
            if melding is not None and (r.get("useDefault", True) or (r.get("overrides") or []) != melding):
                wijzig["reminders"] = {"useDefault": False, "overrides": melding}
            privaat = dict(x.get("_merk") or {})
            if vertrek is not None:
                privaat[VERTREKMERK] = vertrek.isoformat()
            if keten_vanaf is not None:
                privaat[KETENMERK] = keten_vanaf.isoformat()
            else:
                privaat.pop(KETENMERK, None)
            if privaat != (x.get("_merk") or {}):
                wijzig["extendedProperties"] = {"private": privaat}
            if wijzig:
                _patch(x, wijzig, tok, eigen_rit=True)
                if "start" in wijzig:
                    x["start"], x["einde"] = s.isoformat(), e.isoformat()
                if "summary" in wijzig:
                    x["titel"] = titel
                if "description" in wijzig:
                    x["omschrijving"] = tekst
                if "colorId" in wijzig:
                    x["_kleur"] = rit_kleur.get("colorId") or ""
                if "reminders" in wijzig:
                    x["_reminders"] = wijzig["reminders"]
                if "extendedProperties" in wijzig:
                    x["_merk"] = privaat
                return True
            return False
        uitleg_h = f"Reistijd voor: {a['titel']} ({heen} min = " + ("live verkeer Google" if fh == "live" else f"vrije rijtijd x filefactor {fh}") + f" + {BUFFER_MIN} min buffer, OSRM; adres uit {bron_adres}; rit {van_plaats} → {plaats})"
        if keten_einde_merk and wacht_min:
            uitleg_h += (f" ({heen} min rijden, waarvan {wacht_min} min wachten voor vertrek zodat er niet geboekt "
                         f"kan worden; vertrek uiterlijk {laatste_vertrek:%H:%M})")
        uitleg_t = f"Reistijd na: {a['titel']} ({terug} min = " + ("live verkeer Google" if ft == "live" else f"vrije rijtijd x filefactor {ft}") + f" + {BUFFER_MIN} min buffer, OSRM; rit {plaats} → thuis)"
        # Een rit hoort bij de afspraak waarvoor je rijdt: zelfde agenda, zelfde kleur. Een
        # rit voor Lara staat roze op de agenda van Lara, een privérit zwart op privé. Rood
        # is alleen voor werk. Anders zien collega's op je werkagenda dat je ergens heen
        # gaat, zonder wat, en weer terugkomt. Mandaat van Mehdi, 21-09-2026.
        # De kleur komt uit dezelfde regel die elke afspraak nakijkt, zodat maker en
        # controleur het nooit oneens kunnen zijn.
        _wens = kleur_gewenst({"kalender": a["kalender"]}, {"reistijd": True})
        rit_kleur = {"colorId": _wens} if _wens else {}
        # Een Google-herinnering op een blok kan alleen vóór zijn begin afgaan. Bij wachttijd staat daarom de
        # vertrekmelding op de afspraak zelf; de rit krijgt geen te vroege herinnering.
        heen_melding = [] if wacht_min else [{"method": "popup", "minutes": 5}]
        try:
            x = heenblok()
            if x:
                al += 1
                if bijwerken(x, blok_start, aankomst, uitleg_h, f"🚗 Reistijd: {van_plaats} → {plaats}",
                             heen_melding, laatste_vertrek, keten_einde_merk):
                    gemaakt += 1
                # Een afspraak heeft precies één heenrit. Staat er nog een tweede eigen heenrit voor dezelfde afspraak, dan
                # haal ik die weg. Gezien 30-09-2026: 'Sint-Lambrechts-Woluwe -> Mechelen' stond twee keer, nadat de oude rit
                # 'thuis -> Mechelen' was herrekend terwijl de nieuwe al bestond (FR-76).
                for y in [y for y in reistijden if y is not x and y["kalender"] == a["kalender"] and _mijn(y)
                          and y["start"][:10] == a["start"][:10] and rit_hoort_bij(y, a["titel"], "voor")]:
                    if _eigen_rit_weg(y, tok):
                        reistijden.remove(y)
                        regels.append(f"{a['start'][:16]} {_toon(a, 44)}: dubbele heenrit weggehaald")
            elif not handmatige_rit_bij(a, "voor"):
                heen_privaat = _nieuwe_rit()
                heen_privaat["extendedProperties"]["private"][VERTREKMERK] = laatste_vertrek.isoformat()
                if keten_einde_merk:
                    heen_privaat["extendedProperties"]["private"][KETENMERK] = keten_einde_merk.isoformat()
                _insert(a["kalender"], {"summary": f"🚗 Reistijd: {van_plaats} → {plaats}", "start": {"dateTime": blok_start.isoformat()},
                                        "end": {"dateTime": aankomst.isoformat()}, "description": uitleg_h,
                                        **rit_kleur, "reminders": {"useDefault": False, "overrides": heen_melding},
                                        **heen_privaat}, tok)
                gemaakt += 1
            else:
                al += 1
            x = terugblok() if is_laatste else None
            if not is_laatste:
                regels.append(f"{a['start'][:16]} {_toon(a, 44)}: geen rit naar huis, je gaat door naar de volgende afspraak")
                oud_terug = terugblok()
                # terugblok() geeft de rit die op het einde van deze afspraak vertrekt; mijn eigen terugrit
                # herken ik aan zijn merk, niet aan de titel (die kan intussen veranderd zijn, bv. ?? eraf)
                if oud_terug and "Reistijd na:" in (oud_terug.get("omschrijving") or "") \
                        and _eigen_rit_weg(oud_terug, tok):
                    reistijden.remove(oud_terug) if oud_terug in reistijden else None
                    regels.append(f"{a['start'][:16]} {_toon(a, 44)}: mijn oude rit naar huis weggehaald, "
                                  f"er komt nog een buitenafspraak na")
                # ook een terugrit van mij die nog op het oude einde staat (gezien 01-10-2026: Lara ophalen eindigde om
                # 16:10 in plaats van 17:00, en 'De Speelkriebel -> thuis' om 17:00 bleef staan, FR-78)
                for y in [y for y in reistijden if y is not oud_terug and y["kalender"] == a["kalender"] and _mijn(y)
                          and y["start"][:10] == a["start"][:10] and rit_hoort_bij(y, a["titel"], "na")]:
                    if _eigen_rit_weg(y, tok):
                        reistijden.remove(y)
                        regels.append(f"{a['start'][:16]} {_toon(a, 44)}: mijn oude terugrit (ander einde) weggehaald")
            if is_laatste:
                # precies één terugrit: een tweede eigen terugrit voor deze afspraak (op een oud einde) gaat weg (FR-78)
                for y in [y for y in reistijden if y is not x and y["kalender"] == a["kalender"] and _mijn(y)
                          and y["start"][:10] == a["start"][:10] and rit_hoort_bij(y, a["titel"], "na")]:
                    if _eigen_rit_weg(y, tok):
                        reistijden.remove(y)
                        regels.append(f"{a['start'][:16]} {_toon(a, 44)}: dubbele terugrit weggehaald")
            if x:
                al += 1
                if bijwerken(x, terug_start, terug_start + timedelta(minutes=terug), uitleg_t, f"🚗 Reistijd: {plaats} → thuis", []):
                    gemaakt += 1
            elif is_laatste and not handmatige_rit_bij(a, "na"):
                _insert(a["kalender"], {"summary": f"🚗 Reistijd: {plaats} → thuis", "start": {"dateTime": terug_start.isoformat()},
                                        "end": {"dateTime": (terug_start + timedelta(minutes=terug)).isoformat()}, "description": uitleg_t,
                                        **{**rit_kleur, "reminders": {"useDefault": False, "overrides": []}}, **_nieuwe_rit()}, tok)
                gemaakt += 1
            elif is_laatste:
                al += 1
            # de rit is van Mehdi, de afspraak van een collega: op een firmakopie geen vertrekmelding (Codex-hertest 6)
            melding = _vertrekmelding_zetten(a, vertrek_min + 5, tok) if not _firma_kopie(a) else False
            regels.append(f"{a['start'][:16]} {_toon(a, 44)}: {van_plaats} → {plaats} {heen} min (file x{fh})"
                          + (f", terug naar huis {terug} min (file x{ft})" if is_laatste else ", daarna door naar de volgende")
                          + f", adres uit {bron_adres}"
                          + (f", melding {vertrek_min + 5} min vooraf" if melding else ", geen extra vertrekmelding"))
        except Exception as e:  # noqa: BLE001
            fout += 1
            regels.append(f"{a['start'][:16]} {_toon(a, 50)}: reistijd niet gezet ({type(e).__name__})")
    # Een rit die ik zelf maakte en waarvan de afspraak weg of verzet is, meld ik. Een
    # heenrit eindigt op het begin van zijn afspraak, een terugrit begint op het einde.
    # Ik verwijder hem niet zelf; dat beslist Mehdi.
    grenzen = set()
    gemerkt = 0
    elders = {}          # tijdstip -> agenda's met een afspraak die dan begint of eindigt
    begins_alle, eindes_alle = set(), set()
    for x in items:
        _lx = lees_titel(x["titel"]) if "T" in x.get("start", "") else None
        # alleen een afspraak die een rit heeft, houdt een rit vast; een afspraak die geen rit meer vraagt (Lara
        # 'overgeslagen', zonder !!) niet (FR-79, gezien 01-10-2026). Ook een Lara-afspraak op een officiële
        # vakantiedag of met 'vervalt' vooraan niet: dan ruim ik haar eigen ritten op (FR-210)
        if _lx and not _lx["reistijd"] and (_lx["buiten"] or _lx["soort"] in BUITEN_SOORTEN) \
                and not lara_zonder_rit(x, vrij):
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
        # een rit van een afspraak die geen rit meer vraagt (vervallen, of Lara op een officiële vakantiedag) hangt niet
        # meer aan een toevallig gesprek dat op zijn einde begint (reviewronde 27-10-2026, FR-210)
        _mr = re.search(r"Reistijd (?:voor|na): (.+?) \(\d+ min", x.get("omschrijving") or "")
        _van_zonder_rit = bool(_mr) and any(lara_zonder_rit(y, vrij) and y.get("start", "")[:10] == x["start"][:10]
                                            and y.get("kalender") == x.get("kalender")
                                            and titel_sleutel(zonder_vervalt(y["titel"])) == titel_sleutel(zonder_vervalt(_mr.group(1)))
                                            for y in items)
        if "Reistijd voor:" in (x.get("omschrijving") or ""):
            vast = (x["kalender"], e0) in grenzen or (e0 in begins_alle and not _van_zonder_rit)
        else:
            vast = (x["kalender"], s0) in grenzen or (s0 in eindes_alle and not _van_zonder_rit) or (x["kalender"], e0) in grenzen
        if vast and s0 >= nu and _rit_tekst(x) and not (x.get("_merk") or {}).get(RITMERK) and gemerkt < RIT_MERKEN_PER_RONDE \
                and sum(1 for y in reistijden if y.get("kalender") == x["kalender"] and y.get("start") == x["start"]
                        and y.get("einde") == x["einde"]) == 1 and len(_afspraak_van_rit(x, items, s0, e0)) == 1:
            # gecontroleerde overgang (Codex A10): een oude rit krijgt zijn merk alleen als hij aan precies een afspraak
            # hangt waarvan zijn omschrijving de titel draagt, op het juiste tijdstip, en geen tweeling heeft. Een tijd die
            # toevallig past volstaat niet (ronde 3). De rest blijft zonder merk en komt als 'rit zonder afspraak' in de
            # meldingen zodra hij nergens meer aan hangt.
            try:
                _patch(x, {"extendedProperties": {"private": {RITMERK: x["id"]}}}, tok)
                x.setdefault("_merk", {})[RITMERK] = x["id"]
                gemerkt += 1
            except Exception:  # noqa: BLE001
                pass
        if s0 >= nu and not vast and ONGELEZEN:
            # een agenda die deze ronde niet gelezen is, kan de afspraak van deze rit bevatten: niet verhuizen of
            # weghalen op een onvolledige lezing (Codex A15, A17)
            regels.append(f"{x['start'][:16]} {x['titel'][:50]}: rit zonder afspraak, niet opgeruimd ({len(ONGELEZEN)} agenda('s) niet gelezen)")
            continue
        if s0 >= nu and not vast and not is_eigen_rit(x):
            regels.append(f"{x['start'][:16]} {x['titel'][:50]}: rit zonder afspraak (zonder mijn merk: ik verhuis of haal hem niet weg)")
            continue
        if s0 >= nu and not vast:
            # Staat de afspraak intussen op een andere agenda (privé in plaats van werk), dan
            # verhuist mijn rit mee. Gezien 24-09-2026: de ritten voor een privé-afspraak van
            # 23-09 bleven rood op de werkagenda staan, zichtbaar voor collega's.
            m = re.search(r"Reistijd (?:voor|na): (.+?) \(\d+ min", x.get("omschrijving") or "")
            bij = [y for y in items if m and not lees_titel(y["titel"])["reistijd"] and y["start"][:10] == x["start"][:10]
                   and titel_sleutel(y["titel"]) == titel_sleutel(m.group(1)) and not lara_zonder_rit(y, vrij)]
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
    oproep volstaat. Online: BEL_ONLINE_MIN minuten vooraf. Buiten: op het gemerkte echte
    vertrekmoment van mijn rit, anders BEL_BUITEN_MIN vooraf. Niet voor intern (IN),
    terugkerend, hele dag, reistijd, Lara, feestdagen."""
    from datetime import timedelta
    reistijden = [x for x in items if lees_titel(x["titel"])["reistijd"] and "T" in x["start"]]
    regels = []
    for a in items:
        if (a.get("hele_dag") or a.get("_terugkerend") or a["start"][:10] < vandaag
                or a.get("kalender", "").startswith("en.be#") or bellen.afgezegd(a)):
            continue
        kal = KALENDERS.get(a["kalender"], "")
        info = lees_titel(a["titel"])
        if info["reistijd"] or info["soort"] == "IN" or kal == "Lara" or lara_vervalt(a):
            continue
        start = datetime.fromisoformat(a["start"])
        adres = a.get("locatie") or ""
        buiten = (info["buiten"] or info["soort"] in ("KB", "PB")
                  or (adres and not adres.lower().startswith("http"))) and not is_thuis_adres(adres)
        if buiten:
            # de heenrit van DEZE afspraak: zijn omschrijving noemt haar, of hij eindigt op haar begin (plus of min vijf
            # minuten). Nooit zomaar de laatste rit binnen drie uur: die kan bij een andere afspraak horen (Codex A14).
            venster = [x for x in reistijden if (start - timedelta(hours=3) <= datetime.fromisoformat(x["start"]) < start
                       or (is_eigen_rit(x) and (x.get("_merk") or {}).get(KETENMERK)
                           and x["start"][:10] == a["start"][:10] and datetime.fromisoformat(x["start"]) < start))
                       and "Reistijd na:" not in (x.get("omschrijving") or "")]
            blok = [x for x in venster if x["kalender"] == a["kalender"] and rit_hoort_bij(x, a["titel"], "voor")] or \
                [x for x in venster if x["kalender"] == a["kalender"]
                 and abs(datetime.fromisoformat(x["einde"]) - start) <= timedelta(minutes=5)]
            # Een oproep betekent altijd: je hebt vijf minuten om iets te doen (Mehdi, 25-09-2026). Buiten dus
            # vijf minuten voor het vertrek, zoals de melding op de rit; online vijf minuten voor het begin.
            # Zonder reistijdblok ken ik het vertrek niet: dan reken ik BEL_BUITEN_MIN rijden en bel ik ook
            # vijf minuten voor dat vertrek. Het afsprakennummer betekent altijd vijf minuten, nooit dertig
            # (Mehdi, 25-09-2026: "als hij belt, altijd vijf minuten van tevoren").
            vertrek = _rit_vertrek(blok[-1]) if blok else start - timedelta(minutes=BEL_BUITEN_MIN)
            beltijd = vertrek - timedelta(minutes=BEL_ONLINE_MIN)
            hoe = f"over {BEL_ONLINE_MIN} minuten vertrekken"
        else:
            beltijd = start - timedelta(minutes=BEL_ONLINE_MIN)
            hoe = f"over {BEL_ONLINE_MIN} minuten " + ("thuis" if is_thuis_adres(adres) else "online")
        prive = is_prive(a)       # het rooster gaat naar Dropbox: een privé-titel nooit (Codex A25)
        klant = "je privé-afspraak" if prive else (info["klant"] or a["titel"][:60])
        tekst = f"Mehdi, {hoe}: {klant}, om {start.strftime('%H:%M')}." + (" De link staat in je agenda." if not buiten else " Adres staat in je agenda.")
        regels.append({"sleutel": f"{a['kalender']}:{a['id']}:{a['start']}", "tijd": beltijd.isoformat(), "tekst": tekst,
                       "titel": "privé-afspraak" if prive else a["titel"][:80],
                       # de titel kan gemaskeerd zijn: het Lara-merk blijft, zodat een afzegging nooit 'niet vertrekken'
                       # wordt (Codex-hertest 13)
                       "lara": bellen.is_lara_titel(a["titel"])})
    regels.sort(key=lambda r: r["tijd"])
    return regels


ROOSTER_ONZEKER = 0      # oproepen uit het vorige rooster die niet te verifiëren waren en dus wegvielen (Codex A15)


def _regel_delen(r):
    """(agenda, id, begin) uit de sleutel van een roosterregel (agenda:id:begin)."""
    delen = (r.get("sleutel") or "").split(":", 2)
    return tuple(delen) if len(delen) == 3 else ("", "", "")


def _nakijken(regels, tok=None, ritten=(), noden=None):
    """Houdt alleen de roosterregels waarvan het item er nog zo staat (events.get): niet geschrapt en op hetzelfde begin.
    Niet te lezen telt als weg: De Bode belt nooit op basis van een regel die niet nagekeken is (Codex A15). Geeft
    (goede regels, aantal weggevallen)."""
    goed, weg = [], 0
    vandaag = nu_lokaal().date().isoformat()
    for r in regels:
        kal, eid, begin = _regel_delen(r)
        try:
            ev = _event({"kalender": kal, "id": eid}, tok or agenda._toegang())
            ev_start = (ev.get("start") or {}).get("dateTime")
            klopt = not bellen.afgezegd(ev) and _zelfde_tijd(ev_start, begin)
            item = {"id": eid, "kalender": kal, "titel": ev.get("summary") or "", "start": ev_start or "",
                    "einde": (ev.get("end") or {}).get("dateTime") or "", "locatie": ev.get("location") or "",
                    "omschrijving": ev.get("description") or "",
                    "hele_dag": "date" in (ev.get("start") or {}), "_terugkerend": bool(ev.get("recurringEventId"))}
            rit_actueel = []
            for rit in ritten:
                if rit.get("kalender") != kal or not rit.get("id") or not rit.get("start") or not rit.get("einde"):
                    continue
                try:
                    if abs(datetime.fromisoformat(rit["einde"]) - datetime.fromisoformat(ev_start)) > timedelta(minutes=5):
                        continue
                    rv = _event({"kalender": kal, "id": rit["id"]}, tok or agenda._toegang())
                    rit_vers = {**rit, "titel": rv.get("summary") or "", "omschrijving": rv.get("description") or "",
                                "start": (rv.get("start") or {}).get("dateTime") or "",
                                "einde": (rv.get("end") or {}).get("dateTime") or "",
                                "_merk": ((rv.get("extendedProperties") or {}).get("private") or {})}
                    if (rv.get("status") != "cancelled" and rit_vers["start"] and rit_vers["einde"]
                            and lees_titel(rit_vers["titel"])["reistijd"]
                            and abs(datetime.fromisoformat(rit_vers["einde"]) - datetime.fromisoformat(ev_start))
                            <= timedelta(minutes=5)):
                        rit_actueel.append(rit_vers)
                except Exception:  # noqa: BLE001
                    pass
            # ook de inhoud opnieuw beoordelen: een afspraak die intern of privé werd, krijgt geen oude oproeptekst (ronde 6)
            vers = belrooster([item] + rit_actueel, vandaag) if klopt else []
            info = lees_titel(item["titel"])
            if vers and not rit_actueel and (item["locatie"] and not item["locatie"].lower().startswith("http")
                                            or info["buiten"] or info["soort"] in ("KB", "PB")):
                if noden is not None:
                    noden.append({"tekst": "Beltijd met vaste reistijdschatting berekend: actueel reistijdblok niet "
                                          "te verifiëren; kijk het vertrek na", "wie": "mehdi"})
        except Exception:  # noqa: BLE001
            vers = []
        if vers:
            goed.append({**r, "tekst": vers[0]["tekst"], "titel": vers[0]["titel"], "tijd": vers[0]["tijd"],
                         "lara": vers[0].get("lara", False)})
        else:
            weg += 1
    return goed, weg


def _rooster_behouden(nieuw, onvolledig, nu=None, tok=None, ritten=(), noden=None):
    """De komende regels van het vorige belrooster voor de agenda's die deze ronde niet gelezen zijn ('archief' staat voor
    de archiefagenda's), elk nagekeken tegen het item zelf; wat wegvalt telt in ROOSTER_ONZEKER (Codex A15, ronde 3 en 4)."""
    global ROOSTER_ONZEKER
    ROOSTER_ONZEKER = 0
    nu = nu or nu_lokaal()
    try:
        with open(bellen.ROOSTER) as f:
            oud = json.load(f).get("regels", [])
    except (OSError, ValueError, AttributeError):
        return []
    al = {r.get("sleutel") for r in nieuw}
    kandidaten = []
    for r in oud:
        kal = _regel_delen(r)[0]
        try:
            t = datetime.fromisoformat(r["tijd"])
        except (KeyError, TypeError, ValueError):
            continue
        if r.get("sleutel") in al or t.tzinfo is None or t < nu - timedelta(minutes=bellen.VENSTER_MIN):
            continue
        if kal in onvolledig or ("archief" in onvolledig and kal not in KALENDERS):
            kandidaten.append(r)
    goed, ROOSTER_ONZEKER = _nakijken(kandidaten, tok, ritten, noden)
    return goed


def rooster_maken(items, archief, vandaag, noden, tok=None):
    """Het belrooster, uit een lezing NA de ritten: een nieuwe rit bepaalt het vertrek (Codex A14). Lukt die tweede lezing
    niet helemaal, dan de lezing van het begin van de ronde; de regels van de agenda's die de tweede keer faalden, worden dan
    eerst nagekeken tegen het item zelf (Codex A15, ronde 5: een intussen geschrapte afspraak hield zo haar oproep). Een
    agenda die al bij het begin niet gelezen was, houdt haar nagekeken regels uit het vorige rooster (ronde 3 en 4)."""
    try:
        ruw, arch = afspraken(-1, 8), archief_afspraken(-1, 8)
        stuk = {x["kalender"] for x in ruw if x.get("fout")} | ({"archief"} if ARCHIEF_FOUT else set())
        # per agenda: wat de tweede keer gelezen is, komt uit de tweede lezing; alleen een agenda die toen faalde, uit de
        # eerste (en die wordt hieronder nagekeken). Vroeger viel het hele rooster terug op de eerste lezing (ronde 6).
        voor = [x for x in ruw if not x.get("fout")] + ([] if ARCHIEF_FOUT else arch) + \
            [x for x in items + archief if x.get("kalender") in stuk or ("archief" in stuk and x.get("_archief"))]
    except Exception:  # noqa: BLE001
        voor, stuk = items + archief, {"*"}
    rooster = belrooster(voor, vandaag)
    weg = 0
    if stuk:
        te_kijken = [r for r in rooster if "*" in stuk or _regel_delen(r)[0] in stuk
                     or ("archief" in stuk and _regel_delen(r)[0] not in KALENDERS)]
        goed, weg = _nakijken(te_kijken, tok, voor, noden)
        rooster = [r for r in rooster if r not in te_kijken] + goed
        if ONGELEZEN:
            rooster += _rooster_behouden(rooster, set(ONGELEZEN), tok=tok,
                                         ritten=items + archief, noden=noden)
            weg += ROOSTER_ONZEKER
    if weg:
        noden.append({"tekst": f"{weg} oproep(en) vielen weg: de agenda was niet volledig te lezen en de afspraak kon niet "
                               "nagekeken worden (verzet, geschrapt of onleesbaar); kijk ze zelf na", "wie": "mehdi"})
    return sorted(rooster, key=lambda r: r["tijd"])


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


def is_thuis_adres(adres):
    """Alleen het bekende thuisadres, ook als Google nog ', België' toevoegt."""
    adres, thuis = _plat_adres(adres), _plat_adres(THUIS)
    return bool(adres and thuis and (adres == thuis or adres.startswith(thuis + " ")))


def _huisbezoek_locatie(locatie):
    return bool(re.search(r"\b(huisbezoek|aan[-\s]+huis|thuis)\b", locatie or "", re.I))


def _afspraak_is_huisbezoek(a, nu=None):
    if is_zorg_titel(a.get("titel")):
        return _zorg_huisbezoek(a, nu=nu)
    return _huisbezoek_locatie(a.get("locatie"))


def _bruikbare_locatie(locatie):
    """Een ingevulde agenda-plaats mag door coord() als naam of adres worden gezocht."""
    tekst = (locatie or "").strip()
    if (not tekst or _huisbezoek_locatie(tekst)
            or re.search(r"\b(?:[a-z][a-z0-9+.-]*://|www\.|[a-z0-9.-]+\.[a-z]{2,}/)\S*", tekst, re.I)
            or re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", tekst, re.I)):
        return False
    return True


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
            k = nummerlezer.lees(naam, "mapnaam_tkn")
            if k and patroon.search(_plat_adres(naam)):
                kandidaten.add(k[0].nummer)
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
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        if a.get("hele_dag") or "T" not in a.get("start", "") or a.get("_archief") \
                or a["titel"].lower().startswith("canceled"):
            continue
        if (not ook_verleden and _voorbij(a["start"], nu)) or (alleen_dag and a["start"][:10] != alleen_dag):
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
        extern = [g for g in a.get("deelnemers") or [] if not isinstance(g, str)
                  or g.strip().lower() not in _eigen_accounts()]
        if extern or a.get("_agendagasten") or a.get("_terugkerend") or a.get("_reeks"):
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: VOORSTEL '{nieuw}' ({bron})")
            continue
        try:
            _patch(a, {"summary": nieuw}, tok)
            a["titel"] = nieuw
            gezet += 1
            regels.append(f"{a['start'][:16]} {nieuw[:70]}: projectnummer {nr} ({bron})")
        except TitelVoorstel as e:
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: VOORSTEL '{nieuw}' ({e})")
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
        if a.get("hele_dag") or "T" not in a.get("start", "") or _voorbij(a["start"], nu) or a.get("_archief"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        if _firma_kopie(a):
            continue                    # de afspraak van een collega op een firma-agenda: daar schrijf ik niets
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
    zonder adres. Geeft [(sleutel, zin)], de zin is wat Mehdi moet doen, in een zin. De sleutels blijven zoals ze zijn:
    het belgeheugen ontdubbelt erop."""
    return [(sleutel, zin) for sleutel, zin, _ in _vastgelopen(items, nu, uren)]


def _adresvragen(items, nu=None, uren=24 * RIT_VOORUIT_ALLES, projecten=None, niet_op_kaart=None):
    """Elke komende buitenafspraak zonder bestemming of met een niet vindbare kaartplaats."""
    nu = nu or nu_lokaal()
    projecten = projectadressen.index() if projecten is None else projecten
    uit = []
    for a in items:
        if a.get("hele_dag") or _afspraak_is_huisbezoek(a, nu=nu):
            continue
        try:
            start = datetime.fromisoformat(a.get("start") or "")
        except ValueError:
            continue
        if not nu < start <= nu + timedelta(hours=uren):
            continue
        info = lees_titel(a.get("titel") or "")
        if info["reistijd"] or not (info["buiten"] or info["soort"] in BUITEN_SOORTEN):
            continue
        niet_gevonden = (a.get("kalender"), a.get("id"), a.get("start")) in (niet_op_kaart or ())
        if not niet_gevonden:
            if is_thuis_adres(a.get("locatie") or "") or _bruikbare_locatie(a.get("locatie")):
                continue
            if info["nummer"] and info["nummer"] in projecten and _bruikbare_locatie(projecten[info["nummer"]].get("adres")):
                continue
            try:
                plek, _ = plek_zoeken((a.get("titel") or "") + " " + (a.get("omschrijving") or ""))
                woord, vast = vaste_plek(a.get("titel") or "") if not plek else (None, None)
            except Exception:  # noqa: BLE001
                plek = vast = None
            if plek or vast and _bruikbare_locatie(vast.get("adres")):
                continue
        id_ = a.get("id") or hashlib.sha256(f"{a.get('kalender')}|{a.get('start')}|{a.get('titel')}".encode()).hexdigest()[:16]
        zin = (f"Mehdi, het adres van de buitenafspraak van {start:%d-%m %H:%M} vind ik niet op de kaart; "
               "schrijf het zoals op de kaart (straat nummer, postcode gemeente)." if niet_gevonden else
               f"Mehdi, de buitenafspraak van {start:%d-%m %H:%M}: zet het adres erin.")
        uit.append((f"{id_}:adres",
                    zin, [a.get("id")]))
    return uit


def _is_vaste_afspraak(a):
    """Vast: zorg, klant, Lara, een afspraak met gasten of van iemand anders. Eigen werfbezoek zonder gasten is verschuifbaar."""
    if not a:
        return False
    titel = a.get("titel") or ""
    info = lees_titel(titel)
    merk = a.get("_merk") or {}
    lara = (a.get("kalender") in AGENDA_VASTE_KLEUR
            and AGENDA_VASTE_KLEUR[a["kalender"]].get("naam") == "Lara") or info.get("firma") == "LARA"
    zorg = is_zorg_titel(titel) or bool(merk.get(ZORGMERK) or merk.get(ZORGPLAATSMERK))
    gasten = bool(a.get("deelnemers") or a.get("_agendagasten"))
    ander = not _van_mehdi(a) or is_calendly(a) or a.get("_organisator_zelf") is False
    eigen_werfbezoek = (not gasten and not ander
                        and (info.get("type") == "WB" or bool(re.search(r"\bwerfbezoek\b", titel, re.I))))
    klant = info.get("soort") in ("KB", "KO", "PB", "PO") and not eigen_werfbezoek
    return bool(zorg or klant or lara or gasten or ander)


def _te_krap_vr_voor(a, items):
    """Als een eigen verschuifbare afspraak het vertrek voor een vaste volgende afspraak blokkeert: (volgende, vertrek_dt)."""
    if _is_vaste_afspraak(a):
        return None
    try:
        start_a = datetime.fromisoformat(a["start"])
        einde_a = datetime.fromisoformat(a["einde"])
    except (KeyError, ValueError, TypeError):
        return None
    opgeslagen = a.get("_te_krap_vr")
    if opgeslagen:
        volgende, vertrek_dt, rijden, oorspr_start = opgeslagen
        if volgende in items:
            try:
                start_v = datetime.fromisoformat(volgende["start"])
                vertrek_nu = vertrek_dt + (start_v - oorspr_start)
                if einde_a > vertrek_nu and (start_v - einde_a).total_seconds() / 60 < rijden:
                    return volgende, vertrek_nu
            except (KeyError, ValueError, TypeError):
                pass
    for r in items:
        if not is_eigen_rit(r) or "Reistijd voor:" not in (r.get("omschrijving") or ""):
            continue
        if (r.get("start") or "")[:10] != (a.get("start") or "")[:10]:
            continue
        try:
            vertrek_r = _rit_vertrek(r)
        except (KeyError, ValueError, TypeError):
            continue
        if not (start_a < vertrek_r < einde_a):
            continue
        volgende = next((x for x in items if x is not a and not lees_titel(x.get("titel") or "")["reistijd"]
                         and x.get("start") == r.get("einde") and rit_hoort_bij(r, x.get("titel") or "", "voor")
                         and _is_vaste_afspraak(x)), None)
        if volgende:
            return volgende, vertrek_r
    return None


def te_krap_noden(regels):
    """Stabiele nood wanneer twee vaste afspraken te krap op elkaar volgen."""
    if any("TE KRAP" in r for r in (regels or [])):
        return [{"tekst": "TE KRAP: kies welke afspraak schuift", "wie": "mehdi"}]
    return []


def zonder_rit_indelen(rregels):
    """De regels van reistijd_zetten per reden waarom een buitenafspraak geen reistijd kreeg. 'Mijn rit zonder afspraak
    weggehaald' is een geslaagde opruiming, geen nood (F8, overleg 27-10-2026)."""
    zonder_rit = {"geen adres in de agenda": [], "adres niet gevonden": [], "rijtijd niet berekend": [],
                  "rit zonder afspraak": [], "buiten op een dag zonder auto": [],
                  "grendelbron niet te lezen (geen auto of vakantie)": []}
    for regel in rregels or []:
        if "geen adres, geen reistijd" in regel:
            # rsplit: in het uur staat zelf een dubbelpunt, dus split(":") hield alleen
            # "2026-09-21T16" over, zonder de afspraak. Gezien 21-09-2026.
            zonder_rit["geen adres in de agenda"].append(regel.rsplit(": geen adres", 1)[0][:80])
        elif "rit zonder afspraak" in regel and not regel.endswith(": mijn rit zonder afspraak weggehaald"):
            zonder_rit["rit zonder afspraak"].append(regel[:110])
        elif "grendelbron niet te lezen" in regel:
            zonder_rit["grendelbron niet te lezen (geen auto of vakantie)"].append(regel[:110])
        elif "BUITEN op een dag zonder auto" in regel:
            zonder_rit["buiten op een dag zonder auto"].append(regel[:110])
        elif "adres niet gevonden" in regel:
            zonder_rit["adres niet gevonden"].append(regel[:110])
        elif "rijtijd niet berekend" in regel:
            zonder_rit["rijtijd niet berekend"].append(regel[:110])
    return zonder_rit


def noden_voor_hartslag(noden, dag_arg):
    """F8 (overleg 27-10-2026): het bord sluit elke open nood die niet in de lijst staat. Een dagronde (--dag) ziet maar
    een dag en bouwt de mailnoden niet, dus ze mag noden openen maar nooit sluiten: open noden plus de nieuwe. Is het
    bord niet te lezen, dan geen lijst (None), zodat het bord niets sluit. Alleen de volledige ronde stuurt de
    gezaghebbende lijst."""
    return ag.noden_bij_breuk(noden) if dag_arg else noden


WEEKCONSOLIDATIE_MAP = os.path.expanduser("~/appportal/mijnagents-data/export/Agendawacht/weekconsolidatie")
WEEKNOOD = {"tekst": "Weekoverzicht van de Agendawacht ontbreekt: de weekconsolidatie liep niet goed. Start een "
                     "Claude-sessie om ze te herstellen en opnieuw te draaien.", "wie": "mehdi"}


def weekconsolidatie_anker(nu):
    """Zondag 20:00 Brussel voor de laatste maandag 06:00 Brussel: vanaf dan hoort er een weekoverzicht te zijn."""
    t = nu.astimezone(TIJDZONE)
    maandag = t.date() - timedelta(days=t.weekday())
    if t < datetime(maandag.year, maandag.month, maandag.day, 6, 0, tzinfo=TIJDZONE):
        maandag -= timedelta(days=7)
    zondag = maandag - timedelta(days=1)
    return datetime(zondag.year, zondag.month, zondag.day, 20, 0, tzinfo=TIJDZONE)


def weekconsolidatie_noden(weekmap=None, nu=None):
    """De weeknood (laag 4, overleg 27-10-2026): open zolang er sinds het anker geen geslaagd weekoverzicht is. Een
    geslaagde run schrijft altijd <week>.json met 'gemaakt'; een mislukte nooit. Alleen het tijdstip telt, niet het
    weeklabel, zodat ook een geslaagde herhaling met de hand de nood sluit. Een onleesbare map, een tijd zonder zone of
    een tijd in de toekomst telt nooit als geslaagd."""
    nu = nu or nu_lokaal()
    anker = weekconsolidatie_anker(nu)
    map_ = weekmap or WEEKCONSOLIDATIE_MAP
    try:
        namen = os.listdir(map_)
    except OSError:
        return [dict(WEEKNOOD)]
    for naam in namen:
        if not re.fullmatch(r"\d{4}-W\d{2}\.json", naam):
            continue
        try:
            with open(os.path.join(map_, naam), encoding="utf-8") as f:
                gemaakt = datetime.fromisoformat(str(json.load(f).get("gemaakt") or ""))
        except (OSError, ValueError, AttributeError, TypeError):
            continue
        if gemaakt.tzinfo is not None and anker <= gemaakt <= nu:
            return []
    return [dict(WEEKNOOD)]


def weekconsolidatie_fout(weekmap=None):
    """De laatste fout van de weekconsolidatie (laatste.json), alleen voor het detail van de hartslag."""
    try:
        with open(os.path.join(weekmap or WEEKCONSOLIDATIE_MAP, "laatste.json"), encoding="utf-8") as f:
            stand = json.load(f)
        return "" if stand.get("ok") else str(stand.get("fout") or "")[:120]
    except (OSError, ValueError, AttributeError):
        return ""


def _vastgelopen(items, nu=None, uren=48):
    """Zoals vastgelopen, met per vraag de volledige ID's van de betrokken afspraken. Een sleutel als 'dubbel:..',
    'zoompwd:<dag>' of 'wachtkamer:<meeting>' begint niet met een afspraak-ID, dus vragen_in_agenda kan de afspraak
    niet uit de sleutel halen (Codex A24, 15-10-2026)."""
    nu = nu or nu_lokaal()
    projecten = projectadressen.index()
    duur_minuten, duur_patroon = _duurregel()
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
        doel = _duur_doel(a, duur_minuten, duur_patroon)
        if (doel and not (a.get("_merk") or {}).get(DUURMERK) == str(duur_minuten)
                and _duur_botsing(a, items, doel) and _duur_vr_mogelijk(a)):
            huidig = int((datetime.fromisoformat(a["einde"]) - start).total_seconds() // 60)
            uit.append((f"{a['id']}:duur_ter_plaatse",
                        f"Mehdi, voor de afspraak van {start:%d-%m %H:%M}: "
                        f"Barsten en scheuren ter plaatse: 2 uur voorzien, nu {huidig} min; verleng tot {doel:%H:%M}.",
                        [a["id"]]))
        tvr = _te_krap_vr_voor(a, items)
        if tvr and _duur_vr_mogelijk(a):
            volgende, vertrek_nu = tvr
            vorige_naam = re.sub(r"^\s*VR\s+", "", _toon(a, 40))
            volgende_naam = re.sub(r"^\s*VR\s+", "", _toon(volgende, 40))
            uit.append((f"{a['id']}:te_krap_vertrek",
                        f"Mehdi, voor de afspraak van {start:%d-%m %H:%M}: "
                        f"vertrek om {vertrek_nu:%H:%M} bij {vorige_naam} voor {volgende_naam}; "
                        f"korter maken of de volgende verzetten?",
                        [a["id"]]))
        wanneer = f"{['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag'][start.weekday()]} om {start:%H:%M}"
        kort = re.sub(r"[^\w ]", " ", a["titel"])[:40].strip()
        if not info.get("firma") and a.get("kalender") == WERKAGENDA and not is_zorg_titel(a["titel"]):
            # een kine- of tandartsafspraak is privé, geen zakelijke vraag: de zorgstap zet ze op de privé-agenda
            uit.append((f"{a['id']}:firma", f"Mehdi, de afspraak van {wanneer}, {kort}: zeg voor welke firma en welke klant.", [a["id"]]))
    uit.extend(_adresvragen(items, nu, uren, projecten))
    # Twee klanten tegelijk: een zin per paar, wat Mehdi moet doen
    for a, b in dubbele_boekingen(items, nu, uren):
        s_ = datetime.fromisoformat(a["start"])
        dagnaam = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag'][s_.weekday()]
        na = lambda x: (lees_titel(x["titel"])["klant"] or x["titel"])[:30]
        sleutel = "dubbel:" + ":".join(sorted([a.get("id", "")[:16], b.get("id", "")[:16]]))
        uit.append((sleutel, f"Mehdi, {dagnaam} om {s_:%H:%M} staan twee afspraken tegelijk: {na(a)} en {na(b)}. Verzet er een.",
                    [a.get("id"), b.get("id")]))
    # Zoom zonder wachtwoord: een zin per dag voor alle klanten samen, want de klant raakt er niet in
    per_dag = {}
    for a in zoom_zonder_wachtwoord(items, nu, uren):
        per_dag.setdefault(a["start"][:10], []).append(a)
    for dag, lijst in sorted(per_dag.items()):
        namen = ", ".join(f"{(lees_titel(x['titel'])['klant'] or x['titel'])[:25]} om {x['start'][11:16]}" for x in lijst[:4])
        uit.append((f"zoompwd:{dag}", f"Mehdi, {len(lijst)} Zoom-afspraken op {dag[8:10]}-{dag[5:7]} hebben een link zonder wachtwoord "
                    f"({namen}): stuur de klant de uitnodiging vanuit Zoom.", [x.get("id") for x in lijst]))
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
                    uit.append((f"{b['a']['id']}:{b['soort']}", f"Mehdi, {dag[8:10]}-{dag[5:7]}: {b['tekst']}. Zeg wat ik doe.", [b["a"]["id"]]))
    # Zoom zonder wachtkamer: de klant staat meteen binnen (FR-63)
    for a, mid in zoom_zonder_wachtkamer(items, nu, uren):
        s_ = datetime.fromisoformat(a["start"])
        dagnaam = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag'][s_.weekday()]
        klant = (lees_titel(a["titel"])["klant"] or a["titel"])[:30]
        uit.append((f"wachtkamer:{mid}", f"Mehdi, de Zoom met {klant} van {dagnaam} om {s_:%H:%M} heeft geen wachtkamer: "
                    f"zet ze aan in Zoom bij die meeting, anders staat de klant meteen binnen.", [a.get("id")]))
    return uit


AGENDA_SLOT = "Details staan in je agenda."     # Mehdi leest Telegram niet voor de agenda (25-09-2026)
VR_REGEL = "Agendawacht vraagt: "


def _vraag_teruggelezen(a, tok, titel, oms):
    e = _lees_event(a.get("kalender"), a.get("id"), tok)
    return bool(e and (e.get("summary") or "") == canoniek(titel) and (e.get("description") or "") == oms)


def vragen_in_agenda(items, nu=None, niet_op_kaart=None):
    """Mehdi, 25-09-2026: 'ik lees de telegram niet voor de agenda ... de agenda zelf op een oogopslag geeft mij
    veel meer inzicht'. Wat de agent van hem nodig heeft, staat daarom in de afspraak zelf: VR (vraag) helemaal
    vooraan de titel en de vraag in een zin bovenaan de omschrijving. Opgelost: VR en de zin gaan er weer af.
    Ook een eigen buitenafspraak op privé of Lara krijgt VR. Geeft (gezet, weg)."""
    nu = nu or nu_lokaal()
    tok = agenda._toegang()
    open_ = {}
    for _, zin, ids in _vastgelopen(items, nu, uren=24 * 8):
        for id_ in ids:
            if id_:
                open_.setdefault(id_, zin)
    adresvragen = _adresvragen(items, nu, niet_op_kaart=niet_op_kaart)
    adres_ids = {id_ for _, _, ids in adresvragen for id_ in ids}
    for _, zin, ids in adresvragen:
        for id_ in ids:
            open_[id_] = zin
    gezet = weg = 0
    for a in items:
        if _firma_kopie(a):
            continue                    # gastkopie van een firma-afspraak: daar schrijf ik niets (Codex-hertest 6)
        eigen = (a.get("maker") or "").strip().lower() in _eigen_accounts()
        ander = a.get("kalender") in PRIVE_KALENDERS
        sluit_adres = ((a.get("titel") or "").startswith("VR ")
                       and any(s in (a.get("omschrijving") or "").split("\n", 1)[0]
                               for s in ("zet het adres erin", "vind ik niet op de kaart")))
        if (a.get("kalender") != WERKAGENDA and not ander or ander and a.get("id") not in adres_ids and not sluit_adres
                or ander and (a.get("_organisator_zelf") is not True or not eigen)
                or a.get("deelnemers") or a.get("_agendagasten") or a.get("_terugkerend") or a.get("_reeks")
                or a.get("_archief")):
            continue                      # ook geen collega als gast: die ziet titel en omschrijving (Codex A24, ronde 3)
        titel, oms = a["titel"], a.get("omschrijving") or ""
        zin = open_.get(a.get("id"))
        try:
            if zin and not titel.startswith("VR "):
                if len(oms) >= 1900:
                    oms = _volledige_omschrijving(a, tok)   # de lezing kapt af op 2000 tekens: nooit een ingekorte tekst terugschrijven
                schoon = re.sub(rf"^{VR_REGEL}[^\n]*\n*", "", oms)
                nieuw_oms = VR_REGEL + zin.split(": ", 1)[-1] + ("\n\n" + schoon if schoon else "")
                _patch(a, {"summary": "VR " + titel, "description": nieuw_oms}, tok)
                if ander and not _vraag_teruggelezen(a, tok, "VR " + titel, nieuw_oms):
                    raise RuntimeError("VR niet teruggelezen")
                a["titel"] = "VR " + titel
                a["omschrijving"] = nieuw_oms
                gezet += 1
            elif zin and titel.startswith("VR ") and oms.startswith(VR_REGEL):
                gewenst = VR_REGEL + zin.split(": ", 1)[-1]
                if oms.split("\n", 1)[0] != gewenst:
                    if len(oms) >= 1900:
                        oms = _volledige_omschrijving(a, tok)
                    nieuw_oms = re.sub(rf"^{VR_REGEL}[^\n]*", lambda _m: gewenst, oms, count=1)
                    _patch(a, {"description": nieuw_oms}, tok)
                    if ander and not _vraag_teruggelezen(a, tok, titel, nieuw_oms):
                        raise RuntimeError("VR-tekst niet teruggelezen")
                    a["omschrijving"] = nieuw_oms
                    gezet += 1
            elif not zin and (titel.startswith("VR ") or oms.startswith(VR_REGEL)):
                nieuw = titel[3:] if titel.startswith("VR ") else titel
                if len(oms) >= 1900:
                    oms = _volledige_omschrijving(a, tok)
                nieuw_oms = re.sub(rf"^{VR_REGEL}[^\n]*\n*", "", oms)
                _patch(a, {"summary": nieuw, "description": nieuw_oms}, tok)
                if ander and not _vraag_teruggelezen(a, tok, nieuw, nieuw_oms):
                    raise RuntimeError("opgeloste VR niet teruggelezen")
                a["titel"] = nieuw
                a["omschrijving"] = nieuw_oms
                weg += 1
        except Exception as e:  # noqa: BLE001
            print("vraag in agenda mislukt:", _toon(a), type(e).__name__, file=sys.stderr)
    return gezet, weg


def adres_vraag_noden(items, nu=None, niet_op_kaart=None):
    """Een stabiele nood voor een adresvraag die niet zichtbaar in de afspraak kon worden gezet."""
    vragen = _adresvragen(items, nu, niet_op_kaart=niet_op_kaart)
    per_id = {a.get("id"): a for a in items}
    uit = []
    for sleutel, zin, ids in vragen:
        a = per_id.get(ids[0])
        if not a or not ((a.get("titel") or "").startswith("VR ")
                      and (a.get("omschrijving") or "").startswith(VR_REGEL)
                      and any(s in (a.get("omschrijving") or "").split("\n", 1)[0]
                              for s in ("zet het adres erin", "vind ik niet op de kaart"))):
            uit.append({"tekst": f"{zin} VR niet mogelijk ({sleutel})", "wie": "mehdi"})
    return uit


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
        if bellen.beschikbaar() and not bellen.gelukt(uit) and bellen.callmebot_beschikbaar():
            try:                          # het vastzit-nummer faalde: terugvallen op Telegram, nooit op het afsprakennummer
                uit = list(uit) + [("telegram-oproep", bellen.bel_telegram(zin))]
            except Exception as e:  # noqa: BLE001
                uit = list(uit) + [("telegram-oproep", f"mislukt: {type(e).__name__}")]
        if not bellen.gelukt(uit):
            # een mislukte start is geen oproep: niet bewaren, de volgende geplande ronde probeert opnieuw (Codex A13)
            print("vastgelopen: bellen mislukt, volgende ronde opnieuw:", str(uit)[:160], file=sys.stderr)
            return None
        staat[sleutel] = {"tijd": nu.isoformat(), "zin": zin, "resultaat": str(uit)[:200]}
        json.dump(staat, open(BELVRAGEN, "w"), ensure_ascii=False, indent=0)
        return zin
    return None


def botsingen(items):
    """Twee afspraken die elkaar overlappen op dezelfde dag (bv. een Zoom tijdens een opmeting)."""
    uit = []
    tijd = [(datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["einde"]), x) for x in items
            if "T" in x["start"] and not lees_titel(x["titel"])["reistijd"] and not x.get("kalender", "").startswith("en.be#")
            and not lara_vervalt(x)]          # een vervallen Lara-afspraak botst met niets meer (FR-210)
    tijd.sort(key=lambda t: t[0])
    for i, (s1, e1, a) in enumerate(tijd):
        for s2, e2, b in tijd[i + 1:]:
            if s2 >= e1:
                break
            uit.append(f"{a['start'][:16]} {a['titel'][:45]}  ×  {b['start'][11:16]} {b['titel'][:45]}")
    return uit


def _voorouders(pid=None, diepte=10):
    """De procesnamen boven dit proces (Linux /proc), dichtstbij eerst. Elders (Mac, CI) een lege lijst."""
    namen, pid = [], pid or os.getppid()
    for _ in range(diepte):
        try:
            with open(f"/proc/{pid}/stat") as f:
                stat = f.read()
        except OSError:
            break
        namen.append(stat[stat.index("(") + 1:stat.rindex(")")])
        pid = int(stat[stat.rindex(")") + 2:].split()[1])
        if pid <= 1:
            break
    return namen


def geplande_start(argv=None, voorouders=None):
    """Alleen de geplande ronde belt (FR-59). Een argument bewijst dat niet: wie het cron-commando met de hand overneemt
    (ssh, een terminal, Claude), geeft ook '--ronde' mee (Codex A19, 15-10-2026). Gepland is daarom: '--ronde' en cron
    bij de voorouders. De crontab blijft zoals hij is; de Regisseur geeft nooit '--ronde' mee."""
    argv = sys.argv if argv is None else argv
    if "--ronde" not in argv:
        return False
    return any(n in ("cron", "crond") for n in (_voorouders() if voorouders is None else voorouders))


def slot_nemen(max_wachten=None):
    """Nooit twee rondes tegelijk. Gezien 21-09-2026: een volledige ronde en de
    wijzigingswacht maakten tegelijk ritten, en zo stonden ze dubbel."""
    import fcntl
    import time
    from pathlib import Path
    pad = Path(os.path.expanduser("~/appportal/mijnagents-data/agenda_wacht.lock"))
    pad.parent.mkdir(parents=True, exist_ok=True)
    f = open(pad, "w")
    if max_wachten is None:
        # --slot-wacht N: de wijzigingswacht geeft haar dagproces een budget van 900 s en laat het hooguit 120 s op het
        # slot wachten, zodat er tijd overblijft om te werken (Codex A28, 15-10-2026). Standaard 900.
        i = sys.argv.index("--slot-wacht") if "--slot-wacht" in sys.argv else -1
        max_wachten = int(sys.argv[i + 1]) if 0 <= i < len(sys.argv) - 1 and sys.argv[i + 1].isdigit() else 900
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


def terugkijkdag(dag, deals):
    """Lees een oude dag en zet alleen afspraken op het bord; raak geen Google-schrijfroutes aan."""
    ONGELEZEN.clear()
    items = afspraken_dag(dag, alleen_lezen=True)
    offset = (datetime.fromisoformat(dag).date() - datetime.now().date()).days
    archief = [a for a in archief_afspraken(offset - 1, offset + 2, alleen_lezen=True)
              if a.get("start", "")[:10] == dag]
    if ONGELEZEN or ARCHIEF_FOUT:
        raise RuntimeError("agenda van terugkijkdag niet volledig gelezen")
    klaar, gezien = [], set()
    for a in items + archief:
        identiteit = (a.get("kalender"), a.get("id"), a.get("start"))
        if identiteit in gezien:
            continue
        gezien.add(identiteit)
        if is_prive(a):
            continue
        info = lees_titel(a["titel"])
        if info["reistijd"] or a["kalender"] == "en.be#holiday@group.v.calendar.google.com":
            continue
        kal = KALENDERS.get(a["kalender"], a["kalender"])
        afdeling = (FIRMA_AFDELING.get(info["firma"]) or KALENDER_AFDELING.get(kal) or "mehdi") \
            if not info["firma_conflict"] else "mehdi"
        if afdeling == "mehdi":
            continue
        deal, hoe = koppel(info, a["titel"], deals) if afdeling == "h-architects" else (None, "")
        oms = ", ".join(x for x in (SOORT.get(info["soort"], ""), TYPES.get(info["type"], ""),
                                    "buiten + reistijd" if info["buiten"] else "",
                                    "niet bevestigd" if info["onzeker"] else "") if x)
        regel = f"{'hele dag' if a['hele_dag'] else a['start'][11:16]} {a['titel']}" + \
                (f" [{oms}]" if oms else "") + (f" · deal {deal['id']}" if deal else "")
        klaar.append(afspraak_klaarzetitem(a, info, afdeling, kal, regel, deal, hoe, terugkijken=True))
    ag.klaarzet(klaar)
    ag.log(dag, "bron", f"{len(klaar)} zakelijke afspraak/afspraken alleen lezend teruggekeken")
    ag.log_verstuur()
    return len(klaar)


def _kalenderdag(waarde):
    """Alleen de precieze ISO-vorm van een bestaande kalenderdag."""
    try:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", waarde) and
                    datetime.fromisoformat(waarde).date().isoformat() == waarde)
    except (TypeError, ValueError):
        return False


def _oude_dag(waarde):
    """Een kalenderdag in het verleden; een ongeldige datum mag geen taak afvinken."""
    return _kalenderdag(waarde) and waarde < nu_lokaal().date().isoformat()


def terugkijken(dagen):
    geldig = list(dict.fromkeys(d for d in dagen if _oude_dag(d)))
    for dag in dagen:
        if dag not in geldig:
            print(f"terugkijken overgeslagen: {dag} is geen oude kalenderdag")
    if not geldig:
        return 0
    deals = deals_index()
    for dag in geldig:
        terugkijkdag(dag, deals)
    return len(geldig)


def terugkijktaken():
    """Hoogstens veertig verschillende oude dagen per ronde; vink alleen geslaagde dagen af."""
    taken = [it for it in bord.klaargezet_voor(NAAM, n=500)
             if it.get("soort") == "taak" and it.get("voor") == NAAM and it.get("van") == "werfverslag-voorbereider"
             and isinstance(_inhoud_terugkijktaak(it).get("terugkijken"), str)]
    per_dag = {}
    for it in taken:
        dag = _inhoud_terugkijktaak(it)["terugkijken"]
        if not _kalenderdag(dag):
            continue
        per_dag.setdefault(dag, []).append(it)
    vandaag = nu_lokaal().date().isoformat()
    for dag, items in per_dag.items():
        if dag >= vandaag:
            for it in items:
                bord.opgepakt(it["id"], NAAM)
            ag.log(dag, "besluit", "terugkijktaak overgeslagen; de gewone ronde leest vandaag of later")
    oude_dagen = sorted(d for d in per_dag if _oude_dag(d))[:40]
    if oude_dagen:
        deals = deals_index()
        for dag in oude_dagen:
            terugkijkdag(dag, deals)
            for it in per_dag[dag]:
                bord.opgepakt(it["id"], NAAM)
    ag.log_verstuur()
    return len(oude_dagen)


def _inhoud_terugkijktaak(it):
    inhoud = it.get("inhoud") or {}
    if isinstance(inhoud, dict):
        return inhoud
    try:
        waarde = json.loads(inhoud)
        return waarde if isinstance(waarde, dict) else {}
    except (TypeError, ValueError):
        return {}


def terugkijkstand(argv):
    """Eigen commandolijn; onbekende vlaggen kunnen nooit in de schrijvende ronde belanden."""
    p = argparse.ArgumentParser(description="Agendawacht: alleen lezend terugkijken op vraag")
    keuze = p.add_mutually_exclusive_group(required=True)
    keuze.add_argument("--terugkijken", nargs="+", metavar="JJJJ-MM-DD")
    keuze.add_argument("--taken", action="store_true")
    a = p.parse_args(argv)
    if a.terugkijken and not all(_oude_dag(d) for d in a.terugkijken):
        print("terugkijken vraagt bestaande kalenderdagen vóór vandaag", file=sys.stderr)
        return 2
    ag.werkwijze()
    if not agenda.beschikbaar():
        print("geen agendatoegang: GOOGLE_AGENDA_* ontbreekt", file=sys.stderr)
        return 78
    if a.taken:
        print(f"=== {nu_lokaal():%Y-%m-%d %H:%M} Brussel · terugkijktaken", flush=True)
        terugkijktaken()
    else:
        print(f"=== {nu_lokaal():%Y-%m-%d %H:%M} Brussel · alleen lezend terugkijken", flush=True)
        terugkijken(a.terugkijken)
    return 0


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
        markeer_zorgschaduwen(items + archief)
        ONGELEZEN.clear()
        ONGELEZEN.update(f["kalender"] for f in fouten)
        if ARCHIEF_FOUT:                       # onbekend is niet leeg: de nood noemt het (Codex A16)
            fouten.append({"kalender": ARCHIEF_FOUT, "fout": "archief"})
            ONGELEZEN.add("archief")
        try:
            import mail_afspraken as _MA0  # noqa: PLC0415
            if os.path.exists(_MA0.DB):
                ag.prive(_MA0.prive_teksten())   # privé uit mail (Hotmail): nooit op het bord (R1)
        except Exception:  # noqa: BLE001
            pass
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
            afdeling = (FIRMA_AFDELING.get(info["firma"]) or KALENDER_AFDELING.get(kal) or "mehdi") \
                if not info["firma_conflict"] else "mehdi"
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
            if dag >= vandaag and afdeling != "mehdi" and not is_prive(a):    # privé nooit naar een afdeling (A05)
                per_afdeling[afdeling] = per_afdeling.get(afdeling, 0) + 1
                klaar.append(afspraak_klaarzetitem(a, info, afdeling, kal, regel, deal, hoe))
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
            if VERRE_FOUT:
                # een verre agenda niet gelezen: geen keten van ritten op een halve lezing; de acht dagen gaan door (Codex A17)
                fouten += VERRE_FOUT
                extra = []
        else:
            extra = []
        rit_items = items + [a for a in extra if (a["kalender"], a["id"], a["start"]) not in gezien_ids]
        schaduw_noden = markeer_zorgschaduwen(rit_items)
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
        mail_noden = list(schaduw_noden)
        zorgstap_gedaan = False
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
                _alle, _stuk = _agenda_voor_mail()
                mres, mfout = MA.ronde(_alle, (datetime.now() - timedelta(days=14)).date().isoformat(), agenda_onvolledig=_stuk)
                ag.prive(MA.prive_teksten())
                if MA.ZORG_WERKVERSLAG:
                    ag.log(f"dag {vandaag}", "bevinding", "Gedeeld zorgplatform zonder profielbewijs: geen afspraak gemaakt",
                           "\n".join(MA.ZORG_WERKVERSLAG))
                for _mb in sorted({f_["mailbox"] for f_ in mfout}):
                    _nood = MA.mailbron_nood(_mb, afhankelijk=_mailbron_zorg_afhankelijk(_mb, rit_items), nu=nu_lokaal())
                    if _nood:
                        mail_noden.append(_nood)
                if _stuk:
                    # een onvolledige agenda is geen bewijs dat iets ontbreekt: niets vergelijken, niets zetten (Codex A15)
                    raise _Onvolledig(f"{len(_stuk)} agenda('s) niet gelezen: mail niet met de agenda vergeleken")
                # zorgafspraken eerst: een bevestigd consult wordt een echt blok, zodat de gewone melding geen vraag zet
                zst = zorg_afspraken_zetten(mres, rit_items, agenda._toegang(), bijwerken_items=True)
                zorgstap_gedaan = True
                mail_noden.extend(n for n in zst["noden"] if n["tekst"] not in {m["tekst"] for m in mail_noden})
                MA.statussen_bewaren(mres)
                ag.log(f"dag {vandaag}", "schrijf", zst["bord"][0])          # alleen tellingen: niets medisch op het bord
                mregels = mail_meldingen(mres, _alle, agenda._toegang())
                _tel = {s: sum(1 for a in mres if a["status"] == s) for s in ("gekoppeld",) + MA.VRAAG_STATUSSEN + ("zonder_tijd",)}
                ag.log(f"dag {vandaag}", "schrijf", f"mail als bron: {len(mres)} afspraken uit mail ({_tel})", "\n".join(mregels))
                if any(_tel[s] for s in MA.VRAAG_STATUSSEN):
                    mail_noden.append({"tekst": "Afspraken uit mail kloppen niet met de agenda; details in je privé-agenda", "wie": "mehdi"})
                for _mb in sorted({f_["mailbox"] for f_ in mfout}):
                    _stuk = any(not f_.get("map") for f_ in mfout if f_["mailbox"] == _mb)
                    if not _stuk:
                        mail_noden.append({"tekst": f"Mailbron {_mb} niet volledig gelezen; zie de leesstand", "wie": "claude"})
            except _Onvolledig as e:
                mail_noden.append({"tekst": f"Mail als afsprakenbron: {e}", "wie": "claude"})
            except Exception as e:  # noqa: BLE001
                mail_noden.append({"tekst": f"Mail als afsprakenbron mislukt ({type(e).__name__}: {str(e)[:120]})", "wie": "claude"})
        if not zorgstap_gedaan:
            # Ook de dagroute of een onvolledige mailvergelijking mag een reeds bestaande privé-afspraak herstellen.
            _pg, _po = zorg_profielplaatsen_zetten(rit_items, agenda._toegang())
            if _po:
                mail_noden.append({"tekst": "Profielplaats zorgafspraak niet teruggelezen", "wie": "mehdi"})
        pg, pregels = projectnummers_zetten(kort_items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"projectnummer: {pg} in de titel gezet", "\n".join(pregels))
        if not DAG_ARG:
            rg, rregels = codes_reeksen(kort_items)
            if rregels:
                ag.log(f"dag {vandaag}", "schrijf", f"codes van twee letters: {rg} reeks(en) omgezet", "\n".join(rregels))
        if not DAG_ARG and not ALLEEN_VANDAAG:
            mail_noden.extend(lara_vakantie_stap(rit_items, vandaag))
            try:
                mail_noden.extend(firma_stap(vandaag))
            except Exception as e:  # noqa: BLE001
                mail_noden.append({"tekst": f"Firma-agenda's niet nagekeken ({type(e).__name__})", "wie": "claude"})
        # Agendagasten: collega's en partners op de afspraken waar ze bij horen, zonder mail (Mehdi, 03-10-2026).
        # Volledige ronde: twee maanden vooruit; de wijzigingsroute: de dag die veranderde.
        try:
            gregels = agendagasten_zetten(rit_items if DAG_ARG else [x for x in afspraken(0, 60) if not x.get("fout")])
        except Exception as e:  # noqa: BLE001
            gregels = [f"agendagasten niet gezet ({type(e).__name__}: {str(e)[:120]})"]
        if gregels:
            ag.log(f"dag {vandaag}", "schrijf", f"agendagasten: {len(gregels)} afspraak/afspraken", "\n".join(gregels))
        # De duur staat vóór de ritten: een nieuw einde verandert de keten en de terugrit.
        dg, dregels = duur_ter_plaatse_zetten(kort_items)
        ag.log(f"dag {vandaag}", "schrijf", f"duur ter plaatse: {dg} afspraak/afspraken op 2 uur gezet en teruggelezen")
        if dregels:
            ag.log(f"dag {vandaag}", "bevinding", f"duur ter plaatse: {len(dregels)} open punt(en)", "\n".join(dregels))
        tg, tregels = contact_zetten(kort_items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"telefoon: {tg} nummer(s) bovenaan gezet", "\n".join(tregels))
        ag.log(f"dag {vandaag}", "schrijf", f"titels: {ng} rechtgezet uit vrije tekst; link-notitie: {zg} gezet",
               "\n".join(nregels + zregels))
        voorstellen = [r for r in nregels + pregels if "VOORSTEL" in r]
        if zregels or voorstellen:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": "Link doorsturen of titel nakijken",
                          "uniek": f"agenda-zoom-titel:{vandaag}:{dag_grens or 'alle'}",
                          "inhoud": "\n".join("- " + r for r in (zregels + voorstellen)[:30])}])
        # eerst de gewone herinneringen, dan de ritten: zo heeft de vertrekmelding het laatste woord
        gezet, al, weg, fout_h = herinneringen_zetten(kort_items, dag_grens)
        niet_op_kaart = set()
        rg, ral, rgeen, rfout, rregels = reistijd_zetten(rit_items, dag_grens, niet_op_kaart=niet_op_kaart)
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
        zonder_rit = zonder_rit_indelen(rregels)
        te_krap = [r[:140] for r in rregels if "TE KRAP" in r]

        rooster = rooster_maken(items, archief, vandaag, mail_noden)
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
            noden.extend(te_krap_noden(te_krap))
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
        vg, vw = vragen_in_agenda(rit_items, niet_op_kaart=niet_op_kaart)
        noden.extend(adres_vraag_noden(rit_items, niet_op_kaart=niet_op_kaart))
        if vg or vw:
            ag.log(f"dag {vandaag}", "schrijf", f"vragen in de agenda: {vg} gezet (VR), {vw} opgelost")
        if not DAG_ARG and geplande_start():
            # het archief telt mee: een Calendly-boeking kan daar nog staan (FR-39). Een sleutel per dag, zonder
            # aantal, zodat een telling met of zonder archief geen tweede oproep geeft (gezien 25-09-2026, 13:51).
            # Alleen de geplande ronde belt: een ronde die Claude met de hand start, belt nooit (FR-59), ook niet met
            # '--ronde' erbij: gepland is gestart door cron (Codex A19).
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
        # Laag 4 (overleg 27-10-2026): een ontbrekend weekoverzicht is een nood tot de volgende geslaagde run; ook in een
        # dagronde, want die mag hem openen (noden_voor_hartslag). De fout zelf staat in het detail, nooit in de tekst.
        weeknood = weekconsolidatie_noden()
        noden.extend(weeknood)
        weekfout = weekconsolidatie_fout() if weeknood else ""
        onderweg = locatiebeweging.kort(locatiebeweging.lees())
        ag.hartslag("waakt", taak="agenda in het oog",
                    detail=f"vandaag {len(dagplan)} afspraken; {gekoppeld} gekoppeld; "
                           f"{len(niet_conform)} zonder code; "
                           f"{len(onvolledig)} zonder adres; {onderweg}"
                           + (f"; weekoverzicht: {weekfout or 'geen geslaagde run sinds zondag 20:00'}" if weeknood else ""),
                    nood=noden_voor_hartslag(noden, DAG_ARG))
        # H1-1, driehoeksoverleg C2, 17-10-2026: ook vragen en de vastgelopen-oproep horen bij dit rondeverslag.
        ag.log_verstuur()
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


class _Onvolledig(Exception):
    """Een bron is niet volledig gelezen: de stap die erop steunt, slaat over."""


def _agenda_voor_mail(van=-14, tot=120):
    """De agenda waartegen de mail vergeleken wordt, en de agenda's die niet te lezen waren. Een uitnodiging die in een
    ongelezen agenda staat, is niet 'ontbreekt': dan vergelijk ik niet (Codex A15, 15-10-2026)."""
    ruw = afspraken(van, tot)
    stuk = sorted({KALENDERS.get(x["kalender"], x["kalender"]) for x in ruw if x.get("fout")})
    alle = [x for x in ruw if not x.get("fout")] + archief_afspraken(van, tot)
    if ARCHIEF_FOUT:
        stuk.append("archief")
    return alle, stuk


def zorgronde():
    """--zorg: alleen de mailbron met de zorgstap en de mailmeldingen, met de details op stdout (een privélog op de
    server, nooit het bord). Voor de inhaalcontrole en het bewijs; belt niet en raakt verder niets."""
    import mail_afspraken as MA  # noqa: PLC0415
    _slot = slot_nemen()  # noqa: F841
    _alle, _stuk = _agenda_voor_mail()
    mres, mfout = MA.ronde(_alle, (datetime.now() - timedelta(days=14)).date().isoformat(), agenda_onvolledig=_stuk)
    if _stuk:
        print(f"  [zorg] {len(_stuk)} agenda('s) niet gelezen: mail niet met de agenda vergeleken, niets gezet (Codex A15)")
        return 1
    zst = zorg_afspraken_zetten(mres, _alle, agenda._toegang())
    MA.statussen_bewaren(mres)
    mregels = mail_meldingen(mres, _alle, agenda._toegang())
    for mb, r in sorted(MA.leesstand().items()):
        print(f"  [leesstand] {mb}: {r.get('dekking')}, laatst gelukt {r.get('laatst_gelukt')}"
              + (f", fout: {r.get('laatste_fout')[:200]}" if r.get("laatste_fout") else ""))
    print("  [zorg] " + zst["bord"][0])
    for regel in zst["prive"] + mregels:
        print("    " + regel)
    return 0


if __name__ == "__main__":
    if "--terugkijken" in sys.argv or "--taken" in sys.argv:
        sys.exit(terugkijkstand(sys.argv[1:]))
    if "--kleuren" in sys.argv:          # om :17 en :47, ook 's nachts en in het weekend (FR-21)
        print(f"=== {nu_lokaal():%Y-%m-%d %H:%M} Brussel · kleurherstel", flush=True)
        kleurherstel()
        try:                             # firma-agenda's: ook 's nachts en in het weekend (Codex-hertest 3, punt 15)
            for _n in firma_kleurronde(nu_lokaal().date().isoformat()):
                print(f"firma-agenda's: {_n}", flush=True)
        except Exception as _e:  # noqa: BLE001
            print(f"firma-agenda's niet nagekeken ({type(_e).__name__})", file=sys.stderr, flush=True)
        sys.exit(0)
    if "--zorg" in sys.argv:             # zorgafspraken uit mail, met de details in een privélog (opdracht v1.0, 14-10-2026)
        print(f"=== {nu_lokaal():%Y-%m-%d %H:%M} Brussel · zorgafspraken uit mail", flush=True)
        sys.exit(zorgronde())
    if "--ronde" in sys.argv and not is_rondetijd():
        sys.exit(0)          # cron start elk uur; alleen op de ronde-uren (Brusselse tijd) werk ik
    # Elke ronde begint met zijn tijdstip. Gezien 24-09-2026: het logboek had geen enkele tijd,
    # zodat niet na te gaan was wanneer iets gebeurde.
    print(f"=== {nu_lokaal():%Y-%m-%d %H:%M} Brussel · " + (f"dag {DAG_ARG}" if DAG_ARG else "volledige ronde"), flush=True)
    sys.exit(main() or 0)
