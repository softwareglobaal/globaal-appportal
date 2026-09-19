"""Grendels op de ontleder van @Track-berichten.

Elke regel hieronder is een **echt voorbeeldbericht uit de handleiding van de
fabrikant** (GV500CG @Track Air Interface Protocol v3.02 en GL300 v1.02), niet
zelf verzonnen. Breekt een van deze tests, dan leest de ontvanger de trackers
verkeerd en mag de build niet door.

Draaien: python3 locatie/test_atrack.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atrack  # noqa: E402

FRI = ("+RESP:GTFRI,8020090302,864696060004173,GV500CG,11985,10,1,1,0.0,0,118.5,"
       "117.129306,31.839197,20230808033438,0460,0001,DF5C,05FE6667,03,15,0,123.5,"
       "00123:04:44,,,,100,210000,,,,20230808033438,01B3$")
BUFF = ("+BUFF:GTFRI,8020090302,863286020684354,GV500CG,,10,1,1,0.0,0,0.5,121.392413,"
        "31.164143,20160804044602,0460,0000,1877,03A3,00,104.8,,,,100,210100,,,,"
        "20140804044611,2E78$")
VGN = ("+RESP:GTVGN,8020090302,135790246811220,gv500cg,00,2,1200,0,4.3,92,70.0,"
       "121.354335,31.222073,20230214013254,0460,0000,18d8,085BE2AE,01,1,12345:12:34,"
       "2000.0,20231214093254,11F0$")
VGF = ("+RESP:GTVGF,8020090302,866775050904846,gv500cg,00,2,33,0,0.0,0,83.4,117.129347,"
       "31.839286,20231212053622,0460,0000,550B,085BE2AE,01,1,12345:12:34,0.0,"
       "20231212053623,0116$")
BID = ("+RESP:GTBID,8020090302,867488060284402,GV500CG,1,2,00CA,780541295AF5,2935,-57,1,"
       "FDA50693A4E24FB1AFCFC6EB07647825,2A94,283B,00CA,1,0.0,0,47.0,117.129132,31.839405,"
       "20230613111241,0460,0001,DF5C,027A4F1F,01,12,20230613191242,08FF$")
GL300 = ("+RESP:GTFRI,1A0600,135790246811220,,0,0,1,1,4.3,92,70.0,121.354335,31.222073,"
         "20090214013254,0460,0000,18d8,6141,00,,20090214093254,11F0$")
ACK = "+ACK:GTHBD,8020090302,135790246811220,GV500CG,20100214093254,11F0$"
INF = ("+RESP:GTINF,8020090302,135790246811220,GV500CG,16,898600810906F8048812,16,0,1,"
       "12000,2,4.40,0,0,,,20230214013254,,,,,,,+0800,0,20230214093254,11F0$")


def test_positie_wordt_juist_gelezen():
    b = atrack.ontleed(FRI)
    assert b["soort"] == "FRI" and b["positie"]
    assert abs(b["lat"] - 31.839197) < 1e-6, b["lat"]
    assert abs(b["lon"] - 117.129306) < 1e-6, b["lon"]
    assert b["imei"] == "864696060004173"
    assert b["hdop"] == 1 and b["fix_geldig"]
    assert b["tst"] == 1691465678, b["tst"]          # 2023-08-08 03:34:38 UTC
    assert b["satellieten"] == 15, b["satellieten"]
    assert b["ruw"] == FRI


def test_meettijd_en_verzendtijd_zijn_twee_dingen():
    """Een nagestuurd bericht draagt zijn eigen, oude meetmoment."""
    b = atrack.ontleed(BUFF)
    assert b["gebufferd"], "een +BUFF-bericht moet als nagestuurd herkenbaar zijn"
    assert b["tst"] == 1470285962, b["tst"]          # 2016-08-04 04:46:02 UTC
    assert b["verzonden"] == 1407127571, b["verzonden"]
    assert b["tst"] != b["verzonden"]
    assert atrack.ontleed(FRI)["gebufferd"] is False


def test_hdop_nul_is_geen_geldige_meting():
    """19-09-2026: 0 betekent 'geen fix, oude positie herhaald', geen aanwezigheid."""
    kapot = FRI.replace(",1,1,0.0,0,118.5,", ",1,0,0.0,0,118.5,")
    b = atrack.ontleed(kapot)
    assert b["hdop"] == 0 and b["fix_geldig"] is False, b
    # En de waarde mag nergens als meters doorgaan.
    assert "acc" not in b and "nauwkeurigheid_m" not in b


def test_motor_aan_en_uit_zijn_aankomst_en_vertrek():
    aan, uit = atrack.ontleed(VGN), atrack.ontleed(VGF)
    assert aan["gebeurtenis"] == "motor aan" and aan["positie"]
    assert uit["gebeurtenis"] == "motor uit" and uit["positie"]
    assert uit["tst"] == 1702359382, uit["tst"]      # 2023-12-12 05:36:22 UTC
    assert abs(uit["lat"] - 31.839286) < 1e-6


def test_baken_bericht_houdt_zijn_positie():
    """Het baken zelf meet niets; de positie in dit bericht is die van de auto."""
    b = atrack.ontleed(BID)
    assert b["soort"] == "BID" and b["positie"]
    assert abs(b["lat"] - 31.839405) < 1e-6, b["lat"]
    assert b["gebeurtenis"] == "baken gezien"


def test_oudere_protocolversie_wordt_ook_gelezen():
    """Het risico uit het keuzedocument: velden verschuiven per versie."""
    b = atrack.ontleed(GL300)
    assert b["positie"] and b["protocol"] == "1A0600"
    assert abs(b["lat"] - 31.222073) < 1e-6 and abs(b["lon"] - 121.354335) < 1e-6
    assert b["tst"] == 1234575174, b["tst"]          # 2009-02-14 01:32:54 UTC


def test_berichten_zonder_positie_worden_niet_als_meting_gelezen():
    for regel in (ACK, INF):
        b = atrack.ontleed(regel)
        assert b is not None and b["positie"] is False, regel
    assert atrack.ontleed("rommel") is None
    assert atrack.ontleed("") is None


def test_tijd_wordt_als_utc_gelezen_ongeacht_de_klok_van_de_server():
    """14-09-2026 bij de telefoon: de server draait in UTC, het dagboek liep twee
    uur voor. Hier mag de tijdzone van de server nooit meespelen."""
    import time
    vorige = os.environ.get("TZ")
    try:
        for zone in ("UTC", "Europe/Brussels", "America/New_York"):
            os.environ["TZ"] = zone
            time.tzset()
            assert atrack.ontleed(FRI)["tst"] == 1691465678, zone
    finally:
        if vorige is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = vorige
        time.tzset()


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
