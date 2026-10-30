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
   ze vergeet (Codex X2).

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
GRATIS = re.compile(r"gratis|free|kostenlos|gratuit", re.I)
# Algemene pagina's van een winkel waar verzending en voorwaarden voor elk aanbod staan.
ALGEMEEN = re.compile(r"verzend|levering|shipping|delivery|versand|lieferung|livraison|voorwaarden|conditions|terms|agb|"
                      r"cgv|faq|hulp|help|service|klantenservice|veiling|auction|kosten|fees|tarie", re.I)
# "Gratis verzending" voor de prijs is geen kost en mag een juiste prijs niet weigeren (Codex X1, ronde 3).
GRATIS_VERZENDING = re.compile(r"(?:gratis|free|kostenlos\w*|gratuite?)\s+(?:verzending|levering|shipping|delivery|versand|"
                               r"lieferung|livraison)|(?:verzending|levering|shipping|delivery|versand|lieferung|livraison)"
                               r"\s*(?::|is|ist|est)?\s*(?:gratis|free|kostenlos|gratuite?)", re.I)
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
    """De eisen over netspanning en netfrequentie die de vraag zelf stelt, in vaste woorden. Het model beoordeelt elk
    aanbod op precies deze tekst; een eis die het niet beoordeelt, is onbekend en dus nooit de beste keuze."""
    tekst = (vraag or "").lower()
    eisen = []
    hz = re.findall(r"\b(50|60)\s?hz\b", tekst)
    if any(land in tekst for land in ZESTIG_HZ):
        hz.append("60")
    for h in dict.fromkeys(hz):
        eisen.append(EIS_HZ.format(h))
    for v in dict.fromkeys(re.findall(r"\b(1[01]\d|12[07]|2[234]0)\s?v(?:olt)?\b", tekst)):
        eisen.append(EIS_V.format(v))
    return eisen


def _schoon(tekst):
    """Alle soorten spaties als een gewone spatie."""
    return SPATIES.sub(" ", tekst or "").strip()


def citaat_op_pagina(citaat, tekst):
    """Staat dit citaat letterlijk in de tekst (spaties gelijkgemaakt)? Een te kort citaat bewijst niets."""
    citaat = _schoon(str(citaat or ""))
    return len(citaat) >= MIN_CITAAT and citaat in _schoon(tekst)


def gratis_verzending(tekst):
    """Zegt de tekst dat de verzending gratis is, zonder ontkenning ervoor ("geen gratis verzending", Codex X12, ronde 4)?"""
    return any(not NEGATIE.search(tekst[max(0, m.start() - 15):m.start()]) for m in GRATIS_VERZENDING.finditer(tekst or ""))


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


def totaal(aanbod, koersen, alle_tekst=None):
    """(totaal in euro of None, wat ontbreekt, toelichting). Het totaal is alleen een getal als niets ontbreekt.

    Per kostenpost (Codex X9, ronde 2): de prijs (bij een veiling met opgeld en vaste kosten) krijgt 21 procent btw
    als btw_inbegrepen onwaar is; de verzending apart volgens verzending_btw_inbegrepen (onbekend telt als de prijs).
    Buiten de EU: + douane (geschat door het model) en 21 procent btw op het geheel, door de code.
    alle_tekst: de tekst van alle gelezen pagina's. Elke post heeft dan een citaat nodig dat erin staat (bewijs):
    verzending met een verzendwoord en het bedrag, of gratis; opgeld met het percentage; veilingkosten boven nul met
    het bedrag. None slaat die toets over (alleen in tests)."""
    munt = str(aanbod.get("munt") or "").upper()
    ontbreekt, uitleg = [], []
    bewijs = _bewijs(aanbod)

    def bewezen(veld, waarde):
        if alle_tekst is None:
            return True
        citaat = str(bewijs.get(veld) or "")
        if not citaat_op_pagina(citaat, alle_tekst):
            return veld == "veilingkosten" and not waarde      # geen vaste kosten kan je niet citeren
        if veld == "opgeld":
            return procent_op_pagina(waarde, citaat)
        if veld == "verzending":
            if waarde:
                return bool(VERZENDWOORDEN.search(citaat)) and bedrag_op_pagina(waarde, citaat)
            # "gratis retourneren" bewijst geen gratis verzending (Codex X12, ronde 3)
            return gratis_verzending(_schoon(citaat)) or bool(
                VERZENDWOORDEN.search(citaat) and not NEGATIE.search(citaat)
                and re.search(r"(?<![\d.,])0[.,]00(?!\d)", _schoon(citaat)))
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
        btw_verzending = aanbod.get("verzending_btw_inbegrepen")    # nooit geërfd (Codex X9, ronde 3 en 4)
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
_ANDERE_HZ = {"60": "50", "50": "60"}


def _netwaarde_bewezen(eenheid, waarde, citaat, eigen_tekst):
    """Een citaat van de eigen aanbodpagina dat de gevraagde waarde noemt. Bij netfrequentie: noemt het citaat of de
    eigen pagina ook de andere frequentie (50 tegen 60 Hz), behalve als een toestel voor allebei (50/60 Hz), dan is het
    niet duidelijk welke variant dit aanbod is en blijft het onbekend (Codex X2, ronde 3: een 60 Hz-citaat van een
    Amerikaanse variant bewijst niets voor het Europese model op dezelfde pagina)."""
    c = _schoon(citaat).lower()
    if not citaat_op_pagina(citaat, eigen_tekst) or not re.search(rf"(?<!\d){waarde}\s?{eenheid}", c):
        return False
    if eenheid == "hz":
        beide = re.compile(r"50\s?(?:/|-|en|tot|to|bis|à)\s?60\s?hz|60\s?(?:/|-|en|tot|to|bis|à)\s?50\s?hz")
        pagina = _schoon(eigen_tekst).lower()
        if beide.search(c) or beide.search(pagina):
            return True
        ander = _ANDERE_HZ.get(waarde)
        if ander and re.search(rf"(?<!\d){ander}\s?hz", pagina):
            return False
    return True


def compatibel(aanbod, eisen, alle_tekst=None, eigen_tekst=None):
    """"ja", "nee" of "onbekend" tegen de eisen. Zonder eisen is het "ja".

    aanbod["compatibiliteit"] is {eis: {"oordeel": "ja"|"nee"|"onbekend", "citaat": "..."}} (of alleen het oordeel).
    Een eis die er niet in staat, is onbekend. Met de gelezen tekst geldt "ja" alleen met een citaat (Codex X2):
    netspanning en netfrequentie van de eigen aanbodpagina, met die waarde en zonder twijfel over de variant
    (_netwaarde_bewezen); een andere eis van een gelezen pagina. Anders wordt het "onbekend". "nee" wordt altijd
    geloofd: dat kan nooit tot een verkeerde aanbeveling leiden."""
    if not eisen:
        return "ja"
    oordelen = aanbod.get("compatibiliteit") if isinstance(aanbod.get("compatibiliteit"), dict) else {}
    waarden = []
    for eis in eisen:
        o = oordelen.get(eis, "onbekend")
        oordeel, citaat = (o.get("oordeel"), o.get("citaat")) if isinstance(o, dict) else (o, None)
        oordeel = str(oordeel or "onbekend").lower()
        if oordeel == "ja" and alle_tekst is not None:
            m = _EIS_BEWIJS.match(eis)
            if m:
                bewezen = _netwaarde_bewezen(m.group(3).lower(), m.group(2), str(citaat or ""), eigen_tekst or "")
            else:
                bewezen = citaat_op_pagina(citaat, eigen_tekst or "")     # van de eigen pagina (Codex X2, ronde 4)
            if not bewezen:
                oordeel = "onbekend"
        waarden.append(oordeel)
    if "nee" in waarden:
        return "nee"
    if all(w == "ja" for w in waarden):
        return "ja"
    return "onbekend"


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
        """De gelezen pagina's van dezelfde winkel: daar horen verzending, opgeld en voorwaarden van dit aanbod
        (Codex X12, ronde 4: een kostencitaat van een andere winkel bewijst niets)."""
        return "\n".join(t for _, t in winkelpaginas(url))

    def winkelpaginas(url):
        """De eigen aanbodpagina en de algemene pagina's van dezelfde winkel (verzending, voorwaarden, hulp), niet de
        pagina van een ander product (Codex X12, ronde 5)."""
        eigen, host = schoon_url(url), urlparse(schoon_url(url)).netloc
        return [(u, t) for u, t in paginas.items()
                if u == eigen or (urlparse(u).netloc == host and ALGEMEEN.search(urlparse(u).path))]

    def contexten(a, tekst):
        """Per bewijs het citaat met de tekst eromheen en de pagina waar het staat, voor het verslag."""
        uit = {}
        b = _bewijs(a)
        if b.get("prijs"):
            uit["prijs"] = (context(b["prijs"], tekst, vindplaats(b["prijs"], tekst)), a["url"])
        for veld in ("verzending", "opgeld", "veilingkosten"):
            for u, t in winkelpaginas(a["url"]):
                if b.get(veld) and citaat_op_pagina(b[veld], t):
                    uit[veld] = (context(b[veld], t), u)
                    break
        compat = a.get("compatibiliteit") if isinstance(a.get("compatibiliteit"), dict) else {}
        for eis, o in compat.items():
            if isinstance(o, dict) and o.get("citaat") and citaat_op_pagina(o["citaat"], tekst):
                uit[eis] = (context(o["citaat"], tekst), a["url"])
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
        rij["totaal_eur"], rij["ontbreekt"], rij["uitleg"] = totaal(a, koersen,
                                                                  winkeltekst(a["url"]) if paginas is not None else None)
        rij["compatibel"] = compatibel(a, eisen, alle_tekst, tekst)
        rij["context"] = contexten(a, tekst) if paginas is not None else {}
        (niet_compatibel if rij["compatibel"] == "nee" else goed).append(rij)
    goed.sort(key=lambda r: (r["totaal_eur"] is None, r["compatibel"] != "ja",
                             r["totaal_eur"] if r["totaal_eur"] is not None else float("inf")))
    kandidaten = [r for r in goed if r["totaal_eur"] is not None and r["compatibel"] == "ja"]
    beste = kandidaten[0] if kandidaten else None
    reserve = kandidaten[1] if len(kandidaten) > 1 else None
    return {"goed": goed, "niet_compatibel": niet_compatibel, "afgewezen": afgewezen, "beste": beste, "reserve": reserve}
