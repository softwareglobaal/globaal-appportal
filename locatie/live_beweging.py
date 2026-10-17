"""Actuele beweging per tracker, zonder positiegegevens aan agents door te geven.

Een dagboek beschrijft achteraf een rit. Dit oordeel is alleen geldig zolang twee
recente, geloofwaardige GPS-metingen beweging tonen. Ontvangst van een oude of
nagestuurde meting maakt het oordeel nooit opnieuw actueel.
"""
import math
import time

import atrack as A
import bronbeleid as B

LEEFTIJD = {"auto": 120, "persoon": 180}
MAX_VERTRAGING = 120
MAX_PAAR_AFSTAND_S = 180


def _afstand(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    x = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(min(1, math.sqrt(x)))


def _betrouwbaar(p, nu):
    """Een live punt heeft een fix, redelijke HDOP en weinig verzendvertraging."""
    tst, ontvangen = p["tst"], p["ontvangen"]
    return (p["fix"] == 1 and not p["gebufferd"] and p["hdop"] is not None
            and 0 < p["hdop"] <= 10 and ontvangen is not None
            and tst <= nu and ontvangen <= nu + 30
            and -30 <= ontvangen - tst <= MAX_VERTRAGING
            and p["lat"] is not None and p["lon"] is not None)


def _motor_uit_na(conn, waar, params, sinds, nu):
    """Een motor-uit na de bewegingspunten stopt het auto-oordeel direct, ook zonder fix."""
    rijen = conn.execute(
        "SELECT moment, berichtsoort, ruw, ontvangen FROM punt "
        f"WHERE bron = 'auto' AND {waar} AND moment >= ? AND moment <= ? "
        "AND berichtsoort IN ('VGF', 'VGN', 'STT', 'FRI', 'ERI') "
        "ORDER BY moment DESC, bericht_id DESC",
        params + [sinds, nu],
    ).fetchall()
    hoogste = None
    standen = set()
    for p in rijen:
        if p["ontvangen"] is None or p["ontvangen"] > nu + 30:
            continue
        stand = A.motorstand(p["berichtsoort"], p["ruw"])
        if stand:
            if hoogste is not None and p["moment"] < hoogste:
                break
            hoogste = p["moment"]
            standen.add(stand)
    return "uit" in standen  # ook bij gelijktijdig tegenstrijdige standen: geen positief oordeel


def bron(conn, naam, nu=None):
    nu = int(time.time() if nu is None else nu)
    beleid = B.BRONNEN[naam]
    uit = {"bron": naam, "rol": beleid["rol"], "toestand": "onbekend", "reden": "geen actuele beweging bewezen",
           "meettijd": None, "ontvangsttijd": None, "geldig_tot": None}
    if B.ingang(naam) is None:
        uit.update(toestand="niet_aangesloten", reden="deze bron is niet actief")
        return uit
    if not B.toestellen_van(naam):
        uit["reden"] = "actieve bron heeft geen gecontroleerd toestel"
        return uit
    where, params = B.sql_actief()
    rijen = conn.execute(
        "SELECT tst, ontvangen, lat, lon, vel, hdop, fix, gebufferd FROM punt "
        f"WHERE bron = ? AND {where} AND tst >= ? AND tst <= ? "
        "ORDER BY tst DESC, bericht_id DESC LIMIT 20",
        [naam] + params + [nu - 600, nu],
    ).fetchall()
    punten = []
    gezien = set()
    for p in rijen:
        if p["tst"] not in gezien and _betrouwbaar(p, nu):
            punten.append(p)
            gezien.add(p["tst"])
    if not punten:
        uit["reden"] = "geen verse geldige GPS-meting"
        return uit
    laatste = punten[0]
    uit["meettijd"] = B.lokaal(laatste["tst"]).isoformat()
    uit["ontvangsttijd"] = B.lokaal(laatste["ontvangen"]).isoformat()
    leeftijd = LEEFTIJD[beleid["rol"]]
    if nu - laatste["tst"] > leeftijd:
        uit["reden"] = "laatste meting is te oud voor een actueel oordeel"
        return uit

    snelheid_min = 5 if beleid["rol"] == "auto" else 3
    afstand_min = 35 if beleid["rol"] == "auto" else 25
    if (laatste["vel"] or 0) < snelheid_min:
        uit["reden"] = "laatste meting toont geen beweging"
        return uit
    for vroeger in punten[1:]:
        seconden = laatste["tst"] - vroeger["tst"]
        if seconden < 15 or seconden > MAX_PAAR_AFSTAND_S or (vroeger["vel"] or 0) < snelheid_min:
            continue
        meter = _afstand(vroeger, laatste)
        if meter >= afstand_min and meter / seconden * 3.6 <= 200:
            if beleid["rol"] == "auto" and _motor_uit_na(conn, where, params, laatste["tst"], nu):
                uit["reden"] = "motor uit na de bewegingspunten"
                return uit
            uit.update(toestand="onderweg" if beleid["rol"] == "persoon" else "auto_beweegt",
                       reden="twee verse geldige metingen tonen beweging",
                       geldig_tot=B.lokaal(laatste["tst"] + leeftijd).isoformat())
            return uit
    uit["reden"] = "nog geen tweede passende bewegingsmeting"
    return uit


def overzicht(conn, nu=None):
    """Een direct uit SQLite berekend oordeel. Geen coördinaten, geen cache."""
    nu = int(time.time() if nu is None else nu)
    bronnen = {naam: bron(conn, naam, nu) for naam in B.BRONNEN if B.BRONNEN[naam]["rol"] in ("auto", "persoon")}
    persoon = next((bronnen[naam] for naam in B.actieve_bronnen() if B.rol(naam) == "persoon"),
                   bronnen.get("draagbaar", {"toestand": "niet_aangesloten", "rol": "persoon"}))
    return {"gemaakt": B.lokaal(nu).isoformat(), "persoon": persoon, "auto": bronnen.get("auto"),
            "regel": "een bewegende auto bewijst niet dat de persoon onderweg is"}
