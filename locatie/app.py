"""
Locatielogboek: ontvangt de metingen van de trackers en maakt er een dagboek van.

Sinds 3 oktober 2026 meet alleen de tracker in de auto (Queclink GV500CG, eigen
ontvanger in atrack_server.py). De telefoon (OwnTracks, route /pub) is bewust
gestopt; de route blijft bestaan en bewaart wat binnenkomt, maar telt niet mee.
Welke metingen meetellen staat op één plek: bronbeleid.py (startgrens op de
meettijd, het vastgelegde toestel per bron). Het schema staat in schema.py.

Losse punten zijn nog geen logboek. De dagindeling hieronder plakt ze per spoor
(per tracker) aan elkaar tot bezoeken (stilstaan op een plek) en verplaatsingen,
en herkenning.py zegt bij welk project of welke plek een verblijf hoort, en hoe
zeker. Wat de auto meet bewijst waar de auto stond, niet waar Mehdi was.
"""
import base64
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from math import radians, sin, cos, asin, sqrt
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, render_template, request

import bronbeleid as B
import herkenning as H
import schema

app = Flask(__name__)

DB_PAD = os.environ.get("LOCATIE_DB", "/data/locatie.db")
WACHTWOORD = os.environ.get("LOCATIE_WACHTWOORD", "").strip()
# Een bezoek is: minstens zo lang stil binnen zo'n straal.
STILSTAND_METER = 120
STILSTAND_MINUTEN = 8
# Een dag is afgesloten zoveel uur na middernacht: wat de tracker uit zijn buffer
# naleverde is dan binnen. Tot dan is het dagboek voorlopig.
AFSLUIT_UREN = 6


# --------------------------------------------------------------- database

def db():
    """Een verbinding op een database die zeker op de laatste schemaversie staat."""
    return schema.verbind(DB_PAD)


def plek_db(conn):
    """Plekken met een naam: thuis, kantoor, een werf.

    Herkenning gebeurt op twee manieren, en wifi gaat voor (alleen de telefoon zag
    wifi). Een plek met een dossiernummer telt in de herkenning als een ligging van
    dat project (herkenning.kandidaten). De tabel zelf staat in schema.py.
    """
    return None


def plekken(conn):
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

    Bewust niet zomaar +2: tussen eind oktober en eind maart is het +1. En bewust
    met de zone uit het bronbeleid, niet die van de container.
    """
    return B.lokaal(tst)


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


def waypoint_bericht(lijst):
    """De vastgelegde plekken als zones voor de telefoon.

    Zones (regions) worden door iOS zelf bewaakt: hij wekt de app bij aankomst
    en vertrek, ook in de zuinige stand en ook als de app is afgesloten. Dat is
    het enige dat de gaten dicht waarin Mehdi ergens was zonder dat er iets
    gemeten werd: tussen 15 en 18 september 25,6 uur.

    Ze met de hand op de kaart tekenen is werk dat blijft liggen. De telefoon
    kan ze ontvangen als antwoord op een gewone meting, mits afstandsbediening
    (Cmd) in de app aanstaat. Formaat volgens owntracks.org/booklet/tech/json.
    """
    zones = []
    for i, p in enumerate(sorted(lijst, key=lambda x: x["naam"])):
        if p.get("lat") is None or p.get("lon") is None:
            continue
        zones.append({"_type": "waypoint", "desc": p["naam"],
                      "lat": p["lat"], "lon": p["lon"],
                      "rad": int(p.get("straal") or 150),
                      # Vast tijdstip per plek: iOS gebruikt desc als sleutel,
                      # maar een wisselende tst zou elke keer een nieuwe zone maken.
                      "tst": 1789000000 + i})
    if not zones:
        return None
    return {"_type": "cmd", "action": "setWaypoints",
            "waypoints": {"_type": "waypoints", "waypoints": zones}}


def _zones_vingerafdruk(lijst):
    return json.dumps(sorted([(p["naam"], p.get("lat"), p.get("lon"), p.get("straal"))
                              for p in lijst if p.get("lat") is not None]))


def zones_te_sturen(conn, lijst):
    """Geeft het setWaypoints-bericht zodra de lijst plekken veranderd is.

    Een telefoon bevestigt niet dat hij de zones heeft aangenomen, dus we
    onthouden wat we het laatst stuurden en sturen alleen bij een wijziging.
    Komt het niet aan (afstandsbediening uit), dan kan `zones_opnieuw` de
    vingerafdruk wissen zodat hij bij het volgende punt weer meegaat.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS instelling (sleutel TEXT PRIMARY KEY, waarde TEXT)")
    afdruk = _zones_vingerafdruk(lijst)
    rij = conn.execute("SELECT waarde FROM instelling WHERE sleutel='zones'").fetchone()
    if rij and rij[0] == afdruk:
        return None
    bericht = waypoint_bericht(lijst)
    if not bericht:
        return None
    conn.execute("INSERT INTO instelling (sleutel, waarde) VALUES ('zones', ?) "
                 "ON CONFLICT(sleutel) DO UPDATE SET waarde=excluded.waarde", (afdruk,))
    return bericht


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
    ruw = json.dumps(data, ensure_ascii=False)[:4000]
    nu = int(time.time())
    # De telefoon is sinds 03-10-2026 uit gebruik (bronbeleid). Wat hij toch stuurt wordt
    # bewaard, herleidbaar, maar telt nergens mee: het bronbeleid laat bron iphone niet door.
    conn.execute("""INSERT INTO bericht (ontvangen, laatst_ontvangen, bron, toestel, protocol, soort,
                                         posities_gemeld, posities_bewaard, verwerking, vingerafdruk, ruw)
                    VALUES (?, ?, 'iphone', ?, 'owntracks', ?, 1, 1, 'punten', ?, ?)
                    ON CONFLICT(vingerafdruk) DO UPDATE SET aantal = aantal + 1,
                                                            laatst_ontvangen = excluded.laatst_ontvangen""",
                 (nu, nu, str(data.get("tid", ""))[:8] or None, soort, schema.vingerafdruk_bericht(ruw), ruw))
    bid = conn.execute("SELECT id FROM bericht WHERE vingerafdruk = ?",
                       (schema.vingerafdruk_bericht(ruw),)).fetchone()[0]
    conn.execute(
        """INSERT INTO punt (tst, lat, lon, acc, alt, vel, batt, conn, tid, soort, ruw,
                             bs, ssid, bssid, motion, druk, vac, trigger, regios,
                             gebeurtenis, zone, ontvangen, gemaakt, bron,
                             toestel, berichtsoort, volgnr, bericht_id)
           VALUES (:tst, :lat, :lon, :acc, :alt, :vel, :batt, :conn, :tid, :soort, :ruw,
                   :bs, :ssid, :bssid, :motion, :druk, :vac, :trigger, :regios,
                   :gebeurtenis, :zone, :ontvangen, :gemaakt, 'iphone',
                   :tid, :soort, 0, :bid)
           ON CONFLICT(bron, tst, berichtsoort, volgnr) DO NOTHING""",
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
         "ontvangen": nu,
         "gemaakt": heel("created_at"),
         "tst": tst, "lat": lat, "lon": lon, "acc": heel("acc"), "alt": heel("alt"),
         "vel": heel("vel"), "batt": heel("batt"),
         "conn": str(data.get("conn", ""))[:4], "tid": str(data.get("tid", ""))[:8],
         "soort": soort, "ruw": ruw, "bid": bid})
    # Het antwoord op een meting is de enige weg terug naar de telefoon: hier
    # gaan de zones mee zodra ze veranderd zijn.
    antwoord = []
    try:
        bericht = zones_te_sturen(conn, plekken(conn))
        if bericht:
            antwoord.append(bericht)
            app.logger.info("zones meegestuurd: %d",
                            len(bericht["waypoints"]["waypoints"]))
    except Exception as fout:      # noqa: BLE001
        app.logger.warning("zones meesturen mislukt: %s", fout)
    conn.commit()
    conn.close()
    return jsonify(antwoord)


# ------------------------------------------- gebeurtenissen en gezondheid

def gezondheid_db(conn):
    """Losse gezondheidsmetingen en gemelde momenten, elk op een eigen rij.

    Bewust niet een kolom per soort meting: dan vraagt elke nieuwe meting een
    schemawijziging. De tabellen staan in schema.py.
    """
    return None


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
        # Een werf hoort bij een project: firma plus nummer, want hetzelfde nummer kan
        # bij twee firma's bestaan. Zonder firma koppelt de herkenning alleen als het
        # nummer eenduidig is.
        conn.execute("""INSERT INTO plek (naam, lat, lon, straal, wifi, soort, notitie, dossier,
                                          firma, project_id, min_minuten)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(naam) DO UPDATE SET
                          lat=excluded.lat, lon=excluded.lon, straal=excluded.straal,
                          wifi=excluded.wifi, soort=excluded.soort,
                          notitie=excluded.notitie, dossier=excluded.dossier,
                          firma=excluded.firma, project_id=excluded.project_id,
                          min_minuten=excluded.min_minuten""",
                     (naam, d.get("lat"), d.get("lon"), int(d.get("straal") or 120),
                      str(d.get("wifi", ""))[:200] or None,
                      str(d.get("soort", ""))[:40] or None,
                      str(d.get("notitie", ""))[:200] or None,
                      str(d.get("dossier", ""))[:20] or None,
                      str(d.get("firma", ""))[:12] or None,
                      str(d.get("project_id", ""))[:40] or None,
                      int(d["min_minuten"]) if d.get("min_minuten") else None))
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
        B.dagranden(datum)).fetchall()
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


# Een verblijf is een plek waar je minstens STILSTAND_MINUTEN binnen deze straal
# bleef. Ruimer dan STILSTAND_METER omdat rondlopen op een werf of in een gebouw
# er gewoon bij hoort.
VERBLIJF_STRAAL = 150
# Zolang de telefoon niets meldt weten we niet wat er gebeurde. Een stilte langer
# dan dit wordt als gat getoond, tenzij voor en na het gat op dezelfde plek.
GAT_MINUTEN = 30
# Punten met meer onzekerheid dan dit (meter) zijn geen satellietmeting.
MAX_ONZEKERHEID = 250
# Een kortere stilte midden in een rit is een stop als er na de rijtijd nog
# minstens STILSTAND_MINUTEN overblijft. De telefoon zwijgt zodra hij stilligt en
# meldt zich pas weer na een paar honderd meter. Op 15-09-2026 stond Mehdi een
# half uur op de werf van 2145: twee punten bij aankomst (07:34 nog aan de
# autorouter, 07:38 met sensor "automotive"), 27 minuten stilte, om 08:05 562 m
# verder al rijdend. Geen gat (korter dan GAT_MINUTEN) en geen verblijf (de
# punten telden als rijden), dus verdween het werfbezoek in een rit van 07:24
# tot 08:28.
STOP_METER = 1500           # verder na de stilte: hij reed weg of stond in de file
# Meter per minuut (20 km/u, stadsverkeer) om de rijtijd van de stilte af te
# trekken. Met 30 km/u werd op 15-09 een rit van 1,2 km in elf minuten door
# Leuven een stop, terwijl er onderweg een punt "automotive" lag.
STOP_RIJTEMPO = 333


def _rijdt(punt):
    """Zit dit punt zeker in een voertuig?

    Alleen voertuig-wifi en de sensorwaarden automotive en cycling tellen.
    Walking breekt een verblijf niet: rondlopen op een werf is daar zijn. Op
    12-09-2026 viel een middag van drieenhalf uur op Bezelaervelden in Willebroek
    uiteen in twee korte bezoekjes en zeven "verplaatsingen" van 0,0 km, omdat de
    eerste versie elke stap als onderweg las.
    """
    ssid = (punt.get("ssid") or "").lower()
    if ssid and ssid in VOERTUIG_WIFI:
        return True
    # Alleen automotive. Cycling niet: in heel de meting kwam het twee keer voor,
    # beide keren als losse uitschieter midden op een werf. Wie echt wegfietst
    # verlaat de straal van het verblijf en breekt het zo alsnog.
    return "automotive" in (punt.get("motion") or "").lower()


def _middelpunt(groep):
    return (sum(p["lat"] for p in groep) / len(groep),
            sum(p["lon"] for p in groep) / len(groep))


def _verblijven(punten):
    """Zoekt de reeksen punten waar de telefoon op een plek bleef.

    Klassieke verblijfsdetectie: begin bij een punt, groei zolang elk volgend
    punt binnen VERBLIJF_STRAAL van het middelpunt valt en niet in een voertuig
    zit. Duurt dat lang genoeg, dan is het een verblijf.

    Een stilte in de meting breekt een verblijf niet zolang het volgende punt op
    dezelfde plek ligt: dan was je er gewoon, alleen zweeg de telefoon. Maar ligt
    het volgende punt verderop, dan stopt het verblijf, hoe de sensor dat punt
    ook noemt. Op 12-09-2026 plakte de eerste versie een middag in Willebroek en
    een avond thuis in Kessel-Lo over een gat van vijf uur aan elkaar tot een
    bezoek "Thuis" in Willebroek, en verdween de rit van 40 km ertussen.
    """
    uit = []
    i, n = 0, len(punten)
    while i < n:
        if _rijdt(punten[i]):
            i += 1
            continue
        groep = [punten[i]]
        j = i + 1
        while j < n and not _rijdt(punten[j]):
            mlat, mlon = _middelpunt(groep)
            # Een slordige meting mag wat speling krijgen, maar niet onbeperkt:
            # een punt met 150 m onzekerheid mag geen verblijf van 300 m maken.
            speling = min(punten[j].get("acc") or 0, 50)
            if afstand(mlat, mlon, punten[j]["lat"], punten[j]["lon"]) > VERBLIJF_STRAAL + speling:
                break
            groep.append(punten[j])
            j += 1
        if (groep[-1]["tst"] - groep[0]["tst"]) / 60 >= STILSTAND_MINUTEN:
            uit.append((i, j))
            i = j
        else:
            i += 1
    return uit


def _bezoek(groep, bekende_plekken, tot=None):
    """Een verblijf uit een reeks punten op een plek. tot gaat voorbij het laatste
    punt als de telefoon daarna zweeg terwijl hij er nog was (een stop)."""
    tot = groep[-1]["tst"] if tot is None else tot
    mlat, mlon = _middelpunt(groep)
    # De autorouter hangt nog in de lucht na het parkeren; die zegt niets over de plek.
    gezien = {(p.get("ssid") or "").lower() for p in groep
              if p.get("ssid") and (p.get("ssid") or "").lower() not in VOERTUIG_WIFI}
    naam = noem_plek(mlat, mlon, gezien, bekende_plekken)
    dossier = next((p.get("dossier") for p in bekende_plekken
                    if p["naam"] == naam), None) if naam else None
    # Het langste stille stuk binnen het verblijf, zodat een lezer ziet dat
    # "5 uur thuis" op een handvol punten kan rusten.
    stilte = max([(groep[x]["tst"] - groep[x - 1]["tst"]) / 60 for x in range(1, len(groep))]
                 + [(tot - groep[-1]["tst"]) / 60])
    return {
        "soort": "bezoek",
        "van": groep[0]["tst"], "tot": tot,
        "minuten": round((tot - groep[0]["tst"]) / 60),
        "lat": round(mlat, 6), "lon": round(mlon, 6),
        "punten": len(groep),
        "langste_stilte": round(stilte),
        "wifi": next((p.get("ssid") for p in groep if p.get("ssid")
                      and p["ssid"].lower() not in VOERTUIG_WIFI), None),
        "plek": naam,
        "dossier": dossier,
        # Welke tracker dit gemeten heeft. Vanaf 03-10-2026 zijn er meerdere:
        # de GPS in de auto, en later het draagbare toestel. Op het dashboard
        # moet zichtbaar zijn wie wat zag, anders is een gat niet te duiden.
        "bronnen": sorted({p.get("bron") or "telefoon" for p in groep}),
    }


# Na "motor uit" meldt de tracker in de auto niets tot de motor weer aanslaat
# (spaarstand 1, zie bronbeleid). Die stilte is dus gemeten stilstand en geen
# onbekende tijd: ligt het eerste punt erna nog in de buurt, dan stond de auto daar.
# Gemeten 03-10-2026: het eerste punt na het starten lag 115 tot 235 m verder, want
# het komt pas 30 s na "motor aan". Ligt het verder, dan blijft het een gat.
PARKEER_METER = 1000


def _geparkeerd(voor, na):
    return (voor.get("gebeurtenis") == "motor uit"
            and (na["tst"] - voor["tst"]) / 60 >= STILSTAND_MINUTEN
            and afstand(voor["lat"], voor["lon"], na["lat"], na["lon"]) <= PARKEER_METER)


def _is_stop(voor, na):
    """Stond hij stil in de stilte tussen deze twee punten van een rit?"""
    if _geparkeerd(voor, na):
        return True
    minuten = (na["tst"] - voor["tst"]) / 60
    meter = afstand(voor["lat"], voor["lon"], na["lat"], na["lon"])
    return (minuten <= GAT_MINUTEN and meter <= STOP_METER
            and minuten - meter / STOP_RIJTEMPO >= STILSTAND_MINUTEN)


def _rit(spoor, groep, van=None):
    """van: later dan het eerste punt als de rit uit een stop vertrekt; de stop
    loopt tot het eerste punt na de stilte, de afstand telt vanaf de stop."""
    van = spoor[0]["tst"] if van is None else van
    meter = sum(afstand(spoor[x]["lat"], spoor[x]["lon"],
                        spoor[x + 1]["lat"], spoor[x + 1]["lon"])
                for x in range(len(spoor) - 1))
    # De dominante wijze wint, niet een verzameling: een autorit van 83 km die
    # onderweg een paar stappen opving is geen rit "auto en te voet".
    telling = {}
    for p in groep:
        for w in (p.get("motion") or "").split(","):
            if w in ONDERWEG_WOORDEN:
                telling[w] = telling.get(w, 0) + 1
    if not telling and any((p.get("ssid") or "").lower() in VOERTUIG_WIFI for p in groep):
        telling["automotive"] = 1
    return {
        "soort": "verplaatsing",
        "van": van, "tot": spoor[-1]["tst"],
        "minuten": round((spoor[-1]["tst"] - van) / 60),
        "meter": round(meter),
        "wijze": max(telling, key=telling.get) if telling else None,
        "spoor": [[p["lat"], p["lon"]] for p in spoor],
        "bronnen": sorted({p.get("bron") or "telefoon" for p in spoor}),
    }


def _stuk_tussen(spoor, bekende_plekken=()):
    """Het stuk tussen twee verblijven, opgedeeld waar de meting zweeg.

    spoor begint met het laatste punt van het vorige verblijf en eindigt met het
    eerste van het volgende. Een stilte langer dan
    GAT_MINUTEN wordt een gat en geen rit: we weten niet welke weg er gereden is,
    en een rechte lijn tekenen zou een route verzinnen. Een kortere stilte waarin
    hij nauwelijks vooruitkwam is een stop (zie STOP_METER): een bezoek van de
    aankomst tot het eerste punt na de stilte.
    """
    uit = []
    begin = 0
    van = None                          # vertrek uit een stop, als de rit daar begint
    x = 1
    while x < len(spoor):
        if not _is_stop(spoor[x - 1], spoor[x]) and (spoor[x]["tst"] - spoor[x - 1]["tst"]) / 60 > GAT_MINUTEN:
            if x - 1 > begin:
                uit.append(_rit(spoor[begin:x], spoor[begin:x], van))
            uit.append({
                "soort": "gat",
                "van": spoor[x - 1]["tst"], "tot": spoor[x]["tst"],
                "minuten": round((spoor[x]["tst"] - spoor[x - 1]["tst"]) / 60),
                "meter": round(afstand(spoor[x - 1]["lat"], spoor[x - 1]["lon"],
                                       spoor[x]["lat"], spoor[x]["lon"])),
            })
            begin, van = x, None
        elif _is_stop(spoor[x - 1], spoor[x]):
            plek = spoor[x - 1]
            # De aankomst hoort bij de stop: terug zolang de punten op de plek liggen.
            c = x - 1
            while c > begin and afstand(spoor[c - 1]["lat"], spoor[c - 1]["lon"],
                                        plek["lat"], plek["lon"]) <= VERBLIJF_STRAAL:
                c -= 1
            # En wat na de stilte nog op de plek ligt ook: de autorouter en de
            # sensor "automotive" hangen na het parkeren nog even na.
            e = x - 1
            while e + 1 < len(spoor) and afstand(spoor[e + 1]["lat"], spoor[e + 1]["lon"],
                                                 plek["lat"], plek["lon"]) <= VERBLIJF_STRAAL:
                e += 1
            # Vertrokken in de laatste stilte: de stop loopt tot het eerste punt elders.
            weg = e + 1 < len(spoor) and _is_stop(spoor[e], spoor[e + 1])
            tot = spoor[e + 1]["tst"] if weg else spoor[e]["tst"]
            if c > begin:
                uit.append(_rit(spoor[begin:c + 1], spoor[begin:c + 1], van))
            stop = dict(_bezoek(spoor[c:e + 1], bekende_plekken, tot=tot), stop=True)
            if _geparkeerd(spoor[x - 1], spoor[x]):
                stop.update(parkeren=True, bewijs="motor uit om %s" % _lokaal(spoor[x - 1]["tst"]).strftime("%H:%M"))
            if van and stop["van"] < van:
                stop.update(van=van, minuten=round((stop["tot"] - van) / 60))
            uit.append(stop)
            begin, van = e, (tot if weg else None)
            # Niet weg in een stilte: het stuk na e kan nog een gat zijn.
            x = e + 1 if weg else e
        x += 1
    if len(spoor) - begin >= 2:
        uit.append(_rit(spoor[begin:], spoor[begin:], van))
    return uit


# Twee bezoeken met alleen een korte stilte of wat rondlopen ertussen, binnen
# deze afstand van elkaar, zijn een verblijf.
SAMENVOEG_METER = 300


def _zonder_uitschieters(punten):
    """Laat losse GPS-sprongen weg.

    Een punt dat ver van zijn beide buren ligt terwijl die buren vlak bij elkaar
    liggen, is geen verplaatsing maar een foute meting. Op 11-09-2026 brak zo een
    enkel punt een avond thuis in tweeen met een "rit" van 1,4 km in nul minuten.
    """
    if len(punten) < 3:
        return list(punten)
    uit = [punten[0]]
    for i in range(1, len(punten) - 1):
        a, b, c = punten[i - 1], punten[i], punten[i + 1]
        ver_van_a = afstand(a["lat"], a["lon"], b["lat"], b["lon"]) > 500
        ver_van_c = afstand(b["lat"], b["lon"], c["lat"], c["lon"]) > 500
        buren_samen = afstand(a["lat"], a["lon"], c["lat"], c["lon"]) < VERBLIJF_STRAAL
        kort = (c["tst"] - a["tst"]) / 60 < 15
        if ver_van_a and ver_van_c and buren_samen and kort:
            continue
        uit.append(b)
    uit.append(punten[-1])
    return uit


def _klein(stuk, lat, lon):
    """Bleef dit tussenstuk in de buurt van (lat, lon)?

    Bij een rit telt hoe ver je van de plek wegging, niet de afgelegde weg: wie
    op een werf rondloopt telt GPS-ruis op tot een lange weg zonder ver te gaan.
    Op 12-09-2026 werd drieenhalf uur op Bezelaervelden, mediaan 7 m van het
    middelpunt, zo een "wandeling van 0,7 km" die het verblijf in stukken brak.
    """
    if stuk["soort"] == "gat":
        return stuk["meter"] <= SAMENVOEG_METER
    return all(afstand(lat, lon, a, b) <= SAMENVOEG_METER for a, b in stuk.get("spoor", []))


def _voeg_samen(items):
    """Plakt bezoeken aan elkaar die in werkelijkheid een verblijf waren.

    Tussen twee bezoeken op dezelfde plek mag een korte wandeling of een stilte
    zitten; dat is nog steeds daar zijn. En wat vlak voor een bezoek in de buurt
    bleef (uitstappen, een stilte die op dezelfde plek eindigt) hoort bij dat
    bezoek: op 12-09-2026 stapte Mehdi om 10:39 uit in Willebroek, zweeg de
    telefoon 111 minuten, en lag het volgende punt op dezelfde plek.

    De langste stilte gaat mee, zodat zichtbaar blijft waarop een lang bezoek rust.
    """
    uit = []
    for item in items:
        if item["soort"] != "bezoek":
            uit.append(item)
            continue

        # Kleine stukken vlak voor dit bezoek, terug tot het vorige bezoek of
        # tot een stuk dat echt wegging.
        k = len(uit)
        while k > 0 and uit[k - 1]["soort"] != "bezoek" and _klein(uit[k - 1], item["lat"], item["lon"]):
            k -= 1
        voor = uit[k:]
        stilte = max([item.get("langste_stilte", 0)]
                     + [t["minuten"] for t in voor if t["soort"] == "gat"])

        vorig = uit[k - 1] if k > 0 and uit[k - 1]["soort"] == "bezoek" else None
        if vorig and afstand(vorig["lat"], vorig["lon"], item["lat"], item["lon"]) <= SAMENVOEG_METER:
            del uit[k:]
            n1, n2 = vorig["punten"], item["punten"]
            uit[k - 1] = dict(vorig,
                              tot=item["tot"],
                              minuten=round((item["tot"] - vorig["van"]) / 60),
                              lat=round((vorig["lat"] * n1 + item["lat"] * n2) / (n1 + n2), 6),
                              lon=round((vorig["lon"] * n1 + item["lon"] * n2) / (n1 + n2), 6),
                              punten=n1 + n2,
                              langste_stilte=round(max(stilte, vorig.get("langste_stilte", 0))),
                              wifi=vorig.get("wifi") or item.get("wifi"),
                              plek=vorig.get("plek") or item.get("plek"),
                              dossier=vorig.get("dossier") or item.get("dossier"),
                              stop=bool(vorig.get("stop") and item.get("stop")),
                              parkeren=bool(vorig.get("parkeren") or item.get("parkeren")),
                              bewijs=vorig.get("bewijs") or item.get("bewijs"))
            continue

        if voor:
            del uit[k:]
            item = dict(item, van=voor[0]["van"],
                        minuten=round((item["tot"] - voor[0]["van"]) / 60),
                        langste_stilte=round(stilte))
        uit.append(item)
    return uit




def _motor_aan_momenten(punten):
    """Wanneer de motor aansloeg. Zonder fix is tst de tijd van de laatste fix; het
    moment zelf is dan de verzendtijd (gemeten 03-10-2026, zie atrack.py)."""
    uit = []
    for p in punten:
        if p.get("gebeurtenis") != "motor aan":
            continue
        uit.append(p["verzonden"] if p.get("fix") == 0 and p.get("verzonden") else p["tst"])
    return sorted(uit)


def _parkeren_tot_motor_aan(items, punten):
    """Een parkeerstop loopt tot de motor aansloeg, niet tot het eerste punt daarna."""
    aan = _motor_aan_momenten(punten)
    for s in items:
        if not s.get("parkeren"):
            continue
        m = next((t for t in aan if s["van"] < t < s["tot"]), None)
        if m:
            s.update(tot=m, minuten=round((m - s["van"]) / 60),
                     bewijs=(s.get("bewijs") or "motor uit") + ", motor aan om %s" % _lokaal(m).strftime("%H:%M"))


def dagindeling_zuiver(punten, bekende_plekken):
    """Bezoeken, ritten en gaten uit de punten van één spoor, zonder databasetoegang.

    Los van dagindeling() zodat het tegen nagebootste punten getest kan worden.
    """
    if not punten:
        return []
    origineel = punten
    # Een punt zonder fix (hdop 0) herhaalt een oude positie. Het blijft bewaard en
    # zichtbaar, maar bewijst geen aanwezigheid en telt niet mee in een afstand.
    # Tot 04-10-2026 werden zulke "motor aan"-punten gewoon in de indeling gebruikt.
    punten = [p for p in punten if p.get("fix") != 0]
    if not punten:
        return []
    # Een punt met een onzekerheid van honderden meters is geen GPS-meting maar
    # een schatting via zendmast of wifi. Op 14-09-2026 brak zo een punt van
    # 1414 m een avond van drie uur in Gent in stukken: "geen meting" en "5 min
    # onderweg" in plaats van een bezoek. Zulke punten tellen niet mee; zijn er
    # alleen zulke punten, dan houden we ze liever dan niets.
    goed = [p for p in punten if (p.get("acc") or 0) <= MAX_ONZEKERHEID]
    punten = _zonder_uitschieters(goed if goed else punten)
    resultaat = []
    verblijven = _verblijven(punten)
    vorige_eind = None                  # index van het laatste punt van het vorige verblijf

    for (i, j) in verblijven + [(len(punten), len(punten))]:
        # Het stuk voor dit verblijf.
        tussen = punten[(vorige_eind + 1) if vorige_eind is not None else 0:i]
        spoor = ([punten[vorige_eind]] if vorige_eind is not None else []) + tussen
        if i < len(punten):
            spoor.append(punten[i])
        if len(spoor) >= 2:
            resultaat.extend(_stuk_tussen(spoor, bekende_plekken))

        if i >= len(punten):
            break
        resultaat.append(_bezoek(punten[i:j], bekende_plekken))
        vorige_eind = j - 1
    _parkeren_tot_motor_aan(resultaat, origineel)
    return _voeg_samen(resultaat)


# Berichten die iets zeggen over de toestand van de auto. VGL en STC volgen een
# motor uit of aan op de voet en zeggen zelf niets over rijden of staan.
STAAT_SOORTEN = ("VGF", "VGN", "FRI", "ERI", "STT")


def _moment(p):
    return p["verzonden"] if p.get("fix") == 0 and p.get("verzonden") else p["tst"]


def _staat(punten, voor):
    """('geparkeerd', punt) als de laatste toestandsmelding voor `voor` 'motor uit' was,
    ('onderweg', punt) bij een andere melding, (None, None) als er geen is (telefoon)."""
    lijst = [p for p in punten if p.get("berichtsoort") in STAAT_SOORTEN and _moment(p) < voor]
    if not lijst:
        return None, None
    laatste = max(lijst, key=lambda p: (_moment(p), p["tst"]))
    if laatste.get("gebeurtenis") == "motor uit" and laatste.get("fix") != 0:
        return "geparkeerd", laatste
    return "onderweg", laatste


def _parkeerstuk(punt, van, tot, **extra):
    return dict({"soort": "bezoek", "van": int(van), "tot": int(tot), "minuten": round((tot - van) / 60),
                 "lat": round(punt["lat"], 6), "lon": round(punt["lon"], 6), "punten": 0,
                 "langste_stilte": round((tot - van) / 60), "wifi": None, "plek": None, "dossier": None,
                 "bronnen": [punt.get("bron") or "auto"], "parkeren": True}, **extra)


def met_open_einde(indeling, punten, datum, nu=None, voorloper=(), extra=()):
    """Zegt hoe de dag begint en eindigt als daar geen punten liggen.

    Einde: op 13-09-2026 kwam het laatste punt om 11:56, daarna twaalf uur niets, en
    het dagboek eindigde met "rit tot 11:56". Ligt het laatste punt meer dan
    GAT_MINUTEN voor het einde van de dag (of voor nu), dan komt er een open gat bij,
    zonder afstand. Behalve als de auto toen geparkeerd was ('motor uit'): dan staat
    hij daar tot middernacht of tot nu, en dat is gemeten, geen gat.

    Begin: een dag waarop de auto pas om 21:30 vertrekt (04-10-2026) begint met
    geparkeerd staan sinds de vorige avond. voorloper zijn de punten van dit spoor
    voor de dag, uit de actieve reeks; een punt van voor de startgrens komt hier
    nooit in (bronbeleid), dus een verblijf over de grens krijgt geen ouder bewijs.
    extra zijn punten zonder fix met een oude meettijd maar een moment in deze dag
    ("motor aan" na een nacht geparkeerd).
    """
    begin, eind = B.dagranden(datum)
    nu = time.time() if nu is None else nu
    grens = min(eind, nu)
    if grens <= begin:
        return list(indeling)
    uit = list(indeling)
    geldig = [p for p in punten if p.get("fix") != 0]
    aan = [m for m in _motor_aan_momenten(list(punten) + list(extra)) if begin <= m < eind]

    staat, p0 = _staat(list(voorloper) + list(extra), begin)
    if staat == "geparkeerd":
        eerste = geldig[0] if geldig else None
        if eerste is None or afstand(p0["lat"], p0["lon"], eerste["lat"], eerste["lon"]) <= PARKEER_METER:
            tot = eerste["tst"] if eerste else int(grens)
            bewijs = "motor uit op %s" % _lokaal(p0["tst"]).strftime("%d-%m %H:%M")
            m = next((t for t in aan if t <= tot), None)
            if m:
                tot = m
                bewijs += ", motor aan om %s" % _lokaal(m).strftime("%H:%M")
            if tot > begin:
                stuk = _parkeerstuk(p0, begin, tot, open_begin=True, bewijs=bewijs)
                if eerste is None and m is None:
                    stuk.update(open=True, loopt_door=grens >= eind)
                if uit and uit[0]["soort"] == "bezoek" and \
                        afstand(uit[0]["lat"], uit[0]["lon"], stuk["lat"], stuk["lon"]) <= SAMENVOEG_METER:
                    uit[0] = dict(uit[0], van=begin, minuten=round((uit[0]["tot"] - begin) / 60), open_begin=True,
                                  parkeren=True, bewijs=bewijs + "; " + (uit[0].get("bewijs") or ""))
                else:
                    uit.insert(0, stuk)
    elif staat is None and geldig and (geldig[0]["tst"] - begin) / 60 > GAT_MINUTEN and \
            any(p.get("berichtsoort") in STAAT_SOORTEN for p in geldig):
        # Een tracker zonder bekende toestand van daarvoor: zeg dat het begin van de dag
        # niet gemeten is (de eerste dag van de reeks, of na een lange onderbreking).
        uit.insert(0, {"soort": "gat", "open_begin": True, "van": begin, "tot": geldig[0]["tst"],
                       "minuten": round((geldig[0]["tst"] - begin) / 60), "meter": None})

    if not geldig:
        return uit
    staat, pl = _staat(list(voorloper) + list(punten) + list(extra), grens)
    laatste = geldig[-1]
    if staat == "geparkeerd" and pl["tst"] >= begin and (grens - pl["tst"]) / 60 >= 1:
        bewijs = "motor uit om %s" % _lokaal(pl["tst"]).strftime("%H:%M")
        if uit and uit[-1]["soort"] == "bezoek" and \
                afstand(uit[-1]["lat"], uit[-1]["lon"], pl["lat"], pl["lon"]) <= SAMENVOEG_METER:
            uit[-1] = dict(uit[-1], tot=int(grens), minuten=round((grens - uit[-1]["van"]) / 60), open=True,
                           loopt_door=grens >= eind, parkeren=True,
                           bewijs=uit[-1].get("bewijs") or bewijs)
        else:
            stuk = _parkeerstuk(pl, pl["tst"], grens, open=True, loopt_door=grens >= eind, bewijs=bewijs)
            # Aankomen en uitrollen vlak voor 'motor uit' (een paar punten op de plek) is
            # geen rit van 0 km maar het begin van het parkeren.
            while uit and uit[-1]["soort"] == "verplaatsing" and _klein(uit[-1], stuk["lat"], stuk["lon"]):
                vorig = uit.pop()
                stuk.update(van=vorig["van"], minuten=round((stuk["tot"] - vorig["van"]) / 60))
            uit.append(stuk)
        return uit
    if (grens - laatste["tst"]) / 60 <= GAT_MINUTEN:
        return uit
    return uit + [{
        "soort": "gat", "open": True,
        "van": laatste["tst"], "tot": int(grens),
        "minuten": round((grens - laatste["tst"]) / 60),
        "meter": None,
    }]


def dagindeling(punten):
    """Losse punten omzetten naar bezoeken, verplaatsingen en gaten, per spoor samen."""
    if not punten:
        return []
    conn = db()
    bekende_plekken = plekken(conn)
    conn.close()
    uit = []
    for bron in sorted({p.get("bron") or "iphone" for p in punten}):
        uit += dagindeling_zuiver([p for p in punten if (p.get("bron") or "iphone") == bron], bekende_plekken)
    return sorted(uit, key=lambda s: s["van"])


def verrijk(indeling, plek_lijst, project_lijst, correctie_lijst, rol):
    """Elk verblijf krijgt zijn herkenning (herkenning.py), elke rit de projecten waar hij voorbijreed."""
    for s in indeling:
        if s["soort"] == "bezoek":
            h = H.beoordeel(s, plek_lijst, project_lijst, correctie_lijst, rol)
            s["herkenning"] = h
            p = h.get("project")
            s["plek"] = h.get("plek") or (p.get("naam") if p else None)
            s["dossier"] = ("%s %s" % (p.get("firma") or "", p.get("nummer"))).strip() if p else None
        elif s["soort"] == "verplaatsing":
            s["voorbij"] = H.voorbij(s.get("spoor"), project_lijst)
    return indeling


def _rijen(conn, sql, args):
    return [dict(r) for r in conn.execute(sql, args)]


def punten_van_dag(datum, conn=None):
    """De punten van een Belgische kalenderdag, alleen uit de actieve reeks (bronbeleid)."""
    if not B.dag_toegestaan(datum):
        return []
    eigen = conn is None
    conn = conn or db()
    begin, eind = B.dagranden(datum)
    clause, args = B.sql_actief()
    try:
        return _rijen(conn, f"SELECT * FROM punt WHERE tst >= ? AND tst < ? AND {clause} ORDER BY tst, volgnr",
                      [begin, eind] + args)
    finally:
        if eigen:
            conn.close()


def dag_gegevens(datum, nu=None, conn=None):
    """Alles van een dag, per spoor: punten, indeling met herkenning, voorlopig of afgesloten."""
    nu = time.time() if nu is None else nu
    if not B.dag_toegestaan(datum):
        return {"datum": datum, "buiten_reeks": True, "status": "buiten de reeks", "sporen": {}, "punten": [],
                "grens": B.STARTGRENS}
    eigen = conn is None
    conn = conn or db()
    try:
        begin, eind = B.dagranden(datum)
        clause, args = B.sql_actief()
        alle = punten_van_dag(datum, conn)
        voor = _rijen(conn, f"SELECT * FROM punt WHERE tst < ? AND {clause} ORDER BY tst DESC LIMIT 200",
                      [begin] + args)[::-1]
        extra = _rijen(conn, f"""SELECT * FROM punt WHERE tst < ? AND fix = 0 AND verzonden >= ? AND verzonden < ?
                                 AND {clause}""", [begin, begin, eind] + args)
        plek_lijst = plekken(conn)
        projecten = H.projectplekken(conn)
        corr = H.correcties(conn)
        sporen = {}
        for bron in B.actieve_bronnen():
            pb = [p for p in alle if p["bron"] == bron]
            ind = dagindeling_zuiver(pb, plek_lijst)
            ind = met_open_einde(ind, pb, datum, nu, voorloper=[p for p in voor if p["bron"] == bron],
                                 extra=[p for p in extra if p["bron"] == bron])
            verrijk(ind, plek_lijst, projecten, [c for c in corr if c["bron"] == bron], B.rol(bron))
            for s in ind:
                s["bron"] = bron
            sporen[bron] = {"bron": bron, "rol": B.rol(bron), "label": B.BRONNEN[bron].get("label"),
                            "indeling": ind, "punten": len(pb), "geldig": sum(1 for p in pb if p.get("fix") != 0),
                            "zonder_fix": sum(1 for p in pb if p.get("fix") == 0)}
        return {"datum": datum, "status": "afgesloten" if nu >= eind + AFSLUIT_UREN * 3600 else "voorlopig",
                "begin": begin, "eind": eind, "sporen": sporen, "punten": alle, "grens": B.STARTGRENS}
    finally:
        if eigen:
            conn.close()


def hoofdspoor(gegevens):
    """Het spoor dat de persoon volgt: een actieve tracker met rol persoon, anders de auto.
    Auto en persoon worden apart ingedeeld; geparkeerde autopunten filteren geen persoonlijke weg."""
    sporen = gegevens.get("sporen") or {}
    for bron, sp in sporen.items():
        if sp["rol"] == "persoon":
            return sp
    return next(iter(sporen.values()), None)


def dagen_met_data(limiet=60):
    """De dagen met punten uit de actieve reeks, nieuwste eerst; vandaag staat er altijd bij."""
    conn = db()
    clause, args = B.sql_actief()
    rijen = conn.execute(f"SELECT tst FROM punt WHERE {clause} ORDER BY tst DESC LIMIT 20000", args).fetchall()
    conn.close()
    gezien, uit = set(), [B.vandaag().isoformat()]
    gezien.add(uit[0])
    for r in rijen:
        d = _lokaal(r["tst"]).strftime("%Y-%m-%d")
        if d not in gezien:
            gezien.add(d)
            uit.append(d)
            if len(uit) >= limiet:
                break
    return sorted(uit, reverse=True)


# ------------------------------------------------------------------ web

def _iso(tst):
    return _lokaal(tst).isoformat() if tst else None


def _punt_uit(p):
    """Alles wat er gemeten is gaat mee naar buiten, zodat het dagboek de volledige
    meting bevat: ook bron, fix, ontvangst- en verzendtijd (tot 04-10-2026 weggelaten)."""
    return {"tijd": _iso(p["tst"]), "bron": p.get("bron"), "toestel": B.toestel_kort(p.get("toestel")),
            "berichtsoort": p.get("berichtsoort"), "gebeurtenis": p.get("gebeurtenis"),
            "lat": p["lat"], "lon": p["lon"], "fix": p.get("fix"), "geldig": p.get("fix") != 0,
            "hdop": p.get("hdop"), "satellieten": p.get("satellieten"), "snelheid": p.get("vel"),
            "ontvangen": _iso(p.get("ontvangen")), "verzonden": _iso(p.get("verzonden")),
            "nagestuurd": bool(p.get("gebufferd")), "beweging": p.get("motion"),
            "acc": p.get("acc"), "batt": p.get("batt"),
            "laadt": p.get("bs") == 2 if p.get("bs") is not None else None,
            "wifi": p.get("ssid"), "verbinding": p.get("conn"), "hoogte": p.get("alt"),
            "luchtdruk": p.get("druk"), "aanleiding": p.get("trigger"), "zones": p.get("regios")}


def _scherm(datum):
    import status as S                   # noqa: PLC0415
    gegevens = dag_gegevens(datum)
    conn = db()
    try:
        stand = S.overzicht(conn)
    finally:
        conn.close()
    sp = hoofdspoor(gegevens)
    stukken = [dict(s) for s in (sp["indeling"] if sp else [])]
    for s in stukken:
        s["van_tekst"] = _lokaal(s["van"]).strftime("%H:%M")
        s["tot_tekst"] = _lokaal(s["tot"]).strftime("%H:%M")
    km = sum(s.get("meter") or 0 for s in stukken if s["soort"] == "verplaatsing") / 1000
    return {"gegevens": gegevens, "stand": stand, "stukken": stukken, "km": round(km, 1),
            "aantal": len(gegevens.get("punten") or []), "spoor": sp}


@app.route("/")
def index():
    dagen = dagen_met_data()
    vandaag = B.vandaag().isoformat()
    datum = request.args.get("dag") or vandaag
    try:
        date.fromisoformat(datum)
    except ValueError:
        abort(400)
    sch = _scherm(datum)
    return render_template(
        "index.html" if not request.args.get("deel") else "deel.html",
        dagen=dagen, datum=datum, vandaag=vandaag, stukken=sch["stukken"], stand=sch["stand"],
        gegevens=sch["gegevens"], spoor=sch["spoor"],
        wijzen={"automotive": "auto", "cycling": "fiets", "walking": "te voet", "running": "lopend"},
        zekerheid={"bevestigd": "bevestigd", "waarschijnlijk": "waarschijnlijk", "kort": "kort gestopt",
                   "onzeker": "onzeker", "niet_mehdi": "niet Mehdi"},
        aantal=sch["aantal"], km=sch["km"], eerste_dag=B.eerste_dag(),
        nu_tekst=B.lokaal(time.time()).strftime("%H:%M:%S"))


@app.route("/api/dag/<datum>")
def api_dag(datum):
    try:
        date.fromisoformat(datum)
    except ValueError:
        abort(400)
    g = dag_gegevens(datum)
    sp = hoofdspoor(g)
    indeling = sp["indeling"] if sp else []
    return jsonify({
        "datum": datum, "status": g.get("status"), "grens": B.STARTGRENS, "bronbeleid": B.VERSIE,
        "buiten_reeks": bool(g.get("buiten_reeks")),
        "punten": [_punt_uit(p) for p in g.get("punten") or []],
        "indeling": indeling,
        "sporen": {b: {k: v for k, v in s.items()} for b, s in (g.get("sporen") or {}).items()},
        # Punten zonder indeling (een enkel punt, of alleen punten zonder fix) gaan apart
        # mee, zodat een dag met metingen nooit als lege dag wordt overgeslagen.
        "losse_punten": len(g.get("punten") or []) if not indeling else 0,
    })


@app.route("/api/dagboek/<datum>")
def api_dagboek(datum):
    """Het dagboek als tekst en als gegevens: dezelfde bron voor VM, bord en export."""
    import dagboek as D                  # noqa: PLC0415
    try:
        date.fromisoformat(datum)
    except ValueError:
        abort(400)
    g = dag_gegevens(datum)
    conn = db()
    try:
        verblijven = [s for sp in (g.get("sporen") or {}).values() for s in sp["indeling"] if s["soort"] == "bezoek"]
        D.vul_adressen(conn, datum, verblijven, opzoeken=request.args.get("adressen") == "1")
    finally:
        conn.close()
    sp = hoofdspoor(g)
    return jsonify({"datum": datum, "status": g.get("status"), "grens": B.STARTGRENS, "bronbeleid": B.VERSIE,
                    "markdown": D.markdown(datum, g), "sporen": g.get("sporen"),
                    "indeling": sp["indeling"] if sp else [],
                    "punten": [_punt_uit(p) for p in g.get("punten") or []],
                    "buiten_reeks": bool(g.get("buiten_reeks"))})


@app.route("/api/context")
def api_context():
    """Locatiecontext voor agents: alleen projectrelevante verblijven en de bronstatus."""
    import dagboek as D                  # noqa: PLC0415
    import status as S                   # noqa: PLC0415
    datum = request.args.get("dag") or B.vandaag().isoformat()
    try:
        date.fromisoformat(datum)
    except ValueError:
        abort(400)
    g = dag_gegevens(datum)
    conn = db()
    try:
        stand = S.overzicht(conn)
    finally:
        conn.close()
    return jsonify(D.context(datum, g, stand))


@app.route("/api/status")
def api_status():
    import status as S                   # noqa: PLC0415
    conn = db()
    try:
        return jsonify(S.overzicht(conn))
    finally:
        conn.close()


@app.route("/api/beleid")
def api_beleid():
    return jsonify(B.samenvatting())


@app.route("/api/projectplekken")
def api_projectplekken():
    import projectsync                   # noqa: PLC0415
    conn = db()
    try:
        return jsonify({"projectplekken": H.projectplekken(conn, alles=True), "dekking": projectsync.dekking(conn)})
    finally:
        conn.close()


def _wie_mag_corrigeren():
    """De naam van wie een correctie doet, of None.

    Via het portaal zet Authentik de gebruiker in X-authentik-username (de drie
    telefoonroutes maken die kop leeg in nginx). Zonder portaal: het wachtwoord.
    """
    naam = request.headers.get("X-authentik-username", "").strip()
    if naam:
        herkomst = request.headers.get("Origin") or request.headers.get("Referer") or ""
        if herkomst and urlparse(herkomst).netloc != request.host:
            return None
        return naam
    if WACHTWOORD and _wachtwoord_klopt():
        return "intern"
    return None


def _epoch(waarde):
    try:
        return int(float(waarde))
    except (TypeError, ValueError):
        return int(datetime.fromisoformat(str(waarde)).timestamp())


@app.route("/api/correctie", methods=["GET", "POST"])
def api_correctie():
    """Correcties van Mehdi op de herkenning: welk project, geen project, of de auto
    was niet bij hem. Herleidbaar (wie, wanneer, waarom); intrekken zet een tijdstip,
    er wordt niets gewist. Bij elke volgende verwerking toegepast."""
    conn = db()
    try:
        if request.method == "GET":
            return jsonify({"correcties": [dict(r) for r in conn.execute(
                "SELECT * FROM bezoekcorrectie ORDER BY id DESC LIMIT 500")]})
        wie = _wie_mag_corrigeren()
        if not wie:
            abort(403)
        d = request.get_json(silent=True) or request.form.to_dict()
        if d.get("intrekken"):
            conn.execute("UPDATE bezoekcorrectie SET ingetrokken = ? WHERE id = ? AND ingetrokken IS NULL",
                         (int(time.time()), int(d["intrekken"])))
            conn.commit()
            return jsonify({"ok": True, "ingetrokken": int(d["intrekken"])})
        wat = str(d.get("wat", ""))
        bron = str(d.get("bron", ""))
        if wat not in ("project", "geen_project", "niet_mehdi") or bron not in B.BRONNEN:
            abort(400)
        try:
            van, tot = _epoch(d["van"]), _epoch(d["tot"])
        except (KeyError, ValueError):
            abort(400)
        sleutel = str(d.get("sleutel") or "")[:60] or None
        if wat == "project" and not sleutel:
            abort(400)
        cur = conn.execute("""INSERT INTO bezoekcorrectie (bron, van, tot, wat, sleutel, reden, door, wanneer)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                           (bron, van, tot, wat, sleutel, str(d.get("reden", ""))[:300] or None,
                            str(d.get("door") or wie)[:60], int(time.time())))
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})
    finally:
        conn.close()


@app.route("/gezond")
def gezond():
    """Kort, per actieve bron. Een lege database is 'geen gegevens', nooit '0 min geleden'."""
    import status as S                   # noqa: PLC0415
    conn = db()
    try:
        stand = S.overzicht(conn)
    finally:
        conn.close()
    uit = {"bronbeleid": B.VERSIE, "bronnen": {}}
    for b in stand["bronnen"]:
        lg = b.get("laatste_geldige_positie") or {}
        lo = b.get("laatste_ontvangst") or {}
        uit["bronnen"][b["bron"]] = {"status": b["status"], "toestand": b.get("toestand"),
                                    "laatste_ontvangst": lo.get("tijd"), "laatste_geldige_positie": lg.get("tijd"),
                                    "minuten_geleden": lg.get("minuten_geleden"), "alarm": b.get("alarm")}
    uit["alarmen"] = stand["alarmen"]
    return jsonify(uit)


@app.route("/health")
def health():
    conn = db()
    try:
        conn.execute("SELECT 1 FROM punt LIMIT 1").fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3031)))
