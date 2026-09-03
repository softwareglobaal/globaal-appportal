"""Tests op de firma-poort: de kern van deze server.

Vijf administraties naast elkaar, en een deal die in de verkeerde belandt is
niet met een ongedaan-knop op te lossen. Daarom moet er niets gebeuren zolang
niet vaststaat om welke firma het gaat, en moet de weigering de gebruiker
kunnen bereiken.

Draaien:  cd pipedrive-mcp && python -m pytest test_firma.py -q
"""
import pytest

import gereedschap as gs
from gereedschap import FIRMAS, Geweigerd


@pytest.fixture(autouse=True)
def _tokens_aanwezig(monkeypatch):
    """Alle vijf tokens doen alsof ze bestaan; geen netwerk in deze tests."""
    monkeypatch.setattr(gs, "tokens", lambda: {s: "test-token" for s in FIRMAS})


def test_vijf_firmas():
    assert set(FIRMAS) == {"harchitects", "unabo", "tknburo",
                           "energieefficient", "harmoniebouw"}


@pytest.mark.parametrize("waarde, verwacht", [
    ("unabo", "unabo"),
    ("UNABO", "unabo"),
    ("H-Architects", "harchitects"),
    ("h architects", "harchitects"),
    ("Energie Efficiënt", "energieefficient"),
    ("energie efficient", "energieefficient"),      # zonder trema
    ("TKN-Buro", "tknburo"),
    ("TKN-Tekenwerk", "tknburo"),                   # zo heet het in Pipedrive
    ("HarmonieBOUW", "harmoniebouw"),
    ("Harmoniebouw BV", "harmoniebouw"),
])
def test_herkende_schrijfwijzen(waarde, verwacht):
    assert gs.firma_kiezen({"firma": waarde}) == verwacht


@pytest.mark.parametrize("a", [
    {},                       # niets meegegeven
    {"firma": ""},            # leeg
    {"firma": "   "},         # alleen spaties
    {"firma": None},
    {"firma": "alle"},        # 'doe het overal' bestaat niet
    {"firma": "globaal"},
    {"firma": "h"},           # te vaag, lijkt op twee firma's
    {"firma": "melodie"},     # bestaat wel als firma, niet in Pipedrive
])
def test_geen_of_onbekende_firma_wordt_geweigerd(a):
    with pytest.raises(Geweigerd):
        gs.firma_kiezen(a)


def test_weigering_noemt_alle_keuzes():
    """De tekst gaat naar de gebruiker, dus die moet de opties bevatten."""
    with pytest.raises(Geweigerd) as e:
        gs.firma_kiezen({})
    tekst = str(e.value)
    for sleutel in FIRMAS:
        assert sleutel in tekst
    assert "vraag" in tekst.lower()


def test_ontbrekend_token_is_een_nette_weigering(monkeypatch):
    monkeypatch.setattr(gs, "tokens", lambda: {"unabo": "test-token"})
    with pytest.raises(Geweigerd) as e:
        gs.firma_kiezen({"firma": "harmoniebouw"})
    assert "HarmonieBOUW" in str(e.value)


def test_elk_gereedschap_gaat_langs_de_poort(monkeypatch):
    """Geen enkel stuk gereedschap draait zonder firma -- ook nieuw gereedschap
    niet, want de poort zit in voer_uit en niet in de losse functies."""
    geraakt = []
    for naam in gs.UITVOERING:
        monkeypatch.setitem(gs.UITVOERING, naam, lambda *a, **k: geraakt.append(naam))
        with pytest.raises(Geweigerd):
            gs.voer_uit(naam, {}, True)
    assert not geraakt


def test_firmas_mag_wel_zonder_firma():
    uit = gs.voer_uit("firmas", {}, False)
    assert len(uit["firmas"]) == len(FIRMAS)
    assert all("token" in r or "token_aanwezig" in r for r in uit["firmas"])


def test_antwoord_noemt_de_firma(monkeypatch):
    monkeypatch.setitem(gs.UITVOERING, "deals", lambda s, a: {"deals": []})
    uit = gs.voer_uit("deals", {"firma": "unabo"}, False)
    assert uit["firma"] == "UNABO (unabo)"
    assert list(uit)[0] == "firma"          # staat vooraan in het antwoord


def test_onbekend_gereedschap():
    with pytest.raises(Geweigerd):
        gs.voer_uit("verwijder_alles", {"firma": "unabo"}, True)


# ---- Lezen mag iedereen, schrijven niet ----------------------------------
def test_schrijven_zonder_recht_wordt_geweigerd(monkeypatch):
    monkeypatch.setitem(gs.UITVOERING, "deal_aanmaken", lambda s, a: {"ok": True})
    with pytest.raises(Geweigerd) as e:
        gs.voer_uit("deal_aanmaken", {"firma": "unabo", "titel": "x"}, False)
    assert "pipedrive-editors" in str(e.value)


def test_lezen_mag_zonder_schrijfrecht(monkeypatch):
    monkeypatch.setitem(gs.UITVOERING, "deal", lambda s, a: {"id": 1})
    assert gs.voer_uit("deal", {"firma": "unabo", "id": 1}, False)["id"] == 1


def test_schrijvend_gereedschap_is_volledig_herkend():
    """Alles wat aanmaakt of bijwerkt moet in SCHRIJVEND zitten, anders glipt
    het langs de rechtencontrole."""
    verwacht = {n for n in gs.UITVOERING if "aanmaken" in n or "bijwerken" in n}
    assert gs.SCHRIJVEND == verwacht and verwacht


# ---- Tokens blijven binnen ------------------------------------------------
def test_token_staat_niet_in_de_url(monkeypatch):
    """Het token gaat als kopregel mee. In de URL zou het in elke foutmelding,
    log en proxyregel terechtkomen."""
    gezien = {}

    class NepAntwoord:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"success": true, "data": {}}'

    def nep_urlopen(req, timeout=None):
        gezien["url"] = req.full_url
        gezien["koppen"] = {k.lower(): v for k, v in req.header_items()}
        return NepAntwoord()

    monkeypatch.setattr(gs.urllib.request, "urlopen", nep_urlopen)
    monkeypatch.setattr(gs.json, "load", lambda f: {"success": True, "data": {}})
    gs._roep("unabo", "GET", "/deals", {"status": "open"})
    assert "test-token" not in gezien["url"]
    assert gezien["koppen"]["x-api-token"] == "test-token"
