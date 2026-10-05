"""Grendels op de robuustheid: geen langdurig slot op de database terwijl het netwerk traag is.

Gevonden bij de onafhankelijke controle van 05-10-2026: de projectsync en de adresverrijking
hielden tijdens elk geocodeverzoek (tot 13 s) een schrijftransactie open, zodat een tweede
schrijver, zoals de ontvanger van de tracker, 'database is locked' kreeg en niet bevestigde.
Een trage nagebootste geocoder en een gelijktijdige schrijver; eigen proefgegevens, geen netwerk.

Draaien: python3 locatie/test_robuust.py
"""
import os
import sqlite3
import sys
import tempfile
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
PROEF = "990000000000017"
os.environ["LOCATIE_DB"] = os.path.join(tempfile.mkdtemp(), "robuust.db")
os.environ["ATRACK_IMEIS"] = PROEF + ":auto"

import atrack_server  # noqa: E402
import bronbeleid as B  # noqa: E402
import dagboek  # noqa: E402
import projectsync as P  # noqa: E402
import schema  # noqa: E402

B.BRONNEN["auto"]["protocolversie"] = None
atrack_server.schema_klaar()
_n = [6000]


def bericht():
    from datetime import datetime, timedelta, timezone
    _n[0] += 1
    t = (datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc) + timedelta(seconds=30 * _n[0])).strftime("%Y%m%d%H%M%S")
    return ("+RESP:GTFRI,8020090501,%s,,,10,1,1,0.0,90,30.0,4.930000,50.930000,%s,0206,0010,4E84,"
            "061D580C,00,0.0,,,,,85,210000,,,,%s,%04X$" % (PROEF, t, t, _n[0]))


def traag(seconden):
    def geocode(adres):
        time.sleep(seconden)
        return {"lat": 50.9, "lon": 4.6, "kwaliteit": "adres", "bron": "proef"}
    return geocode


HA = [{"firma": "HARC", "nummer": str(9300 + i), "project_id": "u%d" % i, "naam": "p%d" % i,
       "adres": "Proefstraat %d, 3999 Proefdorp" % i, "adres_bron": "projectmap (A13)", "bron": "ha-projecten",
       "link": None} for i in range(4)]


def gelijktijdig(werk):
    """Start werk in een draad en meet hoe snel de ontvanger intussen een bericht bewaart en bevestigt."""
    fout = []
    draad = threading.Thread(target=lambda: fout.append(None) if werk() is None else None)
    draad.start()
    time.sleep(1.4)                      # midden in het tweede trage verzoek, na de eerste schrijfactie
    t0 = time.time()
    terug, wat = atrack_server.verwerk(bericht())
    duur = time.time() - t0
    # Ook een willekeurige tweede schrijver met een korte wachttijd moet erdoor.
    c = sqlite3.connect(os.environ["LOCATIE_DB"], timeout=2)
    c.execute("BEGIN IMMEDIATE")
    c.execute("ROLLBACK")
    c.close()
    draad.join()
    return terug, wat, duur


def test_ontvanger_bevestigt_tijdens_een_trage_projectsync():
    terug, wat, duur = gelijktijdig(lambda: P.synchroniseer(schema.verbind(os.environ["LOCATIE_DB"]), ha=HA, mappen={},
                                                             geocodeer=traag(1.0)))
    assert wat == "bewaard" and terug and duur < 2, (wat, terug, duur)
    conn = schema.verbind(os.environ["LOCATIE_DB"])
    assert conn.execute("SELECT count(*) FROM projectplek").fetchone()[0] == 4, "de index moet volledig staan"


def test_ontvanger_bevestigt_tijdens_een_trage_adresverrijking():
    verblijven = [{"soort": "bezoek", "lat": 50.90 + i / 100, "lon": 4.60} for i in range(4)]

    def langzaam(lat, lon):
        time.sleep(1.0)
        return {"adres": "Proefstraat %.2f" % lat, "volledig": "proef"}
    terug, wat, duur = gelijktijdig(lambda: dagboek.verrijk_adressen(schema.verbind(os.environ["LOCATIE_DB"]),
                                                                     "2026-10-05", verblijven, opzoeken=langzaam))
    assert wat == "bewaard" and terug and duur < 2, (wat, terug, duur)
    conn = schema.verbind(os.environ["LOCATIE_DB"])
    assert conn.execute("SELECT count(*) FROM adrescache").fetchone()[0] == 4
    assert conn.execute("SELECT count(*) FROM adresbezoek WHERE datum = '2026-10-05'").fetchone()[0] == 4


def test_een_storing_bij_de_geocodedienst_houdt_de_goede_coordinaat():
    """Hetzelfde adres, een grove geocode die opnieuw geprobeerd wordt, en de dienst is weg: de vorige
    coördinaat en kwaliteit blijven, de storing staat in het rapport."""
    pad = os.path.join(tempfile.mkdtemp(), "storing.db")
    conn = schema.verbind(pad)
    grof = lambda adres: {"lat": 50.9, "lon": 4.6, "kwaliteit": "straat", "bron": "proef"}  # noqa: E731
    P.synchroniseer(conn, ha=HA[:1], mappen={}, geocodeer=grof)
    weg = lambda adres: {"lat": None, "lon": None, "kwaliteit": "fout", "bron": None}  # noqa: E731
    rapport = P.synchroniseer(conn, ha=HA[:1], mappen={}, geocodeer=weg, opnieuw=True)
    r = conn.execute("SELECT lat, geocode_kwaliteit FROM projectplek WHERE sleutel = 'HARC:9300'").fetchone()
    assert (r[0], r[1]) == (50.9, "straat"), tuple(r)
    assert rapport["dienst_onbereikbaar"] == ["HARC:9300"], rapport


def test_een_adreswijziging_tijdens_een_storing_wordt_later_alsnog_geocodeerd():
    """Nacontrole v1.5: adres A goed, het bronadres wordt B terwijl de dienst weg is, daarna werkt de
    dienst weer. De oude code bewaarde coördinaat A met kwaliteit 'adres' naast de vingerafdruk van B,
    en de volgende gezonde ronde riep de geocoder niet meer aan."""
    for opnieuw in (False, True):
        conn = schema.verbind(os.path.join(tempfile.mkdtemp(), "wijziging.db"))
        P.synchroniseer(conn, ha=HA[:1], mappen={}, geocodeer=traag(0))                       # A
        b = [dict(HA[0], adres="Proefstraat 0 bus 1, 3999 Proefdorp")]
        weg = lambda adres: {"lat": None, "lon": None, "kwaliteit": "fout", "bron": None}  # noqa: E731
        rapport = P.synchroniseer(conn, ha=b, mappen={}, geocodeer=weg, opnieuw=opnieuw)       # B, storing
        r = conn.execute("SELECT lat, geocode_kwaliteit FROM projectplek WHERE sleutel = 'HARC:9300'").fetchone()
        assert (r[0], r[1]) == (50.9, "verouderd"), (opnieuw, tuple(r))
        assert rapport["dienst_onbereikbaar"] == ["HARC:9300"] and "HARC:9300" in rapport["geocode_storing"], rapport
        assert rapport["bruikbaar"] == 0, "een coördinaat van een ander adres herkent niet"
        import herkenning
        assert not herkenning.projectplekken(conn), "verouderd is geen bruikbare projectplek"
        gevraagd = []

        def terug(adres):
            gevraagd.append(adres)
            return {"lat": 50.95, "lon": 4.65, "kwaliteit": "adres", "bron": "proef"}
        rapport = P.synchroniseer(conn, ha=b, mappen={}, geocodeer=terug, opnieuw=opnieuw)    # B, gezond
        r = conn.execute("SELECT lat, geocode_kwaliteit FROM projectplek WHERE sleutel = 'HARC:9300'").fetchone()
        assert gevraagd == [b[0]["adres"]] and (r[0], r[1]) == (50.95, "adres"), (opnieuw, gevraagd, tuple(r))
        assert rapport["geocode_storing"] == [] and rapport["bruikbaar"] == 1, rapport


def test_geocode_meldt_een_storing_niet_als_niet_gevonden():
    import geocode
    echt = geocode._get

    def kapot(*a, **k):
        raise OSError("netwerk weg")
    geocode._get = kapot
    geocode._laatste_nominatim[0] = 0
    try:
        uit = geocode.geocodeer("Bondgenotenlaan 1, 3000 Leuven")
    finally:
        geocode._get = echt
    assert uit["kwaliteit"] == "fout", uit


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except Exception as e:  # noqa: BLE001
                fouten += 1
                print("   MISLUKT   %s: %s: %s" % (naam, type(e).__name__, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)
