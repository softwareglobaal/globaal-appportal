"""
Grendels op de dagindeling.

Elk geval hier speelt een fout na die in de echte meting is voorgekomen. Wie de
indeling aanpast en een van deze tests breekt, brengt die fout terug. Bewust
nagebootste coordinaten: de echte meting bevat Mehdi's thuisadres en hoort niet
in een repository.

Draaien, zonder pytest:   python3 locatie/test_dagindeling.py
Of met pytest:            pytest locatie/test_dagindeling.py
"""
import os
import sys
import time

os.environ.setdefault("LOCATIE_DB", "/tmp/test-dagindeling.db")
os.environ["LOCATIE_VOERTUIG_WIFI"] = "AUTO-ROUTER"
os.environ["TZ"] = "Europe/Brussels"
time.tzset()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402

THUIS = (50.8000, 4.7000)
WERF = (51.0500, 4.3700)        # ruim 30 km van THUIS
PLEKKEN = [{"naam": "Thuis", "lat": THUIS[0], "lon": THUIS[1], "straal": 150,
            "wifi": "THUIS-WIFI", "soort": "thuis", "dossier": None}]
T0 = 1789000000


def punt(minuut, plaats, motion=None, ssid=None, acc=5, dlat=0.0, dlon=0.0):
    return {"tst": T0 + int(minuut * 60), "lat": plaats[0] + dlat, "lon": plaats[1] + dlon,
            "acc": acc, "motion": motion, "ssid": ssid}


def rit(van_min, tot_min, a, b, stap=1, **kw):
    n = max(1, int((tot_min - van_min) / stap))
    return [punt(van_min + i * stap, (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n), **kw)
            for i in range(n + 1)]


def soorten(ind):
    return [s["soort"] for s in ind]


def test_auto_wifi_is_geen_gebouw():
    """9-9-2026: dezelfde wifi in een rijdende auto werd als gebouw gelezen."""
    punten = rit(0, 20, THUIS, WERF, stap=2, ssid="AUTO-ROUTER")
    ind = app.dagindeling_zuiver(punten, PLEKKEN)
    assert "bezoek" not in soorten(ind), ind


def test_gat_plakt_geen_plekken_aan_elkaar():
    """12-09-2026: Willebroek en Kessel-Lo werden over vijf uur stilte een bezoek."""
    punten = ([punt(m, WERF, "stationary") for m in range(0, 61, 3)]
              + [punt(m, THUIS, "stationary", ssid="THUIS-WIFI") for m in range(360, 421, 3)])
    ind = app.dagindeling_zuiver(punten, PLEKKEN)
    assert soorten(ind) == ["bezoek", "gat", "bezoek"], soorten(ind)
    thuis = ind[2]
    assert thuis["plek"] == "Thuis"
    assert app.afstand(thuis["lat"], thuis["lon"], *THUIS) < 150, "Thuis ligt niet thuis"
    assert ind[0]["plek"] is None, "de werf mag niet Thuis heten"
    assert ind[1]["meter"] > 20000


def test_rondlopen_op_werf_met_fietsruis_blijft_een_bezoek():
    """12-09-2026: drieenhalf uur op een werf viel uiteen door stappen en een fietspunt."""
    punten = []
    for m in range(0, 211, 3):
        if 60 <= m <= 70:
            punten.append(punt(m, WERF, "walking", dlat=0.0018))      # uitstap van ~200 m
        elif m == 120:
            punten.append(punt(m, WERF, "cycling", dlon=0.0001))      # losse sensorruis
        else:
            punten.append(punt(m, WERF, "walking" if m % 2 else "stationary",
                               dlat=0.00005 * (m % 5), dlon=0.00005 * (m % 3)))
    ind = app.dagindeling_zuiver(punten, PLEKKEN)
    bezoeken = [s for s in ind if s["soort"] == "bezoek"]
    assert len(bezoeken) == 1, soorten(ind)
    assert bezoeken[0]["minuten"] >= 200


def test_aankomst_en_stilte_horen_bij_het_bezoek():
    """12-09-2026: uitgestapt om 10:39, 111 min stilte, volgende punt op dezelfde plek."""
    punten = (rit(0, 30, THUIS, WERF, stap=2, motion="automotive")
              + [punt(141 + m, WERF, "stationary") for m in range(0, 61, 3)])
    ind = app.dagindeling_zuiver(punten, PLEKKEN)
    bezoek = [s for s in ind if s["soort"] == "bezoek"][0]
    assert bezoek["van"] <= T0 + 30 * 60 + 60, "het bezoek begint pas na de stilte"
    assert bezoek["langste_stilte"] >= 100
    assert "gat" not in soorten(ind)


def test_losse_gps_sprong_breekt_geen_verblijf():
    """11-09-2026: een enkel punt 1,4 km verderop brak een avond thuis in tweeen."""
    punten = [punt(m, THUIS, "stationary", ssid="THUIS-WIFI") for m in range(0, 121, 3)]
    punten.insert(20, punt(59.5, THUIS, None, dlat=0.0126))
    ind = app.dagindeling_zuiver(punten, PLEKKEN)
    assert soorten(ind) == ["bezoek"], soorten(ind)


def test_rit_krijgt_de_dominante_wijze():
    """12-09-2026: een autorit met wat stappen werd 'auto en te voet', 101 km te voet."""
    punten = rit(0, 40, THUIS, WERF, stap=1, motion="automotive")
    punten[5]["motion"] = "walking"
    punten[6]["motion"] = "walking"
    ind = app.dagindeling_zuiver(punten, PLEKKEN)
    ritten = [s for s in ind if s["soort"] == "verplaatsing"]
    assert ritten and all(r["wijze"] == "automotive" for r in ritten), ritten


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
