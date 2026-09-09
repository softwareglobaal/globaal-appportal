"""
Locatielogboek: ontvangt de berichten van de OwnTracks-app op Mehdi's iPhone
en maakt er een dagboek van.

De app op de telefoon stuurt om de zoveel tijd een punt naar /pub. Die route
passeert de forward-auth van Authentik (een telefoon heeft geen browsersessie)
en controleert zelf het wachtwoord uit LOCATIE_WACHTWOORD, net zoals de
agents-tegel dat doet op /agent-status.

Losse punten zijn nog geen logboek. De dagindeling hieronder plakt ze aan
elkaar tot bezoeken (je stond ergens stil) en verplaatsingen (je was onderweg),
zodat het resultaat te vergelijken valt met wat Google Maps oplevert.
"""
import base64
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, asin, sqrt

from flask import Flask, abort, jsonify, render_template, request

app = Flask(__name__)

DB_PAD = os.environ.get("LOCATIE_DB", "/data/locatie.db")
WACHTWOORD = os.environ.get("LOCATIE_WACHTWOORD", "").strip()
# Een bezoek is: minstens zo lang stil binnen zo'n straal.
STILSTAND_METER = 120
STILSTAND_MINUTEN = 8


# --------------------------------------------------------------- database

def db():
    conn = sqlite3.connect(DB_PAD)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS punt (
            tst     INTEGER PRIMARY KEY,   -- tijdstip van de telefoon (epoch)
            lat     REAL NOT NULL,
            lon     REAL NOT NULL,
            acc     INTEGER,               -- nauwkeurigheid in meter
            alt     INTEGER,
            vel     INTEGER,               -- snelheid km/u
            batt    INTEGER,
            conn    TEXT,                  -- w=wifi, m=mobiel, o=offline
            tid     TEXT,
            soort   TEXT,                  -- location / transition
            ruw     TEXT
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS punt_tst ON punt(tst)")
    conn.commit()
    return conn


def _lokaal(tst):
    """Epoch naar Belgische tijd.

    Bewust niet zomaar +2: tussen eind oktober en eind maart is het +1. We
    laten Python de zone bepalen via de tijdzone-database van de container.
    """
    return datetime.fromtimestamp(tst, tz=timezone.utc).astimezone()


def afstand(lat1, lon1, lat2, lon2):
    """Afstand in meter tussen twee punten (haversine)."""
    r = 6371000
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2)
    return 2 * r * asin(sqrt(a))


# ------------------------------------------------------------- ontvangst

def _wachtwoord_klopt():
    """OwnTracks stuurt gebruiker en wachtwoord als HTTP Basic Auth."""
    kop = request.headers.get("Authorization", "")
    if not kop.startswith("Basic "):
        return False
    try:
        ontcijferd = base64.b64decode(kop[6:]).decode("utf-8", "replace")
    except Exception:
        return False
    _, _, gegeven = ontcijferd.partition(":")
    # Vergelijking in constante tijd: anders verraadt de looptijd het wachtwoord.
    if len(gegeven) != len(WACHTWOORD):
        return False
    verschil = 0
    for a, b in zip(gegeven, WACHTWOORD):
        verschil |= ord(a) ^ ord(b)
    return verschil == 0


def _waarom_geweigerd():
    """Zegt waarom een poging strandde, zonder het wachtwoord te verraden.

    Bij het instellen van de telefoon is een kale 403 nutteloos: je weet niet of
    het veld leeg bleef, of iOS er een hoofdletter van maakte, of er een spatie
    is meegeplakt. Deze meldingen noemen alleen vorm en lengte, nooit inhoud.
    """
    kop = request.headers.get("Authorization", "")
    if not kop.startswith("Basic "):
        return "geen wachtwoord meegestuurd (Authentication staat uit in de app)"
    try:
        ontcijferd = base64.b64decode(kop[6:]).decode("utf-8", "replace")
    except Exception:
        return "onleesbare Authorization-kop"
    gebruiker, _, gegeven = ontcijferd.partition(":")

    if not gegeven:
        return f"leeg wachtwoord (gebruiker '{gebruiker}')"
    if gegeven != gegeven.strip():
        return "wachtwoord heeft een spatie of regeleinde aan het begin of eind"
    if len(gegeven) != len(WACHTWOORD):
        return (f"wachtwoord is {len(gegeven)} tekens, verwacht {len(WACHTWOORD)}"
                f" (gebruiker '{gebruiker}')")
    if gegeven.lower() == WACHTWOORD.lower():
        return "wachtwoord klopt op hoofdletters na; iOS heeft waarschijnlijk de eerste letter gekapitaliseerd"
    gelijk = sum(1 for a, b in zip(gegeven, WACHTWOORD) if a == b)
    return (f"wachtwoord heeft de juiste lengte maar {len(WACHTWOORD) - gelijk}"
            f" tekens wijken af (gebruiker '{gebruiker}')")


@app.route("/pub", methods=["POST"])
def pub():
    if not WACHTWOORD:
        abort(404)          # niet ingesteld: doe alsof de route niet bestaat
    if not _wachtwoord_klopt():
        app.logger.warning("pub geweigerd: %s", _waarom_geweigerd())
        abort(403)

    data = request.get_json(silent=True) or {}
    soort = str(data.get("_type", ""))
    if soort not in ("location", "transition"):
        return jsonify([])  # ping, waypoints, lwt: netjes negeren

    try:
        tst = int(data["tst"])
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (KeyError, TypeError, ValueError):
        abort(400)

    def heel(sleutel):
        try:
            return int(data[sleutel])
        except (KeyError, TypeError, ValueError):
            return None

    conn = db()
    conn.execute(
        """INSERT INTO punt (tst, lat, lon, acc, alt, vel, batt, conn, tid, soort, ruw)
           VALUES (:tst, :lat, :lon, :acc, :alt, :vel, :batt, :conn, :tid, :soort, :ruw)
           ON CONFLICT(tst) DO NOTHING""",
        {"tst": tst, "lat": lat, "lon": lon, "acc": heel("acc"), "alt": heel("alt"),
         "vel": heel("vel"), "batt": heel("batt"),
         "conn": str(data.get("conn", ""))[:4], "tid": str(data.get("tid", ""))[:8],
         "soort": soort, "ruw": json.dumps(data, ensure_ascii=False)[:4000]})
    conn.commit()
    conn.close()
    return jsonify([])      # OwnTracks verwacht een (eventueel lege) lijst terug


# ------------------------------------------------------------ dagindeling

def dagindeling(punten):
    """Losse punten omzetten naar bezoeken en verplaatsingen.

    Werkwijze: loop de punten af en begin een tros zolang elk volgend punt
    binnen STILSTAND_METER van het begin van die tros valt. Duurt een tros
    lang genoeg, dan was dat een bezoek; wat ertussen zit is onderweg.
    """
    resultaat = []
    i = 0
    n = len(punten)
    while i < n:
        anker = punten[i]
        j = i + 1
        while j < n and afstand(anker["lat"], anker["lon"],
                                punten[j]["lat"], punten[j]["lon"]) <= STILSTAND_METER:
            j += 1
        minuten = (punten[j - 1]["tst"] - anker["tst"]) / 60

        if minuten >= STILSTAND_MINUTEN:
            groep = punten[i:j]
            resultaat.append({
                "soort": "bezoek",
                "van": anker["tst"], "tot": punten[j - 1]["tst"],
                "minuten": round(minuten),
                "lat": round(sum(p["lat"] for p in groep) / len(groep), 6),
                "lon": round(sum(p["lon"] for p in groep) / len(groep), 6),
                "punten": len(groep),
            })
            i = j
        else:
            # Geen stilstand: verzamel tot de eerstvolgende echte stop.
            start = i
            while i < n:
                anker2 = punten[i]
                k = i + 1
                while k < n and afstand(anker2["lat"], anker2["lon"],
                                        punten[k]["lat"], punten[k]["lon"]) <= STILSTAND_METER:
                    k += 1
                if (punten[k - 1]["tst"] - anker2["tst"]) / 60 >= STILSTAND_MINUTEN:
                    break
                i = k if k > i else i + 1
            eind = max(i, start + 1)
            rit = punten[start:eind]
            meter = sum(afstand(rit[x]["lat"], rit[x]["lon"],
                                rit[x + 1]["lat"], rit[x + 1]["lon"])
                        for x in range(len(rit) - 1))
            if len(rit) >= 2:
                resultaat.append({
                    "soort": "verplaatsing",
                    "van": rit[0]["tst"], "tot": rit[-1]["tst"],
                    "minuten": round((rit[-1]["tst"] - rit[0]["tst"]) / 60),
                    "meter": round(meter),
                    "spoor": [[p["lat"], p["lon"]] for p in rit],
                })
    return resultaat


def punten_van_dag(datum):
    """datum als 'JJJJ-MM-DD', in Belgische tijd."""
    d = datetime.strptime(datum, "%Y-%m-%d")
    # Dagrand bepalen in de lokale zone van de container (TZ=Europe/Brussels),
    # zodat een dag loopt van middernacht tot middernacht Belgische tijd.
    lokaal_begin = datetime(d.year, d.month, d.day).astimezone()
    begin = int(lokaal_begin.timestamp())
    eind = int((lokaal_begin + timedelta(days=1)).timestamp())
    conn = db()
    rijen = conn.execute(
        "SELECT * FROM punt WHERE tst >= ? AND tst < ? ORDER BY tst", (begin, eind)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rijen]


def dagen_met_data(limiet=60):
    conn = db()
    rijen = conn.execute(
        "SELECT tst FROM punt ORDER BY tst DESC LIMIT 20000").fetchall()
    conn.close()
    gezien, uit = set(), []
    for r in rijen:
        d = _lokaal(r["tst"]).strftime("%Y-%m-%d")
        if d not in gezien:
            gezien.add(d)
            uit.append(d)
            if len(uit) >= limiet:
                break
    return uit


# ------------------------------------------------------------------ web

@app.route("/")
def index():
    dagen = dagen_met_data()
    datum = request.args.get("dag") or (dagen[0] if dagen else
                                        datetime.now().strftime("%Y-%m-%d"))
    punten = punten_van_dag(datum)
    stukken = dagindeling(punten)
    for s in stukken:
        s["van_tekst"] = _lokaal(s["van"]).strftime("%H:%M")
        s["tot_tekst"] = _lokaal(s["tot"]).strftime("%H:%M")
    km = sum(s.get("meter", 0) for s in stukken) / 1000
    laatste = punten[-1] if punten else None
    return render_template(
        "index.html", dagen=dagen, datum=datum, stukken=stukken,
        aantal=len(punten), km=round(km, 1),
        batterij=laatste["batt"] if laatste else None,
        laatste_tijd=_lokaal(laatste["tst"]).strftime("%H:%M") if laatste else None)


@app.route("/api/dag/<datum>")
def api_dag(datum):
    punten = punten_van_dag(datum)
    return jsonify({
        "datum": datum,
        "punten": [{"tijd": _lokaal(p["tst"]).isoformat(), "lat": p["lat"],
                    "lon": p["lon"], "acc": p["acc"], "batt": p["batt"]}
                   for p in punten],
        "indeling": dagindeling(punten),
    })


@app.route("/gezond")
def gezond():
    conn = db()
    rij = conn.execute("SELECT COUNT(*) n, MAX(tst) laatste FROM punt").fetchone()
    conn.close()
    laatste = rij["laatste"]
    return jsonify({
        "punten": rij["n"],
        "laatste": _lokaal(laatste).isoformat() if laatste else None,
        "minuten_geleden": round((time.time() - laatste) / 60) if laatste else None,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3031)))
