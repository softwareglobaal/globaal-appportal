"""Grendels voor het actuele signaal, met verzonnen toestellen en plaatsen."""
import json
import os
import sys
import tempfile
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import bronbeleid as B  # noqa: E402
import live_beweging as L  # noqa: E402
import schema  # noqa: E402
import app  # noqa: E402
import status as S  # noqa: E402

AUTO = "990000000000017"
PERSOON = "990000000000025"
os.environ["ATRACK_IMEIS"] = f"{AUTO}:auto,{PERSOON}:draagbaar"
B.BRONNEN["auto"]["toestel_sha256"] = B.vingerafdruk(AUTO)


def db():
    return schema.verbind(os.path.join(tempfile.mkdtemp(), "proef.db"))


def tijd(u, m=0, s=0):
    return int(datetime(2026, 10, 17, u, m, s, tzinfo=B.BRUSSEL).timestamp())


def punt(conn, tst, lat, lon, bron="auto", toestel=AUTO, vel=30, fix=1, hdop=1,
         ontvangen=None, gebufferd=0, verdacht=None, soort="FRI", moment=None):
    ontvangen = tst + 1 if ontvangen is None else ontvangen
    bid = conn.execute("""INSERT INTO bericht (ontvangen, laatst_ontvangen, bron, toestel, protocol,
                                               vingerafdruk, ruw)
                          VALUES (?, ?, ?, ?, 'atrack', ?, 'proef')""",
                       (ontvangen, ontvangen, bron, toestel, f"proef-{id(conn)}-{tst}-{bron}-{soort}")).lastrowid
    conn.execute("""INSERT INTO punt (tst, lat, lon, vel, bron, toestel, fix, hdop, ontvangen, gebufferd,
                                     verdacht, berichtsoort, volgnr, moment, bericht_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                 (tst, lat, lon, vel, bron, toestel, fix, hdop, ontvangen, gebufferd, verdacht,
                  soort, tst if moment is None else moment, bid))
    conn.commit()


def met_persoon(fn):
    oud = dict(B.BRONNEN["draagbaar"])
    B.BRONNEN["draagbaar"].update(status="actief", ingang="2026-10-17T00:00:00+02:00",
                                  toestel_sha256=B.vingerafdruk(PERSOON))
    try:
        fn()
    finally:
        B.BRONNEN["draagbaar"].clear()
        B.BRONNEN["draagbaar"].update(oud)


def test_auto_beweegt_maar_persoon_is_niet_bewezen():
    conn = db()
    nu = tijd(10, 2)
    punt(conn, nu - 60, 50.8, 4.7)
    punt(conn, nu - 30, 50.801, 4.7)
    uit = L.overzicht(conn, nu)
    assert uit["auto"]["toestand"] == "auto_beweegt", uit
    assert uit["persoon"]["toestand"] == "niet_aangesloten", uit
    assert "lat" not in json.dumps(uit) and "50.8" not in json.dumps(uit), uit


def test_gedragen_tracker_heeft_eigen_verse_reeks():
    def proef():
        conn = db()
        nu = tijd(10, 2)
        punt(conn, nu - 60, 50.8, 4.7, bron="draagbaar", toestel=PERSOON, vel=4)
        punt(conn, nu - 30, 50.8005, 4.7, bron="draagbaar", toestel=PERSOON, vel=4)
        uit = L.overzicht(conn, nu)
        assert uit["persoon"]["toestand"] == "onderweg", uit
        assert uit["auto"]["toestand"] == "onbekend", uit
    met_persoon(proef)


def test_motor_uit_zonder_nieuwe_fix_stopt_auto_oordeel():
    conn = db()
    nu = tijd(10, 2)
    punt(conn, nu - 60, 50.8, 4.7)
    punt(conn, nu - 30, 50.801, 4.7)
    punt(conn, nu - 30, 50.801, 4.7, fix=0, hdop=0, vel=0, soort="VGF",
         moment=nu - 20, ontvangen=nu - 19)
    assert L.bron(conn, "auto", nu)["toestand"] == "onbekend"


def test_oude_buffer_en_oude_ontvangst_starten_geen_vertrek():
    conn = db()
    nu = tijd(10, 2)
    punt(conn, nu - 60, 50.8, 4.7, ontvangen=nu, gebufferd=1)
    punt(conn, nu - 30, 50.801, 4.7, ontvangen=nu, gebufferd=1)
    assert L.bron(conn, "auto", nu)["toestand"] == "onbekend"
    conn2 = db()
    punt(conn2, nu - 121, 50.8, 4.7, ontvangen=nu)
    punt(conn2, nu - 30, 50.801, 4.7, ontvangen=nu)
    assert L.bron(conn2, "auto", nu)["toestand"] == "onbekend", "een ontvangst >120 s te laat is geen live bewijs"


def test_slechte_fix_verkeerd_toestel_en_stilte_geen_beweging_bewijzen():
    nu = tijd(10, 2)
    conn = db()
    punt(conn, nu - 60, 50.8, 4.7, hdop=20)
    punt(conn, nu - 30, 50.801, 4.7, hdop=20)
    assert L.bron(conn, "auto", nu)["toestand"] == "onbekend"
    conn2 = db()
    punt(conn2, nu - 60, 50.8, 4.7, toestel=PERSOON)
    punt(conn2, nu - 30, 50.801, 4.7, toestel=PERSOON)
    assert L.bron(conn2, "auto", nu)["toestand"] == "onbekend"
    conn3 = db()
    punt(conn3, nu - 240, 50.8, 4.7)
    punt(conn3, nu - 210, 50.801, 4.7)
    assert L.bron(conn3, "auto", nu)["toestand"] == "onbekend"
    conn4 = db()
    punt(conn4, nu - 60, 50.8, 4.7)
    punt(conn4, nu - 30, 50.801, 4.7, verdacht="onmogelijke sprong")
    assert L.bron(conn4, "auto", nu)["toestand"] == "onbekend"


def test_api_geeft_het_oordeel_zonder_coordinaten():
    conn = db()
    app.DB_PAD = conn.execute("PRAGMA database_list").fetchone()[2]
    response = app.app.test_client().get("/api/beweging")
    assert response.status_code == 200
    data = response.get_json()
    assert data["persoon"]["toestand"] == "niet_aangesloten"
    assert "lat" not in data and "lon" not in data and "punten" not in data


def test_draagbare_status_gebruikt_geen_automotor():
    def proef():
        conn = db()
        nu = tijd(10, 2)
        punt(conn, nu - 30, 50.8, 4.7, bron="draagbaar", toestel=PERSOON)
        stand = S.bron(conn, "draagbaar", nu)
        assert stand["toestand"] == "laatst ontvangen", stand
        assert "motor" not in stand["uitleg"] and not stand["alarm"], stand
    met_persoon(proef)


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("geslaagd", naam)
            except Exception as fout:  # noqa: BLE001
                fouten += 1
                print("MISLUKT", naam, type(fout).__name__, fout)
    sys.exit(1 if fouten else 0)
