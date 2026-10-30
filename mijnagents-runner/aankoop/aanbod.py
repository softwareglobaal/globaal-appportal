"""Een aanbod keuren, de totaalprijs in euro rekenen en de aanbiedingen rangschikken.

Het taalmodel zoekt; deze module beslist wat in het verslag mag. Drie regels die nooit aan het model
worden overgelaten:

1. Geen link, geen prijs of geen datum gezien: het aanbod gaat niet in het verslag (afgewezen, met reden).
2. Een totaalprijs is pas volledig met verzending, bij een veiling het opgeld en buiten de EU de invoer
   (btw en douane). Ontbreekt er iets, dan staat het aanbod er met "totaal onvolledig" en wat ontbreekt,
   en kan het nooit als beste aanbod bovenaan komen.
3. Een aanbod dat niet past bij een eis uit de vraag (spanning, stekker, aansluiting) staat apart onder
   "niet compatibel" en wordt nooit aanbevolen, hoe goedkoop ook.

Draaien van de tests: python3 mijnagents-runner/tests/test_aankoop_prijs.py
"""
from datetime import date
from urllib.parse import urlparse

SOORTEN = ("nieuw", "refurbished", "tweedehands", "veiling")
# Een prijs die langer geleden gezien is, geldt niet meer als actueel aanbod.
MAX_OUDERDOM_DAGEN = 3
# De lidstaten van de EU (ISO 3166 alpha-2). Binnen de EU geen invoer; buiten de EU moet de invoer erbij.
EU = frozenset("AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split())


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


def keur(aanbod, vandaag):
    """De redenen waarom dit aanbod niet in het verslag mag; een lege lijst betekent dat het mag."""
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


def totaal(aanbod, koersen):
    """(totaal in euro of None, wat ontbreekt). Het totaal is alleen een getal als niets ontbreekt.

    prijs + verzending; bij een veiling + opgeld (procent op de hamerprijs) + vaste veilingkosten (0 als er geen zijn);
    buiten de EU + invoerkosten (btw, douane en inklaring, zoals de bron ze geeft)."""
    munt = str(aanbod.get("munt") or "").upper()
    ontbreekt = []
    prijs = in_euro(aanbod.get("prijs"), munt, koersen)
    if prijs is None:
        ontbreekt.append("koers" if _getal(aanbod.get("prijs")) is not None else "prijs")
    som = prijs or 0.0
    if aanbod.get("verzending") is None:
        ontbreekt.append("verzending")
    else:
        verzending = in_euro(aanbod["verzending"], munt, koersen)
        if verzending is None:
            ontbreekt.append("verzending")
        else:
            som += verzending
    if aanbod.get("soort") == "veiling":
        opgeld = _getal(aanbod.get("opgeld_pct"))
        if opgeld is None:
            ontbreekt.append("opgeld")
        elif prijs is not None:
            som += prijs * opgeld / 100
        # Onbekende vaste kosten zijn geen nul (overleg K3): 0 alleen als de voorwaarden zeggen dat er geen zijn.
        if aanbod.get("veilingkosten") is None:
            ontbreekt.append("veilingkosten")
        else:
            kosten = in_euro(aanbod["veilingkosten"], munt, koersen)
            if kosten is None:
                ontbreekt.append("veilingkosten")
            else:
                som += kosten
    land = str(aanbod.get("land") or "").upper()
    if land not in EU:
        if aanbod.get("invoer") is None:
            ontbreekt.append("invoer" if land else "land")
        else:
            invoer = in_euro(aanbod["invoer"], munt, koersen)
            if invoer is None:
                ontbreekt.append("invoer")
            else:
                som += invoer
    return (round(som, 2) if not ontbreekt else None), ontbreekt


def compatibel(aanbod, eisen):
    """"ja", "nee" of "onbekend" tegen de eisen uit de vraag. Zonder eisen is het "ja".

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


def verwerk(aanbiedingen, vandaag, koersen, eisen=()):
    """Alle aanbiedingen van het model door de regels. Geeft een dict met:
    goed: in het verslag, gerangschikt (volledig totaal en compatibel eerst, dan het laagste totaal);
    niet_compatibel: apart, nooit aanbevolen; afgewezen: met hun redenen, alleen in het werkverslag;
    beste en reserve: het aanbevolen aanbod en het tweede, of None (alleen een compatibel aanbod met volledig
    totaal komt ervoor in aanmerking; overleg X2: een beste keuze en een reserve)."""
    goed, niet_compatibel, afgewezen = [], [], []
    gezien = set()
    for a in aanbiedingen or []:
        redenen = keur(a, vandaag)
        if redenen:
            afgewezen.append({"aanbod": a, "redenen": redenen})
            continue
        sleutel = str(a["url"]).strip().rstrip("/").lower()
        if sleutel in gezien:
            afgewezen.append({"aanbod": a, "redenen": ["dubbel"]})
            continue
        gezien.add(sleutel)
        rij = dict(a)
        rij["totaal_eur"], rij["ontbreekt"] = totaal(a, koersen)
        rij["compatibel"] = compatibel(a, eisen)
        (niet_compatibel if rij["compatibel"] == "nee" else goed).append(rij)
    goed.sort(key=lambda r: (r["totaal_eur"] is None, r["compatibel"] != "ja",
                             r["totaal_eur"] if r["totaal_eur"] is not None else float("inf")))
    kandidaten = [r for r in goed if r["totaal_eur"] is not None and r["compatibel"] == "ja"]
    beste = kandidaten[0] if kandidaten else None
    reserve = kandidaten[1] if len(kandidaten) > 1 else None
    return {"goed": goed, "niet_compatibel": niet_compatibel, "afgewezen": afgewezen, "beste": beste, "reserve": reserve}
