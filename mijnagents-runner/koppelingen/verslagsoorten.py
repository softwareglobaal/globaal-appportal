"""De verslagsoorten van Mehdi Agents: één register voor het Commandocentrum en de verslagagents.

Het principe (Mehdi, 16-09-2026): de data komt overal langs dezelfde weg (agenda -> bezoek -> foto's, opname,
transcript in de bezoekmap), alleen de dienst en de firma verschillen. Elke verslagsoort zegt hier:
welke agent hem draagt, bij welke afdeling hij hoort, hoe hij in een agendatitel te herkennen is, waar zijn
dossiers in Dropbox staan, hoe de bezoekmap heet en welke hoofdstukken het verslag heeft.

Een nieuwe verslagsoort toevoegen = een blok in SOORTEN + een dunne runner (zie verslag_basis.py).
"""
import re

SOORTEN = {
    "werfverslag": {
        "label": "Werfverslag",
        "agent": "werfverslag-voorbereider",       # bestaande keten: voorbereider -> schrijver, pagina /werfverslagen
        "afdeling": "h-architects",
        "firmas": ("HA",),
        "codes": ("WB", "OPL"),
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
        "firmas": ("UNABO", "ENERGIE"),
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
        "firmas": ("UNABO", "ENERGIE", "HA"),
        "codes": ("PLB", "PB"),
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
        "firmas": ("UNABO", "TKN", "ENERGIE"),
        "codes": ("BS", "STA"),
        "trefwoorden": ("barsten", "scheur", "stabiliteit", "bs "),
        "basismappen": ["/Work All/03. Enstaco WORK/7. STA (Stabiliteit)"],
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
}

ONLINE_SOORTEN = ("KO", "PO", "IN")


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
