"""Lokale tests voor register, extractie, promptbudget en verslagrondreis."""

import sys
from pathlib import Path

from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from naslag import bouw_register, naslag  # noqa: E402
import sjabloon_werfverslag as sjab  # noqa: E402


def _pdf(pad, paginas):
    pad.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pad))
    for tekst in paginas:
        c.drawString(50, 750, tekst)
        c.showPage()
    c.save()


def _omgeving(tmp_path, monkeypatch):
    basis = tmp_path / "pdf"
    for mapnaam in bouw_register.MAPPEN:
        (basis / mapnaam).mkdir(parents=True)
    _pdf(basis / "tv" / "TVN_283 Plaatsen van buitenschrijnwerk (Vervangt de TV 188).pdf",
         ["Algemene aspecten.", "Plaatsing ramen: raamaansluiting zorgvuldig luchtdicht afwerken."])
    _pdf(basis / "tv" / "TVN_202 Daken met betonpannen.pdf", ["Oude betonpannen."])
    registerpad = tmp_path / "bronnenregister.json"
    regels = bouw_register.schrijf_register(basis, uitvoer=registerpad)
    monkeypatch.setattr(naslag, "REGISTER", registerpad)
    monkeypatch.setattr(naslag, "PDF_BASIS", basis)
    monkeypatch.setattr(naslag, "CACHE", tmp_path / "tekst")
    return regels


def test_register_uit_bestandsnamen(tmp_path, monkeypatch):
    regels = _omgeving(tmp_path, monkeypatch)
    assert "TV240" not in bouw_register.inventarisgegevens()[2]
    assert bouw_register.inventarisgegevens()[1]["TV258.1"] == 2024
    assert len(regels) == 2
    tv = next(r for r in regels if r["sleutel"] == "TV283")
    assert tv["vervangt"] == ["TV188"]
    assert tv["jaar"] == 2022
    assert "buitenschrijnwerk" in tv["fases"]
    assert next(r for r in regels if r["sleutel"] == "TV202")["status"] == "verouderd"


def test_zoeken_op_werfpunt_en_fragmentpagina(tmp_path, monkeypatch):
    _omgeving(tmp_path, monkeypatch)
    assert naslag.zoek(trefwoorden=("plaatsing ramen",))[0]["sleutel"] == "TV283"
    assert naslag.zoek(trefwoorden=("betonpannen",))[0]["sleutel"] == "TV202"
    assert "[p. 2]" in naslag.tekst("TV283")
    assert "[p. 2]" in naslag.fragmenten("TV283", ("raamaansluiting",))[0]
    assert (tmp_path / "tekst" / "TV283.txt").is_file()


def test_promptbudget(tmp_path, monkeypatch):
    _omgeving(tmp_path, monkeypatch)
    blok = naslag.naslag_voor_punten(["Buitenschrijnwerk: plaatsing ramen, raamaansluiting"], max_tekens=130)
    assert blok.startswith("### NASLAG")
    assert len(blok) <= 130
    assert len(naslag.naslag_voor_punten(["Buitenschrijnwerk: plaatsing ramen"], max_tekens=3)) <= 3


def test_keuze_nee_slaat_naslag_over(monkeypatch):
    import werfverslag_proef as proef
    monkeypatch.setattr(proef, "naslag_voor_punten", lambda *_: (_ for _ in ()).throw(AssertionError("mag niet zoeken")))
    assert proef._naslagblok({"keuzes": {"naslag": "nee"}}, {"onderdelen": ["Ramen"]}) == ""
    assert proef._naslagblok({"keuzes": {"opmerking": "Naslag: nee"}}, {"onderdelen": ["Ramen"]}) == ""


def test_markdown_rondreis_naslag():
    verslag = {"dossier": "1234", "bezoek": "1", "adres": "Teststraat 1", "opgemaakt": "2026-10-18",
               "datum": "2026-10-17", "categorieen": [{"naam": "Buitenschrijnwerk", "punten": [{
                   "nummer": "1.1", "titel": "Raam", "datum": "2026-10-17", "vlag": "", "tekst_nl": "Aansluiting controleren.",
                   "tekst_en": "", "verantwoordelijke": "Aannemer", "naslag": "TV 283, Buildwise 2022, p. 2: aansluiting",
                   "fotos": []}]}]}
    md = sjab.naar_markdown(verslag)
    assert "Naslag: TV 283" in md
    terug = sjab.van_markdown(md)
    assert terug["categorieen"][0]["punten"][0]["naslag"] == verslag["categorieen"][0]["punten"][0]["naslag"]
