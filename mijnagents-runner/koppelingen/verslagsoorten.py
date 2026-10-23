"""De verslagsoorten van Mehdi Agents: één register voor het Commandocentrum en de verslagagents.

Het principe (Mehdi, 16-09-2026): de data komt overal langs dezelfde weg (agenda -> bezoek -> foto's, opname,
transcript in de bezoekmap), alleen de dienst en de firma verschillen. Elke verslagsoort zegt hier:
welke agent hem draagt, bij welke afdeling hij hoort, hoe hij in een agendatitel te herkennen is, waar zijn
dossiers in Dropbox staan, hoe de bezoekmap heet en welke hoofdstukken het verslag heeft.

Een nieuwe verslagsoort toevoegen = een blok in SOORTEN + een dunne runner (zie verslag_basis.py).
"""
import json
import os
import re
import unicodedata
from functools import lru_cache

SOORTEN = {
    "werfverslag": {
        "label": "Werfverslag",
        "agent": "werfverslag-voorbereider",       # bestaande keten: voorbereider -> schrijver, pagina /werfverslagen
        "afdeling": "h-architects",
        "firmas": ("HA", "HARC"),
        "codes": ("WB", "OPL", "OP", "VO", "DO", "VOPL", "DOPL"),     # twee letters sinds 02-10-2026, oude blijven leesbaar
        "trefwoorden": ("werfbezoek", "werfverslag", "oplevering", "werf "),
        "basismappen": [],                          # eigen zoeker in werfverslag_voorbereider (STAN-fasen + light)
        "communicatiemap": "_00. Communication",
        "bezoeknaam": "bezoek klant - werfbezoek",
        "eigen_keten": True,
        "hoofdstukken": [],
    },
    "veiligheidscoordinatie": {
        "label": "Veiligheidscoördinatie",
        "agent": "veiligheidscoordinatie-verslag",
        "afdeling": "unabo",
        "firmas": ("UNABO", "ENERGIE", "UB", "UNAB", "EE", "ENEF"),
        "codes": ("VC",),
        "trefwoorden": ("veiligheidsco", "vc-bezoek", "vc bezoek", "vc werf"),
        "basismappen": ["/Work All/03. Enstaco WORK/3. VC (Veiligheidscoördinatie)",
                        "/Work All/02. UNABO/01. U-WORK/03. U-SAFETY"],
        "communicatiemap": "_00. Communication",
        "bezoeknaam": "bezoek werf - veiligheidscoördinatie",
        "eigen_keten": False,
        "verslagtitel": "Verslag werfbezoek veiligheidscoördinatie",
        "hoofdstukken": [
            ("Algemeen", "werf, bouwheer, veiligheidscoördinator, aanwezige aannemers, fase van de werken, weer"),
            ("Documenten op de werf", "veiligheids- en gezondheidsplan, postinterventiedossier, aanwezigheidsregistratie, "
                                      "verzekeringen, keuringsattesten (stelling, hijswerktuigen, elektrische installatie)"),
            ("Vaststellingen per thema", "werforganisatie en netheid; valbeveiliging, stellingen en ladders; persoonlijke "
                                         "beschermingsmiddelen; elektriciteit en werfkast; opslag, toegang en afsluiting; "
                                         "machines en hijsen; stof, asbest en gevaarlijke stoffen; eerste hulp en signalisatie"),
            ("Inbreuken en tekortkomingen", "genummerd, met foto, ernst (laag, ernstig, onmiddellijk stilleggen), verantwoordelijke en termijn"),
            ("Acties", "wie - wat - tegen wanneer"),
            ("Volgend bezoek", "datum of fase"),
        ],
        "slot": "Zonder tegenbericht per e-mail binnen de vijf kalenderdagen wordt aangenomen dat alle partijen akkoord gaan met dit verslag.",
    },
    "plaatsbeschrijving": {
        "label": "Plaatsbeschrijving",
        "agent": "plaatsbeschrijving-verslag",
        "afdeling": "unabo",
        "firmas": ("UNABO", "ENERGIE", "HA", "UB", "UNAB", "EE", "ENEF", "HARC"),
        "codes": ("PLB", "PB", "PS"),
        "trefwoorden": ("plaatsbeschrijving", "plaatsbeschr"),
        "basismappen": ["/Work All/02. UNABO/01. U-WORK/07. U-PLAATSBESCHRIJVING",
                        "/Work All/03. Enstaco WORK/4. PB (Plaatsbeschrijving)"],
        "communicatiemap": "_00. Communication",
        "bezoeknaam": "bezoek klant - plaatsbeschrijving",
        "eigen_keten": False,
        "verslagtitel": "Tegensprekelijke plaatsbeschrijving",
        "hoofdstukken": [
            ("Algemeen", "opdrachtgever, aanvrager, betrokken panden en partijen, datum en uur, aanwezigen, weersomstandigheden"),
            ("Voorwerp en werkwijze", "welke panden en delen (buiten, binnen, openbaar domein) beschreven zijn, fotonummering, meetmethode van barsten"),
            ("Beschrijving per pand", "per gevel en per ruimte: vloer, wanden, plafond, schrijnwerk, afwerking; elke barst met plaats, "
                                      "richting, breedte en foto; vocht en verzakkingen"),
            ("Openbaar domein", "voetpad, boordstenen, rijweg, nutsvoorzieningen, beplanting"),
            ("Algemene opmerkingen en voorbehoud", "wat niet toegankelijk was, wat niet beoordeeld kon worden"),
            ("Tegensprekelijkheid en ondertekening", "partijen, datum, akkoord of opmerkingen"),
        ],
        "slot": "Deze plaatsbeschrijving is tegensprekelijk opgemaakt; opmerkingen worden binnen de acht werkdagen schriftelijk gemeld.",
    },
    "barsten-scheuren": {
        "label": "Barsten en scheuren",
        "agent": "barsten-scheuren-verslag",
        "afdeling": "unabo",
        "firmas": ("UNABO", "TKN", "ENERGIE", "UB", "UNAB", "TK", "TKNB", "EE", "ENEF"),
        "codes": ("BS", "STA", "ST"),
        "trefwoorden": ("barsten", "scheur", "stabiliteit", "bs "),
        "basismappen": ["/Work/TKN BURO WORK/1 Projects"],
        "jaarmappen": True,
        "overslaan": r"(?i)^(0[. ]|_|\.)|mapstructuur|sjabloon|archive",
        "bezoekmap_is_dossiermap": True,
        "submappen": {"fotos": "1. Foto's", "plaud": "2. plaud", "documenten": "3.Documents", "mail": "4.Email"},
        "vereiste_submappen": ["fotos", "plaud"],
        "fotodatummap": "{datum} iPhone",
        "transcriptnaam": "{datum} Plaud transcript.txt",
        "fotoformaat": "jpg",
        "fotovenster_min": (30, 180),
        "fototaak_na_min": 15,
        "bronnen_max_tekens": 200000,
        "communicatiemap": "_00. Communication",
        "bezoeknaam": "bezoek klant - barsten en scheuren",
        "eigen_keten": False,
        "pijplijn": "barsten_en_scheuren",         # de bestaande pijplijn op de VM (~/barsten_en_scheuren) maakt het rapport
        "verslagtitel": "Stabiliteitsverslag barsten en scheuren",
        "hoofdstukken": [
            ("Aanleiding en opdracht", "wie vroeg wat, wanneer, welk pand"),
            ("Het gebouw en zijn omgeving", "bouwjaar, structuur, funderingswijze, bodem en grondwater (DOV), recente werken in de buurt"),
            ("Vaststellingen", "elke barst of scheur: plaats, richting, breedte, patroon, ouderdom (stof, verf), foto"),
            ("Mogelijke oorzaken", "checklist uit het handboek: zetting, uitdroging, thermisch, overbelasting, vocht, trillingen, bomen, werken naast de deur"),
            ("Aanbevolen onderzoek en maatregelen", "monitoring, sonderingen, herstel, dringendheid"),
            ("Conclusie en voorbehoud", "voorlopig oordeel, wat niet onderzocht is"),
        ],
        "slot": "Dit verslag geeft de vaststellingen van het plaatsbezoek weer; een definitief oordeel vraagt de aanbevolen onderzoeken.",
    },
    "aankoopkeuring": {
        "label": "Aankoopkeuring",
        "agent": "aankoopkeuring-verslag",
        "afdeling": "unabo",
        "firmas": ("UNABO", "TKN", "ENERGIE", "UB", "UNAB", "TK", "TKNB", "EE", "ENEF"),
        "codes": ("AK", "AB"),
        "trefwoorden": ("aankoopkeuring", "aankoopbegeleiding", "aankoopadvies", "bouwkundige keuring"),
        "basismappen": ["/Work All/02. UNABO/01. U-WORK/09. U-AANKOOPKEURING",
                        "/Work All/02. UNABO/01. U-WORK/01. U-GENERAL"],
        "communicatiemap": "_00. Communication",
        "bezoeknaam": "bezoek klant - aankoopkeuring",
        "eigen_keten": False,
        "schrijfprofiel": "aankoopkeuring",
        "verslagtitel": "Technisch en stedenbouwkundig aankoopkeuringsverslag",
        "hoofdstukken": [
            ("Algemeen en opdrachtkader",
             "opdrachtgever, kandidaat-koper, adres, datum en uur, aanwezigen, weersomstandigheden, "
             "visuele en niet-destructieve aard van de opname"),
            ("Niet-beoordeelde en ontoegankelijke delen",
             "verplicht overzicht van elk bouwdeel of elke ruimte die tijdens het bezoek niet zichtbaar, "
             "afgesloten of niet inspecteerbaar was, met de reden"),
            ("Bouwkundige en stabiliteitsstaat (K0-K3 en UN)",
             "per bouwdeel (dak, gevels, buitenschrijnwerk, kelder en vocht, structuur en scheurvorming, "
             "binnenafwerking, technieken): scheid zichtbare waarneming, bronfeit (zoals DOV-bodemgevoeligheid "
             "met peildatum) en ernstcode K0, K1, K2, K3 of UN (nader onderzoek vereist), met foto"),
            ("Stedenbouwkundige plan- en luchtfotovergelijking",
             "vergelijking van voorgelegde vergunde plannen, kadaster en luchtfoto-tijdreis met de zichtbare "
             "toestand ter plaatse; gebruik uitsluitend de uitkomst 'visueel conform voorgelegd plan', "
             "'zichtbare afwijking t.o.v. voorgelegd plan (code UN)' of 'niet te beoordelen (vergunde plannen ontbreken)'"),
            ("Doorlichting verplichte attesten en omgeving",
             "synthese van voorgelegde stukken (EPC en renovatieplicht, asbestattest, elektrische keuring AREI, "
             "stedenbouwkundig uittreksel, overstromingsgevoeligheid P/G-score) met bron- en datumvermelding; "
             "ontbrekende stukken expliciet als 'onbekend / op te vragen'"),
            ("Prioriteitenmatrix (zonder herstelbedragen)",
             "samenvatting van de bevindingen zonder eurobedragen, opgedeeld in: (A) Directe actie vereist "
             "(K3 en wettelijke verplichtingen uit attesten), (B) Actie op termijn (K2), en "
             "(C) Nader gespecialiseerd of stedenbouwkundig onderzoek vereist (UN)"),
        ],
        "slot": ("Dit verslag betreft een visuele en niet-destructieve momentopname ter ondersteuning van de "
                 "kandidaat-koper, bevat geen kostenramingen of juridische garanties, en vervangt geen wettelijk "
                 "verplichte keuringen of stedenbouwkundige beslissingen van de vergunningverlenende overheid."),
    },
}


def plat(t):
    t = str(t or "").replace("’", "'").replace("‘", "'")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", t))


def straat_nummer(adres):
    straat = str(adres or "").split(",", 1)[0]
    straat = re.sub(r"(?i)\s*(?:bus|bte|bt)\s*\d+[a-z]?\s*$", "", straat)
    straat = re.sub(r"(?i)\s*/\s*\d+[a-z]?\s*$", "", straat)
    straat = plat(straat)
    return straat if re.fullmatch(r"[a-z][a-z0-9 ]* \d{1,4}(?: ?[a-z])?", straat) else ""


def busnummer(adres):
    tekst = str(adres or "")
    voor_komma = tekst.split(",", 1)[0]
    match = re.search(r"(?i)\b\d{1,4}[a-z]?\s*/\s*(\d+[a-z]?)\b", voor_komma)
    if not match:
        match = re.search(r"(?i)\b(?:bus|bte|bt)\s*(\d+[a-z]?)\b", tekst)
    if not match:
        return ""
    waarde = match.group(1).lower()
    cijfers = re.match(r"\d+", waarde).group()
    return str(int(cijfers)) + waarde[len(cijfers):]


def mapnummer(naam):
    m = re.match(r"^\s*(\d{4,6})(?=[_ ])", str(naam or ""))
    return m.group(1) if m else ""


def submap_sleutel(naam):
    p = plat(naam)
    for patroon, sleutel in ((r"^1 ?foto", "fotos"), (r"^2 ?plaud", "plaud"),
                            (r"^3 ?doc", "documenten"), (r"^4 ?e ?mail", "mail")):
        if re.match(patroon, p):
            return sleutel
    return None


def tkn_pad(pad, basis):
    if not isinstance(pad, str) or not isinstance(basis, str) or "\x00" in pad:
        return ""
    if not pad.startswith(basis + "/") or pad.endswith("/"):
        return ""
    delen = pad[len(basis) + 1:].split("/")
    if len(delen) != 2 or any(not d or d == ".." for d in delen):
        return ""
    if not re.fullmatch(r"\d{4}", delen[0]):
        return ""
    return mapnummer(delen[1])


@lru_cache(maxsize=1)
def pakketcontract():
    with open(os.path.join(os.path.dirname(__file__), "pakketcontract.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def ketenstandcontract():
    with open(os.path.join(os.path.dirname(__file__), "ketenstandcontract.json"), encoding="utf-8") as f:
        return json.load(f)

ONLINE_SOORTEN = ("KO", "PO", "IN", "LO", "AO", "XO", "B2B")


def _online(info, inhoud):
    loc = (inhoud.get("locatie") or "").strip().lower()
    return info.get("soort") in ONLINE_SOORTEN or loc.startswith("http") or "zoom" in loc


def ter_plaatse(inhoud):
    """Een bezoek ter plaatse: '!!' in de titel (buiten met reistijd) of een fysiek adres als locatie.
    Les van de eerste droge ronde (16-09-2026): het dagelijkse werkblok 'Ai stabiliteit' zonder adres is geen bezoek."""
    loc = (inhoud.get("locatie") or "").strip().lower()
    return bool(inhoud.get("buiten")) or bool(loc and not loc.startswith("http") and "zoom" not in loc)


def herken(inhoud):
    """Welke verslagsoort hoort bij een afspraak uit de bak van de Agendawacht? None = geen verslag nodig.
    Alleen bezoeken ter plaatse tellen: interne en online afspraken krijgen nooit een verslagimpuls."""
    info = {"firma": (inhoud.get("firma") or "").upper(), "soort": (inhoud.get("soort") or "").upper(),
            "type": (inhoud.get("type") or "").upper()}
    if _online(info, inhoud) or not ter_plaatse(inhoud):
        return None
    titel = (inhoud.get("titel") or "").lower()
    kaal = re.sub(r"\[[^\]]*\]", " ", titel)
    kaal = re.sub(r"^\s*(mehdi|siyan|shelton|angela)[^:]*:\s*", "", kaal).replace("!!", " ").replace("??", " ")
    for sleutel, s in SOORTEN.items():
        if info["type"] and info["type"] in s["codes"]:
            return sleutel
        for code in s["codes"]:
            if re.search(rf"(^|[\s:\-]){code.lower()}(\s|$|[\-:])", kaal):
                return sleutel
        if any(t in kaal for t in s["trefwoorden"]):
            if s["firmas"] and info["firma"] and info["firma"] not in s["firmas"]:
                continue
            return sleutel
    return None


def agents():
    return sorted({s["agent"] for s in SOORTEN.values()})
