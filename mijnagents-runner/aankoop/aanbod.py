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


def bedrag_op_pagina(bedrag, tekst):
    """Staat dit bedrag in de tekst, in een gangbare schrijfwijze (1.299,00 of 1,299.00 of 1299 of 1 299)?"""
    bedrag = _getal(bedrag)
    if bedrag is None or not tekst:
        return False
    heel, cent = int(bedrag), round((bedrag - int(bedrag)) * 100)
    groepen = f"{heel:,}"
    vormen = set()
    for sep in ("", ".", ",", " ", " ", "'"):
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
    return any(re.search(rf"(?<![\d.,]){re.escape(v)}\s?%", tekst) for v in vormen)


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
        if len(paginatekst.strip()) < MIN_PAGINATEKST:
            redenen.append("pagina zonder leesbare tekst")
        elif prijs and not bedrag_op_pagina(prijs, paginatekst):
            redenen.append("prijs niet op de gelezen pagina")
    return redenen


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

    prijs + verzending, + btw als de prijs zonder btw is; bij een veiling + opgeld (procent op de hamerprijs) + vaste
    veilingkosten (0 als er geen zijn); buiten de EU + douane (geschat door het model) + 21 procent btw op het geheel.
    alle_tekst: de tekst van alle gelezen pagina's; opgeld, verzending en veilingkosten boven nul moeten erin staan.
    None slaat die toets over (alleen in tests)."""
    munt = str(aanbod.get("munt") or "").upper()
    ontbreekt, uitleg = [], []

    def bewezen(veld, waarde):
        if alle_tekst is None or not waarde:
            return True
        return procent_op_pagina(waarde, alle_tekst) if veld == "opgeld" else bedrag_op_pagina(waarde, alle_tekst)

    def euro_veld(veld, waarde):
        if waarde is None:
            ontbreekt.append(veld)
            return 0.0
        e = in_euro(waarde, munt, koersen)
        if e is None:
            ontbreekt.append(veld)
            return 0.0
        if not bewezen(veld, _getal(waarde)):
            ontbreekt.append(f"{veld} niet op een gelezen pagina")
        return e

    prijs = in_euro(aanbod.get("prijs"), munt, koersen)
    if prijs is None:
        ontbreekt.append("koers" if _getal(aanbod.get("prijs")) is not None else "prijs")
        prijs = 0.0
    verzending = euro_veld("verzending", aanbod.get("verzending"))
    som = prijs + verzending
    if aanbod.get("soort") == "veiling":
        opgeld = _getal(aanbod.get("opgeld_pct"))
        if opgeld is None:
            ontbreekt.append("opgeld")
        else:
            if not bewezen("opgeld", opgeld):
                ontbreekt.append("opgeld niet op een gelezen pagina")
            som += prijs * opgeld / 100
        som += euro_veld("veilingkosten", aanbod.get("veilingkosten"))
    land = str(aanbod.get("land") or "").upper()
    if land in EU:
        btw_in = aanbod.get("btw_inbegrepen")
        if btw_in is False:
            som *= 1 + BTW
            uitleg.append("21 procent btw bijgeteld")
        elif btw_in is not True:
            ontbreekt.append("btw")
    elif not land:
        ontbreekt.append("land")
    else:
        douane = _getal(aanbod.get("douane"))
        if douane is None:
            ontbreekt.append("invoer")
        else:
            d = in_euro(douane, munt, koersen)
            if d is None:
                ontbreekt.append("invoer")
            else:
                som = (som + d) * (1 + BTW)
                uitleg.append("invoer: douane geschat, 21 procent btw berekend")
    return (round(som, 2) if not ontbreekt else None), ontbreekt, uitleg


def compatibel(aanbod, eisen):
    """"ja", "nee" of "onbekend" tegen de eisen. Zonder eisen is het "ja".

    aanbod["compatibiliteit"] is {eis: "ja"|"nee"|"onbekend"}. Een eis die er niet in staat, is onbekend."""
    if not eisen:
        return "ja"
    oordeel = aanbod.get("compatibiliteit") if isinstance(aanbod.get("compatibiliteit"), dict) else {}
    waarden = [str(oordeel.get(eis, "onbekend")).lower() for eis in eisen]
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
        rij["totaal_eur"], rij["ontbreekt"], rij["uitleg"] = totaal(a, koersen, alle_tekst)
        rij["compatibel"] = compatibel(a, eisen)
        (niet_compatibel if rij["compatibel"] == "nee" else goed).append(rij)
    goed.sort(key=lambda r: (r["totaal_eur"] is None, r["compatibel"] != "ja",
                             r["totaal_eur"] if r["totaal_eur"] is not None else float("inf")))
    kandidaten = [r for r in goed if r["totaal_eur"] is not None and r["compatibel"] == "ja"]
    beste = kandidaten[0] if kandidaten else None
    reserve = kandidaten[1] if len(kandidaten) > 1 else None
    return {"goed": goed, "niet_compatibel": niet_compatibel, "afgewezen": afgewezen, "beste": beste, "reserve": reserve}
