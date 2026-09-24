"""Grendels op de Locatiewacht: waar een afspraak plaatsvindt en hoe een plek heet.

Elk geval speelt een fout na die op 21 en 22-09-2026 in het dagboek stond. Bewust
nagebootste coördinaten en projectnummers: de echte meting bevat Mehdi's
thuisadres en hoort niet in een repository. Geen netwerk: Nominatim en de agenda
worden hier vervangen.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_locatie_wacht.py
"""
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import locatie_wacht as L  # noqa: E402

WERF = (50.7000, 4.6000)
ELDERS = (50.7300, 4.6400)        # ruim 4 km van de werf
REG = {"9145": {"adres": "Werfstraat 9, 3999 Proefdorp", "coord": WERF, "bron": "projectregister",
                "afspraken": 30, "map": True},
       "9146": {"adres": "Mapstraat 1, 3998 Mapdorp", "coord": None, "bron": "projectmap (A13)",
                "afspraken": 0, "map": True},
       "3999": {"adres": "Postcodestraat 1, 3999 Proefdorp", "coord": ELDERS, "bron": "projectregister",
                "afspraken": 1, "map": False}}
BRUSSEL = ZoneInfo("Europe/Brussels")


def tijd(u, m):
    return int(datetime(2026, 9, 22, u, m, tzinfo=BRUSSEL).timestamp())


class Coord:
    """Vervangt W.coord en onthoudt welke adressen omgezet moesten worden."""
    def __init__(self, uitkomst=None):
        self.gevraagd, self.uitkomst = [], uitkomst

    def __call__(self, adres, cache):
        self.gevraagd.append(adres)
        return self.uitkomst


def reg():
    return {k: dict(v) for k, v in REG.items()}


def test_projectnummer_gaat_voor_nominatim():
    """21-09-2026: 'WB 9145' met adres in een deelgemeente gaf 'adres niet gevonden',
    terwijl het projectregister de coördinaten al had."""
    L.W.coord = Coord()
    a = {"titel": "Mehdi: !! [HARC-KB] WB 9145 - wekelijks werfbezoek", "locatie": "Werfstraat 9, 3999 Deelgemeente"}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), reg(), {})
    assert (lat, lon) == WERF, herkomst
    assert "9145" in herkomst and "projectregister" in herkomst, herkomst
    assert not L.W.coord.gevraagd, "Nominatim gevraagd terwijl het projectregister het wist"


def test_zonder_adres_haalt_de_projectmap():
    """15-09-2026: '!! Mehdi: 2145 werfbezoek 1' stond zonder adres en werd niet getoetst."""
    L.W.coord = Coord([50.71, 4.61])
    a = {"titel": "!! Mehdi: 9146 werfbezoek 1", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), reg(), {})
    assert (lat, lon) == (50.71, 4.61), herkomst
    assert L.W.coord.gevraagd == ["Mapstraat 1, 3998 Mapdorp"], "het adres komt uit de projectmapnaam (A13)"


def test_postcode_is_geen_projectnummer():
    L.W.coord = Coord([50.72, 4.62])
    a = {"titel": "!! Mehdi: plaatsbezoek Kerkstraat 1, 3999 Proefdorp", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), reg(), {})
    assert (lat, lon) != ELDERS, "de postcode 3999 werd als projectnummer gelezen"


def test_stilstand_op_een_bouwplaats_krijgt_het_projectnummer():
    """22-09-2026: 15:48-16:56 op de werf van 2145 stond er als 'geen meting, 1,1 km'."""
    gegevens = {
        "punten": [{"tijd": datetime.fromtimestamp(tijd(15, 48), BRUSSEL).isoformat(),
                    "lat": WERF[0] + 0.0002, "lon": WERF[1], "acc": 16}],
        "indeling": [{"soort": "gat", "van": tijd(15, 48), "tot": tijd(16, 56), "minuten": 68, "meter": 1176}],
    }
    tekst, verblijven = L.dagboek("2026-09-22", gegevens, [], reg(), {})
    assert "bouwplaats 9145" in tekst, tekst
    assert len(verblijven) == 1 and verblijven[0]["bouwplaats"] == "9145" and verblijven[0].get("stilstand")
    # Een gat waarna het volgende punt ver weg ligt, is geen stilstand.
    gegevens["indeling"][0]["meter"] = L.STILSTAND_METER + 1
    _, verblijven = L.dagboek("2026-09-22", gegevens, [], reg(), {})
    assert not verblijven, "een gat met een lange rit erin werd een stilstand"


def test_bouwplaats_is_nooit_een_vaste_plek():
    """Een wekelijkse werf zou na vijf bezoeken als vaste plek uit de meldingen vallen."""
    cache = {f"{WERF[0]:.4f},{WERF[1]:.4f}": {"adres": "Werfstraat 9", "n": 40}}
    plek = L.benoem(WERF[0], WERF[1], [], reg(), cache)
    assert plek["bouwplaats"] == "9145" and not plek["vaste_plek"], plek


def test_afspraak_zonder_adres_op_de_werf_is_doorgegaan():
    """15-09-2026: het werfbezoek 07:00-09:00 zonder adres, ter plaatse 07:34-08:05."""
    L.W.coord = Coord()
    L.agenda.beschikbaar = lambda: True
    L.W.afspraken_dag = lambda dag: [
        {"titel": "!! Mehdi: 9145 werfbezoek 1", "start": "2026-09-22T07:00:00+02:00",
         "einde": "2026-09-22T09:00:00+02:00", "locatie": ""},
        {"titel": "Mehdi: [UNABO-PO] Iemand", "start": "2026-09-22T09:00:00+02:00",
         "einde": "2026-09-22T09:30:00+02:00", "locatie": "https://us06web.zoom.us/j/1"},
        {"titel": "🚗 Reistijd → Proefdorp", "start": "2026-09-22T06:30:00+02:00",
         "einde": "2026-09-22T07:00:00+02:00", "locatie": ""}]
    verblijf = {"soort": "bezoek", "stop": True, "van": tijd(7, 34), "tot": tijd(8, 5), "minuten": 31,
                "lat": WERF[0], "lon": WERF[1], "waar": "bouwplaats 9145", "bouwplaats": "9145"}
    # 15-09-2026, Kortenberg: de stilstand na het bezoek hoort bij dezelfde afspraak.
    erna = {"soort": "gat", "stilstand": True, "van": tijd(8, 5), "tot": tijd(8, 41), "minuten": 36,
            "lat": WERF[0], "lon": WERF[1], "waar": "bouwplaats 9145", "bouwplaats": "9145"}
    doorgegaan, niet_gezien, zonder_adres, overig = L.vergelijk_agenda("2026-09-22", [verblijf, erna], reg(), {})
    assert len(doorgegaan) == 1 and "07:34-08:41" in doorgegaan[0], doorgegaan
    assert not niet_gezien and not zonder_adres, (niet_gezien, zonder_adres)
    assert overig == 2, "online en reistijd horen niet bij de adresloze buitenafspraken"
    assert verblijf.get("afspraak") and erna.get("afspraak"), "een verblijf is niet aan de afspraak gekoppeld"


def test_trackeralarm_belt_niet_en_komt_niet_elk_uur_terug():
    """AGENTNORM v1.3: 'stil' in een signaaltitel laat De Bode bellen. Tot 24-09-2026
    heette dit alarm 'Tracker stil sinds N uur', met het uur in de sleutel."""
    bron = open(os.path.join(HIER, "locatie_wacht.py"), encoding="utf-8").read()
    titels = re.findall(r'"titel":\s*(f?"[^"]*")', bron)
    assert titels and not any("stil" in t.lower() for t in titels), titels
    assert not re.search(r'"uniek":\s*f"[^"]*%H', bron), "het uur staat in de sleutel van een signaal"


def test_gaat_door_de_ronde():
    """N12: de wacht gaat door de gedeelde ronde (werkwijze lezen, kennis melden)."""
    bron = open(os.path.join(HIER, "locatie_wacht.py"), encoding="utf-8").read()
    assert "ag.ronde(" in bron


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
