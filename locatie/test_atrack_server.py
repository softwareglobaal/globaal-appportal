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
    conn.execute("INSERT INTO punt (tst, lat, lon, bron, berichtsoort) VALUES (?,?,?, 'iphone', 'location') "
                 "ON CONFLICT(bron, tst, berichtsoort, volgnr) DO NOTHING", (tst, 50.0, 4.0))
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


def berichten(waar="1=1", *args):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM toestelbericht WHERE " + waar, args)]
    finally:
        conn.close()


# Teruggelezen instellingen (AT+GTRTO sub 2), vorm uit de handleiding v3.02,
# 4.4.2. Bewust zo gekozen dat er twee getallen voor de verzendtijd staan.
ALM = ("+RESP:GTALM,8020090501,864696060004173,GV500CG,0,1,1,CFG,gv500cg,GV500CG,0,0.0,"
       ",,003F,1,00,1BDEF,,3,0,300,00,1,0,0,0017,0,0,20261003120000,0007$")
HBD = "+ACK:GTHBD,8020090501,864696060004173,GV500CG,20261003120100,0008$"


def test_teruggelezen_instellingen_worden_voluit_bewaard_en_zijn_geen_meting():
    """03-10-2026: de log kapte op 90 tekens en bewaarde niets, zodat we de
    echte veldvolgorde van de tracker (protocol 5.01) niet konden nalezen."""
    voor = len(rijen())
    terug, wat = atrack_server.verwerk(ALM)
    assert wat == "geen meting", wat
    assert terug == "+SACK:0007$", terug
    assert len(rijen()) == voor, "instellingen mogen nooit als punt (0, 0) belanden"
    b = berichten("soort = 'ALM'")
    assert len(b) == 1 and b[0]["ruw"] == ALM and b[0]["bron"] == "auto", b
    assert b[0]["kop"] == "RESP" and b[0]["verzonden"] == 1791028800, b


def test_een_hartslag_wordt_bevestigd_en_als_levensteken_bewaard():
    terug, wat = atrack_server.verwerk(HBD)
    assert terug == "+SACK:GTHBD,8020090501,0008$", terug
    b = berichten("soort = 'HBD'")
    assert len(b) == 1 and b[0]["kop"] == "ACK", b


def test_een_vreemd_toestel_schrijft_ook_geen_toestelbericht():
    voor = len(berichten())
    terug, wat = atrack_server.verwerk(ALM.replace("864696060004173", "111111111111111"))
    assert terug is None and wat == "onbekend toestel"
    assert len(berichten()) == voor


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


DRIE = ("+RESP:GTFRI,8020090501,864696060004173,,,10,3,"
        "1,0.0,180,30.3,4.700000,50.800000,20261004100000,0206,0010,4E84,061D580C,00,"
        "1,12.0,90,30.0,4.701000,50.801000,20261004100030,0206,0010,4E84,061D580C,00,"
        "2,40.0,90,30.0,4.705000,50.802000,20261004100100,0206,0010,4E84,061D580C,00,"
        "0.0,,,,,85,210000,,,,20261004100105,0030$")


def ruwe(waar="1=1", *args):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM bericht WHERE " + waar, args)]
    finally:
        conn.close()


def test_meerdere_posities_worden_allemaal_bewaard_met_een_ruw_bericht():
    terug, wat = atrack_server.verwerk(DRIE)
    assert wat == "bewaard" and terug == "+SACK:0030$", (wat, terug)
    p = rijen("teller = '0030' ORDER BY volgnr")
    assert [r["volgnr"] for r in p] == [0, 1, 2] and len({r["bericht_id"] for r in p}) == 1, p
    b = ruwe("teller = '0030'")
    assert len(b) == 1 and b[0]["posities_gemeld"] == 3 and b[0]["posities_bewaard"] == 3, b
    assert b[0]["ruw"] == DRIE and b[0]["toestel"] == "864696060004173"


def test_een_onvolledig_bericht_wordt_bewaard_en_gemeld():
    vier = DRIE.replace(",10,3,", ",10,4,").replace(",0030$", ",0031$").replace("2026100410", "2026100412")
    terug, wat = atrack_server.verwerk(vier)
    assert wat == "onvolledig" and terug == "+SACK:0031$", (wat, terug)
    b = ruwe("teller = '0031'")[0]
    assert b["verwerking"].startswith("onvolledig") and b["ruw"] == vier, b


def test_een_dubbel_bericht_wordt_bevestigd_maar_niet_dubbel_bewaard():
    """Opnieuw verstuurd omdat de bevestiging uitbleef: geen tweede rit."""
    regel = FRI.replace("20230808033438,01B3$", "20230808033500,01D0$")
    atrack_server.verwerk(regel)
    voor = len(rijen())
    terug, wat = atrack_server.verwerk(regel)
    assert wat == "dubbel" and terug == "+SACK:01D0$", (wat, terug)
    assert len(rijen()) == voor
    assert ruwe("teller = '01D0'")[0]["aantal"] == 2


def test_naleveren_uit_de_buffer_bewaart_een_keer_met_de_oorspronkelijke_meettijd():
    """Netwerk weg: het toestel bewaart en stuurt later met +BUFF. Kwam het origineel
    toch binnen, dan is het hetzelfde bericht; anders een nieuw punt, eenmaal."""
    nieuw = ("+BUFF:GTFRI,8020090501,864696060004173,,,10,1,1,30.0,90,30.0,4.710000,50.810000,20261004090000,"
             "0206,0010,4E84,061D580C,00,0.0,,,,,85,210000,,,,20261004093000,0040$")
    terug, wat = atrack_server.verwerk(nieuw)
    assert wat == "bewaard" and terug == "+SACK:0040$"
    r = rijen("teller = '0040'")
    assert len(r) == 1 and r[0]["gebufferd"] == 1 and r[0]["tst"] == 1791104400, r
    assert r[0]["verzonden"] - r[0]["tst"] == 1800
    # Hetzelfde bericht nog eens, nu als +RESP: geen tweede punt.
    terug, wat = atrack_server.verwerk(nieuw.replace("+BUFF:", "+RESP:"))
    assert wat == "dubbel" and len(rijen("teller = '0040'")) == 1


def test_motor_aan_zonder_fix_verdwijnt_niet_naast_motor_uit():
    """03-10-2026: 27 'motor aan' in de log, 5 in de database."""
    uit = ("+RESP:GTVGF,8020090501,864696060004173,,00,7,600,1,0.0,353,5.9,4.720000,50.820000,20261004110000,"
           "0206,0010,4E84,061D580C,00,,0.0,20261004110001,0050$")
    aan = ("+RESP:GTVGN,8020090501,864696060004173,,00,7,1800,0,0.0,353,5.9,4.720000,50.820000,20261004110000,"
           "0206,0010,4E84,061D580C,00,,0.0,20261004113001,0051$")
    atrack_server.verwerk(uit)
    terug, wat = atrack_server.verwerk(aan)
    assert wat == "bewaard", wat
    soorten = {r["berichtsoort"] for r in rijen("tst = 1791111600")}
    assert soorten == {"VGF", "VGN"}, soorten
    vgn = rijen("berichtsoort = 'VGN' AND tst = 1791111600")[0]
    assert vgn["fix"] == 0 and vgn["verzonden"] == 1791113401


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
