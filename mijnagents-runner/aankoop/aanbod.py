"""Een aanbod keuren, de totaalprijs in euro rekenen en de aanbiedingen rangschikken.

Het taalmodel zoekt; deze module beslist wat in het verslag mag. Regels die nooit aan het model worden overgelaten:

1. Geen link, geen prijs of geen datum gezien: het aanbod gaat niet in het verslag (afgewezen, met reden).
2. De prijs moet letterlijk op de gelezen pagina van het aanbod staan, en een pagina zonder leesbare tekst telt niet
   als gelezen (controle Codex X1, 30-10-2026). Opgeld, verzending en veilingkosten boven nul moeten op een gelezen
   pagina staan; anders is het totaal onvolledig.
3. Een totaalprijs is pas volledig met verzending, de btw (bijgeteld als de prijs zonder btw is, Codex X9), bij een
   veiling het opgeld en de vaste kosten, en buiten de EU de invoer (douane geschat door het model, btw berekend door
   de code). Ontbreekt er iets, dan staat het aanbod er met "totaal onvolledig" en kan het nooit als beste of reserve.
4. Een aanbod dat niet past bij een eis staat apart onder "niet compatibel" en wordt nooit aanbevolen. De eisen over
   netspanning en netfrequentie haalt de code zelf uit de vraag (eisen_uit_vraag), zodat ze er ook staan als het model
   ze vergeet (Codex X2). Het bewijs daarvoor mag van een gelezen pagina van de fabrikant, de handleiding of het
   specificatieblad komen, als dezelfde volledige modelcode op die pagina en op de aanbodpagina staat (overleg 9, X1).

Draaien van de tests: python3 mijnagents-runner/tests/test_aankoop_prijs.py
"""
import re
from datetime import date
from urllib.parse import urlparse

SOORTEN = ("nieuw", "refurbished", "tweedehands", "veiling")
# Een prijs die langer geleden gezien is, geldt niet meer als actueel aanbod.
MAX_OUDERDOM_DAGEN = 3
# De lidstaten van de EU (ISO 3166 alpha-2). Binnen de EU geen invoer; buiten de EU moet de invoer erbij.
EU = frozenset("AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split())
BTW = 0.21                     # Belgisch tarief: bij een prijs zonder btw en bij invoer
MIN_PAGINATEKST = 200          # minder tekens is geen gelezen pagina (een lege of geblokkeerde pagina)
MIN_CITAAT = 8                 # een citaat als bewijs is minstens zo lang, anders bewijst het niets
# Alle soorten spaties, ook de vaste en de smalle vaste spatie in "1 299,00" (Codex X11, ronde 2).
SPATIES = re.compile(r"[\s\xa0   ]+")
# Woorden die een bedrag tot een bijkomende kost maken: zo'n citaat bewijst nooit de productprijs (Codex X1, ronde 2).
KOSTWOORDEN = re.compile(r"verzend|verzonden|levering|leverkost|shipping|delivery|versand|lieferung|livraison|"
                         r"opgeld|premium|aufgeld|frais|kosten|\bfee\b|toeslag|borg|deposit|statiegeld", re.I)
VERZENDWOORDEN = re.compile(r"verzend|verzonden|levering|leverkost|shipping|delivery|versand|lieferung|livraison", re.I)
# Een verzendtarief van een andere pagina van dezelfde winkel telt alleen als het citaat zegt dat het voor Belgie (of
# de Benelux) of voor alle bestellingen geldt, en nooit van de pagina van een ander product (overleg 29, X2).
VOOR_BELGIE = re.compile(r"belgi[eëu]|belgique|belgien|benelux|alle bestellingen|elke bestelling|all orders|every order|"
                         r"alle bestellungen|jede bestellung|toutes les commandes|chaque commande", re.I)
LANDCODE_BE = re.compile(r"(?<![A-Za-z])BE(?![A-Za-z])")
PRODUCTPAGINA = re.compile(r'"price"\s*:|product:price:amount', re.I)
# Een modelnaam in een tarief (P70, V70, X1, MOVA-RC-V70ULC): dan geldt het tarief voor dat product (overleg 29, X2).
MODELNAAM = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,6}-?\d{1,5}[A-Za-z]*(?![A-Za-z0-9])")
# Een EAN of GTIN met zijn label: "Barcodenummer: 6978794734941", "EAN-code\n6978...", '"gtin13": "6978..."' (overleg 35).
GTIN = re.compile(r"(?<![A-Za-z])(?:ean|gtin|barcode)(?:\d{1,2}|[a-z-]*)[^0-9]{0,20}?(?<!\d)(\d{13})(?!\d)", re.I)
GRATIS = re.compile(r"gratis|free|kostenlos|gratuit", re.I)
# Een "past" vlak na zo'n woord kan over iets anders gaan dan het toestel zelf (Codex X2, ronde 6).
ACCESSOIRE = re.compile(r"accessoire|accessory|accessories|zubeh|optione|optional|los verkrijgbaar|apart verkrijgbaar|"
                        r"sold separately|separat erh|vendu s[ée]par|laadstation|docking|onderdeel|spare part|ersatzteil|"
                        r"bundel|bundle|\bkit\b|\bset\b", re.I)
VOOR_EIS = 250                 # zoveel tekens voor een citaat bij een eis worden nagekeken en in het verslag getoond
# "Gratis verzending" voor de prijs is geen kost en mag een juiste prijs niet weigeren (Codex X1, ronde 3).
GRATIS_VERZENDING = re.compile(r"(?:gratis|free|kostenlos\w*|gratuite?)\s+(?:verzending|levering|shipping|delivery|versand|"
                               r"lieferung|livraison)|(?:verzending|levering|shipping|delivery|versand|lieferung|livraison)"
                               r"\s*(?::|is|ist|est)?\s*(?:gratis|free|kostenlos|gratuite?)", re.I)
# "Levering aan huis: vanaf di. 03 november Gratis": tekst tussen verzendwoord en gratis (overleg 33, M4).
LEVERING_DAN_GRATIS = re.compile(r"(?:verzending|levering|shipping|delivery|versand|lieferung|livraison)(.{0,50}?)"
                                 r"(?:gratis|free|kostenlos|gratuite?)", re.I | re.S)
BEDRAG_TUSSEN = re.compile(r"€|\beur(?:o|os)?\b|\d+[.,]\d{2}", re.I)
# "morgen gratis geleverd", "delivered tomorrow for free", "Verzending inbegrepen" (coolblue.be, refurbed.be; overleg 44, A)
_GELEVERD = r"(?:geleverd|bezorgd|verzonden|verstuurd|delivered|shipped|geliefert|versandt|livr[ée]e?s?)"
GELEVERD_GRATIS = re.compile(rf"(?:gratis|free|kostenlos\w*|gratuite?)\W+(?:\w+\W+){{0,3}}?{_GELEVERD}\b"
                             rf"|\b{_GELEVERD}\W+(?:\w+\W+){{0,3}}?(?:for free|gratis|kostenlos|gratuitement)", re.I)
INBEGREPEN = re.compile(r"(?:verzending|verzendkosten|levering|bezorging|shipping|versand\w*|livraison)\s*(?:is\s+|zijn\s+)?"
                        r"(?:inbegrepen|inclusief|included|inklusive|inbegriffen|incluse?)\b"
                        r"|\b(?:incl\.?|inclusief|including|inkl\.?|y compris)\s+(?:verzending|verzendkosten|levering|"
                        r"bezorging|shipping|versand\w*|livraison)", re.I)
# Een drempel voor gratis verzending: "boven de € 75,00 excl. btw", "vanaf € 99" (overleg 44, B). Alleen met een munt
# ernaast, zodat "vanaf di. 03 november" geen drempel is.
DREMPEL = re.compile(r"(?:vanaf|boven|from|over|above|ab|à partir de|dès)\s+(?:de\s+|een bedrag van\s+)?"
                     r"(?:€\s*(\d+(?:[.,]\d{1,2})?)|(\d+(?:[.,]\d{1,2})?)\s*(?:€|eur\b|euro))"
                     r"(\s*(?:excl|exkl|hors|zonder btw|ht\b|ex\.? vat|net))?", re.I)
ANDERE_LEVERWIJZE = re.compile(r"afhal|click|collect|pick.?up|abhol|retrait|retour|return|terug|rücksend|renvoi", re.I)
RETOUR = re.compile(r"retour|return|terug|rücksend|renvoi", re.I)
# Een winkel die zegt dat bedragen zonder btw zijn: dan erft de verzending de btw niet (overleg 33, X5).
EXCL_BTW = re.compile(r"excl\w*\.?\s*(?:btw|vat|tva|mwst)|zzgl\.?\s*mwst|hors\s+tva|zonder\s+btw|ohne\s+mwst|"
                      r"(?:btw|vat|tva)\s+excl", re.I)
ONTKENNING = re.compile(r"\b(?:geen|niet|no|not|kein\w*|pas|sans|ohne)\b", re.I)
VERZENDKOP = 150   # zoveel tekens voor een tarief op de verzendpagina mag het verzendwoord staan: de tabelkop (overleg 33, C)
# Alleen een doorhaling of een zinseinde scheidt; "nu" niet, dat wiste een kostwoord ervoor (Codex X14, ronde 4).
SCHEIDING = re.compile(r"~~|[.;|!?]\s")
# Een vermelding tussen haakjes vlak na het bedrag, ook na een punt, hoort bij dat bedrag (Codex X1, ronde 5).
NAHAAKJE = re.compile(r"^\W{0,3}\([^)]{0,25}\)")
NEGATIE = re.compile(r"\b(?:geen|niet|no|not|kein\w*|pas de|sans|ohne)\b\W*$", re.I)
# Een oude of doorgestreepte prijs is niet de prijs van vandaag (Codex X1, ronde 3).
OUDE_PRIJS = re.compile(r"~~|adviesprijs|oude prijs|\bvan\s*:|\bwas\s*:|\bwas\b\s*[\u20ac$\u00a3]|uvp|\bstatt\b|vorher|"
                        r"au lieu de|prix barr|\brrp\b|list price|vergelijkingsprijs|normale prijs|doorgestreept", re.I)

# Landen op 60 Hz waar Mehdi toestellen naartoe brengt; de vraag noemt het land, de code maakt er een eis van.
ZESTIG_HZ = {"suriname": "Suriname", "verenigde staten": "VS", "amerika": "VS", "usa": "VS", "canada": "Canada"}
EIS_HZ = "netfrequentie {} Hz"
EIS_V = "netspanning {} V"
# Een modelcode die de vraag zelf noemt, is bindend: een andere kleur of variant wordt nooit aanbevolen (overleg 35, X1).
EIS_MODEL = "modelcode {}"
# "Accu voor mijn Makita DDF484": het product moet op dat toestel passen (overleg 44, F). Bewezen door een citaat van de
# aanbodpagina met de code en een woord als "geschikt voor"; alleen de code ergens noemen is te weinig (X6).
EIS_PAST = "past op {}"
PAST_IN_VRAAG = re.compile(r"\b(?:voor|op|bij|met)\s+(?:mijn|onze|ons|de|het|een)\s+(?:[A-Z][\w-]+\s+)?"
                           r"([A-Z]{2,6}-?\d{3,5}[A-Z0-9]*)\b")
PASWOORD = re.compile(r"geschikt|past\b|passend|compatib|voor gebruik met|werkt met|suitable|fits|passt|kompatib|"
                      r"convient|adapté", re.I)
MODELCODE_IN_VRAAG = re.compile(r"\b(?:modelcode|typenummer|artikelnummer|fabrikantcode)\s*:?\s*([A-Za-z0-9][A-Za-z0-9./-]{3,}[A-Za-z0-9])")
# Ook zonder dat woord: hoofdletters en cijfers met een streepje, zoals MOVA-RC-V70ULC-WHT of VX-200EU (Codex
# controle 36, punt 2). Een te veel herkende code houdt een aanbeveling hoogstens tegen, ze kiest nooit verkeerd.
MODELCODE_ZONDER_LABEL = re.compile(r"(?<![A-Za-z0-9-])[A-Z0-9]+(?:-[A-Z0-9]+)+(?![A-Za-z0-9-])")


def _getal(waarde):
    """Een bedrag als getal, of None. Booleans tellen niet als bedrag."""
    if isinstance(waarde, bool) or waarde is None:
        return None
    if isinstance(waarde, (int, float)):
        return float(waarde)
    if isinstance(waarde, str):
        tekst = waarde.strip().replace(" ", "").replace(" ", "")
        if "," in tekst and "." in tekst:
            tekst = tekst.replace(".", "").replace(",", ".") if tekst.rfind(",") > tekst.rfind(".") else tekst.replace(",", "")
        elif "," in tekst:
            tekst = tekst.replace(",", ".")
        try:
            return float(tekst)
        except ValueError:
            return None
    return None


def _datum(waarde):
    if isinstance(waarde, date):
        return waarde
    try:
        return date.fromisoformat(str(waarde)[:10])
    except (TypeError, ValueError):
        return None


def eisen_uit_vraag(vraag):
    """De eisen over netspanning en netfrequentie die de vraag zelf stelt, in vaste woorden, en de modelcode die ze
    noemt. Het model beoordeelt elk aanbod op precies deze tekst; een eis die het niet beoordeelt, is onbekend en dus
    nooit de beste keuze. De modelcode toetst de code zelf (oordeel_per_eis)."""
    tekst = (vraag or "").lower()
    eisen = []
    hz = re.findall(r"\b(50|60)\s?hz\b", tekst)
    if any(land in tekst for land in ZESTIG_HZ):
        hz.append("60")
    for h in dict.fromkeys(hz):
        eisen.append(EIS_HZ.format(h))
    for v in dict.fromkeys(re.findall(r"\b(1[01]\d|12[07]|2[234]0)\s?v(?:olt)?\b", tekst)):
        eisen.append(EIS_V.format(v))
    for code in dict.fromkeys(PAST_IN_VRAAG.findall(vraag or "")):
        eisen.append(EIS_PAST.format(code))
    codes = MODELCODE_IN_VRAAG.findall(vraag or "") + MODELCODE_ZONDER_LABEL.findall(vraag or "")
    for code in dict.fromkeys(c for c in codes if any(t.isdigit() for t in c) and any(t.isalpha() for t in c)
                              and sum(t.isalnum() for t in c) >= 5):
        eisen.append(EIS_MODEL.format(code))
    return eisen


def _schoon(tekst):
    """Alle soorten spaties als een gewone spatie."""
    return SPATIES.sub(" ", tekst or "").strip()


def citaat_op_pagina(citaat, tekst):
    """Staat dit citaat letterlijk in de tekst (spaties gelijkgemaakt)? Een te kort citaat bewijst niets."""
    citaat = _schoon(str(citaat or ""))
    return len(citaat) >= MIN_CITAAT and citaat in _schoon(tekst)


def _ervoor(citaat, tekst, n):
    """De n tekens voor de eerste plaats van het citaat in de tekst (spaties gelijkgemaakt), of ""."""
    citaat, tekst = _schoon(citaat), _schoon(tekst)
    i = tekst.find(citaat) if citaat else -1
    return tekst[max(0, i - n):i] if i >= 0 else ""


def _verzendkop(citaat, tekst):
    """Staat er een verzendwoord in de VERZENDKOP tekens voor het citaat, zonder retourwoord tussen dat woord en het
    citaat ("Verzendkosten: ... Retour naar België: 9,95 euro" telt niet, overleg 33, X3)?"""
    ervoor = _ervoor(citaat, tekst, VERZENDKOP)
    laatste = list(VERZENDWOORDEN.finditer(ervoor))
    return bool(laatste) and not RETOUR.search(ervoor[laatste[-1].end():] + " " + _schoon(citaat))


def belgische_winkel(aanbod):
    """Verkoopt de winkel vanuit Belgie: land BE of een .be-adres."""
    from aankoop.onderzoek import schoon_url
    return str(aanbod.get("land") or "").upper() == "BE" or urlparse(schoon_url(aanbod.get("url"))).netloc.endswith(".be")


def voor_dit_product(citaat, aanbod):
    """Noemt een verzendtarief een model, dan moet elk genoemd model dit aanbod zijn (titel of modelcode): "P70
    gratis; V70 39,95 euro" bewijst niets voor de V70. Een tarief zonder modelnaam is algemeen (Codex-controle 30 en
    31, X2)."""
    namen = MODELNAAM.findall(str(citaat or ""))
    eigen = f"{aanbod.get('titel') or ''} {aanbod.get('modelcode') or ''}".lower()
    return all(n.lower() in eigen for n in namen)


def voor_belgie(citaat):
    """Zegt het citaat dat het tarief voor Belgie, de Benelux of alle bestellingen geldt (overleg 29, X2)?"""
    return bool(VOOR_BELGIE.search(_schoon(citaat)) or LANDCODE_BE.search(str(citaat or "")))


def gratis_verzending(tekst):
    """Zegt de tekst dat de verzending gratis is, zonder ontkenning ervoor ("geen gratis verzending", Codex X12, ronde 4)?
    Ook met tekst ertussen, zoals "Levering aan huis: vanaf di. 03 november Gratis" (overleg 33, M4): hoogstens 50
    tekens, zonder bedrag en zonder een andere leverwijze (afhaling) ertussen."""
    tekst = tekst or ""
    if any(not NEGATIE.search(tekst[max(0, m.start() - 15):m.start()]) for m in GRATIS_VERZENDING.finditer(tekst)):
        return True
    for patroon in (GELEVERD_GRATIS, INBEGREPEN):
        for m in patroon.finditer(tekst):
            na = tekst[m.end():m.end() + 25]
            if not (NEGATIE.search(tekst[max(0, m.start() - 15):m.start()]) or BEDRAG_TUSSEN.search(m.group(0))
                    or ANDERE_LEVERWIJZE.search(m.group(0)) or ONTKENNING.search(m.group(0))
                    or (BEDRAG_TUSSEN.search(na) and not DREMPEL.search(tekst[m.end():m.end() + 40]))):
                return True
    for m in LEVERING_DAN_GRATIS.finditer(tekst):
        tussen = m.group(1)
        if not (BEDRAG_TUSSEN.search(tussen) or ANDERE_LEVERWIJZE.search(tussen) or ONTKENNING.search(tussen)):
            return True
    return False


def boven_drempel(citaat, aanbod):
    """Haalt de prijs de drempel voor gratis verzending in het citaat? True zonder drempel. Een drempel zonder btw
    vergelijkt met de prijs zonder btw (een prijs met btw gedeeld door 1,21); een andere munt dan euro haalt hem nooit
    (overleg 44, B)."""
    drempels = DREMPEL.findall(_schoon(citaat))
    if not drempels:
        return True
    prijs = _getal(aanbod.get("prijs"))
    if prijs is None or str(aanbod.get("munt") or "EUR").upper() != "EUR":
        return False
    for met, zonder, excl in drempels:
        grens = _getal((met or zonder).replace(",", "."))
        netto = prijs / 1.21 if excl and aanbod.get("btw_inbegrepen") is not False else prijs
        if grens is None or netto < grens:
            return False
    return True


def _zonder_gratis_verzending(tekst):
    """De tekst zonder de niet-ontkende vermeldingen van gratis verzending: die zijn geen kost."""
    stukken, vanaf = [], 0
    for m in GRATIS_VERZENDING.finditer(tekst):
        if not NEGATIE.search(tekst[max(0, m.start() - 15):m.start()]):
            stukken.append(tekst[vanaf:m.start()])
            vanaf = m.end()
    return " ".join(stukken + [tekst[vanaf:]])


def zonder_kostwoord(citaat, tekst, ervoor=40):
    return vindplaats(citaat, tekst, ervoor) >= 0


def context(citaat, tekst, plaats=None, rond=70):
    """Het citaat met de tekst eromheen, zoals het op de pagina staat. Het verslag toont dit onder de aanbeveling,
    zodat wat het citaat weglaat (een accessoire, een oude prijs, een ander product) zichtbaar is (Codex ronde 5)."""
    citaat, tekst = _schoon(str(citaat or "")), _schoon(tekst)
    i = tekst.find(citaat) if plaats is None or plaats < 0 else plaats
    if i < 0 or not citaat:
        return ""
    begin, eind = max(0, i - rond), min(len(tekst), i + len(citaat) + rond)
    return ("..." if begin else "") + tekst[begin:eind] + ("..." if eind < len(tekst) else "")


def vindplaats(citaat, tekst, ervoor=40):
    """Staat het citaat minstens een keer op de pagina zonder een kostwoord (verzending, opgeld, kosten) of een teken
    van een oude prijs (doorgestreept, adviesprijs, "van") vlak ervoor of erin? Zo bewijst "499 euro" uit
    "Verzendkosten: 499 euro" nooit de productprijs (Codex X1, ronde 2), en "1.399" uit "~~1.399~~" ook niet (ronde 3).
    "Gratis verzending" telt niet als kost (ronde 3)."""
    citaat, tekst = _schoon(str(citaat or "")), _schoon(tekst)
    i = tekst.find(citaat)
    while i >= 0 and citaat:
        # De eerste plaats waar het citaat als productprijs geldt, of -1. Binnen een doorgestreept stuk (~~ ... ~~) is het nooit de prijs van vandaag. Wat ervoor staat, telt alleen
        # tot het laatste scheidingsteken ("Adviesprijs 1.399. Nu 1.099": "Nu 1.099" is de prijs).
        if tekst[:i].count("~~") % 2 == 0:
            ervoor_tekst = SCHEIDING.split(tekst[max(0, i - ervoor):i])[-1]
            erna = tekst[i + len(citaat):i + len(citaat) + 30]
            erna_tekst = SCHEIDING.split(erna)[0]                                           # "100 euro (oude prijs)"
            erna_tekst += " " + (NAHAAKJE.match(erna).group(0) if NAHAAKJE.match(erna) else "")  # "100 euro. (oude prijs)"
            stuk = _zonder_gratis_verzending(ervoor_tekst + citaat)
            if not KOSTWOORDEN.search(stuk) and not OUDE_PRIJS.search(stuk + erna_tekst):
                return i
        i = tekst.find(citaat, i + 1)
    return -1


def bedrag_op_pagina(bedrag, tekst):
    """Staat dit bedrag in de tekst, in een gangbare schrijfwijze (1.299,00 of 1,299.00 of 1299 of 1 299)?"""
    bedrag = _getal(bedrag)
    tekst = _schoon(tekst)
    if bedrag is None or not tekst:
        return False
    heel, cent = int(bedrag), round((bedrag - int(bedrag)) * 100)
    groepen = f"{heel:,}"
    vormen = set()
    for sep in ("", ".", ",", " ", "'"):
        h = groepen.replace(",", sep) if heel >= 1000 else str(heel)
        if cent:
            vormen |= {f"{h},{cent:02d}", f"{h}.{cent:02d}"}
            if cent % 10 == 0:
                vormen |= {f"{h},{cent // 10}", f"{h}.{cent // 10}"}
        else:
            vormen |= {h, f"{h},00", f"{h}.00", f"{h},-", f"{h},–"}
    for v in vormen:
        if re.search(rf"(?<![\d.,]){re.escape(v)}(?![\d]|[.,]\d)", tekst):
            return True
    return False


def procent_op_pagina(pct, tekst):
    """Staat dit percentage in de tekst (18%, 18 %, 18,0 %, 18.0%)?"""
    pct = _getal(pct)
    if pct is None or not tekst:
        return False
    heel = int(pct)
    vormen = {f"{pct:g}".replace(".", ","), f"{pct:g}"} | ({str(heel), f"{heel},0", f"{heel}.0"} if pct == heel else set())
    return any(re.search(rf"(?<![\d.,]){re.escape(v)}\s?%", _schoon(tekst)) for v in vormen)


def keur(aanbod, vandaag, paginatekst=None):
    """De redenen waarom dit aanbod niet in het verslag mag; een lege lijst betekent dat het mag.
    paginatekst: de tekst van de gelezen pagina van dit aanbod; None slaat de paginatoets over (alleen in tests)."""
    redenen = []
    if not isinstance(aanbod, dict):
        return ["geen aanbod"]
    url = str(aanbod.get("url") or "").strip()
    deel = urlparse(url)
    if deel.scheme not in ("http", "https") or "." not in (deel.netloc or ""):
        redenen.append("geen werkende link")
    prijs = _getal(aanbod.get("prijs"))
    if prijs is None or prijs <= 0:
        redenen.append("geen prijs")
    munt = str(aanbod.get("munt") or "").strip().upper()
    if len(munt) != 3 or not munt.isalpha():
        redenen.append("geen munt")
    gezien = _datum(aanbod.get("gezien_op"))
    if gezien is None:
        redenen.append("geen datum gezien")
    elif gezien > vandaag:
        redenen.append("datum gezien ligt in de toekomst")
    elif (vandaag - gezien).days > MAX_OUDERDOM_DAGEN:
        redenen.append("prijs te oud")
    if aanbod.get("soort") not in SOORTEN:
        redenen.append("soort onbekend")
    if aanbod.get("beschikbaar") is False:
        redenen.append("niet meer beschikbaar")
    if not str(aanbod.get("titel") or "").strip():
        redenen.append("geen productnaam")
    if paginatekst is not None:
        # De prijs hoort bij dit aanbod: een citaat van de eigen pagina met dat bedrag, dat geen bijkomende kost
        # noemt. Een bedrag dat ergens anders op de pagina staat (verzending, opgeld) bewijst niets (Codex X1, ronde 2).
        citaat = str(_bewijs(aanbod).get("prijs") or "")
        if len(_schoon(paginatekst)) < MIN_PAGINATEKST:
            redenen.append("pagina zonder leesbare tekst")
        elif prijs and not (citaat_op_pagina(citaat, paginatekst) and bedrag_op_pagina(prijs, citaat)
                            and zonder_kostwoord(citaat, paginatekst)):
            redenen.append("prijs niet bewezen op de gelezen pagina")
    return redenen


def _bewijs(aanbod):
    b = aanbod.get("bewijs") if isinstance(aanbod, dict) else None
    return b if isinstance(b, dict) else {}


def in_euro(bedrag, munt, koersen):
    """Een bedrag in euro met de koersen van de ECB (1 euro = koers munt), of None als de koers ontbreekt."""
    bedrag = _getal(bedrag)
    if bedrag is None:
        return None
    munt = str(munt or "").upper()
    if munt == "EUR":
        return bedrag
    koers = (koersen or {}).get(munt)
    if not koers:
        return None
    return bedrag / koers


def totaal(aanbod, koersen, alle_tekst=None, eigen_tekst=None, verzendtekst=None):
    """(totaal in euro of None, wat ontbreekt, toelichting). Het totaal is alleen een getal als niets ontbreekt.

    Per kostenpost (Codex X9, ronde 2): de prijs (bij een veiling met opgeld en vaste kosten) krijgt 21 procent btw
    als btw_inbegrepen onwaar is; de verzending apart volgens verzending_btw_inbegrepen (onbekend telt als de prijs).
    Buiten de EU: + douane (geschat door het model) en 21 procent btw op het geheel, door de code.
    alle_tekst: de gelezen pagina's van dezelfde host, eigen_tekst: de aanbodpagina. Elke post heeft dan een citaat
    nodig (bewijs): de verzending van de aanbodpagina, of van verzendtekst (de gelezen pagina's van dezelfde winkel
    die geen productpagina zijn) als het citaat Belgie of alle bestellingen noemt (overleg 29, X2); opgeld en
    veilingkosten van een pagina van dezelfde host:
    verzending met een verzendwoord en het bedrag, of gratis; opgeld met het percentage; veilingkosten boven nul met
    het bedrag. None slaat die toets over (alleen in tests)."""
    munt = str(aanbod.get("munt") or "").upper()
    ontbreekt, uitleg = [], []
    bewijs = _bewijs(aanbod)

    def bewezen(veld, waarde):
        if alle_tekst is None:
            return True
        citaat = str(bewijs.get(veld) or "")
        if veld == "verzending":
            # De verzendpagina van dezelfde winkel telt voor Belgie of voor alle bestellingen (Codex X16; overleg 29,
            # X2, gemeten bij RoboCleaners); een tarief voor een ander land of een ander product niet (Codex X12).
            eigen = eigen_tekst if eigen_tekst is not None else alle_tekst
            op_eigen = citaat_op_pagina(citaat, eigen)
            if not (op_eigen or (verzendtekst and citaat_op_pagina(citaat, verzendtekst)
                                 and voor_belgie(citaat) and voor_dit_product(citaat, aanbod))):
                return False
            # Een winkel buiten Belgie: ook een citaat van de eigen pagina moet zeggen dat het voor Belgie geldt
            # (beamerexpert.nl, P07; overleg 44, C).
            if op_eigen and not belgische_winkel(aanbod) and not voor_belgie(citaat):
                return False
            # In een tarieftabel staat het verzendwoord alleen in de kop: "Land | Verzendkost | België | 12,50 €"
            # (overleg 33, M3). Dat mag dan in de VERZENDKOP tekens ervoor op de verzendpagina staan.
            woord = bool(VERZENDWOORDEN.search(citaat)) or (not op_eigen and _verzendkop(citaat, verzendtekst))
        elif not citaat_op_pagina(citaat, alle_tekst):
            return veld == "veilingkosten" and not waarde      # geen vaste kosten kan je niet citeren
        if veld == "opgeld":
            return procent_op_pagina(waarde, citaat)
        if veld == "verzending":
            if waarde:
                return woord and bedrag_op_pagina(waarde, citaat)
            # "gratis retourneren" bewijst geen gratis verzending (Codex X12, ronde 3); een drempel moet gehaald zijn
            return boven_drempel(citaat, aanbod) and (gratis_verzending(_schoon(citaat)) or bool(
                woord and not NEGATIE.search(citaat) and re.search(r"(?<![\d.,])0[.,]00(?!\d)", _schoon(citaat))))
        return bedrag_op_pagina(waarde, citaat)

    def euro_veld(veld, waarde):
        if waarde is None:
            ontbreekt.append(veld)
            return 0.0
        e = in_euro(waarde, munt, koersen)
        if e is None:
            ontbreekt.append(veld)
            return 0.0
        if not bewezen(veld, _getal(waarde)):
            ontbreekt.append(f"{veld} niet bewezen")
        return e

    prijs = in_euro(aanbod.get("prijs"), munt, koersen)
    if prijs is None:
        ontbreekt.append("koers" if _getal(aanbod.get("prijs")) is not None else "prijs")
        prijs = 0.0
    goed = prijs
    if aanbod.get("soort") == "veiling":
        opgeld = _getal(aanbod.get("opgeld_pct"))
        if opgeld is None:
            ontbreekt.append("opgeld")
        else:
            if not bewezen("opgeld", opgeld):
                ontbreekt.append("opgeld niet bewezen")
            goed += prijs * opgeld / 100
        goed += euro_veld("veilingkosten", aanbod.get("veilingkosten"))
    verzending = euro_veld("verzending", aanbod.get("verzending"))
    land = str(aanbod.get("land") or "").upper()
    if land in EU:
        btw_in = aanbod.get("btw_inbegrepen")
        # Is de prijs met btw, dan is een consumentenverzending dat ook. Is de prijs zonder btw, dan moet de status van
        # de verzending apart gekend zijn; ze erft niet (Codex X9, ronde 3).
        btw_verzending = aanbod.get("verzending_btw_inbegrepen")
        # Bij een consumentenprijs met btw in de EU is de vooraf gemelde verzendkost dat ook (richtlijn 2011/83/EU,
        # art. 6.1 e: de totaalprijs met belastingen en vrachtkosten), tenzij de winkel zegt dat bedragen zonder btw
        # zijn (overleg 33, X5; vroeger nooit geërfd, Codex X9 ronde 4).
        if btw_verzending is None and btw_in is True and not EXCL_BTW.search(alle_tekst or ""):
            btw_verzending = True
        if btw_in is None or (verzending and btw_verzending is None):
            ontbreekt.append("btw")
        if btw_in is False:
            goed *= 1 + BTW
            uitleg.append("21 procent btw bijgeteld op de prijs")
        if verzending and btw_verzending is False:
            verzending *= 1 + BTW
            uitleg.append("21 procent btw bijgeteld op de verzending")
        som = goed + verzending
    elif not land:
        ontbreekt.append("land")
        som = goed + verzending
    else:
        douane = _getal(aanbod.get("douane"))
        d = in_euro(douane, munt, koersen) if douane is not None else None
        if d is None:
            ontbreekt.append("invoer")
            d = 0.0
        som = (goed + verzending + d) * (1 + BTW)
        uitleg.append("invoer: douane geschat, 21 procent btw berekend")
    return (round(som, 2) if not ontbreekt else None), ontbreekt, uitleg


# Eisen die de code uit de vraag haalt, met wat een citaat moet bevatten om "ja" te bewijzen.
_EIS_BEWIJS = re.compile(r"^(netfrequentie|netspanning) (\d+) (Hz|V)$")
_EIS_MODEL = re.compile(r"^modelcode (\S+)$")
_EIS_PAST = re.compile(r"^past op (\S+)$")


def bindend(eis):
    """Houdt deze eis zonder bevestiging een aanbeveling tegen? Netspanning, netfrequentie en de modelcode uit de vraag;
    een eigen eis van het model niet, die sluit alleen uit met "nee" (overleg 35, A en X1)."""
    return bool(_EIS_BEWIJS.match(str(eis)) or _EIS_MODEL.match(str(eis)) or _EIS_PAST.match(str(eis)))
_ANDERE_HZ = {"60": "50", "50": "60"}
# Een spanningsbereik zoals 220-240 V of 100~240V; specificatiebladen schrijven het zo (overleg 9, X1).
_SPANNING_BEREIK = re.compile(r"(?<![\d.,])(\d{2,3})\s?v?\s?(?:-|–|~|/|tot|to|bis|à)\s?(\d{2,3})\s?v(?:olts?)?\b")


def _waarde_in(eenheid, waarde, citaat):
    """Noemt het citaat de gevraagde waarde? Bij spanning telt ook een bereik dat ze omvat (220-240 V voor 220 V)."""
    c = _schoon(citaat).lower()
    if re.search(rf"(?<![\d.,]){waarde}\s?{eenheid}", c):
        return True
    return eenheid == "v" and any(int(a) <= int(waarde) <= int(b) for a, b in _SPANNING_BEREIK.findall(c))


def _twee_regios(tekst):
    """Noemt een bewijspagina netspanningen van twee streken (een losse 100 tot 130 V naast 200 tot 250 V), dan is niet
    duidelijk welke variant het aanbod is (overleg 9, K1 en X1). Een breed bereik als 100-240 V is een toestel voor
    allebei en telt hier niet mee."""
    t = _schoon(tekst).lower()
    smal = [(int(a), int(b)) for a, b in _SPANNING_BEREIK.findall(t) if int(b) - int(a) < 50]
    los = [int(v) for v in re.findall(r"(?<![\d.,])(\d{3})\s?v(?:olts?)?\b", _SPANNING_BEREIK.sub(" ", t))]
    waarden = los + [x for paar in smal for x in paar]
    return any(100 <= v <= 130 for v in waarden) and any(200 <= v <= 250 for v in waarden)


def modelcode_op(code, tekst):
    """Staat deze volledige modelcode op de pagina? Hoofdletters, spaties en streepjes tellen niet, maar een langere
    code (RLV77CEX of RLV77CE-X naast RLV77CE) is een andere variant. Een code korter dan vijf tekens, of zonder cijfer
    of letter, bewijst niets."""
    tekens = [c for c in str(code or "").lower() if c.isalnum()]
    if len(tekens) < 5 or not any(c.isdigit() for c in tekens) or not any(c.isalpha() for c in tekens):
        return False
    # Ook een aanhangsel na een liggend streepje, punt of plus is een andere variant: VX-200EU_US (Codex controle 10).
    patroon = (r"(?<![a-z0-9_])(?<![a-z0-9][-/._+])" + r"[\s\-/.]?".join(map(re.escape, tekens))
               + r"(?![a-z0-9_])(?![-/._+][a-z0-9])")
    return bool(re.search(patroon, _schoon(tekst).lower()))


_BEIDE_HZ = re.compile(r"50\s?(?:/|-|en|tot|to|bis|à)\s?60\s?hz|60\s?(?:/|-|en|tot|to|bis|à)\s?50\s?hz")


def _netspanning(v):
    return 100 <= v <= 130 or 200 <= v <= 250


def tegenstrijdig(eenheid, waarde, tekst):
    """Noemt de pagina ergens een netwaarde die de gevraagde tegenspreekt? Bij netfrequentie een losse andere
    frequentie (50 Hz naast 60 Hz; 50/60 Hz telt als allebei). Bij netspanning een losse andere netspanning of een smal
    bereik dat de gevraagde niet omvat (230 V of 220-230 V tegen 127 V; een breed bereik als 100-240 V spreekt niets
    tegen). Dan is niet zeker welk onderdeel of welke variant het citaat beschrijft, en blijft het onbekend (Codex X2
    ronde 3; controle 10: "Robot: 220-240 V, 50/60 Hz. Basisstation: 230 V, 50 Hz" bewijst niets voor 60 Hz)."""
    t = _schoon(tekst).lower()
    if eenheid == "hz":
        ander = _ANDERE_HZ.get(str(waarde))
        return bool(ander) and bool(re.search(rf"(?<![\d.,/]){ander}\s?hz", _BEIDE_HZ.sub(" ", t)))
    w = int(waarde)
    smal = [(int(a), int(b)) for a, b in _SPANNING_BEREIK.findall(t) if int(b) - int(a) < 50]
    los = [int(v) for v in re.findall(r"(?<![\d.,])(\d{3})\s?v(?:olts?)?\b", _SPANNING_BEREIK.sub(" ", t))]
    return (any(_netspanning(v) and v != w for v in los)
            or any(not a <= w <= b and (_netspanning(a) or _netspanning(b)) for a, b in smal))


def _netwaarde_bewezen(eenheid, waarde, citaat, eigen_tekst):
    """Een citaat van de pagina dat de gevraagde waarde noemt, op een pagina die nergens een andere netwaarde noemt
    (tegenstrijdig): dan is niet duidelijk welke variant of welk onderdeel het citaat beschrijft en blijft het onbekend
    (Codex X2, ronde 3: een 60 Hz-citaat van een Amerikaanse variant bewijst niets voor het Europese model op dezelfde
    pagina; controle 10: een robot op 50/60 Hz naast een basisstation op 50 Hz)."""
    if not citaat_op_pagina(citaat, eigen_tekst) or not _waarde_in(eenheid, waarde, citaat):
        return False
    return not tegenstrijdig(eenheid, waarde, eigen_tekst)


def _accessoire_ervoor(citaat, tekst):
    """Staat er in de VOOR_EIS tekens voor het citaat een woord als accessoire, optioneel of los verkrijgbaar? Dan kan
    het "past" over iets anders gaan dan het toestel, en telt het niet (Codex X2, ronde 6)."""
    citaat, tekst = _schoon(citaat), _schoon(tekst)
    i = tekst.find(citaat)
    return i >= 0 and bool(ACCESSOIRE.search(tekst[max(0, i - VOOR_EIS):i + len(citaat)]))


def _gtin_geldig(code):
    """Klopt het controlecijfer van deze EAN/GTIN (GS1, modulo 10)?"""
    cijfers = [int(c) for c in code]
    som = sum(c * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(cijfers[:-1])))
    return (10 - som % 10) % 10 == cijfers[-1]


def gtins(tekst):
    """De EAN-13-codes met label en geldig controlecijfer op een pagina (overleg 35, G3)."""
    return {c for c in GTIN.findall(str(tekst or "")) if _gtin_geldig(c)}


def _linkt(tekst, bron_url):
    """Staat bron_url op de regel "Documenten:" van deze gelezen tekst?"""
    from aankoop.onderzoek import schoon_url
    regel = next((r for r in str(tekst or "").splitlines() if r.startswith("Documenten: ")), "")
    return schoon_url(bron_url) in {schoon_url(u) for u in regel[len("Documenten: "):].split()}


def ean_pagina(eigen_tekst, paginas, aanbod, past):
    """De url van een andere gelezen pagina met dezelfde EAN als de aanbodpagina (elk precies een EAN met label en
    geldig controlecijfer) waarvoor past(tekst) geldt, of None. Het aanbod mag het model niet tegenspreken: een
    modelcode van het aanbod en elke modelnaam in zijn titel (V70) staan ook op die pagina (overleg 35, C en K3)."""
    eigen_gtin = gtins(eigen_tekst)
    if len(eigen_gtin) != 1:
        return None
    code = aanbod.get("modelcode")
    namen = {n.lower() for n in MODELNAAM.findall(str(aanbod.get("titel") or ""))}
    for u, t in (paginas or {}).items():
        if (t != eigen_tekst and gtins(t) == eigen_gtin and (not code or modelcode_op(code, t))
                and namen <= {n.lower() for n in MODELNAAM.findall(t)} and past(t)):
            return u
    return None


def gelinkt_document(bron_url, eigen_tekst, bron, aanbod, paginas=None):
    """Linkt de aanbodpagina zelf dit document (de regel "Documenten:" van de leestool) en noemt het hetzelfde model
    als het aanbod (V70 uit "MOVA V70 Ultra Complete")? Dan koppelt de winkel het aan dit product, ook zonder de
    volledige modelcode erin: de handleiding van Vanden Borre noemt "MOVA V70 Ultra Complete" en het basisstation
    RCVE0707, niet MOVA-RC-V70ULC-WHT (overleg 33, M2, X2).

    Ook goed: een andere gelezen pagina linkt het document en toont dezelfde EAN als de aanbodpagina, elk precies een
    EAN met label en geldig controlecijfer. Een EAN wijst een handelsartikel eenduidig aan: RoboCleaners toont alleen
    de barcode, Vanden Borre dezelfde barcode met de handleiding (overleg 35, M3, C)."""
    if not _linkt(eigen_tekst, bron_url) and not ean_pagina(eigen_tekst, paginas, aanbod, lambda t: _linkt(t, bron_url)):
        return False
    eigen = {n.lower() for n in MODELNAAM.findall(f"{aanbod.get('titel') or ''} {aanbod.get('modelcode') or ''}")}
    return bool(eigen & {n.lower() for n in MODELNAAM.findall(str(bron or ""))})


def bewijspagina(aanbod, o, paginas):
    """De url van een andere gelezen pagina die het model als bewijs voor een eis gaf, of None als het bewijs van de
    aanbodpagina zelf komt (overleg 9, X1)."""
    from aankoop.onderzoek import schoon_url
    u = schoon_url(o.get("bewijs_url")) if isinstance(o, dict) else ""
    return u if u and paginas is not None and u != schoon_url(aanbod.get("url")) else None


def compatibel(aanbod, eisen, alle_tekst=None, eigen_tekst=None, paginas=None):
    """"ja", "nee" of "onbekend" tegen de eisen. Zonder eisen is het "ja".

    aanbod["compatibiliteit"] is {eis: {"oordeel": "ja"|"nee"|"onbekend", "citaat": "...", "bewijs_url": "..."}} (of
    alleen het oordeel). Een eis die er niet in staat, is onbekend. Met de gelezen tekst geldt "ja" alleen met een
    citaat (Codex X2): netspanning en netfrequentie van de eigen aanbodpagina, met die waarde en zonder twijfel over de
    variant (_netwaarde_bewezen); een andere eis van een gelezen pagina. Anders wordt het "onbekend". "nee" wordt altijd
    geloofd: dat kan nooit tot een verkeerde aanbeveling leiden.

    Netspanning en netfrequentie mogen ook van een andere gelezen pagina komen (bewijs_url: fabrikant, handleiding,
    specificatieblad), maar alleen als de modelcode van het aanbod op de aanbodpagina en op die pagina staat, die
    pagina geen netspanningen van twee streken noemt, geen van beide pagina's de waarde tegenspreekt (tegenstrijdig), en
    er geen woord als accessoire voor het citaat staat (overleg 9, X1 en K1; Codex controle 10 en 11). Ook geen andere
    gelezen pagina met dezelfde modelcode mag de waarde tegenspreken, waar het bewijs ook vandaan komt (controle 12).
    paginas is {genormaliseerde url: tekst} van de gelezen pagina's."""
    if not eisen:
        return "ja"
    waarden = oordeel_per_eis(aanbod, eisen, alle_tekst, eigen_tekst, paginas)
    if "nee" in waarden:
        return "nee"
    if all(w == "ja" for w in waarden):
        return "ja"
    return "onbekend"


def oordeel_per_eis(aanbod, eisen, alle_tekst=None, eigen_tekst=None, paginas=None):
    """Het oordeel van de code per eis, in de volgorde van eisen (zie compatibel), voor compatibel en het werkverslag."""
    oordelen = aanbod.get("compatibiliteit") if isinstance(aanbod.get("compatibiliteit"), dict) else {}
    waarden = []
    for eis in eisen:
        o = oordelen.get(eis, "onbekend")
        oordeel, citaat = (o.get("oordeel"), o.get("citaat")) if isinstance(o, dict) else (o, None)
        oordeel = str(oordeel or "onbekend").lower()
        mc = _EIS_MODEL.match(eis)
        if mc and alle_tekst is not None:
            # De modelcode uit de vraag toetst de code zelf, los van het oordeel van het model: op de aanbodpagina, of
            # op een gelezen pagina met dezelfde EAN (overleg 35, X1 en C).
            code = mc.group(1)
            gevonden = modelcode_op(code, eigen_tekst or "") or ean_pagina(eigen_tekst, paginas, aanbod,
                                                                          lambda t: modelcode_op(code, t))
            waarden.append("ja" if gevonden else "nee" if oordeel == "nee" else "onbekend")
            continue
        mp = _EIS_PAST.match(eis)
        if mp and alle_tekst is not None:
            # Het citaat staat op de aanbodpagina en verbindt het toestel met een paswoord (overleg 44, F en X6).
            c = str(citaat or "")
            gevonden = (oordeel == "ja" and citaat_op_pagina(c, eigen_tekst or "") and modelcode_op(mp.group(1), c)
                        and PASWOORD.search(c) and not _accessoire_ervoor(c, eigen_tekst or ""))
            waarden.append("ja" if gevonden else "nee" if oordeel == "nee" else "onbekend")
            continue
        if oordeel == "ja" and alle_tekst is not None:
            m = _EIS_BEWIJS.match(eis)
            bron_url = bewijspagina(aanbod, o, paginas) if m else None
            bron = (paginas or {}).get(bron_url, "") if bron_url else (eigen_tekst or "")
            if bron_url:
                code = aanbod.get("modelcode")
                # Ook de aanbodpagina mag de waarde niet tegenspreken: "basisstation 50 Hz" op de winkelpagina weegt
                # zwaarder dan een handleiding die alleen de robot beschrijft (Codex controle 11).
                gekoppeld = ((modelcode_op(code, eigen_tekst or "") and modelcode_op(code, bron))
                             or gelinkt_document(bron_url, eigen_tekst or "", bron, aanbod, paginas))
                bewezen = (gekoppeld and not _twee_regios(bron)
                           and not tegenstrijdig(m.group(3).lower(), m.group(2), eigen_tekst or "")
                           and _netwaarde_bewezen(m.group(3).lower(), m.group(2), str(citaat or ""), bron))
            elif m:
                bewezen = _netwaarde_bewezen(m.group(3).lower(), m.group(2), str(citaat or ""), bron)
            else:
                bewezen = citaat_op_pagina(citaat, bron)     # van de eigen pagina (Codex X2, ronde 4)
            if bewezen and m and any(tegenstrijdig(m.group(3).lower(), m.group(2), t) for t in (paginas or {}).values()
                                     if modelcode_op(aanbod.get("modelcode"), t)):
                bewezen = False      # een andere gelezen pagina van dezelfde modelcode spreekt het tegen (Codex controle 12)
            if bewezen and _accessoire_ervoor(str(citaat or ""), bron):
                bewezen = False
            if not bewezen:
                oordeel = "onbekend"
        waarden.append(oordeel)
    return waarden


def via_ean(aanbod, eisen, per_eis, eigen_tekst, paginas):
    """{eis: url} voor elke bevestigde eis die alleen via een pagina met dezelfde EAN bewezen is, zodat het verslag die
    herkomst noemt (overleg 35, K3)."""
    compat = aanbod.get("compatibiliteit") if isinstance(aanbod.get("compatibiliteit"), dict) else {}
    code = aanbod.get("modelcode")
    uit = {}
    for eis, w in zip(eisen, per_eis):
        mc, m = _EIS_MODEL.match(str(eis)), _EIS_BEWIJS.match(str(eis))
        if w != "ja" or not (mc or m):
            continue
        if mc and not modelcode_op(mc.group(1), eigen_tekst or ""):
            uit[eis] = ean_pagina(eigen_tekst, paginas, aanbod, lambda t: modelcode_op(mc.group(1), t))
        bron_url = bewijspagina(aanbod, compat.get(eis), paginas) if m else None
        if bron_url and not _linkt(eigen_tekst, bron_url) and not (
                modelcode_op(code, eigen_tekst or "") and modelcode_op(code, paginas.get(bron_url, ""))):
            uit[eis] = ean_pagina(eigen_tekst, paginas, aanbod, lambda t: _linkt(t, bron_url))
    return {e: u for e, u in uit.items() if u}


def verwerk(aanbiedingen, vandaag, koersen, eisen=(), paginas=None):
    """Alle aanbiedingen van het model door de regels. Geeft een dict met:
    goed: in het verslag, gerangschikt (volledig totaal en compatibel eerst, dan het laagste totaal);
    niet_compatibel: apart, nooit aanbevolen; afgewezen: met hun redenen, alleen in het werkverslag;
    beste en reserve: het aanbevolen aanbod en het tweede, of None (alleen een compatibel aanbod met volledig
    totaal komt ervoor in aanmerking; overleg X2: een beste keuze en een reserve).
    paginas: {genormaliseerde url: tekst} van de gelezen pagina's; de runner geeft ze altijd mee."""
    from aankoop.onderzoek import schoon_url   # hier, zodat aanbod.py zonder de rest te testen blijft
    alle_tekst = "\n".join(paginas.values()) if paginas is not None else None

    def winkeltekst(url):
        """De gelezen pagina's van dezelfde host, voor opgeld en veilingkosten van het veilinghuis."""
        host = urlparse(schoon_url(url)).netloc
        return "\n".join(t for u, t in paginas.items() if urlparse(u).netloc == host)

    def verzendtekst(url):
        """De gelezen pagina's van dezelfde winkel die geen productpagina zijn: de verzendpagina (overleg 29, X2)."""
        host, eigen = urlparse(schoon_url(url)).netloc, schoon_url(url)
        return "\n".join(t for u, t in paginas.items()
                         if urlparse(u).netloc == host and u != eigen and not PRODUCTPAGINA.search(t))

    def contexten(a, tekst):
        """Per bewijs het citaat met de tekst eromheen en de pagina waar het staat, voor het verslag."""
        uit = {}
        b = _bewijs(a)
        if b.get("prijs"):
            uit["prijs"] = (context(b["prijs"], tekst, vindplaats(b["prijs"], tekst)), a["url"])
        host = urlparse(schoon_url(a["url"])).netloc
        if b.get("verzending") and citaat_op_pagina(b["verzending"], tekst):
            uit["verzending"] = (context(b["verzending"], tekst), a["url"])
        for veld in ("verzending", "opgeld", "veilingkosten"):
            if veld in uit:
                continue
            for u, t in paginas.items():
                if veld == "verzending" and PRODUCTPAGINA.search(t):
                    continue                    # nooit de verzendtekst van een ander product (overleg 29, X2)
                if b.get(veld) and urlparse(u).netloc == host and citaat_op_pagina(b[veld], t):
                    uit[veld] = (context(b[veld], t), u)
                    break
        compat = a.get("compatibiliteit") if isinstance(a.get("compatibiliteit"), dict) else {}
        for eis, o in compat.items():
            if not (isinstance(o, dict) and o.get("citaat")):
                continue
            bron_url = bewijspagina(a, o, paginas) if _EIS_BEWIJS.match(str(eis)) else None
            bron = paginas.get(bron_url, "") if bron_url else tekst
            if citaat_op_pagina(o["citaat"], bron):        # het bewijs met zijn pagina, ook als die niet de aanbodpagina is
                uit[eis] = (context(o["citaat"], bron, rond=VOOR_EIS), bron_url or a["url"])
        return uit
    goed, niet_compatibel, afgewezen = [], [], []
    gezien = set()
    for a in aanbiedingen or []:
        tekst = (paginas or {}).get(schoon_url(a.get("url"))) if isinstance(a, dict) and paginas is not None else None
        if paginas is not None and tekst is None:
            tekst = ""
        redenen = keur(a, vandaag, tekst)
        if redenen:
            afgewezen.append({"aanbod": a, "redenen": redenen})
            continue
        sleutel = str(a["url"]).strip().rstrip("/").lower()
        if sleutel in gezien:
            afgewezen.append({"aanbod": a, "redenen": ["dubbel"]})
            continue
        gezien.add(sleutel)
        rij = dict(a)
        rij["totaal_eur"], rij["ontbreekt"], rij["uitleg"] = (
            totaal(a, koersen, winkeltekst(a["url"]), tekst, verzendtekst(a["url"])) if paginas is not None
            else totaal(a, koersen))
        rij["compatibel"] = compatibel(a, eisen, alle_tekst, tekst, paginas)
        rij["per_eis"] = oordeel_per_eis(a, eisen, alle_tekst, tekst, paginas) if eisen else []
        rij["niet_bevestigd"] = [e for e, w in zip(eisen, rij["per_eis"]) if w != "ja"]
        # Bindend zijn netspanning, netfrequentie en de modelcode uit de vraag; een eigen eis van het model sluit alleen
        # uit met "nee" en staat anders als niet bevestigd in het verslag (overleg 35, A en X1).
        rij["kandidaat"] = (rij["totaal_eur"] is not None and rij["compatibel"] != "nee"
                            and not any(bindend(e) for e in rij["niet_bevestigd"]))
        rij["via_ean"] = via_ean(a, eisen, rij["per_eis"], tekst, paginas) if paginas is not None else {}
        rij["context"] = contexten(a, tekst) if paginas is not None else {}
        (niet_compatibel if rij["compatibel"] == "nee" else goed).append(rij)
    # Onder de kandidaten telt alleen de prijs: een bevestigde eigen eis van het model gaat niet voor een lager totaal
    # (Codex controle 36, punt 1).
    goed.sort(key=lambda r: (r["totaal_eur"] is None, not r["kandidaat"],
                             r["totaal_eur"] if r["totaal_eur"] is not None else float("inf")))
    kandidaten = [r for r in goed if r["kandidaat"]]
    beste = kandidaten[0] if kandidaten else None
    reserve = kandidaten[1] if len(kandidaten) > 1 else None
    return {"goed": goed, "niet_compatibel": niet_compatibel, "afgewezen": afgewezen, "beste": beste, "reserve": reserve}
