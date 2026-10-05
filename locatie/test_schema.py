"""Grendels op de schema-upgrade: één keer, in één transactie, met een kopie vooraf,
en de reeks van de tracker blijft rij voor rij gelijk.

Nagebootst met een database in de vorm van 03-10-2026 (schema 1, sleutel (bron, tst))
en eigen proefberichten. Geen echte metingen.

Draaien: python3 locatie/test_schema.py
"""
import os
import sqlite3
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import schema  # noqa: E402

IMEI = "990000000000017"
FRI = ("+RESP:GTFRI,8020090501,{imei},,,10,1,1,0.0,180,30.3,4.700000,50.800000,{tijd},0206,0010,4E84,061D580C,"
       "00,0.0,,,,,85,210000,,,,{tijd},{teller}$")
STT22 = ("+RESP:GTSTT,8020090501,{imei},,22,1,0.0,180,30.3,4.700100,50.800100,{tijd},0206,0010,4E84,061D580C,"
         "00,{tijd},{teller}$")


def oude_database():
    """Een database zoals ze op 03-10-2026 live stond: schema 1, zonder versie."""
    pad = os.path.join(tempfile.mkdtemp(), "locatie.db")
    c = sqlite3.connect(pad)
    schema._v1(c)                      # de vorm van toen, zonder user_version
    c.commit()
    rijen = [
        (1791019069, FRI.format(imei=IMEI, tijd="20261003091749", teller="0024"), 0, "vast interval", "stationary"),
        (1791019100, STT22.format(imei=IMEI, tijd="20261003091820", teller="0025"), 0, "beweging", "stationary"),
    ]
    for tst, ruw, vel, geb, motion in rijen:
        c.execute("""INSERT INTO punt (tst, lat, lon, vel, soort, ruw, motion, gebeurtenis, ontvangen, bron, hdop,
                                       fix, gebufferd) VALUES (?, 50.8, 4.7, ?, 'location', ?, ?, ?, ?, 'auto', 1, 1, 0)""",
                  (tst, vel, ruw, motion, geb, tst + 2))
    c.execute("INSERT INTO plek (naam, lat, lon, straal, soort, dossier) VALUES ('Thuis', 50.8, 4.7, 150, 'thuis', NULL)")
    c.commit()
    c.close()
    return pad


def test_upgrade_houdt_de_reeks_rij_voor_rij_gelijk():
    pad = oude_database()
    c = sqlite3.connect(pad)
    voor = c.execute("SELECT tst, lat, lon, ruw, ontvangen, bron FROM punt ORDER BY tst").fetchall()
    c.close()
    v_voor, v_na, kopie = schema.migreer(pad)
    assert (v_voor, v_na) == (0, schema.LAATSTE), (v_voor, v_na)
    c = sqlite3.connect(pad)
    assert c.execute("SELECT count(*) FROM punt WHERE moment IS NULL").fetchone()[0] == 0, "elk punt een gebeurtenistijd"
    pk = [r[1] for r in c.execute("PRAGMA table_info(punt)") if r[5]]
    assert pk == ["bericht_id", "volgnr"] or sorted(pk) == ["bericht_id", "volgnr"], pk
    c.close()
    c = sqlite3.connect(pad)
    na = c.execute("SELECT tst, lat, lon, ruw, ontvangen, bron FROM punt ORDER BY tst").fetchall()
    assert voor == na, "de upgrade veranderde de reeks"
    r = c.execute("SELECT toestel, berichtsoort, teller, bericht_id FROM punt WHERE tst = 1791019069").fetchone()
    assert r[0] == IMEI and r[1] == "FRI" and r[2] == "0024" and r[3], r
    # GTSTT 22 is 'motor aan, rijdt', ook op snelheid 0: dat wordt uit het ruwe bericht opnieuw gelezen.
    assert c.execute("SELECT motion FROM punt WHERE tst = 1791019100").fetchone()[0] == "automotive"
    assert c.execute("SELECT count(*) FROM bericht").fetchone()[0] == 2
    assert c.execute("SELECT naam FROM plek").fetchone()[0] == "Thuis", "de plekken moeten blijven"
    # Een plek uit de telefoontijd gaat buiten de actieve herkenning, bewaard in plek_historiek (opdracht v1.4).
    assert c.execute("SELECT actief, herkomst FROM plek WHERE naam = 'Thuis'").fetchone() == (0, "telefoontijd 9-9 tot 3-10-2026")
    assert c.execute("SELECT count(*) FROM plek_historiek WHERE naam = 'Thuis'").fetchone()[0] == 1
    c.close()


def test_upgrade_maakt_eerst_een_kopie_met_datum():
    pad = oude_database()
    _, _, kopie = schema.migreer(pad)
    assert kopie and os.path.exists(kopie), kopie
    assert os.path.basename(os.path.dirname(kopie)) == "backups"
    assert "schema0" in os.path.basename(kopie)
    c = sqlite3.connect(kopie)
    assert c.execute("SELECT count(*) FROM punt").fetchone()[0] == 2, "de kopie moet de oude toestand bevatten"
    assert c.execute("PRAGMA user_version").fetchone()[0] == 0
    c.close()


def test_upgrade_is_eenmalig_en_herhalen_verandert_niets():
    pad = oude_database()
    schema.migreer(pad)
    c = sqlite3.connect(pad)
    eerst = c.execute("SELECT * FROM punt ORDER BY tst").fetchall()
    c.close()
    assert schema.migreer(pad) == (schema.LAATSTE, schema.LAATSTE, None), "een tweede keer mag niets doen"
    c = sqlite3.connect(pad)
    assert c.execute("SELECT * FROM punt ORDER BY tst").fetchall() == eerst
    c.close()


def test_een_upgrade_die_breekt_laat_niets_half_achter():
    """Alles of niets: valt een stap om, dan staat de database zoals voordien."""
    pad = oude_database()
    echt = schema._v2

    def kapot(conn):
        echt(conn)
        raise RuntimeError("stroom weg midden in de upgrade")
    schema.MIGRATIES[1] = (2, kapot)
    try:
        try:
            schema.migreer(pad)
        except RuntimeError:
            pass
        else:
            raise AssertionError("de fout moest doorkomen")
    finally:
        schema.MIGRATIES[1] = (2, echt)
    c = sqlite3.connect(pad)
    # Alle stappen zitten in één transactie: ook schema 1 is teruggedraaid.
    assert c.execute("PRAGMA user_version").fetchone()[0] == 0, "een deel van de upgrade bleef staan"
    kol = [r[1] for r in c.execute("PRAGMA table_info(punt)")]
    assert "berichtsoort" not in kol and "bericht" not in [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master")], "een halve ombouw bleef staan"
    assert c.execute("SELECT count(*) FROM punt").fetchone()[0] == 2
    c.close()
    # En daarna lukt het gewoon.
    assert schema.migreer(pad)[1] == schema.LAATSTE


def test_een_punt_en_een_gebeurtenis_in_dezelfde_seconde_blijven_allebei():
    """03-10-2026: 'motor aan' zonder fix draagt de meettijd van het 'motor uit' ervoor;
    met de sleutel (bron, tst) verdween hij stil. Ook een zonegebeurtenis (GIN) in
    dezelfde seconde als een punt moet blijven."""
    pad = oude_database()
    schema.migreer(pad)
    c = sqlite3.connect(pad)
    for i, soort in enumerate(("VGF", "VGN", "GIN", "FRI", "STT", "STT")):
        c.execute("""INSERT INTO punt (tst, lat, lon, bron, berichtsoort, volgnr, bericht_id) VALUES (1791030000, 50.8,
                     4.7, 'auto', ?, 0, ?) ON CONFLICT(bericht_id, volgnr) DO NOTHING""", (soort, 9000 + i))
    c.commit()
    n = c.execute("SELECT count(*) FROM punt WHERE tst = 1791030000").fetchone()[0]
    assert n == 6, "twee statusmeldingen met dezelfde fix horen ook allebei te blijven (controle 05-10-2026)"
    c.close()


def test_toestelbericht_blijft_leesbaar_als_venster():
    """De handleiding van de tracker verwijst naar de tabel toestelbericht."""
    pad = oude_database()
    c = sqlite3.connect(pad)
    c.execute("INSERT INTO toestelbericht (ontvangen, bron, soort, kop, verzonden, ruw) VALUES "
              "(1791030000, 'auto', 'ALM', 'RESP', 1791030000, '+RESP:GTALM,8020090501,%s,,0,1,1,CFG,,"
              "20261003120000,0007$')" % IMEI)
    c.commit()
    c.close()
    schema.migreer(pad)
    c = sqlite3.connect(pad)
    assert schema.soort_van(c, "toestelbericht") == "view"
    rij = c.execute("SELECT soort, ruw FROM toestelbericht").fetchone()
    assert rij[0] == "ALM" and IMEI in rij[1], rij
    assert c.execute("SELECT count(*) FROM toestelbericht_schema1").fetchone()[0] == 1, "het origineel blijft bewaard"
    c.close()


def test_een_nieuwe_database_krijgt_meteen_de_laatste_vorm():
    pad = os.path.join(tempfile.mkdtemp(), "nieuw.db")
    v_voor, v_na, kopie = schema.migreer(pad)
    assert (v_voor, v_na, kopie) == (0, schema.LAATSTE, None)
    c = sqlite3.connect(pad)
    for tabel in ("punt", "bericht", "plek", "projectplek", "projectplek_override", "bezoekcorrectie",
                  "taakstatus", "adrescache", "adresbezoek"):
        assert schema.soort_van(c, tabel) == "table", tabel
    c.close()


if __name__ == "__main__":
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
