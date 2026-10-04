"""Adres naar coördinaat en terug, voor de projectplekken en het dagboek.

Volgorde zoals Mehdi het wil (03-10-2026: "Google Maps is geen referentie, Geopunt
wel"): eerst Geopunt, de officiële adresdienst van de Vlaamse overheid, en pas als
die niets vindt (Brussel, Wallonië, een schrijfwijze die Geopunt niet kent)
Nominatim. Zelfde diensten en dezelfde lessen als koppelingen/adresregister.py
(Geopunt, busnummer weg) en agenda_wacht.coord() (gestructureerd zoeken op straat
en postcode, want een deelgemeente als Kessel-Lo kent Nominatim niet) in
mijnagents-runner. Deze container kan die modules niet laden, dus staat de kern
hier; wie daar iets verbetert, kijkt ook hier.

Elke uitkomst draagt zijn kwaliteit: 'adres' (op huisnummer), 'straat',
'gemeente' of 'niet_gevonden'. Alleen 'adres' mag een verblijf aan een project
koppelen (herkenning.BRUIKBAAR).
"""
import json
import re
import time
import urllib.parse
import urllib.request

UA = "globaal-locatielogboek/2.0 (mch@h-architects.be)"
GEOLOC = "https://geo.api.vlaanderen.be/geolocation/v4/Location"
NOMINATIM = "https://nominatim.openstreetmap.org"
_laatste_nominatim = [0.0]

POSTCODE = re.compile(r"\b(\d{4})\b")
BUS = re.compile(r"\s*(?:/|\bbus\b|\bbt\.?)\s*[A-Za-z]?\d+[A-Za-z]?\b", re.I)


def _get(url, timeout=20):
    verzoek = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(verzoek, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _nominatim(pad, params):
    wacht = 1.1 - (time.time() - _laatste_nominatim[0])
    if wacht > 0:
        time.sleep(wacht)               # nooit sneller dan een vraag per seconde
    _laatste_nominatim[0] = time.time()
    return _get(f"{NOMINATIM}/{pad}?" + urllib.parse.urlencode(params))


def zonder_bus(adres):
    """'Pontstraat 72 bus 1, 9300 Aalst' -> 'Pontstraat 72, 9300 Aalst'. Het gebouw zit op het huisnummer."""
    return BUS.sub("", adres or "").strip()


def splits(adres):
    """(straat met nummer, postcode, gemeente) of (adres, None, None)."""
    m = re.search(r"^(.*?),?\s*(\d{4})\s+([A-Za-zÀ-ÿ' .\-]+?)\s*$", (adres or "").strip())
    if not m:
        return adres, None, None
    return m.group(1).strip(" ,"), m.group(2), m.group(3).strip()


def geopunt(adres):
    a = zonder_bus(adres)
    d = _get(GEOLOC + "?" + urllib.parse.urlencode({"q": a, "c": 1}))
    res = d.get("LocationResult") or []
    if not res:
        return None
    l = res[0]
    _, post, _ = splits(a)
    # Geopunt vult aan wat het niet vindt; een andere postcode is een ander adres.
    if post and l.get("Zipcode") and str(l["Zipcode"]) != post:
        return None
    kwaliteit = "adres" if l.get("Housenumber") else ("straat" if l.get("Thoroughfarename") else "gemeente")
    p = l["Location"]
    return {"lat": p["Lat_WGS84"], "lon": p["Lon_WGS84"], "kwaliteit": kwaliteit, "bron": "geopunt",
            "gevonden": l.get("FormattedAddress")}


def nominatim(adres):
    a = zonder_bus(adres)
    straat, post, gemeente = splits(a)
    pogingen = []
    if post:
        pogingen.append({"street": straat.split(",")[-1].strip(), "postalcode": post, "country": "Belgium"})
    pogingen.append({"q": a, "countrycodes": "be,nl"})
    if post and gemeente:
        pogingen.append({"q": f"{straat}, {gemeente}, België", "countrycodes": "be,nl"})
    for q in pogingen:
        q.update(format="jsonv2", limit=1, addressdetails=1)
        try:
            d = _nominatim("search", q)
        except Exception:  # noqa: BLE001
            continue
        if not d:
            continue
        r = d[0]
        adr = r.get("address") or {}
        if post and adr.get("postcode") and adr["postcode"][:4] != post:
            continue
        kwaliteit = "adres" if adr.get("house_number") else ("straat" if adr.get("road") else "gemeente")
        return {"lat": float(r["lat"]), "lon": float(r["lon"]), "kwaliteit": kwaliteit, "bron": "nominatim",
                "gevonden": r.get("display_name", "")[:160]}
    return None


LABELS = re.compile(r"^\s*((\([^)]*\)|\[[^\]]*\])\s*)+")
REEKS = re.compile(r"(\b\d+)(?:\s*[-–.]\s*\d+[A-Za-z]?)+(?=\s*,|\s+\d{4}\b|\s*$)")
LETTER = re.compile(r"(\b\d+)\s*[A-Za-z]{1,2}(?:\s+(?:rechts|links|in|achter|voor|boven|beneden))?(?=\s*,|\s+\d{4}\b|\s*$)",
                    re.I)


def varianten(adres):
    """De schrijfwijzen die we proberen, de oorspronkelijke eerst. De bron blijft zoals ze is.

    Gemeten bij de eerste synchronisatie (04-10-2026): 39 van de 197 projectadressen kwamen
    niet terug, omdat de mapnaam labels vooraan draagt ('(INR) (HP) ...', '[INT EPB-VC] ...'),
    een reeks huisnummers ('95-97-99', '210 - 212', '10.4') of een letter of woord achter het
    huisnummer ('12A', '127B rechts', '163b in'). Geopunt en Nominatim kennen die vormen niet.
    """
    a = re.sub(r"\s+[–-]\s*(?=,|$)", "", LABELS.sub("", adres or "").strip())
    uit = [adres.strip()] if adres.strip() != a else []
    for v in (a, REEKS.sub(r"\1", a), LETTER.sub(r"\1", REEKS.sub(r"\1", a))):
        if v and v not in uit:
            uit.append(v)
    return uit


def geocodeer(adres):
    """Adres naar {lat, lon, kwaliteit, bron, gevonden}. Gooit niet; een fout is een uitkomst."""
    if not (adres or "").strip() or not re.search(r"\d", adres or ""):
        # Zonder enig cijfer (geen huisnummer, geen postcode, bv. 'not signed') is het geen adres.
        return {"lat": None, "lon": None, "kwaliteit": "geen_adres", "bron": None, "gevonden": None}
    fouten, beste = [], None
    for zoeker in (geopunt, nominatim):
        for v in varianten(adres):
            try:
                uit = zoeker(v)
            except Exception as e:  # noqa: BLE001
                fouten.append(f"{zoeker.__name__}: {type(e).__name__}")
                continue
            if uit and uit["kwaliteit"] == "adres":
                if v != adres.strip():
                    uit["variant"] = v
                return uit
            if uit:
                fouten.append(f"{zoeker.__name__}: alleen {uit['kwaliteit']}")
                beste = beste or uit
    if beste:
        return beste          # te grof om te herkennen, maar wel zichtbaar in de dekking
    return {"lat": None, "lon": None, "kwaliteit": "niet_gevonden", "bron": None, "gevonden": "; ".join(fouten)}


def omgekeerd(lat, lon):
    """Coördinaat naar een kort adres (Nominatim), of None."""
    try:
        d = _nominatim("reverse", {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 18, "accept-language": "nl"})
    except Exception:  # noqa: BLE001
        return None
    a = d.get("address", {})
    straat = " ".join(x for x in (a.get("road"), a.get("house_number")) if x)
    plaats = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or a.get("suburb") or ""
    kort = ", ".join(x for x in (straat, f"{a.get('postcode', '')} {plaats}".strip()) if x)
    return {"adres": kort or d.get("display_name", "")[:80], "volledig": d.get("display_name", "")}
