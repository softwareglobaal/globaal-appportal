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
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import locatie_wacht as L  # noqa: E402

WERF = (50.7000, 4.6000)
ELDERS = (50.7300, 4.6400)
BRUSSEL = ZoneInfo("Europe/Brussels")
PER_SLEUTEL = {
    "HARC:9145": {"adres": "Werfstraat 9, 3999 Proefdorp", "coord": WERF, "bron": "ha-projecten",
                  "link": "https://ha-projecten.globaal.be/project/9145", "firma": "HARC", "nummer": "9145"},
    "HARC:9146": {"adres": "Mapstraat 1, 3998 Mapdorp", "coord": None, "bron": "projectmap", "link": None,
                  "firma": "HARC", "nummer": "9146"},
    "HARC:3999": {"adres": "Postcodestraat 1, 3999 Proefdorp", "coord": ELDERS, "bron": "projectmap",
                  "link": None, "firma": "HARC", "nummer": "3999"},
    "HARC:9200": {"adres": "A 1, 3999 Proefdorp", "coord": (50.71, 4.61), "bron": "ha-projecten", "link": None,
                  "firma": "HARC", "nummer": "9200"},
    "UNAB:9200": {"adres": "B 2, 2000 Antwerpen", "coord": (51.2, 4.4), "bron": "unabo", "link": None,
                  "firma": "UNAB", "nummer": "9200"},
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
    a = {"titel": "Mehdi: !! [HARC-KB] WB 9145 - wekelijks werfbezoek", "locatie": "Werfstraat 9, 3999 Deelgemeente"}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == WERF, herkomst
    assert "HARC 9145" in herkomst, herkomst
    assert not L.W.coord.gevraagd, "Nominatim gevraagd terwijl de projectplek het wist"


def test_zonder_coordinaat_het_adres_van_de_projectbron():
    L.W.coord = Coord([50.71, 4.61])
    a = {"titel": "!! Mehdi: 9146 werfbezoek 1", "locatie": ""}
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
    a = {"titel": "!! Mehdi: 9200 werfbezoek", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert lat is None and "meer firma" in herkomst, herkomst
    a = {"titel": "!! Mehdi: [HARC-KB] WB 9200", "locatie": ""}
    lat, lon, herkomst = L.plek_van_afspraak(a, L.W.lees_titel(a["titel"]), INDEX, {})
    assert (lat, lon) == (50.71, 4.61) and "HARC 9200" in herkomst, herkomst


def dagboek(*verblijven):
    return {"status": "afgesloten", "markdown": "# Locatielogboek proef\n",
            "sporen": {"auto": {"rol": "auto", "label": "Tracker in de auto", "indeling": list(verblijven)}}}


def test_afspraak_op_de_werf_is_doorgegaan_met_de_auto_ter_plaatse():
    """15-09-2026: werfbezoek zonder adres, ter plaatse 07:34-08:05; aankomen en parkeren horen samen."""
    L.W.coord = Coord()
    L.agenda.beschikbaar = lambda: True
    L.W.afspraken_dag = lambda dag: [
        {"titel": "!! Mehdi: [HARC-KB] WB 9145 werfbezoek 1", "start": "2026-10-05T07:00:00+02:00",
         "einde": "2026-10-05T09:00:00+02:00", "locatie": ""},
        {"titel": "Mehdi: [UNABO-PO] Iemand", "start": "2026-10-05T09:00:00+02:00",
         "einde": "2026-10-05T09:30:00+02:00", "locatie": "https://us06web.zoom.us/j/1"},
        {"titel": "🚗 Reistijd → Proefdorp", "start": "2026-10-05T06:30:00+02:00",
         "einde": "2026-10-05T07:00:00+02:00", "locatie": ""}]
    project = {"sleutel": "HARC:9145", "firma": "HARC", "nummer": "9145", "link": PER_SLEUTEL["HARC:9145"]["link"]}
    aankomst = {"soort": "bezoek", "van": tijd(7, 34), "tot": tijd(8, 5), "minuten": 31, "lat": WERF[0],
                "lon": WERF[1], "herkenning": {"zekerheid": "waarschijnlijk", "project": project}}
    geparkeerd = dict(aankomst, van=tijd(8, 5), tot=tijd(8, 41), minuten=36, parkeren=True)
    verblijven = L.verblijven_van(dagboek(aankomst, geparkeerd))
    doorgegaan, niet_gezien, zonder_adres, overig = L.vergelijk_agenda("2026-10-05", verblijven, INDEX, {})
    assert len(doorgegaan) == 1 and "07:34-08:41" in doorgegaan[0] and "auto ter plaatse" in doorgegaan[0], doorgegaan
    assert not niet_gezien and not zonder_adres and overig == 2, (niet_gezien, zonder_adres, overig)
    assert all(v.get("afspraak") for v in verblijven)


def test_onzekere_herkenning_blijft_een_kandidatenlijst():
    kand = [{"sleutel": "HARC:9145", "firma": "HARC", "nummer": "9145"},
            {"sleutel": "HARC:9146", "firma": "HARC", "nummer": "9146"}]
    v = L.verblijven_van(dagboek({"soort": "bezoek", "van": tijd(10, 0), "tot": tijd(11, 0), "minuten": 60,
                                  "lat": WERF[0], "lon": WERF[1],
                                  "herkenning": {"zekerheid": "onzeker", "project": None, "kandidaten": kand}}))[0]
    assert v["project"] is None and "een van: HARC 9145, HARC 9146" == v["waar"], v["waar"]


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
    import archivaris
    map_ = tempfile.mkdtemp()
    echt = os.path.expanduser
    os.path.expanduser = lambda p: p.replace("~/appportal/mijnagents-data", map_)
    try:
        os.makedirs(os.path.join(map_, "locatielogboek", "dagen"))
        for dag in ("2026-09-20", "2026-10-05"):
            open(os.path.join(map_, "locatielogboek", "dagen", f"{dag}.md"), "w").write(
                "| 10:00 | 11:00 | 1u00 | verblijf | ergens |\n")
        assert archivaris.locatie_op("2026-09-20", "10:30") == "", "oude telefoondagboeken worden niet meer gelezen"
        assert archivaris.locatie_op("2026-10-05", "10:30") == "verblijf: ergens"
    finally:
        os.path.expanduser = echt


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
