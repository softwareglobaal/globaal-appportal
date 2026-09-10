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
from datetime import date, datetime, timedelta, timezone
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
    "gebeurtenis": "TEXT",  # enter of leave, bij een zone-overgang
    "zone": "TEXT",         # naam van de zone die betreden of verlaten werd
    # Wanneer het bericht hier aankwam, naast tst (wanneer het gemeten werd).
    # Zonder dit verschil is niet te zien of een stilte betekent dat de telefoon
    # niets mat, of dat hij wel mat maar niets kwijt kon en het later nastuurde.
    # Op 10-9-2026 viel de stroom stil zodra de telefoon op de wifi van de auto
    # zat (4G-router); pas dit veld kan zeggen welke van de twee het was.
    "ontvangen": "INTEGER",
    "gemaakt": "INTEGER",   # created_at van OwnTracks: wanneer het bericht klaarstond
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


def plek_db(conn):
    """Plekken met een naam: thuis, kantoor, een werf.

    Herkenning gebeurt op twee manieren, en wifi gaat voor. Een wifi-naam is
    onmiskenbaar: GPS drijft 's nachts tientallen meters, een netwerknaam niet.
    Mehdi's huis heeft er twee (6La5Ra en Proximus-Home-829822) en beide wijzen
    naar hetzelfde adres.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plek (
            naam    TEXT PRIMARY KEY,
            lat     REAL,
            lon     REAL,
            straal  INTEGER DEFAULT 120,   -- meter
            wifi    TEXT,                  -- kommagescheiden ssid's
            soort   TEXT,                  -- thuis, werk, klant, werf, onderweg
            notitie TEXT
        )""")
    # Het dossiernummer van H-Architects hoort in een eigen veld en niet in de
    # notitie: hierop gaat de agent straks een werfbezoek aan het projectdossier
    # koppelen, en dan moet het exact te vergelijken zijn.
    kolommen = {r["name"] for r in conn.execute("PRAGMA table_info(plek)")}
    if "dossier" not in kolommen:
        conn.execute("ALTER TABLE plek ADD COLUMN dossier TEXT")
    conn.commit()


def plekken(conn):
    plek_db(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM plek")]


def noem_plek(lat, lon, wifis, lijst):
    """Geeft de naam van de plek waar dit bezoek was, of None.

    wifis is de verzameling netwerknamen die tijdens het bezoek gezien zijn.
    """
    for p in lijst:
        eigen = {w.strip().lower() for w in (p.get("wifi") or "").split(",") if w.strip()}
        if eigen and wifis & eigen:
            return p["naam"]
    for p in lijst:
        if p.get("lat") is None or p.get("lon") is None:
            continue
        if afstand(lat, lon, p["lat"], p["lon"]) <= (p.get("straal") or 120):
            return p["naam"]
    return None


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
                             bs, ssid, bssid, motion, druk, vac, trigger, regios,
                             gebeurtenis, zone, ontvangen, gemaakt)
           VALUES (:tst, :lat, :lon, :acc, :alt, :vel, :batt, :conn, :tid, :soort, :ruw,
                   :bs, :ssid, :bssid, :motion, :druk, :vac, :trigger, :regios,
                   :gebeurtenis, :zone, :ontvangen, :gemaakt)
           ON CONFLICT(tst) DO NOTHING""",
        {"bs": heel("bs"),
         "ssid": str(data.get("ssid", ""))[:64] or None,
         "bssid": str(data.get("bssid", ""))[:32] or None,
         "motion": komma("motionactivities"),
         "druk": kommagetal("p"),
         "vac": heel("vac"),
         "trigger": str(data.get("t", ""))[:4] or None,
         "regios": komma("inregions"),
         # Bij _type=transition meldt de telefoon exact wanneer je een zone
         # binnenkwam of verliet. Dat is een gemeten moment, geen afleiding uit
         # afstanden, en het werkt ook in de zuinige stand van iOS.
         "gebeurtenis": str(data.get("event", ""))[:8] or None,
         "zone": str(data.get("desc", ""))[:80] or None,
         "ontvangen": int(time.time()),
         "gemaakt": heel("created_at"),
         "tst": tst, "lat": lat, "lon": lon, "acc": heel("acc"), "alt": heel("alt"),
         "vel": heel("vel"), "batt": heel("batt"),
         "conn": str(data.get("conn", ""))[:4], "tid": str(data.get("tid", ""))[:8],
         "soort": soort, "ruw": json.dumps(data, ensure_ascii=False)[:4000]})
    conn.commit()
    conn.close()
    return jsonify([])      # OwnTracks verwacht een (eventueel lege) lijst terug


# ------------------------------------------- gebeurtenissen en gezondheid

def gezondheid_db(conn):
    """Losse metingen, elk op een eigen rij.

    Bewust niet een kolom per soort meting: dan vraagt elke nieuwe meting een
    schemawijziging. Zo kan de telefoon morgen slaapduur of hartritmevariatie
    gaan sturen zonder dat hier iets verandert.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gezondheid (
            datum   TEXT NOT NULL,      -- JJJJ-MM-DD, de dag waarop het geldt
            soort   TEXT NOT NULL,      -- stappen, hartslag_rust, slaap_uren, ...
            waarde  REAL NOT NULL,
            eenheid TEXT,
            bron    TEXT,               -- iphone, watch, handmatig
            gezet   INTEGER NOT NULL,   -- wanneer binnengekomen (epoch)
            PRIMARY KEY (datum, soort, bron)
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gebeurtenis (
            tst     INTEGER NOT NULL,
            soort   TEXT NOT NULL,      -- rit-start, rit-eind, werkdag-start, ...
            detail  TEXT,
            bron    TEXT,
            PRIMARY KEY (tst, soort)
        )""")
    conn.commit()


@app.route("/gebeurtenis", methods=["POST"])
def gebeurtenis():
    """Een gemeld moment, bijvoorbeeld uit een Opdrachten-automatisering.

    De telefoon weet exact wanneer hij met de auto-router verbindt. Dat is een
    beter ritbegin dan wat uit losse GPS-punten valt af te leiden, en het kost
    geen batterij. Verwacht {"soort": "rit-start"} en eventueel "detail" en
    "tijd" (ISO of epoch; standaard nu).
    """
    if not WACHTWOORD:
        abort(404)
    if not _wachtwoord_klopt():
        app.logger.warning("gebeurtenis geweigerd: %s", _waarom_geweigerd())
        abort(403)

    data = request.get_json(silent=True) or {}
    soort = str(data.get("soort", "")).strip()[:40]
    if not soort:
        abort(400)

    tijd = data.get("tijd")
    if tijd is None:
        tst = int(time.time())
    else:
        try:
            tst = int(float(tijd))
        except (TypeError, ValueError):
            try:
                tst = int(datetime.fromisoformat(str(tijd)).timestamp())
            except ValueError:
                tst = int(time.time())

    conn = db()
    gezondheid_db(conn)
    conn.execute("""INSERT INTO gebeurtenis (tst, soort, detail, bron)
                    VALUES (?,?,?,?) ON CONFLICT(tst, soort) DO NOTHING""",
                 (tst, soort, str(data.get("detail", ""))[:200] or None,
                  str(data.get("bron", "iphone"))[:40]))
    conn.commit()
    conn.close()
    app.logger.info("gebeurtenis: %s om %s", soort, _lokaal(tst).strftime("%H:%M"))
    return jsonify({"ok": True, "soort": soort, "tijd": _lokaal(tst).isoformat()})


@app.route("/gezondheid", methods=["POST"])
def gezondheid():
    """Metingen uit de Health-app, gestuurd door een Opdrachten-automatisering.

    De Health-app heeft geen koppeling, maar Opdrachten kan er wel in lezen en
    een webverzoek doen. Zo komen stappen, hartslag en slaap hier binnen zonder
    dat er elke keer met de hand geexporteerd moet worden.

    Verwacht {"datum": "2026-09-09", "metingen": {"stappen": 8234, ...}} of het
    kortere {"datum": ..., "stappen": 8234, "hartslag_rust": 58}.
    """
    if not WACHTWOORD:
        abort(404)
    if not _wachtwoord_klopt():
        app.logger.warning("gezondheid geweigerd: %s", _waarom_geweigerd())
        abort(403)

    data = request.get_json(silent=True) or {}
    datum = str(data.get("datum", "")).strip()[:10] or date.today().isoformat()
    try:
        date.fromisoformat(datum)
    except ValueError:
        abort(400)

    metingen = data.get("metingen")
    if not isinstance(metingen, dict):
        # Alles wat geen bekende sleutel is telt als meting, zodat een
        # eenvoudige Opdracht plat {"datum":..., "stappen":...} mag sturen.
        metingen = {k: v for k, v in data.items()
                    if k not in ("datum", "bron", "eenheden")}

    eenheden = data.get("eenheden") if isinstance(data.get("eenheden"), dict) else {}
    bron = str(data.get("bron", "iphone"))[:40]

    conn = db()
    gezondheid_db(conn)
    n = 0
    nu = int(time.time())
    for soort, waarde in metingen.items():
        try:
            getal = float(waarde)
        except (TypeError, ValueError):
            continue        # tekst en lege waarden overslaan, niet struikelen
        conn.execute("""INSERT INTO gezondheid (datum, soort, waarde, eenheid, bron, gezet)
                        VALUES (?,?,?,?,?,?)
                        ON CONFLICT(datum, soort, bron) DO UPDATE SET
                          waarde=excluded.waarde, eenheid=excluded.eenheid,
                          gezet=excluded.gezet""",
                     (datum, str(soort)[:40], getal,
                      str(eenheden.get(soort, ""))[:20] or None, bron, nu))
        n += 1
    conn.commit()
    conn.close()
    app.logger.info("gezondheid %s: %d metingen van %s", datum, n, bron)
    return jsonify({"ok": True, "datum": datum, "bewaard": n})


@app.route("/api/plekken", methods=["GET", "POST"])
def api_plekken():
    """Plekken met een naam beheren.

    Deze route zit achter de gewone login van Authentik; alleen /pub,
    /gebeurtenis en /gezondheid passeren die. Vanaf de VM zelf is hij
    rechtstreeks bereikbaar op 127.0.0.1:3031, en zo worden plekken toegevoegd.
    De wachtwoordcontrole bij POST is een tweede slot voor het geval de route
    later wel naar buiten wordt opengezet.
    """
    conn = db()
    if request.method == "POST":
        if not WACHTWOORD or not _wachtwoord_klopt():
            abort(403)
        d = request.get_json(silent=True) or {}
        naam = str(d.get("naam", "")).strip()[:60]
        if not naam:
            abort(400)
        if d.get("verwijder"):
            conn.execute("DELETE FROM plek WHERE naam=?", (naam,))
            conn.commit(); conn.close()
            return jsonify({"ok": True, "verwijderd": naam})
        plek_db(conn)
        conn.execute("""INSERT INTO plek (naam, lat, lon, straal, wifi, soort, notitie, dossier)
                        VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT(naam) DO UPDATE SET
                          lat=excluded.lat, lon=excluded.lon, straal=excluded.straal,
                          wifi=excluded.wifi, soort=excluded.soort,
                          notitie=excluded.notitie, dossier=excluded.dossier""",
                     (naam, d.get("lat"), d.get("lon"), int(d.get("straal") or 120),
                      str(d.get("wifi", ""))[:200] or None,
                      str(d.get("soort", ""))[:40] or None,
                      str(d.get("notitie", ""))[:200] or None,
                      str(d.get("dossier", ""))[:20] or None))
        conn.commit()
        uit = plekken(conn)
        conn.close()
        return jsonify({"ok": True, "bewaard": naam, "plekken": uit})

    uit = plekken(conn)
    conn.close()
    return jsonify({"plekken": uit})


@app.route("/api/gezondheid/<datum>")
def api_gezondheid(datum):
    conn = db()
    gezondheid_db(conn)
    rijen = conn.execute(
        "SELECT soort, waarde, eenheid, bron FROM gezondheid WHERE datum=? ORDER BY soort",
        (datum,)).fetchall()
    geb = conn.execute(
        "SELECT tst, soort, detail FROM gebeurtenis WHERE tst >= ? AND tst < ? ORDER BY tst",
        (int(datetime.fromisoformat(datum).astimezone().timestamp()),
         int((datetime.fromisoformat(datum).astimezone() + timedelta(days=1)).timestamp()))
    ).fetchall()
    conn.close()
    return jsonify({
        "datum": datum,
        "metingen": [dict(r) for r in rijen],
        "gebeurtenissen": [{"tijd": _lokaal(r["tst"]).isoformat(),
                            "soort": r["soort"], "detail": r["detail"]} for r in geb],
    })


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

    # Eenmalig ophalen: de lijst is kort en verandert zelden, maar hem per
    # bezoek opvragen zou een databaseverbinding per stuk kosten.
    conn = db()
    bekende_plekken = plekken(conn)
    conn.close()

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
            mlat = round(sum(p["lat"] for p in groep) / len(groep), 6)
            mlon = round(sum(p["lon"] for p in groep) / len(groep), 6)
            gezien = {(p.get("ssid") or "").lower() for p in groep if p.get("ssid")}
            naam = noem_plek(mlat, mlon, gezien, bekende_plekken)
            dossier = next((p.get("dossier") for p in bekende_plekken
                            if p["naam"] == naam), None) if naam else None
            resultaat.append({
                "soort": "bezoek",
                "van": groep[0]["tst"], "tot": groep[-1]["tst"],
                "minuten": round(minuten),
                "lat": mlat, "lon": mlon,
                "punten": len(groep),
                "wifi": next((p.get("ssid") for p in groep if p.get("ssid")), None),
                "plek": naam,
                "dossier": dossier,
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
