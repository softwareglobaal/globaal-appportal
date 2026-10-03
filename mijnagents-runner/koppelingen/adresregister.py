"""Geopunt en het Adressenregister: een adres officieel maken voor we in een archief zoeken.

Mehdi, 03-10-2026: "Google Maps is geen referentie. Geopunt is een veel betere referentie."
Een appartementsgebouw draagt vaak meer dan een huisnummer (August Van de Wielelei 85 en 87 staan
op hetzelfde perceel, het dossier in FelixArchief heet "85-87"), en een hoekpand kan vanuit elk van
zijn straten aangevraagd zijn. Daarom geeft deze module niet een adres terug maar het pand:
de officiele straatnaam, alle huisnummers op hetzelfde perceel, en de straten die er vlak naast liggen.

Alleen publieke diensten van de Vlaamse overheid, zonder sleutel:
- geo.api.vlaanderen.be/geolocation/v4   adres -> punt, en punt -> dichtste adressen
- api.basisregisters.vlaanderen.be/v2    adressen, busnummers, percelen
"""
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

GEOLOC = "https://geo.api.vlaanderen.be/geolocation/v4/Location"
REGISTER = "https://api.basisregisters.vlaanderen.be/v2"
HOEK_AFSTAND_M = 30  # een andere straat binnen deze afstand van het adrespunt: mogelijk hoekpand


def _get(url, accept="application/json", timeout=30):
    verzoek = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "globaal-felixwacht/1.0"})
    with urllib.request.urlopen(verzoek, timeout=timeout) as antwoord:
        return json.loads(antwoord.read().decode("utf-8"))


def _register(pad, **params):
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    return _get(f"{REGISTER}/{pad}{q}", accept="application/ld+json")


BUS_RE = re.compile(r"(\b\d+[A-Za-z]?)\s*(?:/|\bbus\b|\bbt\.?|\bb\.?)\s*([A-Za-z]?\d+[A-Za-z]?|[A-Za-z])\b", re.I)


def splits_bus(adres):
    """'August van de Wielelei 85/101, 2100 Deurne' -> ('August van de Wielelei 85, 2100 Deurne', '101').

    Geopunt vindt een adres met busnummer niet; het gebouw zit op het huisnummer. Het busnummer
    bewaren we wel, het zegt welk appartement de klant bedoelt.
    """
    m = BUS_RE.search(adres or "")
    if not m:
        return adres, None
    return adres[:m.start()] + m.group(1) + adres[m.end():], m.group(2)


def lokaliseer(adres):
    """Adres in vrije tekst -> het officiele adres volgens Geopunt, of None."""
    d = _get(f"{GEOLOC}?" + urllib.parse.urlencode({"q": adres, "c": 1}))
    res = d.get("LocationResult") or []
    if not res:
        return None
    l = res[0]
    p = l["Location"]
    return {
        "geopunt": l.get("FormattedAddress"),
        "straat": l.get("Thoroughfarename"),
        "huisnummer": l.get("Housenumber"),
        "postcode": l.get("Zipcode"),
        "gemeente": l.get("Municipality"),
        "soort": l.get("LocationType"),
        "x": p["X_Lambert72"], "y": p["Y_Lambert72"],
        "lat": p["Lat_WGS84"], "lon": p["Lon_WGS84"],
    }


def _adres_detail(objectid):
    d = _register(f"adressen/{objectid}")
    straat = (((d.get("straatnaam") or {}).get("straatnaam") or {}).get("geografischeNaam") or {}).get("spelling")
    return {"id": str(objectid), "straat": straat, "huisnummer": d.get("huisnummer"),
            "busnummer": d.get("busnummer"), "status": d.get("adresStatus")}


def adressen_op_huisnummer(gemeente, straat, huisnummer):
    """Alle adresobjecten op dit huisnummer: het hoofdadres en de busnummers."""
    d = _register("adressen", gemeentenaam=gemeente, straatnaam=straat, huisnummer=huisnummer, limit=500)
    return [{"id": a["identificator"]["objectId"], "huisnummer": a.get("huisnummer"),
             "busnummer": a.get("busnummer"), "status": a.get("adresStatus")} for a in d.get("adressen", [])]


def percelen_van(adres_id):
    d = _register("percelen", adresObjectId=adres_id)
    return [p["identificator"]["objectId"] for p in d.get("percelen", [])]


def adressen_op_perceel(capakey, maximum=300):
    """Alle adressen op een perceel, met hun straat. Een perceel met adressen in twee straten is een hoekpand."""
    d = _register("percelen/" + urllib.parse.quote(capakey, safe=""))
    ids = [a["objectId"] for a in d.get("adressen", [])][:maximum]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(_adres_detail, ids))


def buren(lat, lon, aantal=15):
    """De dichtste adressen rond een punt, met hun afstand in meter (Lambert72)."""
    d = _get(f"{GEOLOC}?" + urllib.parse.urlencode({"latlon": f"{lat},{lon}", "c": aantal}))
    return [{"adres": l.get("FormattedAddress"), "straat": l.get("Thoroughfarename"),
             "huisnummer": l.get("Housenumber"),
             "x": l["Location"]["X_Lambert72"], "y": l["Location"]["Y_Lambert72"]}
            for l in d.get("LocationResult", [])]


def _sorteer(nummers):
    def sleutel(n):
        cijfers = "".join(c for c in (n or "") if c.isdigit())
        return (int(cijfers) if cijfers else 0, n or "")
    return sorted(set(nummers), key=sleutel)


def pand(adres):
    """Het volledige beeld van een pand volgens Geopunt, als basis voor elke archiefzoektocht.

    Geeft het officiele adres, de huisnummers die op hetzelfde perceel staan (per straat),
    de straten die binnen HOEK_AFSTAND_M liggen, en wat er onderweg niet lukte. Gooit nooit:
    wat niet gevonden wordt, staat in 'opmerkingen', want ook dat is bewijs.
    """
    uit = {"invoer": adres, "opmerkingen": []}
    zonder_bus, bus = splits_bus(adres)
    if bus:
        uit["bus_invoer"] = bus
    loc = lokaliseer(zonder_bus)
    if not loc:
        uit["opmerkingen"].append("Geopunt vindt dit adres niet.")
        return uit
    uit.update(loc)
    try:
        objecten = adressen_op_huisnummer(loc["gemeente"], loc["straat"], loc["huisnummer"])
    except Exception as e:  # het register kan haperen; het punt van Geopunt blijft bruikbaar
        objecten = []
        uit["opmerkingen"].append(f"Adressenregister niet bereikbaar: {e}")
    uit["busnummers"] = sorted(o["busnummer"] for o in objecten if o.get("busnummer"))
    hoofd = [o for o in objecten if not o.get("busnummer")] or objecten

    per_straat = {loc["straat"]: [loc["huisnummer"]]}
    uit["percelen"] = []
    if hoofd:
        try:
            uit["percelen"] = percelen_van(hoofd[0]["id"])
            for capa in uit["percelen"]:
                for a in adressen_op_perceel(capa):
                    if a.get("straat") and a.get("huisnummer"):
                        per_straat.setdefault(a["straat"], []).append(a["huisnummer"])
        except Exception as e:
            uit["opmerkingen"].append(f"Perceel niet op te halen: {e}")
    if not uit["percelen"]:
        uit["opmerkingen"].append("Geen perceel gekoppeld aan dit adres in het Adressenregister.")
    uit["nummers_per_straat"] = {s: _sorteer(n) for s, n in per_straat.items()}

    try:
        omgeving = buren(loc["lat"], loc["lon"])
    except Exception as e:
        omgeving = []
        uit["opmerkingen"].append(f"Omgeving niet op te halen: {e}")
    dicht = {}
    for b in omgeving:
        afstand = ((b["x"] - loc["x"]) ** 2 + (b["y"] - loc["y"]) ** 2) ** 0.5
        if b["straat"] and b["straat"] != loc["straat"] and afstand <= HOEK_AFSTAND_M:
            dicht.setdefault(b["straat"], []).append((round(afstand), b["huisnummer"]))
    uit["straten_dichtbij"] = {s: sorted(v) for s, v in dicht.items()}
    uit["hoekpand"] = len(uit["nummers_per_straat"]) > 1 or bool(dicht)
    return uit
