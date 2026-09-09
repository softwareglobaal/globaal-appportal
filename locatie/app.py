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

# Velden die er later bij zijn gekomen. SQLite kan kolommen toevoegen aan een
# bestaande tabel, dus dit hoeft niet in een migratie: bij het eerste verzoek na
# een uitrol worden ze stil aangemaakt en blijven de bestaande rijen staan.
LATERE_KOLOMMEN = {
    "bs": "INTEGER",        # 1 = niet aan de lader, 2 = laadt, 3 = vol
    "ssid": "TEXT",         # naam van het wifi-netwerk
    "bssid": "TEXT",        # hardware-adres van het toegangspunt
    "motion": "TEXT",       # wat de telefoon zelf zegt: stationary, walking, automotive
    "druk": "REAL",         # luchtdruk in kPa, onderscheidt verdiepingen
    "vac": "INTEGER",       # verticale nauwkeurigheid
    "trigger": "TEXT",      # waarom dit punt verstuurd is (t=timer, u=handmatig, c=zone)
    "regios": "TEXT",       # geofences waar de telefoon op dat moment in zat
}


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

    bestaand = {r["name"] for r in conn.execute("PRAGMA table_info(punt)")}
    for kolom, soort in LATERE_KOLOMMEN.items():
        if kolom not in bestaand:
            conn.execute(f"ALTER TABLE punt ADD COLUMN {kolom} {soort}")
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

    def komma(sleutel):
        """Lijstjes uit OwnTracks als tekst bewaren, bv. ['stationary']."""
        w = data.get(sleutel)
        if isinstance(w, list):
            return ",".join(str(x) for x in w) or None
        return str(w)[:80] if w else None

    def kommagetal(sleutel):
        try:
            return float(data[sleutel])
        except (KeyError, TypeError, ValueError):
            return None

    conn = db()
    conn.execute(
        """INSERT INTO punt (tst, lat, lon, acc, alt, vel, batt, conn, tid, soort, ruw,
                             bs, ssid, bssid, motion, druk, vac, trigger, regios)
           VALUES (:tst, :lat, :lon, :acc, :alt, :vel, :batt, :conn, :tid, :soort, :ruw,
                   :bs, :ssid, :bssid, :motion, :druk, :vac, :trigger, :regios)
           ON CONFLICT(tst) DO NOTHING""",
        {"bs": heel("bs"),
         "ssid": str(data.get("ssid", ""))[:64] or None,
         "bssid": str(data.get("bssid", ""))[:32] or None,
         "motion": komma("motionactivities"),
         "druk": kommagetal("p"),
         "vac": heel("vac"),
         "trigger": str(data.get("t", ""))[:4] or None,
         "regios": komma("inregions"),
         "tst": tst, "lat": lat, "lon": lon, "acc": heel("acc"), "alt": heel("alt"),
         "vel": heel("vel"), "batt": heel("batt"),
         "conn": str(data.get("conn", ""))[:4], "tid": str(data.get("tid", ""))[:8],
         "soort": soort, "ruw": json.dumps(data, ensure_ascii=False)[:4000]})
    conn.commit()
    conn.close()
    return jsonify([])      # OwnTracks verwacht een (eventueel lege) lijst terug


# ------------------------------------------------------------ dagindeling

ONDERWEG_WOORDEN = ("automotive", "cycling", "walking", "running")

# Wifi-netwerken die meerijden in plaats van stil te staan. Mehdi's auto heeft
# een eigen router met externe antenne (Teltonika RUT), dus tijdens het rijden
# blijft de telefoon aan hetzelfde netwerk hangen. Zonder deze lijst leest de
# regel "zelfde wifi als het vorige punt betekent hetzelfde gebouw" een autorit
# als een bezoek: op 9-9-2026 werd zo een stuk rit het begin van een bezoek van
# 55 minuten. Kommagescheiden in LOCATIE_VOERTUIG_WIFI.
VOERTUIG_WIFI = {n.strip().lower()
                 for n in os.environ.get("LOCATIE_VOERTUIG_WIFI", "").split(",")
                 if n.strip()}


def _toestand(punt, vorige):
    """Stond de telefoon stil of was hij onderweg, op dit punt?

    De eerste versie leidde dat af uit de afstand tot het vorige punt. Dat gaat
    stuk in de zuinige stand van iOS: die meldt pas na enkele honderden meters,
    dus twee punten van dezelfde plek liggen 600 meter uit elkaar en elk bezoek
    verdwijnt. Op 9-9-2026 werd een avond van anderhalf uur zo een rit van
    7,8 km.

    De telefoon weet het zelf en stuurt het mee. We geloven in deze volgorde:

    1. `motion` - de bewegingssensor van iOS zegt stationary, walking, cycling
       of automotive. Dit is een meting, geen gok, en kost geen batterij.
    2. `ssid` - hetzelfde wifi-netwerk als het vorige punt betekent hetzelfde
       gebouw. Zekerder dan elke coordinaat.
    3. de afstand - alleen als de eerste twee niets zeggen.
    """
    ssid = punt.get("ssid")
    in_voertuig = bool(ssid) and ssid.lower() in VOERTUIG_WIFI

    motion = (punt.get("motion") or "").lower()
    if motion:
        # Stilstaan in een rijdende auto bestaat niet: dan sta je stil in een
        # file of voor een licht, en dat is nog steeds onderweg.
        if "stationary" in motion and not in_voertuig:
            return "stil"
        if any(w in motion for w in ONDERWEG_WOORDEN):
            return "onderweg"

    if in_voertuig:
        return "onderweg"

    if ssid and vorige and vorige.get("ssid") == ssid:
        return "stil"

    if vorige is None:
        return "stil"
    meter = afstand(vorige["lat"], vorige["lon"], punt["lat"], punt["lon"])
    # Ruime marge: de onzekerheid van beide metingen telt mee.
    speling = STILSTAND_METER + (punt.get("acc") or 0) + (vorige.get("acc") or 0)
    return "stil" if meter <= speling else "onderweg"


def dagindeling(punten):
    """Losse punten omzetten naar bezoeken en verplaatsingen.

    Bepaalt per punt of de telefoon stilstond of onderweg was, plakt
    opeenvolgende gelijke toestanden aan elkaar, en houdt alleen stiltes over
    die lang genoeg duurden om een bezoek te heten.
    """
    if not punten:
        return []

    toestanden = []
    for i, p in enumerate(punten):
        toestanden.append(_toestand(p, punten[i - 1] if i else None))

    # Opeenvolgende gelijke toestanden samenvoegen tot blokken.
    blokken = []
    start = 0
    for i in range(1, len(punten) + 1):
        if i == len(punten) or toestanden[i] != toestanden[start]:
            blokken.append((toestanden[start], punten[start:i]))
            start = i

    resultaat = []
    for b, (soort, groep) in enumerate(blokken):
        if soort == "stil":
            minuten = (groep[-1]["tst"] - groep[0]["tst"]) / 60
            if minuten < STILSTAND_MINUTEN:
                continue        # te kort om een bezoek te heten
            resultaat.append({
                "soort": "bezoek",
                "van": groep[0]["tst"], "tot": groep[-1]["tst"],
                "minuten": round(minuten),
                "lat": round(sum(p["lat"] for p in groep) / len(groep), 6),
                "lon": round(sum(p["lon"] for p in groep) / len(groep), 6),
                "punten": len(groep),
                "wifi": next((p.get("ssid") for p in groep if p.get("ssid")), None),
            })
        else:
            # Een rit loopt van waar je vertrok tot waar je aankwam, dus het
            # laatste punt van het vorige blok en het eerste van het volgende
            # tellen mee. Anders mist de afstand precies de twee stukken waar
            # het meeste verplaatsing in zit, en verdwijnt een rit die maar
            # een enkel onderweg-punt opleverde volledig.
            spoor = list(groep)
            if b > 0:
                spoor.insert(0, blokken[b - 1][1][-1])
            if b + 1 < len(blokken):
                spoor.append(blokken[b + 1][1][0])
            if len(spoor) < 2:
                continue
            meter = sum(afstand(spoor[x]["lat"], spoor[x]["lon"],
                                spoor[x + 1]["lat"], spoor[x + 1]["lon"])
                        for x in range(len(spoor) - 1))
            wijzen = {w for p in groep for w in (p.get("motion") or "").split(",")
                      if w in ONDERWEG_WOORDEN}
            resultaat.append({
                "soort": "verplaatsing",
                "van": spoor[0]["tst"], "tot": spoor[-1]["tst"],
                "minuten": round((spoor[-1]["tst"] - spoor[0]["tst"]) / 60),
                "meter": round(meter),
                "wijze": ", ".join(sorted(wijzen)) or None,
                "spoor": [[p["lat"], p["lon"]] for p in spoor],
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
        # Alles wat de telefoon meestuurde gaat mee naar buiten, zodat het
        # dagboek in Dropbox de volledige meting bevat en er later aan de
        # agenda, foto's of facturatie gekoppeld kan worden.
        "punten": [{"tijd": _lokaal(p["tst"]).isoformat(), "lat": p["lat"],
                    "lon": p["lon"], "acc": p["acc"], "batt": p["batt"],
                    "laadt": p["bs"] == 2 if p["bs"] is not None else None,
                    "wifi": p["ssid"], "beweging": p["motion"],
                    "verbinding": p["conn"], "hoogte": p["alt"],
                    "luchtdruk": p["druk"], "aanleiding": p["trigger"],
                    "zones": p["regios"]}
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
