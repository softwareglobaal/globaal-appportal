"""Grendels op De Locatiewacht (werkwijze v3, 04-10-2026).

Elk geval speelt een fout of een afspraak na: de plek van een afspraak (21 en
22-09-2026), het valse alarm over de telefoon terwijl de auto geparkeerd stond
(4-10-2026), de startgrens van de meetreeks, hetzelfde projectnummer bij twee
firma's, en een herzien dagboek dat de vorige versie niet mag overschrijven.

Nagebootste coördinaten, projectnummers en tegelantwoorden; geen netwerk, geen bord.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_locatie_wacht.py
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import locatie_wacht as L  # noqa: E402

WERF = (50.7000, 4.6000)
ELDERS = (50.7300, 4.6400)
BRUSSEL = ZoneInfo("Europe/Brussels")
# Verzonnen dossiers met geldige JJNN uit 2026. De vroegere 91xx/92xx-fiches
# vielen buiten de H-A-jaargrens en testten daardoor niet meer de locatiekoppeling.
PER_SLEUTEL = {
    "HARC:2645": {"adres": "Werfstraat 9, 3999 Proefdorp", "coord": WERF, "bron": "ha-projecten",
                  "link": "https://ha-projecten.globaal.be/project/2645", "firma": "HARC", "nummer": "2645"},
    "HARC:2646": {"adres": "Mapstraat 1, 3998 Mapdorp", "coord": None, "bron": "projectmap", "link": None,
                  "firma": "HARC", "nummer": "2646"},
    "HARC:3999": {"adres": "Postcodestraat 1, 3999 Proefdorp", "coord": ELDERS, "bron": "projectmap",
                  "link": None, "firma": "HARC", "nummer": "3999"},
    "HARC:2620": {"adres": "A 1, 3999 Proefdorp", "coord": (50.71, 4.61), "bron": "ha-projecten", "link": None,
                  "firma": "HARC", "nummer": "2620"},
    "UNAB:2620": {"adres": "B 2, 2000 Antwerpen", "coord": (51.2, 4.4), "bron": "unabo", "link": None,
                  "firma": "UNAB", "nummer": "2620"},
}
PER_NUMMER = {}
for k, v in PER_SLEUTEL.items():
    PER_NUMMER.setdefault(v["nummer"], []).append(k)
INDEX = (PER_SLEUTEL, PER_NUMMER)


def tijd(u, m):
    return int(datetime(2026, 10, 5, u, m, tzinfo=BRUSSEL).timestamp())


class Coord:
    """Vervangt W.coord en onthoudt welke adressen omgezet moesten worden."""
    def __init__(self, uitkomst=None):
        self.gevraagd, self.uitkomst = [], uitkomst

    def __call__(self, adres, cache):
        self.gevraagd.append(adres)
        return self.uitkomst


def test_firma_en_projectnummer_gaan_voor_nominatim():
    """21-09-2026: 'WB 2145' met een adres in een deelgemeente gaf 'adres niet gevonden'."""
    L.W.coord = Coord()
    a = {"titel": "Mehdi: !! [HARC-KB] WB 2645 - wekelijks werfbezoek", "locatie": "Werfstraat 9, 3999 Deelgemeente"}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == WERF, herkomst
    assert "HARC 2645" in herkomst, herkomst
    assert not L.W.coord.gevraagd, "Nominatim gevraagd terwijl de projectplek het wist"


def test_zonder_coordinaat_het_adres_van_de_projectbron():
    L.W.coord = Coord([50.71, 4.61])
    a = {"titel": "!! Mehdi: 2646 werfbezoek 1", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == (50.71, 4.61), herkomst
    assert L.W.coord.gevraagd == ["Mapstraat 1, 3998 Mapdorp"]


def test_postcode_is_geen_projectnummer():
    L.W.coord = Coord([50.72, 4.62])
    a = {"titel": "!! Mehdi: plaatsbezoek Kerkstraat 1, 3999 Proefdorp", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) != ELDERS, "de postcode 3999 werd als projectnummer gelezen"


def test_hetzelfde_nummer_bij_twee_firmas_wordt_niet_gegokt():
    L.W.coord = Coord()
    a = {"titel": "!! Mehdi: 2620 werfbezoek", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert lat is None and "meer firma" in herkomst, herkomst
    a = {"titel": "!! Mehdi: [HARC-KB] WB 2620", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == (50.71, 4.61) and "HARC 2620" in herkomst, herkomst
    a = {"titel": "!! Mehdi: [UNABO-KB] BS 2620", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == (51.2, 4.4) and "UNAB 2620" in herkomst, herkomst


def test_een_onmogelijk_h_a_nummer_wordt_niet_uit_de_projectbron_gegokt():
    """Een projectplek maakt 9145 niet alsnog geldig binnen de H-A-jaargrens."""
    L.W.coord = Coord()
    a = {"titel": "!! Mehdi: [HARC-KB] WB 9145 werfbezoek", "locatie": ""}
    plek = dict(PER_SLEUTEL["HARC:2645"], nummer="9145")
    index = ({"HARC:9145": plek}, {"9145": ["HARC:9145"]})
    with patch.object(L.W.nummerlezer, "jaar_nu_brussel", return_value=2026):
        info = L.W.lees_titel(a["titel"])
        lat, lon, herkomst = L.plek_van_afspraak(a, info, index, {})
    assert info["firma"] == "HARC" and not info["nummer"], info
    assert lat is None and lon is None and "geen bekend projectnummer" in herkomst, herkomst
    assert not L.W.coord.gevraagd, "een ongeldige dossiercode werd toch gegeocodeerd"


STADSKANTOOR = (50.7500, 4.7000)


def test_een_ander_adres_in_de_titel_gaat_voor_op_de_projectplek():
    """26-10-2026: een vooroverleg op het stadskantoor over een project elders werd aan de werf getoetst."""
    L.W.coord = Coord(list(STADSKANTOOR))
    a = {"titel": "!! Mehdi: [HARC] 2645 Proefstad vooroverleg (stadskantoor), Stadskantoor, Proefplein 1, 3990 Proefstad",
         "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == STADSKANTOOR, herkomst
    assert "in de titel" in herkomst and "niet de projectplek HARC 2645" in herkomst, herkomst
    assert L.W.coord.gevraagd == ["Proefplein 1, 3990 Proefstad"], L.W.coord.gevraagd


def test_een_ander_adres_in_de_agenda_gaat_voor_op_de_projectplek():
    """Meting 26-10-2026: 'Gesprek met de gemeente' stond met het adres van het gemeentehuis alleen in het locatieveld."""
    L.W.coord = Coord(list(STADSKANTOOR))
    a = {"titel": "!! Mehdi: 2645 Gesprek met de gemeente", "locatie": "Gemeenteplein 3, 3999 Proefdorp, België"}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == STADSKANTOOR and "in de agenda" in herkomst, herkomst


def test_het_locatieveld_gaat_voor_op_de_titel():
    """Driehoeksoverleg 26-10-2026, X3: het locatieveld is voor de plek bedoeld; de titel kan het projectadres dragen."""
    L.W.coord = Coord(list(STADSKANTOOR))
    a = {"titel": "!! Mehdi: [HARC-KB] 2645 - Proefklant, Werfstraat 9, 3999 Proefdorp",
         "locatie": "Stadskantoor, Proefplein 1, 3990 Proefstad"}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == STADSKANTOOR and "in de agenda" in herkomst, herkomst
    assert L.W.coord.gevraagd == ["Proefplein 1, 3990 Proefstad"], L.W.coord.gevraagd


def test_het_projectadres_in_de_titel_of_de_agenda_blijft_de_projectplek():
    """De Agendawacht zet het projectadres achteraan de titel; 'Werf Straat' is 'Werfstraat' zonder spatie."""
    L.W.coord = Coord()
    for titel, loc in (("!! Mehdi: [HARC-KB] 2645 - Proefklant, Werfstraat 9, 3999 Proefdorp", ""),
                       ("!! Mehdi: 2645 werfbezoek 4", "Werf Straat 9, 3999 Proefdorp, België"),
                       ("!! Mehdi: 2645 werfbezoek 5", "Online: https://us06web.zoom.us/j/1")):
        a = {"titel": titel, "locatie": loc}
        lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(titel), INDEX, {})
        assert (lat, lon) == WERF and "projectplek HARC 2645" in herkomst, (titel, herkomst)
    assert not L.W.coord.gevraagd, "de kaartdienst gevraagd voor de werf zelf"


def test_een_tikfout_beslist_de_afstand_niet_de_tekst():
    """X4 en K4: een bijna gelijke straat kan een andere straat zijn; binnen de straal blijft het de werf."""
    a = {"titel": "!! Mehdi: opmeting 2645", "locatie": "Werfstrat 9, 3999 Proefdorp"}
    L.W.coord = Coord([WERF[0] + 0.001, WERF[1]])
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == WERF and "projectplek HARC 2645" in herkomst, herkomst
    assert L.W.coord.gevraagd == ["Werfstrat 9, 3999 Proefdorp"], L.W.coord.gevraagd
    L.W.coord = Coord([WERF[0] + 0.01, WERF[1]])
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == (WERF[0] + 0.01, WERF[1]) and "in de agenda" in herkomst, herkomst


def test_een_ander_adres_binnen_de_straal_blijft_de_projectplek():
    """Een tikfout in de postcode van de projectbron: de kaartdienst legt het adres op de werf."""
    L.W.coord = Coord([WERF[0] + 0.001, WERF[1]])
    a = {"titel": "!! Mehdi: 2645 werfbezoek", "locatie": "Werfstraat 9, 3909 Proefdorp"}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == WERF and "projectplek HARC 2645" in herkomst, herkomst


def test_een_onvindbaar_adres_geeft_geen_plek_in_plaats_van_de_werf():
    a = {"titel": "!! Mehdi: [HARC] 2645 vooroverleg, Stadskantoor, Proefplein 1, 3990 Proefstad", "locatie": ""}
    L.W.coord = Coord(None)
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert lat is None and "niet gevonden: Proefplein 1, 3990 Proefstad" in herkomst, herkomst
    L.W.coord = Coord(L.W.KAARTDIENST_STORING)
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert lat is None and "kaartdienst onbereikbaar" in herkomst, herkomst


def test_een_adres_in_de_titel_zonder_project_wordt_getoetst():
    """Meting 26-10-2026: twintig buitenafspraken noemden het adres alleen in de titel en kregen 'geen adres'."""
    L.W.coord = Coord([50.76, 4.71])
    a = {"titel": "!! Mehdi: Korte Proefstraat 2, 3990 Proefstad Scanning", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == (50.76, 4.71) and "in de titel" in herkomst, herkomst
    assert L.W.coord.gevraagd == ["Korte Proefstraat 2, 3990 Proefstad"], "wat na de gemeente staat, hoort er niet bij"


def test_het_projectnummer_en_vrije_tekst_zijn_geen_adres():
    """'2645, 3990 Proefstad' is geen huisnummer, ook niet naast een tweede nummer (K5) of als bekend projectnummer
    zonder firma; 'Gemeentehuis Proefdorp' zonder straat blijft de projectplek."""
    L.W.coord = Coord(list(STADSKANTOOR))
    for titel, loc in (("!! Mehdi: [HARC-KB] VO 2645, 3990 Proefstad", ""),
                       ("!! Mehdi: [HARC-KB] VO 2645 en 2646, 3990 Proefstad", ""),
                       ("!! Mehdi: [HARC-KB] 2645 bespreking Proefklant 2646, 3990 Proefstad", ""),
                       ("Mehdi: !! [HARC-KB] 2645 Gemeentehuis Proefdorp", "Gemeentehuis Proefdorp")):
        a = {"titel": titel, "locatie": loc}
        lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(titel), INDEX, {})
        assert (lat, lon) == WERF, (titel, herkomst)
    assert not L.W.coord.gevraagd, L.W.coord.gevraagd
    assert L.adres_in("!! Mehdi: plaatsbezoek Kerkstraat 1, 3999 Proefdorp")["tekst"] == "Kerkstraat 1, 3999 Proefdorp"
    assert L.adres_in("Proefstraat 10.4, 2999 Proefdorp")["nr"] == "10.4"


def test_zelfde_adres_vergelijkt_het_volledige_huisnummer():
    """Codex, 26-10-2026: een ander busnummer of een ander deel van het huisnummer is een andere plek."""
    werf = L.adres_in("Werfstraat 12, 3999 Proefdorp")
    for links, rechts, zelfde in (("12 bus 2", "12 bus 3", False), ("12-14", "12-16", False), ("10.4", "10.5", False),
                                  ("10.4", "104", False), ("12A", "12a", True), ("12 Bus 2", "12 bus 2", True)):
        a, b = (L.adres_in(f"Werfstraat {x}, 3999 Proefdorp") for x in (links, rechts))
        assert L.zelfde_adres(a, b) is zelfde, (links, rechts)
    assert not L.zelfde_adres(L.adres_in("Werfstraat 12 bus 2, 3999 Proefdorp"), werf)


def test_de_adreslezer_leest_bus_en_lidwoord_ongeacht_hoofdletters():
    for tekst, verwacht in (("Werfstraat 12 Bus 2, 3999 Proefdorp", ("Werfstraat", "12 Bus 2", "3999")),
                            ("Proefdijk 5, 8999 de Proefhaven, België", ("Proefdijk", "5", "8999")),
                            ("Proeflaan 12-14, 2999 Sint-Proef-Waver", ("Proeflaan", "12-14", "2999"))):
        a = L.adres_in(tekst)
        assert (a["straat"], a["nr"], a["pc"]) == verwacht, (tekst, a)
    assert L.adres_in("Proefdijk 5, 8999 de Proefhaven, België")["tekst"] == "Proefdijk 5, 8999 de Proefhaven"
    assert L.adres_in("Proeflaan 12-14, 2999 Sint-Proef-Waver")["tekst"].endswith("2999 Sint-Proef-Waver")


def test_bij_twee_adressen_telt_het_afwijkende_en_bij_twijfel_geen_oordeel():
    """Codex, 26-10-2026: eerst het overlegadres, dan het werfadres; de werf is dan niet de plek. Twee andere plekken
    dan de werf: niet eenduidig, geen oordeel."""
    L.W.coord = Coord(list(STADSKANTOOR))
    a = {"titel": "!! Mehdi: [HARC] 2645 vooroverleg, Proefplein 1, 3990 Proefstad, over Werfstraat 9, 3999 Proefdorp",
         "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == STADSKANTOOR and "Proefplein 1" in herkomst, herkomst
    assert L.W.coord.gevraagd == ["Proefplein 1, 3990 Proefstad"], "de werf zelf hoeft niet op de kaart"
    plekken = iter([[50.75, 4.70], [50.80, 4.80]])
    L.W.coord = lambda adres, cache: next(plekken)
    a = {"titel": "!! Mehdi: [HARC] 2645 rondgang, Proefplein 1, 3990 Proefstad en Markt 2, 3991 Proefgem", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert lat is None and "niet eenduidig" in herkomst, herkomst


def test_een_storing_blijft_zichtbaar_ook_bij_een_vrij_adres():
    """Codex, 26-10-2026: ook de oude route met een vrij adres in de agenda zegt dat de kaartdienst onbereikbaar was."""
    L.W.coord = Coord(L.W.KAARTDIENST_STORING)
    a = {"titel": "!! Mehdi: rondleiding", "locatie": "Proefzaal Proefdorp"}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert lat is None and "kaartdienst onbereikbaar" in herkomst and "Proefzaal" in herkomst, herkomst
    L.W.coord = Coord(None)
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert lat is None and herkomst == "adres niet gevonden: Proefzaal Proefdorp", herkomst


def test_een_afgesloten_projectnummer_is_ook_geen_huisnummer():
    """Codex, 26-10-2026: de grendel kent ook de projecten die niet meer actief zijn."""
    echt_haal, bekend = L.haal, set(L.BEKENDE_NUMMERS)
    L.haal = lambda pad: {"projectplekken": [{"sleutel": "HARC:2699", "nummer": "2699", "actief": False}], "dekking": {}}
    try:
        L.projectindex()
        assert "2699" in L.BEKENDE_NUMMERS
        L.W.coord = Coord(list(STADSKANTOOR))
        a = {"titel": "!! Mehdi: [HARC-KB] 2645 bespreking Proefklant 2699, 3990 Proefstad", "locatie": ""}
        lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
        assert (lat, lon) == WERF and not L.W.coord.gevraagd, herkomst
        # Codex ronde 2: de volgende index vervangt de nummers; een verdwenen nummer verbergt geen adres meer.
        L.haal = lambda pad: {"projectplekken": [{"sleutel": "HARC:2698", "nummer": "2698", "actief": False}], "dekking": {}}
        L.projectindex()
        assert L.BEKENDE_NUMMERS == {"2698"}, L.BEKENDE_NUMMERS
        lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
        assert (lat, lon) == STADSKANTOOR, herkomst
    finally:
        L.haal = echt_haal
        L.BEKENDE_NUMMERS.clear()
        L.BEKENDE_NUMMERS.update(bekend)


def test_een_overleg_op_het_stadskantoor_is_doorgegaan_en_de_plek_gaat_naar_de_dagbundelaar():
    L.W.coord = Coord(list(STADSKANTOOR))
    L.agenda.beschikbaar = lambda: True
    afspraak = {"id": "ov1", "titel": "!! Mehdi: [HARC] 2645 vooroverleg, Stadskantoor, Proefplein 1, 3990 Proefstad",
                "start": "2026-10-05T10:00:00+02:00", "einde": "2026-10-05T11:00:00+02:00",
                "locatie": "Stadskantoor, Proefplein 1, 3990 Proefstad"}
    bezoek = {"soort": "bezoek", "van": tijd(9, 52), "tot": tijd(11, 8), "minuten": 76, "lat": STADSKANTOOR[0],
              "lon": STADSKANTOOR[1], "herkenning": {"zekerheid": "geen"}}
    verblijven = L.verblijven_van(dagboek(bezoek))
    per_id = {}
    doorgegaan, niet_gezien, zonder_adres, overig = L.vergelijk_agenda("2026-10-05", verblijven, INDEX, {},
                                                                       per_id=per_id, afspraken=[afspraak])
    assert len(doorgegaan) == 1 and not niet_gezien and not zonder_adres, (doorgegaan, niet_gezien, zonder_adres)
    assert per_id["ov1"]["uitkomst"] == "doorgegaan" and (per_id["ov1"]["lat"], per_id["ov1"]["lon"]) == STADSKANTOOR


def test_een_adres_alleen_in_de_titel_maakt_een_afspraak_toetsbaar_maar_niet_online():
    """X5: zonder !! en zonder locatieveld telt een volledig adres in de titel als fysiek; een online gesprek niet."""
    L.W.coord = Coord(list(STADSKANTOOR))
    titel = "Mehdi: [HARC-IN] 2645 overleg, Proefplein 1, 3990 Proefstad"
    afspraken = [{"id": "t1", "titel": titel, "start": "2026-10-05T10:00:00+02:00",
                  "einde": "2026-10-05T11:00:00+02:00", "locatie": ""},
                 {"id": "t2", "titel": titel, "start": "2026-10-05T14:00:00+02:00",
                  "einde": "2026-10-05T15:00:00+02:00", "locatie": "https://us06web.zoom.us/j/1"}]
    per_id = {}
    doorgegaan, niet_gezien, zonder_adres, overig = L.vergelijk_agenda("2026-10-05", [], INDEX, {},
                                                                       per_id=per_id, afspraken=afspraken)
    assert per_id["t1"]["uitkomst"] == "niet_gezien" and (per_id["t1"]["lat"], per_id["t1"]["lon"]) == STADSKANTOOR
    assert "t2" not in per_id and overig == 1, (per_id, overig)


def dagboek(*verblijven):
    return {"status": "afgesloten", "markdown": "# Locatielogboek proef\n",
            "sporen": {"auto": {"rol": "auto", "label": "Tracker in de auto", "indeling": list(verblijven)}}}


def test_afspraak_op_de_werf_is_doorgegaan_met_de_auto_ter_plaatse():
    """15-09-2026: werfbezoek zonder adres, ter plaatse 07:34-08:05; aankomen en parkeren horen samen."""
    L.W.coord = Coord()
    L.agenda.beschikbaar = lambda: True
    L.W.afspraken_dag = lambda dag: [
        {"titel": "!! Mehdi: [HARC-KB] WB 2645 werfbezoek 1", "start": "2026-10-05T07:00:00+02:00",
         "einde": "2026-10-05T09:00:00+02:00", "locatie": ""},
        {"titel": "Mehdi: [UNABO-PO] Iemand", "start": "2026-10-05T09:00:00+02:00",
         "einde": "2026-10-05T09:30:00+02:00", "locatie": "https://us06web.zoom.us/j/1"},
        {"titel": "🚗 Reistijd → Proefdorp", "start": "2026-10-05T06:30:00+02:00",
         "einde": "2026-10-05T07:00:00+02:00", "locatie": ""}]
    project = {"sleutel": "HARC:2645", "firma": "HARC", "nummer": "2645", "link": PER_SLEUTEL["HARC:2645"]["link"]}
    aankomst = {"soort": "bezoek", "van": tijd(7, 34), "tot": tijd(8, 5), "minuten": 31, "lat": WERF[0],
                "lon": WERF[1], "herkenning": {"zekerheid": "waarschijnlijk", "project": project}}
    geparkeerd = dict(aankomst, van=tijd(8, 5), tot=tijd(8, 41), minuten=36, parkeren=True)
    verblijven = L.verblijven_van(dagboek(aankomst, geparkeerd))
    doorgegaan, niet_gezien, zonder_adres, overig = L.vergelijk_agenda("2026-10-05", verblijven, INDEX, {})
    assert len(doorgegaan) == 1 and "07:34-08:41" in doorgegaan[0] and "auto ter plaatse" in doorgegaan[0], doorgegaan
    assert not niet_gezien and not zonder_adres and overig == 2, (niet_gezien, zonder_adres, overig)
    assert all(v.get("afspraak") for v in verblijven)


def test_onzekere_herkenning_blijft_een_kandidatenlijst():
    kand = [{"sleutel": "HARC:2645", "firma": "HARC", "nummer": "2645"},
            {"sleutel": "HARC:2646", "firma": "HARC", "nummer": "2646"}]
    v = L.verblijven_van(dagboek({"soort": "bezoek", "van": tijd(10, 0), "tot": tijd(11, 0), "minuten": 60,
                                  "lat": WERF[0], "lon": WERF[1],
                                  "herkenning": {"zekerheid": "onzeker", "project": None, "kandidaten": kand}}))[0]
    assert v["project"] is None and "een van: HARC 2645, HARC 2646" == v["waar"], v["waar"]


def test_geen_dag_voor_de_startgrens():
    """Opdracht v1.2: oude bewegingsdata wordt nergens opgevraagd of herberekend."""
    try:
        L.maak("2026-10-02")
    except ValueError as e:
        assert "2026-10-03" in str(e)
    else:
        raise AssertionError("een dag voor de grens werd opgevraagd")
    L.STAND = os.path.join(tempfile.mkdtemp(), "stand.json")
    assert L.te_doen("2026-10-05") == ["2026-10-03", "2026-10-04", "2026-10-05"]
    json.dump({"afgesloten_tot": "2026-10-04"}, open(L.STAND, "w"))
    assert L.te_doen("2026-10-06") == ["2026-10-05", "2026-10-06"], "een gemiste avond wordt ingehaald"
    L.MAP = os.path.dirname(L.STAND)
    assert L.stand_bijwerken(["2026-10-05"]) == "2026-10-05"
    assert L.stand_bijwerken(["2026-10-07"]) == "2026-10-05", "een gat in de afgesloten dagen stopt de stand"


def test_een_herzien_dagboek_bewaart_de_vorige_versie():
    pad = os.path.join(tempfile.mkdtemp(), "dagen", "2026-10-05.md")
    assert L.schrijf_met_revisie(pad, "eerste\n") == "nieuw"
    assert L.schrijf_met_revisie(pad, "eerste\n") == "gelijk"
    assert L.schrijf_met_revisie(pad, "tweede\n") == "herzien"
    rev = os.listdir(os.path.join(os.path.dirname(pad), "revisies"))
    assert len(rev) == 1 and open(os.path.join(os.path.dirname(pad), "revisies", rev[0])).read() == "eerste\n"
    assert open(pad).read() == "tweede\n"


class Bord:
    def __init__(self):
        self.klaar, self.hart = [], []

    def klaarzet(self, items):
        self.klaar += items
        return {"nieuw": len(items)}

    def hartslag(self, status, **kw):
        self.hart.append((status, kw))

    def log(self, *a, **k):
        pass

    def log_verstuur(self):
        pass


def test_geparkeerd_geeft_geen_alarm_en_de_telefoon_nooit():
    """4-10-2026: de auto stond de hele dag geparkeerd en elke twee uur kwam 'tracker zwijgt,
    kijk de OwnTracks-app na'."""
    echt_ag, echt_nu, echt_haal, echt_taak = L.ag, L.nu, L.haal, L.taak_melden
    L.ag, L.taak_melden = Bord(), (lambda *a, **k: None)
    L.nu = lambda: datetime(2026, 10, 5, 14, 5, tzinfo=BRUSSEL)
    try:
        L.haal = lambda pad: {"bronnen": [
            {"bron": "auto", "label": "Tracker in de auto", "status": "actief", "toestand": "geparkeerd", "alarm": None},
            {"bron": "iphone", "label": "Telefoon (OwnTracks)", "status": "uit_gebruik", "toestand": "uit gebruik",
             "alarm": None}], "alarmen": []}
        L.controle()
        assert not L.ag.klaar and L.ag.hart[-1][0] == "waakt", (L.ag.klaar, L.ag.hart)
        L.haal = lambda pad: {"bronnen": [], "alarmen": [{"titel": "Locatietracker valt weg zonder motor uit",
                                                          "tekst": "...", "sleutel": "locatie-wegval-auto"}]}
        L.controle()
        assert L.ag.klaar and L.ag.klaar[0]["uniek"] == "locatie-wegval-auto:2026-10-05", L.ag.klaar
        assert L.ag.hart[-1][0] == "fout"
    finally:
        L.ag, L.nu, L.haal, L.taak_melden = echt_ag, echt_nu, echt_haal, echt_taak


def test_geen_telefoon_en_geen_stil_in_wat_de_wacht_meldt():
    """AGENTNORM v1.3: 'stil' in een signaaltitel laat De Bode bellen. En de bron is de auto."""
    bron = open(os.path.join(HIER, "locatie_wacht.py"), encoding="utf-8").read()
    titels = re.findall(r'"titel":\s*(f?"[^"]*")', bron)
    assert titels and not any("stil" in t.lower() for t in titels), titels
    assert not re.search(r'"uniek":\s*f"[^"]*%H', bron), "het uur staat in de sleutel van een signaal"
    assert "OwnTracks-app" not in bron and "Kijk de OwnTracks" not in bron
    code = bron.split('"""', 2)[2]
    assert "werkwijze/projecten.json\")" not in code and '"projecten.json"' not in code, \
        "de wacht leest nog het losse agendaregister"
    # De server draait in UTC: nooit de klok van de server zonder zone.
    assert "datetime.now()" not in bron
    assert re.search(r"fromtimestamp\(int\(epoch\),\s*BRUSSEL\)", bron), "uur() rekent niet naar Belgische tijd"


def test_de_klokgrendel_houdt_het_verkeerde_utc_uur_tegen():
    gebeurd = []
    echt_om, echt_venster, echt_maak = L.OM, L.BB.binnen_venster, L.maak
    L.OM, L.CONTROLE = "21:30", False
    L.BB.binnen_venster = lambda hhmm: False
    L.maak = lambda dag: gebeurd.append(dag)
    try:
        L.main()
        assert not gebeurd, "buiten het Belgische uur mag de wacht niets doen"
    finally:
        L.OM, L.BB.binnen_venster, L.maak = echt_om, echt_venster, echt_maak


def test_gaat_door_de_ronde():
    """N12: de wacht gaat door de gedeelde ronde (werkwijze lezen, kennis melden)."""
    bron = open(os.path.join(HIER, "locatie_wacht.py"), encoding="utf-8").read()
    assert "ag.ronde(" in bron


def test_archivaris_leest_geen_dagboek_van_voor_de_grens():
    """De Archivaris leest geen markdown meer maar de gestructureerde context, met de grens."""
    import archivaris
    assert archivaris.locatie_op("2026-09-20", "10:30") == ("", None), "oude telefoondagboeken worden niet meer gelezen"
    bron = open(os.path.join(HIER, "archivaris.py"), encoding="utf-8").read()
    assert "locatielogboek/dagen" not in bron, "De Archivaris leest weer het markdown-dagboek"


def test_een_grote_achterstand_begint_bij_de_oudste_open_dag():
    """Controle 05-10-2026: bij meer open dagen dan het maximum koos de inhaal de nieuwste."""
    L.STAND = os.path.join(tempfile.mkdtemp(), "stand.json")
    dagen = L.te_doen("2026-11-10")
    assert dagen[0] == "2026-10-03" and len(dagen) == L.INHAAL_MAX_DAGEN, dagen


def test_een_afgesloten_dag_met_een_latere_revisie_wordt_opnieuw_gemaakt():
    L.STAND = os.path.join(tempfile.mkdtemp(), "stand.json")
    L.MAP = os.path.dirname(L.STAND)
    L.stand_bijwerken(["2026-10-03", "2026-10-04", "2026-10-05"], {"2026-10-03": "a", "2026-10-04": "b", "2026-10-05": "c"})
    revisies = {"2026-10-03": {"versie": "a"}, "2026-10-04": {"versie": "b2"}, "2026-10-05": {"versie": "c"},
                "2026-10-06": {"versie": "d"}}
    assert L.te_doen("2026-10-06", revisies) == ["2026-10-04", "2026-10-06"]
    # Een dag van voor de grens in de revisies telt nooit.
    revisies["2026-10-01"] = {"versie": "x"}
    assert "2026-10-01" not in L.te_doen("2026-10-06", revisies)


class Ronde:
    def __init__(self):
        self.noden, self.detail, self.bronnen = [], "", {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def bron(self, naam, inhoud):
        self.bronnen[naam] = inhoud

    def nood(self, tekst, wie="mehdi"):
        self.noden.append(tekst)


class Agent(Bord):
    def __init__(self):
        super().__init__()
        self.r = Ronde()

    def ronde(self, taak):
        return self.r


def proefronde(status_dag, droog=False):
    """De wacht volledig, met een nagebootste tegel: wat werd gevraagd, wat verrijkt, wat de stand werd."""
    map_ = tempfile.mkdtemp()
    oud = {k: getattr(L, k) for k in ("MAP", "STAND", "haal", "verrijk", "ag", "taak_melden", "DROOG", "DAG", "OM",
                                       "CONTROLE", "controle", "nu")}
    gevraagd, verrijkt = [], []

    def haal(pad):
        gevraagd.append(pad)
        if pad.startswith("/api/dagboek/"):
            return {"status": status_dag, "versie": "v1", "markdown": "# Locatielogboek proef\n", "sporen": {}}
        if pad.startswith("/api/context"):
            return {"verblijven": [], "kandidaten": []}
        if pad == "/api/revisies":
            return {"revisies": {}}
        if pad == "/api/projectplekken":
            return {"projectplekken": [], "dekking": {}}
        return {"bronnen": [], "alarmen": []}
    L.MAP, L.STAND = map_, os.path.join(map_, "stand.json")
    L.haal, L.verrijk, L.ag, L.taak_melden = haal, (lambda dag: verrijkt.append(dag) or True), Agent(), (lambda *a: None)
    L.DROOG, L.DAG, L.OM, L.CONTROLE, L.controle = droog, ("2026-10-04" if droog else None), None, False, (lambda: None)
    L.nu = lambda: datetime(2026, 10, 5, 21, 31, tzinfo=BRUSSEL)
    L.agenda.beschikbaar = lambda: False
    L.dropbox_prive.spiegel_map = lambda *a: {"verstuurd": 0, "fout": ""}
    L.dropbox_prive.nood = lambda **k: []
    try:
        L.main()
        stand = L.lees_stand()
        noden = L.ag.r.noden
    finally:
        for k, v in oud.items():
            setattr(L, k, v)
    return gevraagd, verrijkt, stand, noden, map_


def test_droog_vraagt_alleen_leesroutes_en_verrijkt_niet():
    gevraagd, verrijkt, stand, _, map_ = proefronde("afgesloten", droog=True)
    assert not verrijkt, "--droog mag de tegel niet laten schrijven"
    assert all("adressen=1" not in p for p in gevraagd), gevraagd
    assert not os.path.exists(os.path.join(map_, "dagen")) and stand["afgesloten_tot"] == ""


def test_zonder_toestelconfiguratie_sluit_de_wacht_geen_dag_af():
    _, verrijkt, stand, noden, _ = proefronde("niet ingesteld")
    assert verrijkt, "de gewone ronde verrijkt elke dag"
    assert stand["afgesloten_tot"] == "", stand
    assert any("ATRACK_IMEIS" in n for n in noden), noden
    _, _, stand, _, _ = proefronde("afgesloten")
    assert stand["afgesloten_tot"] == "2026-10-05" and stand["versies"]["2026-10-03"] == "v1", stand


def test_een_onbereikbare_tegel_geeft_een_signaal_en_een_foute_hartslag():
    echt_ag, echt_nu, echt_haal = L.ag, L.nu, L.haal
    L.ag = Bord()
    L.nu = lambda: datetime(2026, 10, 5, 14, 5, tzinfo=BRUSSEL)

    def weg(pad):
        raise ConnectionError("geen verbinding")
    L.haal = weg
    try:
        L.controle()
        assert L.ag.klaar and L.ag.klaar[0]["titel"] == "Locatietegel onbereikbaar", L.ag.klaar
        assert L.ag.hart[-1][0] == "fout"
        assert "stil" not in L.ag.klaar[0]["titel"].lower()
    finally:
        L.ag, L.nu, L.haal = echt_ag, echt_nu, echt_haal


def test_de_controle_meldt_een_verouderde_export_ook_zonder_alarm_van_de_tegel():
    """Bronproef van de controle (05-10-2026): projectsync 48 uur en export 49 uur oud, en de
    status gaf geen alarm mee; de controle zei 'waakt'."""
    echt_ag, echt_nu, echt_haal, echt_taak = L.ag, L.nu, L.haal, L.taak_melden
    L.ag, L.taak_melden = Bord(), (lambda *a, **k: None)
    L.nu = lambda: datetime(2026, 10, 5, 14, 5, tzinfo=BRUSSEL)
    L.haal = lambda pad: {"bronnen": [{"status": "actief", "label": "Auto", "toestand": "geparkeerd"}], "alarmen": [],
                          "taken": [{"taak": "projectsync", "uren_geleden": 48}, {"taak": "export", "uren_geleden": 49},
                                    {"taak": "dagboek", "uren_geleden": 3}]}
    try:
        L.controle()
        titels = {k["titel"] for k in L.ag.klaar}
        assert "Export van het locatielogboek naar Dropbox loopt achter" in titels, titels
        assert "Projectadressen van het locatielogboek niet bijgewerkt" in titels, titels
        assert "Locatiedagboek loopt achter" not in titels and L.ag.hart[-1][0] == "fout"
    finally:
        L.ag, L.nu, L.haal, L.taak_melden = echt_ag, echt_nu, echt_haal, echt_taak


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
