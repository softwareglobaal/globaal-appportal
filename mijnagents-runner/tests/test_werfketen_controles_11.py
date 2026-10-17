"""Regressies voor bewijs per controlepost; alle externe bronnen zijn fictief."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen")]
import werfverslag_voorbereider as v  # noqa: E402
echte_werfapp_bezoeken = v.werfapp_bezoeken


def bezoek():
    return {"datum": "2026-10-14", "map": "/project/2026-10-14 bezoek", "fotos": 0,
            "foto_bestanden": [], "foto_manifest": "", "opnames": [], "opname_starts": [],
            "transcripten": [], "transcript_bestanden": [], "verslagen": [], "notities": [],
            "volgnr": 1, "nr_label": "1", "werfnr": 1, "soort_bezoek": "werfbezoek"}


def afspraak(nummer="9999"):
    return {"van": "agenda-wacht", "voor": "h-architects", "soort": "afspraak", "status": "klaar",
            "inhoud": json.dumps({"firma": "HARC", "nummer": nummer, "datum": "2026-10-14", "agenda": "H-A Buiten",
                                  "type": "WB", "onzeker": False, "buiten": True,
                                  "start": "2026-10-14T11:00:00+02:00", "einde": "2026-10-14T12:00:00+02:00"})}


def foto():
    return {"van": "icloud-wacht", "soort": "foto", "sleutel": "2026-10-14",
            "inhoud": json.dumps({"datum": "2026-10-14", "nummer": "9999",
                                  "bouwplaats": {"adres": "Werfstraat 1", "lat": 51.0, "lon": 4.0}, "fotos": [
                {"vastgelegd_utc": "2026-10-14T09:30:00Z", "lat": 51.0, "lon": 4.0}]})}


@pytest.fixture
def buiten(monkeypatch):
    monkeypatch.setattr(v, "contractbewijs", lambda nr: ("onbekend", "fictieve contractdienst uit"))
    monkeypatch.setattr(v, "werfapp_bezoeken", lambda nr: [])
    monkeypatch.setattr(v, "projectcoordinaten", lambda nr, adres, bak: (51.0, 4.0))
    return {"afspraak": [afspraak()], "foto": [], "transcript": [], "locatie": []}


def posten(b, bak):
    c, _, _ = v.controleer("9999", "Werfstraat 1", "standaard", "/project", b, bak, bezoeken=[b])
    return {p["code"]: p for p in c}


def test_w1_andere_dossier_op_dezelfde_dag_is_geen_agendabewijs(buiten):
    buiten["afspraak"] = [afspraak("9998")]
    assert posten(bezoek(), buiten)["W1"]["stand"] == "ontbreekt"


def test_w1_gebruikt_vooraf_gekoppeld_bezoek_id_bij_twee_bezoeken_op_een_dag(buiten):
    eerste, tweede = bezoek(), bezoek()
    eerste["registratie"] = {"bezoek_id": "vast-eerste"}
    tweede["map"] = "/project/2026-10-14 tweede bezoek"
    tweede["registratie"] = {"bezoek_id": "vast-tweede"}
    afspraak_eerste = json.loads(afspraak()["inhoud"])
    afspraak_eerste["bezoek_id"] = "vast-eerste"
    buiten["afspraak"] = [dict(afspraak(), inhoud=json.dumps(afspraak_eerste))]
    c, _, _ = v.controleer("9999", "Werfstraat 1", "standaard", "/project", eerste, buiten,
                           {"registratie": {"bezoek_id": "oud-bord-id"}}, [eerste, tweede])
    assert next(p for p in c if p["code"] == "W1")["stand"] == "ok"
    c, _, _ = v.controleer("9999", "Werfstraat 1", "standaard", "/project", tweede, buiten,
                           bezoeken=[eerste, tweede])
    assert next(p for p in c if p["code"] == "W1")["stand"] == "ontbreekt"


def test_e4_foto_met_gps_herstelt_w1_maar_nooit_tot_agenda_ok(buiten):
    buiten["afspraak"] = []
    buiten["foto"] = [foto()]
    p = posten(bezoek(), buiten)
    assert p["W1"]["stand"] == "let_op"
    assert "niet door de agenda" in p["W1"]["toelichting"]
    assert p["W2"]["stand"] == "ok"


def test_e4_opname_met_explicit_starttijd_geeft_geen_agenda_ok(buiten):
    buiten["afspraak"] = []
    b = bezoek()
    b["opname_starts"] = ["2026-10-14T11:20:00+02:00"]
    p = posten(b, buiten)
    assert p["W1"]["stand"] == "let_op"
    assert p["W2"]["stand"] == "ok"


def test_w2_geen_gps_of_opnamestart_is_ontbrekend(buiten):
    assert posten(bezoek(), buiten)["W2"]["stand"] == "ontbreekt"


def test_w3_los_verslag_zonder_eigen_bezoekmap_is_ontbrekend(buiten):
    b = bezoek()
    b["bron_map"] = "los verslag"
    assert posten(b, buiten)["W3"]["stand"] == "ontbreekt"


def test_foto_gps_mag_niet_zelf_het_bouwplaatsadres_bepalen(monkeypatch):
    monkeypatch.setattr(v.LC, "projectplek", lambda firma, nummer: None)
    foto_item = {"van": "icloud-wacht", "soort": "foto",
                 "inhoud": json.dumps({"firma": "HARC", "nummer": "9999",
                                        "bouwplaats": {"adres": "Werfstraat 1", "lat": 51.0, "lon": 4.0}})}
    assert v.projectcoordinaten("9999", "Werfstraat 1", {"foto": [foto_item]}) is None
    assert v.projectcoordinaten("9999", "Werfstraat 1", {"afspraak": [dict(foto_item, van="agenda-wacht", soort="afspraak")]}) == (51.0, 4.0)


def test_projectcoordinaten_uit_de_tegel_alleen_via_de_gedeelde_lezer(monkeypatch):
    gevraagd = []
    monkeypatch.setattr(v.LC, "projectplek", lambda firma, nummer: gevraagd.append((firma, nummer)) or (50.5, 4.5))
    assert v.projectcoordinaten("9999", "Werfstraat 1", {"afspraak": []}) == (50.5, 4.5)
    assert gevraagd == [("HARC", "9999")]


def verblijf(rol, aankomst="2026-10-14T11:05:00+02:00", vertrek="2026-10-14T11:40:00+02:00", nummer="9999"):
    return {"aankomst": aankomst, "vertrek": vertrek, "rol": rol, "positief": True, "zekerheid": "waarschijnlijk",
            "bewijs": "fictief", "project": {"firma": "HARC", "nummer": nummer}}


def test_w2_gedragen_tracker_bij_het_project_is_aanwezigheid(buiten, monkeypatch):
    monkeypatch.setattr(v.LC, "context", lambda dag: {"dag": dag, "bronbeleid": {}, "verblijven": [verblijf("tracker")]})
    assert posten(bezoek(), buiten)["W2"]["stand"] == "ok"


def test_w2_alleen_de_auto_bij_het_project_is_ok(buiten, monkeypatch):
    monkeypatch.setattr(v.LC, "context", lambda dag: {"dag": dag, "bronbeleid": {}, "verblijven": [verblijf("auto")]})
    w2 = posten(bezoek(), buiten)["W2"]
    assert w2["stand"] == "ok" and "auto bij het project; Mehdi gaat altijd met de auto, E1b" in w2["toelichting"]


def test_w2_verblijf_buiten_het_venster_of_bij_een_ander_project_telt_niet(buiten, monkeypatch):
    for vb in (verblijf("tracker", "2026-10-14T08:00:00+02:00", "2026-10-14T09:00:00+02:00"),
               verblijf("tracker", nummer="9998"),
               verblijf("auto", "2026-10-14T08:00:00+02:00", "2026-10-14T09:00:00+02:00"),
               verblijf("auto", nummer="9998")):
        monkeypatch.setattr(v.LC, "context", lambda dag, vb=vb: {"dag": dag, "bronbeleid": {}, "verblijven": [vb]})
        assert posten(bezoek(), buiten)["W2"]["stand"] == "ontbreekt"


def test_w2_verblijf_dat_voor_het_venster_begint_maar_erin_doorloopt(buiten, monkeypatch):
    vb = verblijf("tracker", "2026-10-14T10:55:00+02:00", "2026-10-14T11:20:00+02:00")
    monkeypatch.setattr(v.LC, "context", lambda dag: {"dag": dag, "bronbeleid": {}, "verblijven": [vb]})
    assert posten(bezoek(), buiten)["W2"]["stand"] == "ok"


def test_w2_dag_voor_de_meetreeks_geeft_geen_locatie(monkeypatch):
    monkeypatch.setattr(v.LC.bronbeleid, "dag_toegestaan", lambda dag: False)
    monkeypatch.setattr(v.LC, "_haal", lambda pad: (_ for _ in ()).throw(AssertionError("mag de tegel niet vragen")))
    assert v.LC.verblijven_in_venster("2026-09-01T10:00:00+02:00", "2026-09-01T11:00:00+02:00", "HARC", "9999") == []


def test_w2_foto_met_gps_in_het_venster_is_aanwezigheid(buiten, monkeypatch):
    monkeypatch.setattr(v.LC, "context", lambda dag: None)
    buiten["foto"] = [foto()]
    assert posten(bezoek(), buiten)["W2"]["stand"] == "ok"


def test_w4_wortelfoto_en_alleen_heic_blijven_let_op(buiten):
    b = bezoek()
    b.update(fotos=1, foto_bestanden=[b["map"] + "/foto.jpg"])
    assert posten(b, buiten)["W4"]["stand"] == "let_op"
    b["foto_bestanden"] = [b["map"] + "/fotos/foto.heic"]
    b["foto_manifest"] = b["map"] + "/fotos/00 fotos.md"
    assert posten(b, buiten)["W4"]["stand"] == "let_op"


def test_w4_manifest_met_tijd_per_jpeg_in_venster_wordt_ok(buiten, monkeypatch):
    b = bezoek()
    b.update(fotos=1, foto_bestanden=[b["map"] + "/fotos/foto.jpg"], foto_manifest=b["map"] + "/fotos/00 fotos.md")
    monkeypatch.setattr(v.bronnen, "download", lambda *a, **kw: b"- 2026-10-14T11:30:00+02:00 | foto.jpg\n")
    assert posten(b, buiten)["W4"]["stand"] == "ok"
    monkeypatch.setattr(v.bronnen, "download", lambda *a, **kw: b"- 2026-10-14T14:30:00+02:00 | foto.jpg\n")
    assert posten(b, buiten)["W4"]["stand"] == "let_op"


def test_w6_transcript_alleen_in_bak_is_ontbrekend_met_plaatstaak(buiten):
    buiten["transcript"] = [{"van": "plaud-wacht", "titel": "9999 transcript", "sleutel": "9999",
                             "inhoud": json.dumps({"datum": "2026-10-14", "firma": "HARC", "projectnummer": "9999"})}]
    c, taken, _ = v.controleer("9999", "Werfstraat 1", "standaard", "/project", bezoek(), buiten, bezoeken=[bezoek()])
    assert next(p for p in c if p["code"] == "W6")["stand"] == "ontbreekt"
    assert any(a == "plaud-wacht" and "Plaats het transcript" in tekst for a, tekst in taken)


def test_w8_hoger_werfappnummer_is_geen_groen(buiten, monkeypatch):
    monkeypatch.setattr(v, "werfapp_bezoeken", lambda nr: [{"volgnummer": 7}])
    assert posten(bezoek(), buiten)["W8"]["stand"] == "let_op"


def test_w8_ook_projectteller_en_bezoeklijst_ijken_het_nummer(buiten, monkeypatch):
    monkeypatch.setattr(v, "werfapp_bezoeken", echte_werfapp_bezoeken)
    monkeypatch.setattr(v.werfapp, "call", lambda pad: {"werfbezoek_teller": 7, "verslagen": []})
    assert v.werfapp_bezoeken("9999") == [{"werfbezoek_teller": 7}]
    assert posten(bezoek(), buiten)["W8"]["stand"] == "let_op"
    monkeypatch.setattr(v.werfapp, "call", lambda pad: {} if pad.endswith("/9999") else {"bezoeken": [{"weergave_nummer": "8"}]})
    assert posten(bezoek(), buiten)["W8"]["stand"] == "let_op"


def test_w8_werfapp_onbereikbaar_is_onbekend(buiten, monkeypatch):
    monkeypatch.setattr(v, "werfapp_bezoeken", lambda nr: None)
    assert posten(bezoek(), buiten)["W8"]["stand"] == "onbekend"
    monkeypatch.setattr(v, "werfapp_bezoeken", lambda nr: [])
    assert posten(bezoek(), buiten)["W8"]["stand"] == "onbekend"


def test_w9_alleen_werfapp_verzendbewijs(buiten, monkeypatch):
    b = bezoek()
    assert posten(b, buiten)["W9"]["stand"] == "onbekend"
    monkeypatch.setattr(v, "werfapp_bezoeken", lambda nr: [{"id": 3, "status": "verzonden"}])
    c, _, _ = v.controleer("9999", "Werfstraat 1", "standaard", "/project", b, buiten,
                           {"proef_info": {"werfapp": {"id": 3}}}, [b])
    assert next(p for p in c if p["code"] == "W9")["stand"] == "ok"
    monkeypatch.setattr(v, "werfapp_bezoeken", lambda nr: [{"id": 3, "nummer": "9999-1", "verzonden": [{"status": "klaargezet"}]}])
    assert posten(b, buiten)["W9"]["stand"] == "onbekend"
    monkeypatch.setattr(v, "werfapp_bezoeken", lambda nr: [{"nummer": "9999-1", "verzonden": [{"status": "verstuurd"}]}])
    assert posten(b, buiten)["W9"]["stand"] == "ok"


def test_w12_onbereikbaar_blijft_onbekend(monkeypatch):
    def uit(*args, **kwargs):
        raise RuntimeError("fictief buiten bereik")
    monkeypatch.setattr(v.contracten_mcp, "call", uit)
    monkeypatch.setattr(v.werfapp, "call", uit)
    assert v.contractbewijs("9999")[0] == "onbekend"


def test_w12_eist_getekend_en_werfopvolging(monkeypatch):
    aanroepen = []
    monkeypatch.setattr(v.contracten_mcp, "call", lambda *a, **kw: aanroepen.append((a, kw)) or {
        "dossier": {"status": "getekend"},
        "velden": {"architectuur_scope": "volledige_afwerking", "werfopvolging_keuze": "nee"}})
    assert v.contractbewijs("9999")[0] == "ontbreekt"
    assert aanroepen == [(('dossier',), {"project_nummer": "9999", "soort": "architectuur"})]
    monkeypatch.setattr(v.contracten_mcp, "call", lambda *a, **kw: {
        "dossier": {"status": "getekend"},
        "velden": {"architectuur_scope": "volledige_afwerking", "werfopvolging_keuze": "ja"}})
    assert v.contractbewijs("9999")[0] == "ok"


def test_w12_raadpleegt_werfapp_als_contractdashboard_geen_dossier_heeft(monkeypatch):
    monkeypatch.setattr(v.contracten_mcp, "call", lambda *a, **kw: (_ for _ in ()).throw(v.contracten_mcp.ToolFout("Geen dossier gevonden")))
    monkeypatch.setattr(v.werfapp, "call", lambda pad: {"stand": "getekend", "architectuur_scope": "wind_waterdicht",
                                                        "werfopvolging_keuze": "ja"})
    assert v.contractbewijs("9999")[0] == "ok"


@pytest.mark.parametrize("post", ["W1", "W2", "W12"])
def test_zonder_blokkerend_bewijs_niet_klaar(post):
    c = [{"code": k, "naam": k, "stand": "ok"} for k in ("W1", "W2", "W3", "W4", "W5", "W6", "W12")]
    next(p for p in c if p["code"] == post)["stand"] = "ontbreekt"
    assert v.stand_van(c) == "te verzamelen"
    assert post in v.ontbrekende_posten(c)[0]


def test_w6_plaud_exporttranscript_in_de_map_telt_zoals_bij_de_schrijver(buiten):
    b = bezoek()
    naam = "20260820 2173 Vergadering_ Renovatie eengezinswoning-transcript.txt"
    b.update(transcripten=[naam], transcript_bestanden=[b["map"] + "/" + naam])
    assert posten(b, buiten)["W6"]["stand"] == "ok"
    import werfverslag_proef as proef
    assert proef.eigen_tekst(naam) and v.werfnamen.eigen_transcript(naam)


def test_w6_transcript_van_derden_telt_niet(buiten):
    b = bezoek()
    naam = "derden-transcript.txt"
    b.update(transcripten=[naam], transcript_bestanden=[b["map"] + "/" + naam])
    assert posten(b, buiten)["W6"]["stand"] == "ontbreekt"


def test_w12_project_van_voor_het_contractsysteem_is_onbekend_niet_ontbreekt(monkeypatch):
    class Fout(Exception):
        pass
    monkeypatch.setattr(v.contracten_mcp, "ToolFout", Fout)
    monkeypatch.setattr(v.contracten_mcp, "call", lambda *a, **kw: (_ for _ in ()).throw(Fout("Geen dossier gevonden voor '2173'")))
    monkeypatch.setattr(v.werfapp, "call", lambda *a, **kw: (_ for _ in ()).throw(OSError("project onbekend")))
    stand, toel = v.contractbewijs("2173")
    assert stand == "onbekend" and "vóór het systeem" in toel
