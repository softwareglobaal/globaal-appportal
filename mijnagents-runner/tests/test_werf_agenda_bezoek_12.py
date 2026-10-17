"""E1b: een nieuwe momentnaam wordt pas met H-A-agenda of project-GPS een bezoek."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen")]
import werfverslag_voorbereider as V  # noqa: E402

PM = "/voorbeeld/2145 Proefstraat 1"
COMM = PM + "/_00. Communication"
OUD = COMM + "/2026-06-05 bezoek klant - plaatsbezoek"
NIEUW = COMM + "/2026-06-06 1030 HARC 2145 - klant - ramen en terras"


def mapitem(pad):
    return {".tag": "folder", "path_display": pad, "name": pad.rsplit("/", 1)[-1]}


def afspraak(nummer="2145", buiten=True, status="klaar", start="2026-06-06T10:00:00+02:00",
             einde="2026-06-06T11:00:00+02:00"):
    return {"van": "agenda-wacht", "voor": "h-architects", "soort": "afspraak", "status": status,
            "inhoud": json.dumps({"datum": "2026-06-06", "nummer": nummer, "buiten": buiten,
                                  "start": start, "einde": einde, "titel": "!! Mehdi: 2145 plaatsbezoek"})}


@pytest.fixture
def bron(monkeypatch):
    mappen = [mapitem(OUD), mapitem(NIEUW)]
    monkeypatch.setattr(V.bronnen, "lijst", lambda *a, **kw: mappen)
    monkeypatch.setattr(V, "zoek_projectmap", lambda nr: (PM, "standaard"))
    monkeypatch.setattr(V, "dossiers_lezen", lambda: {"2145": {"werfstart": "2026-09-14"}})
    monkeypatch.setattr(V, "controleer", lambda *a, **kw: ([], [], []))
    monkeypatch.setattr(V, "vooraf_koppelen", lambda bezoeken, *a: bezoeken)
    monkeypatch.setattr(V.ag, "log", lambda *a, **kw: None)
    monkeypatch.setattr(V.LC, "verblijven_in_venster", lambda *a: [])
    def bord(pad, data=None):
        return {"rijen": []} if data is None else {"herkoppeld": []}
    monkeypatch.setattr(V.bord, "call", bord)
    monkeypatch.setattr(V.bord, "klaargezet_voor", lambda *a, **kw: [])
    return mappen


def test_momentnaam_is_kandidaat_en_verkeerd_dossier_of_uur_wordt_geweigerd(bron):
    bron.extend([mapitem(COMM + "/2026-06-06 1030 HARC 9999 - klant - ander project"),
                mapitem(COMM + "/2026-06-06 2560 HARC 2145 - klant - fout uur"),
                mapitem(COMM + "/2026-06-06 1030 HARC 2145 - klant - offerte.pdf"),
                {".tag": "file", "path_display": COMM + "/2026-06-06 1030 HARC 9999 - klant - ander project/2026-06-06 verslag.md",
                 "name": "2026-06-06 verslag.md"}])
    b = V.bezoeken_in(PM, "2145")
    assert [x["map"] for x in b] == [OUD, NIEUW]
    assert "kandidaat_uur" not in b[0]
    assert b[1]["kandidaat_uur"] == "2026-06-06T10:30:00+02:00"


@pytest.mark.parametrize("item", [
    afspraak(nummer="9999"), afspraak(buiten=False), afspraak(status="vervallen"),
    afspraak(start="2026-06-06T11:01:00+02:00", einde="2026-06-06T12:00:00+02:00"),
    afspraak(start="2026-06-06T07:00:00+02:00", einde="2026-06-06T09:29:00+02:00"),
])
def test_verkeerd_of_buiten_venster_agendabewijs_telt_niet(bron, monkeypatch, item):
    kandidaat = next(x for x in V.bezoeken_in(PM, "2145") if x["map"] == NIEUW)
    assert V.kandidaatbewijs(kandidaat, {"afspraak": [item]}, "2145") is None


def test_verwerk_promoveert_pas_na_agendabewijs_en_nummert_daarna(bron, monkeypatch):
    bak = {"afspraak": [afspraak()]}
    monkeypatch.setattr(V, "klaargezet", lambda nr: bak)
    rijen, _, _ = V.verwerk("2145", droog=True)
    assert [r["bezoekmap"] for r in rijen] == [OUD, NIEUW]
    assert [r["bronnen"]["nr_label"] for r in rijen] == ["PB1", "PB2"]
    assert rijen[1]["bronnen"]["herkend_via"] == "agenda"
    assert rijen[1]["bronnen"]["herkenning_bewijs"] == "!! Mehdi: 2145 plaatsbezoek"
    bak["afspraak"] = []
    rijen, _, _ = V.verwerk("2145", droog=True)
    assert [r["bezoekmap"] for r in rijen] == [OUD]


def test_auto_gps_promoveert_kandidaat_met_exact_project_en_venster(bron, monkeypatch):
    gevraagd = []
    def verblijf(start, einde, firma, nummer):
        gevraagd.append((start, einde, firma, nummer))
        return [{"rol": "auto", "positief": True, "zekerheid": "waarschijnlijk", "bewijs": "fictief",
                 "project": {"firma": firma, "nummer": nummer}, "aankomst": start, "vertrek": einde}]
    monkeypatch.setattr(V.LC, "verblijven_in_venster", verblijf)
    monkeypatch.setattr(V, "klaargezet", lambda nr: {"afspraak": []})
    rijen, _, _ = V.verwerk("2145", droog=True)
    assert rijen[1]["bronnen"]["herkend_via"] == "gps"
    assert "auto bij project HARC 2145" in rijen[1]["bronnen"]["herkenning_bewijs"]
    assert gevraagd == [("2026-06-06T10:15:00+02:00", "2026-06-06T11:30:00+02:00", "HARC", "2145")]


def test_zonder_bewijs_een_terugkijktaak_per_dossier_en_dag(bron, monkeypatch):
    bron.append(mapitem(COMM + "/2026-06-06 1530 HARC 2145 - aannemer - overleg"))
    monkeypatch.setattr(V, "klaargezet", lambda nr: {"afspraak": []})
    taken = []
    monkeypatch.setattr(V.ag, "klaarzet", lambda items: taken.extend(items) or {"nieuw": len(items)})
    rijen, _, _ = V.verwerk("2145")
    assert [r["bezoekmap"] for r in rijen] == [OUD]
    terug = [t for t in taken if t["voor"] == "agenda-wacht" and t["uniek"].startswith("werf:terugkijken:")]
    assert len(terug) == 1
    assert terug[0]["uniek"] == "werf:terugkijken:2145:2026-06-06"
    assert terug[0]["inhoud"] == {"terugkijken": "2026-06-06", "dossier": "2145"}


def test_na_terugkijken_geen_nieuwe_taak_ook_als_geen_buitenafspraak(bron, monkeypatch):
    bekeken = {"van": "agenda-wacht", "voor": "h-architects", "soort": "afspraak",
               "inhoud": json.dumps({"datum": "2026-06-06", "nummer": "2145", "terugkijken": True,
                                     "buiten": False})}
    monkeypatch.setattr(V, "klaargezet", lambda nr: {"afspraak": [bekeken]})
    taken = []
    monkeypatch.setattr(V.ag, "klaarzet", lambda items: taken.extend(items) or {"nieuw": len(items)})
    V.verwerk("2145")
    assert not any(t.get("uniek") == "werf:terugkijken:2145:2026-06-06" for t in taken)


def test_w1_afdeling_bewijst_ha_ook_zonder_firmacode_en_type(bron):
    b = next(x for x in V.bezoeken_in(PM, "2145") if x["map"] == NIEUW)
    d = json.loads(afspraak()["inhoud"])
    d.update(firma="", type="", agenda="H-Architects", onzeker=False)
    bak = {"afspraak": [dict(afspraak(), inhoud=json.dumps(d))]}
    venster = V.bevestigd_fotovenster("2145", b, [b], bak, "")
    assert venster["start"] == "2026-06-06T10:00:00+02:00"
    d["titel"] = "!! Mehdi: 2145 overleg"
    with pytest.raises(ValueError, match="bezoekvenster_ontbreekt"):
        V.bevestigd_fotovenster("2145", b, [b], {"afspraak": [dict(afspraak(), inhoud=json.dumps(d))]}, "")
    d["titel"] = "!! Mehdi: 9999 plaatsbezoek"
    d["nummer"] = "9999"
    with pytest.raises(ValueError, match="bezoekvenster_ontbreekt"):
        V.bevestigd_fotovenster("2145", b, [b], {"afspraak": [dict(afspraak(), inhoud=json.dumps(d))]}, "")


def test_afspraak_van_een_andere_firma_of_afdeling_herkent_geen_ha_bezoek(bron):
    kandidaat = next(x for x in V.bezoeken_in(PM, "2145") if x["map"] == NIEUW)
    unabo = afspraak()
    unabo["inhoud"] = json.dumps(dict(json.loads(unabo["inhoud"]), firma="UNAB"))
    assert V.kandidaatbewijs(kandidaat, {"afspraak": [unabo]}, "2145") is None
    andere = dict(afspraak(), voor="unabo")
    assert V.kandidaatbewijs(kandidaat, {"afspraak": [andere]}, "2145") is None
    assert V.kandidaatbewijs(kandidaat, {"afspraak": [afspraak()]}, "2145") is not None


def test_bak_bladert_per_soort_terug_tot_de_oude_afspraak(monkeypatch):
    oud = dict(afspraak(), id=447, uniek="agenda:k:oud")
    recent = [dict(afspraak(nummer="9998"), id=3000 - i, uniek=f"agenda:k:{i}") for i in range(500)]
    gevraagd = []

    def bord(pad, data=None):
        gevraagd.append(pad)
        if "soort=afspraak" not in pad:
            return {"items": []}
        return {"items": [oud]} if "tot_id=2501" in pad else {"items": recent}
    monkeypatch.setattr(V.bord, "call", bord)
    items = V.bak_items()
    assert 447 in [it["id"] for it in items] and any("tot_id=2501" in p for p in gevraagd)
    assert len([it for it in items if it["id"] == 447]) == 1


def test_oude_firmacode_ha_telt_als_h_architects(bron):
    kandidaat = next(x for x in V.bezoeken_in(PM, "2145") if x["map"] == NIEUW)
    ha = afspraak()
    ha["inhoud"] = json.dumps(dict(json.loads(ha["inhoud"]), firma="HA"))
    assert V.kandidaatbewijs(kandidaat, {"afspraak": [ha]}, "2145") is not None
