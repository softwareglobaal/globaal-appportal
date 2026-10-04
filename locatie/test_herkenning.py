"""Grendels op de projectherkenning en de synchronisatie van projectadressen.

Elk geval uit de opdracht v1.2 of uit een reproductie in de audit: een project
zonder afspraak, hetzelfde nummer bij twee firma's, twee projecten op dezelfde
plek, een adreswijziging, een bron die wegvalt. Verzonnen projecten, adressen en
coördinaten; geen netwerk (de geocoder wordt vervangen).

Draaien: python3 locatie/test_herkenning.py
"""
import os
import sqlite3
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import herkenning as H  # noqa: E402
import projectsync as P  # noqa: E402
import schema  # noqa: E402

WERF = (50.9000, 4.6000)
NAAST = (50.9001, 4.6002)          # zelfde perceel, ander project
ANDERE_FIRMA = (51.2000, 4.4000)   # zelfde nummer, ander adres, andere firma
T0 = 1791100000


def db():
    pad = os.path.join(tempfile.mkdtemp(), "locatie.db")
    return schema.verbind(pad)


class Geo:
    """Vervangt de geocoder: een vast antwoord per adres, en hij telt de vragen."""
    def __init__(self, antwoorden):
        self.antwoorden, self.gevraagd = antwoorden, []

    def __call__(self, adres):
        self.gevraagd.append(adres)
        lat, lon, kw = self.antwoorden.get(adres, (None, None, "niet_gevonden"))
        return {"lat": lat, "lon": lon, "kwaliteit": kw, "bron": "proef"}


HA = [{"firma": "HARC", "firma_id": "f-harc", "nummer": "9604", "project_id": "uuid-9604", "naam": "9604 Werfstraat",
       "adres": "Werfstraat 1, 3999 Proefdorp", "adres_bron": "projectmap (A13)", "status": "lopend",
       "bron": "ha-projecten", "link": "https://ha-projecten.globaal.be/project/9604"},
      {"firma": "HARC", "firma_id": "f-harc", "nummer": "9603", "project_id": "uuid-9603", "naam": "9603 Werfstraat",
       "adres": "Werfstraat 1 bus 2, 3999 Proefdorp", "adres_bron": "projectmap (A13)", "status": "lopend",
       "bron": "ha-projecten", "link": "https://ha-projecten.globaal.be/project/9603"}]
MAPPEN = {"9145": {"adres": "Oudstraat 9, 3998 Oudedorp", "map": "/Work All/01. H-A WORK/x/9145 Oudstraat 9"}}
GEO = Geo({"Werfstraat 1, 3999 Proefdorp": (WERF[0], WERF[1], "adres"),
           "Werfstraat 1 bus 2, 3999 Proefdorp": (NAAST[0], NAAST[1], "adres"),
           "Oudstraat 9, 3998 Oudedorp": (50.95, 4.65, "adres")})


def verblijf(plaats, minuten=40):
    return {"soort": "bezoek", "van": T0, "tot": T0 + minuten * 60, "minuten": minuten,
            "lat": plaats[0], "lon": plaats[1]}


def test_een_project_zonder_agenda_afspraak_wordt_herkend():
    """De oude lijst groeide alleen uit de agenda: een project zonder afspraak bestond niet."""
    c = db()
    P.synchroniseer(c, ha=[HA[0]], mappen=MAPPEN, geocodeer=GEO)
    h = H.beoordeel(verblijf((50.95, 4.65)), [], H.projectplekken(c))
    assert h["zekerheid"] == "waarschijnlijk" and h["project"]["sleutel"] == "HARC:9145", h
    assert "mogelijk werfbezoek" in h["formulering"] and "auto" in h["formulering"]
    assert h["project"]["bron"] == "projectmap", "een H-A-nummer buiten de afbakening komt uit de projectmap"


def test_hetzelfde_nummer_bij_twee_firmas_blijft_twee_projecten():
    """In de audit viel de firma weg bij een gelijk projectnummer."""
    c = db()
    unabo = dict(HA[0], firma="UNAB", firma_id="f-unab", project_id="uuid-u", adres="Andere 5, 2000 Antwerpen",
                 link=None)
    geo = Geo(dict(GEO.antwoorden, **{"Andere 5, 2000 Antwerpen": (ANDERE_FIRMA[0], ANDERE_FIRMA[1], "adres")}))
    P.synchroniseer(c, ha=[HA[0], unabo], mappen={}, geocodeer=geo)
    sleutels = sorted(r[0] for r in c.execute("SELECT sleutel FROM projectplek"))
    assert sleutels == ["HARC:9604", "UNAB:9604"], sleutels
    h = H.beoordeel(verblijf(ANDERE_FIRMA), [], H.projectplekken(c))
    assert h["project"]["sleutel"] == "UNAB:9604" and h["project"]["firma"] == "UNAB", h
    h = H.beoordeel(verblijf(WERF), [], H.projectplekken(c))
    assert h["project"]["sleutel"] == "HARC:9604", h


def test_twee_projecten_op_dezelfde_plek_geven_een_onzekere_kandidatenlijst():
    """In de audit koos de agent er een zonder onzekerheid (2603 en 5603, Provinciebaan 20)."""
    c = db()
    P.synchroniseer(c, ha=HA, mappen={}, geocodeer=GEO)
    h = H.beoordeel(verblijf(WERF), [], H.projectplekken(c))
    assert h["zekerheid"] == "onzeker" and h["project"] is None, h
    assert {k["sleutel"] for k in h["kandidaten"]} == {"HARC:9604", "HARC:9603"}
    assert P.dekking(c)["zelfde_adres"] == [], "verschillend busnummer is een ander adres"


def test_een_correctie_van_mehdi_gaat_voor_en_blijft_herleidbaar():
    c = db()
    P.synchroniseer(c, ha=HA, mappen={}, geocodeer=GEO)
    corr = [{"id": 1, "bron": "auto", "van": T0 - 60, "tot": T0 + 60, "wat": "project", "sleutel": "HARC:9603",
             "reden": "dashboard", "door": "mehdi", "wanneer": T0 + 9999}]
    h = H.beoordeel(verblijf(WERF), [], H.projectplekken(c), corr)
    assert h["zekerheid"] == "bevestigd" and h["project"]["sleutel"] == "HARC:9603", h
    assert h["correctie"]["door"] == "mehdi"
    corr = [dict(corr[0], wat="niet_mehdi", sleutel=None)]
    h = H.beoordeel(verblijf(WERF), [], H.projectplekken(c), corr)
    assert h["zekerheid"] == "niet_mehdi" and not h["project"], h


def test_kort_gestopt_en_te_grove_geocode():
    c = db()
    P.synchroniseer(c, ha=[HA[0]], mappen={}, geocodeer=GEO)
    plek = H.projectplekken(c)
    assert H.beoordeel(verblijf(WERF, minuten=5), [], plek)["zekerheid"] == "kort"
    assert H.beoordeel(verblijf(WERF, minuten=12), [], plek)["aard"] == "kort_stoppen"
    assert H.beoordeel(verblijf(WERF, minuten=45), [], plek)["aard"] == "verblijf"
    # Een geocode op straatniveau mag niet herkennen.
    c2 = db()
    P.synchroniseer(c2, ha=[HA[0]], mappen={}, geocodeer=Geo({HA[0]["adres"]: (WERF[0], WERF[1], "straat")}))
    assert H.projectplekken(c2) == []
    assert P.dekking(c2)["te_grof"] == ["HARC:9604"]


def test_een_plek_met_dossier_is_een_ligging_van_dat_project():
    c = db()
    P.synchroniseer(c, ha=[HA[0]], mappen={}, geocodeer=GEO)
    werfplek = [{"naam": "9604 parking", "lat": 50.903, "lon": 4.600, "straal": 150, "dossier": "9604", "firma": None}]
    h = H.beoordeel(verblijf((50.903, 4.600)), werfplek, H.projectplekken(c))
    assert h["project"]["sleutel"] == "HARC:9604" and h["project"]["via_plek"] == "9604 parking", h
    thuis = [{"naam": "Thuis", "lat": 50.80, "lon": 4.70, "straal": 150, "dossier": None}]
    h = H.beoordeel(verblijf((50.80, 4.70)), thuis, H.projectplekken(c))
    assert h["plek"] == "Thuis" and h["zekerheid"] == "geen", h


def test_adreswijziging_vernieuwt_de_geocode_anders_niet():
    c = db()
    geo = Geo(dict(GEO.antwoorden, **{"Werfstraat 3, 3999 Proefdorp": (50.91, 4.61, "adres")}))
    P.synchroniseer(c, ha=[HA[0]], mappen={}, geocodeer=geo)
    P.synchroniseer(c, ha=[HA[0]], mappen={}, geocodeer=geo)
    assert geo.gevraagd.count(HA[0]["adres"]) == 1, "een ongewijzigd adres wordt niet opnieuw opgezocht"
    P.synchroniseer(c, ha=[dict(HA[0], adres="Werfstraat 3, 3999 Proefdorp")], mappen={}, geocodeer=geo)
    r = c.execute("SELECT lat, adres FROM projectplek WHERE sleutel = 'HARC:9604'").fetchone()
    assert r[0] == 50.91 and r[1] == "Werfstraat 3, 3999 Proefdorp", tuple(r)


def test_bronuitval_bewaart_de_laatste_goede_index():
    c = db()
    P.synchroniseer(c, ha=HA, mappen=MAPPEN, geocodeer=GEO)
    voor = c.execute("SELECT sleutel, project_id, actief FROM projectplek ORDER BY sleutel").fetchall()
    # H-A Projecten onbereikbaar: niets van zijn projecten mag veranderen of verdwijnen.
    P.synchroniseer(c, ha=None, mappen=MAPPEN, ha_fout="H-A Projecten niet bereikbaar", geocodeer=GEO)
    na = c.execute("SELECT sleutel, project_id, actief FROM projectplek ORDER BY sleutel").fetchall()
    assert [tuple(r) for r in voor] == [tuple(r) for r in na], (voor, na)
    try:
        P.synchroniseer(c, ha=None, mappen=None, ha_fout="weg", mappen_fout="weg", geocodeer=GEO)
    except P.BronFout:
        pass
    else:
        raise AssertionError("zonder enige bron mag er niets gebeuren")
    P.zet_taak(c, "projectsync", False, None, "H-A Projecten niet bereikbaar")
    r = c.execute("SELECT fout, laatst_geslaagd FROM taakstatus WHERE taak = 'projectsync'").fetchone()
    assert r[0] and r[1] is None, "de fout moet zichtbaar zijn"


def test_een_project_dat_uit_de_bron_verdwijnt_wordt_uitgezet_niet_gewist():
    c = db()
    P.synchroniseer(c, ha=HA, mappen={}, geocodeer=GEO)
    P.synchroniseer(c, ha=[HA[0]], mappen={}, geocodeer=GEO)
    r = c.execute("SELECT actief FROM projectplek WHERE sleutel = 'HARC:9603'").fetchone()
    assert r is not None and r[0] == 0, "verdwenen project moet blijven staan, op actief 0"
    assert [p["sleutel"] for p in H.projectplekken(c)] == ["HARC:9604"]


def test_een_override_van_mehdi_wordt_niet_overschreven():
    c = db()
    P.synchroniseer(c, ha=[HA[0]], mappen={}, geocodeer=GEO)
    c.execute("""INSERT INTO projectplek_override (sleutel, lat, lon, straal, reden, door, wanneer)
                 VALUES ('HARC:9604', 50.905, 4.605, 120, 'parking achteraan', 'mehdi', 1)""")
    c.commit()
    P.synchroniseer(c, ha=[dict(HA[0], adres="Werfstraat 1, 3999 Proefdorp")], mappen={}, geocodeer=GEO)
    p = H.projectplekken(c)[0]
    assert (p["lat"], p["lon"], p["straal"]) == (50.905, 4.605, 120), p
    assert p["override"]["door"] == "mehdi"
    assert c.execute("SELECT count(*) FROM projectplek_override").fetchone()[0] == 1


def test_voorbijrijden_is_geen_bezoek_maar_wel_te_zien():
    c = db()
    P.synchroniseer(c, ha=[HA[0]], mappen={}, geocodeer=GEO)
    spoor = [(50.890, 4.600), (50.8995, 4.6001), (50.910, 4.600)]
    assert [v["sleutel"] for v in H.voorbij(spoor, H.projectplekken(c))] == ["HARC:9604"]


def test_de_api_van_ha_projecten_moet_de_firma_leveren():
    """Koppelen op nummer alleen mag niet: zonder firma weigert de sync."""
    import json
    import io
    import urllib.request
    echt = urllib.request.urlopen

    class Antwoord(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    urllib.request.urlopen = lambda *a, **k: Antwoord(json.dumps(
        {"projecten": [{"nummer": "9604", "adres": "x"}]}).encode())
    try:
        P.lees_ha_projecten(url="http://proef", token="t")
    except P.BronFout as e:
        assert "firma" in str(e)
    else:
        raise AssertionError("een API zonder firma mag niet aanvaard worden")
    finally:
        urllib.request.urlopen = echt


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
