"""De naamregel van Mehdi (18-09-2026) mag niet stilzwijgend sneuvelen: tijd, FIRMA, dossier,
dan met wie en onderwerp; firmacodes uit kern; sales zonder dossier = de naam van de persoon."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import benaming  # noqa: E402

COLLEGAS = {"ashvand": {"naam": "Ashvand (H-Energy)", "diensten_voor": ["ENEF"]},
            "shaniel": {"naam": "Shaniel (H-AI & ICT)", "diensten_voor": ["ELEV", "ORVA"]},
            "tom": {"naam": "Tom (P-Engineering)", "diensten_voor": ["TKNB"]}}


def herken(naam):
    return COLLEGAS.get((naam or "").strip().lower().split()[0]) if naam else None


def test_agendacode_geeft_firma_en_sales_zonder_dossier():
    b = benaming.benoem({"title": "Mehdi [UNABO-PO] Alexander Symons - Stabiliteit"}, herken)
    assert b["firma"] == "UNAB" and b["dossier"] == "Alexander Symons"
    assert b["met_wie"] == "Alexander Symons" and b["onderwerp"] == "Stabiliteit"
    assert benaming.naam("2026-09-17 1403", b) == "2026-09-17 1403 UNAB Alexander Symons - Alexander Symons - Stabiliteit"


def test_calendly_prospectie():
    b = benaming.benoem({"title": "Ronald Verlinden: H-Architects Prospections (second meeting)"}, herken)
    assert (b["firma"], b["dossier"], b["onderwerp"]) == ("HARC", "Ronald Verlinden", "tweede prospectiegesprek")
    assert b["zekerheid"] == "hoog"


def test_ee_met_collega_ertussen():
    b = benaming.benoem({"title": "EE: Mehdi: Ashvand: Kevin Grandjean"}, herken)
    assert b["firma"] == "ENEF" and b["met_wie"] == "Kevin Grandjean" and b["dossier"] == "Kevin Grandjean"


def test_projectnummer_is_het_dossier():
    b = benaming.benoem({"title": "Meeting 2145 Online Sophie en Nico"}, herken)
    assert b["firma"] == "HARC" and b["dossier"] == "2145" and b["met_wie"] == "Sophie en Nico"


def test_generieke_titel_blijft_onbenoemd_zonder_herkenning():
    b = benaming.benoem({"title": "Impromptu Zoom Meeting"}, herken)
    assert b["ontbreekt"] == ["firma", "dossier", "met_wie", "onderwerp"] and benaming.naam("2026-09-17 1100", b) == ""


def test_herkenning_vult_aan_en_collega_is_intern():
    g = {"title": "Impromptu Zoom Meeting", "herkenning": {"afdeling": "elevait", "personen": ["Shaniel", "Afspraken (Mehdi)"],
                                                          "thema": "agent voor telefonie: opname en transcript", "project": ""}}
    b = benaming.benoem(g, herken)
    assert b["firma"] == "ELEV" and b["dossier"] == "intern" and b["met_wie"] == "Shaniel"


def test_dubbele_punten_eerste_stuk_is_de_klant():
    b = benaming.benoem({"title": "Mehdi: [HA-KO] Yannick Verlinden: (3RD): Vervolg bespreking"}, herken)
    assert (b["firma"], b["dossier"], b["met_wie"], b["onderwerp"]) == ("HARC", "Yannick Verlinden", "Yannick Verlinden", "Vervolg bespreking")


def test_firmanaam_als_stuk_en_b2b_valt_weg():
    b = benaming.benoem({"title": "Fatlum Gashi: UNABO: Offertevoorbereidend gesprek (B2C)"}, herken)
    assert (b["firma"], b["met_wie"]) == ("UNAB", "Fatlum Gashi") and b["onderwerp"].startswith("Offertevoorbereidend gesprek")
    b = benaming.benoem({"title": "Harmoniebouw: B2B: Kevin Sieckelinck"}, herken)
    assert (b["firma"], b["dossier"]) == ("HARM", "Kevin Sieckelinck")


def test_projectzin_uit_de_herkenning_is_geen_dossier():
    g = {"title": "Impromptu Zoom Meeting", "herkenning": {"afdeling": "tkn", "personen": ["Mehdi Chegini", "Tom"],
         "project": "Interne IT-ondersteuning TKN-Buro (Dropbox, Revit Sofistik-versies)", "thema": "software"}}
    b = benaming.benoem(g, herken)
    assert b["dossier"] == "intern" and b["met_wie"] == "Tom" and b["firma"] == "TKNB"


def test_prive_vraagt_geen_firma():
    b = benaming.benoem({"title": "Impromptu Zoom Meeting", "herkenning": {"prive": True, "afdeling": "prive", "personen": ["Angela"], "thema": "weekend"}}, herken)
    assert "firma" not in b["ontbreekt"] and b["prive"] is True
