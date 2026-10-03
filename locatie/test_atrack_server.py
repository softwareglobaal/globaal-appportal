"""Grendels op de ontvanger van de autotracker en op de tweede bron.

Deze tests draaien tegen een echte socket en een echte database, want juist
daar zaten de gevaren: een punt dat stilletjes verdwijnt omdat twee bronnen
hetzelfde tijdstip hebben, en een bevestiging die vertrekt voordat het punt
bewaard is.

Draaien: python3 locatie/test_atrack_server.py
"""
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import time

PAD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PAD)
DB = os.path.join(tempfile.mkdtemp(), "proef.db")
os.environ["LOCATIE_DB"] = DB
os.environ["ATRACK_IMEIS"] = "864696060004173:auto"
os.environ.setdefault("TZ", "Europe/Brussels")

import app as webapp            # noqa: E402
import atrack_server            # noqa: E402

FRI = ("+RESP:GTFRI,8020090302,864696060004173,GV500CG,11985,10,1,1,0.0,0,118.5,"
       "4.700000,50.800000,20230808033438,0460,0001,DF5C,05FE6667,03,15,0,123.5,"
       "00123:04:44,,,,100,210000,,,,20230808033438,01B3$")
VGF = ("+RESP:GTVGF,8020090302,864696060004173,gv500cg,00,2,33,0,0.0,0,83.4,4.370000,"
       "51.050000,20231212053622,0460,0000,550B,085BE2AE,01,1,12345:12:34,0.0,"
       "20231212053623,0116$")
VREEMD = FRI.replace("864696060004173", "111111111111111")


def rijen(waar="1=1", *args):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM punt WHERE " + waar, args)]
    finally:
        conn.close()


def test_een_bericht_wordt_bewaard_met_zijn_eigen_velden():
    terug, wat = atrack_server.verwerk(FRI)
    assert wat == "bewaard", wat
    assert terug == "+SACK:01B3$", terug
    r = rijen("bron = 'auto'")[0]
    assert abs(r["lat"] - 50.8) < 1e-6 and abs(r["lon"] - 4.7) < 1e-6
    assert r["tst"] == 1691465678, r["tst"]
    assert r["hdop"] == 1 and r["satellieten"] == 15 and r["fix"] == 1
    assert r["acc"] is None, "een HDOP mag nooit in het meterveld belanden"
    assert r["gebufferd"] == 0 and r["verzonden"] == 1691465678
    assert r["motion"] == "stationary", "snelheid 0, dus geen rit"


def test_twee_bronnen_op_dezelfde_seconde_blijven_allebei_staan():
    """De oude tabel had het tijdstip als sleutel; dan verdween er een."""
    conn = webapp.db()
    tst = 1691465678                          # zelfde seconde als het FRI-bericht
    conn.execute("INSERT INTO punt (tst, lat, lon, bron) VALUES (?,?,?, 'iphone') "
                 "ON CONFLICT(bron, tst) DO NOTHING", (tst, 50.0, 4.0))
    conn.commit()
    conn.close()
    atrack_server.verwerk(FRI)
    gevonden = {r["bron"] for r in rijen("tst = ?", tst)}
    assert gevonden == {"iphone", "auto"}, gevonden


def test_motor_uit_telt_als_stilstand_en_motor_aan_als_rit():
    atrack_server.verwerk(VGF)
    r = rijen("gebeurtenis = 'motor uit'")[0]
    assert r["motion"] == "stationary" and r["bron"] == "auto"
    assert r["tst"] == 1702359382, r["tst"]


def test_de_ontvanger_maakt_zelf_het_schema_klaar():
    """03-10-2026: de ontvanger stond te luisteren terwijl de kolom bron nog
    niet bestond, omdat de webapp in een andere container het schema beheert."""
    import sqlite3 as s
    pad = os.path.join(tempfile.mkdtemp(), "leeg.db")
    oud_db, atrack_server.DB_PAD = atrack_server.DB_PAD, pad
    oud_env = os.environ["LOCATIE_DB"]
    os.environ["LOCATIE_DB"] = pad
    try:
        import importlib
        importlib.reload(webapp)
        atrack_server.schema_klaar()
        kolommen = {r[1] for r in s.connect(pad).execute("PRAGMA table_info(punt)")}
        assert "bron" in kolommen and "hdop" in kolommen, kolommen
    finally:
        atrack_server.DB_PAD = oud_db
        os.environ["LOCATIE_DB"] = oud_env
        importlib.reload(webapp)


def test_onbekend_toestel_wordt_geweigerd():
    voor = len(rijen())
    terug, wat = atrack_server.verwerk(VREEMD)
    assert terug is None and wat == "onbekend toestel"
    assert len(rijen()) == voor, "een vreemd IMEI mag niets kunnen schrijven"


def test_bevestiging_komt_pas_na_het_opslaan():
    """Het toestel wist zijn kopie na +SACK. Breekt het schrijven, dan mag er
    geen bevestiging vertrekken, anders is de meting weg."""
    echt = atrack_server.schrijf
    atrack_server.schrijf = lambda b: (_ for _ in ()).throw(sqlite3.OperationalError("vol"))
    try:
        fout = None
        try:
            atrack_server.verwerk(FRI.replace("20230808033438,01B3$", "20230808033439,01B4$"))
        except sqlite3.OperationalError as e:
            fout = e
        assert fout is not None, "een mislukt schrijven mag niet stil bevestigd worden"
    finally:
        atrack_server.schrijf = echt


def test_de_poort_neemt_een_echte_verbinding_aan():
    server = atrack_server.Server(("127.0.0.1", 0), atrack_server.Verbinding)
    poort = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        s = socket.create_connection(("127.0.0.1", poort), timeout=5)
        # Twee berichten in één pakket: de splitsing op $ moet dat aankunnen.
        s.sendall((FRI.replace(",01B3$", ",01C1$") + VGF.replace(",0116$", ",01C2$")).encode())
        s.settimeout(5)
        gekregen = b""
        eind = time.time() + 5
        while gekregen.count(b"$") < 2 and time.time() < eind:
            brok = s.recv(256)
            if not brok:
                break
            gekregen += brok
        s.close()
        assert b"+SACK:01C1$" in gekregen and b"+SACK:01C2$" in gekregen, gekregen
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    webapp.db().close()          # zoals in bedrijf: de webapp maakt de tabel
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except AssertionError as e:
                fouten += 1
                print("   MISLUKT   %s: %s" % (naam, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)
