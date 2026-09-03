"""Toetst de rechtenlaag van de Xelion-MCP.

Twee soorten controle:

1. Gedragstests op config.py met een echt rechtenbestand: telt persoon plus
   groep goed op, sluit dicht wat niet openstaat, en laat de noodrem winnen.
2. Een ast-toets op tools.py: elke wijzigende tool MOET config.eisen()
   aanroepen. Een tool die dat vergeet is een gat dat je met gewone tests pas
   merkt als het misgaat, en bij Xelion is verwijderen niet terug te draaien.

Draaien: python -m pytest xelion/test_rechten.py
"""
import ast
import io
import os
import pathlib
import sys

import pytest

HIER = pathlib.Path(__file__).parent
sys.path.insert(0, str(HIER))

VOORBEELD = """
personen:
  - naam: mehdi
    lezen: ja
    aanmaken: ja
    bijwerken: ja
    verwijderen: nee
  - naam: joan
    lezen: ja
groepen:
  - naam: xelion
    lezen: ja
  - naam: telefoonbeheer
    bijwerken: ja
    verwijderen: ja
"""


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    pad = tmp_path / "rechten.yaml"
    pad.write_text(VOORBEELD, encoding="utf-8")
    monkeypatch.setenv("XELION_RECHTEN", str(pad))
    for r in ("AANMAKEN", "BIJWERKEN", "VERWIJDEREN"):
        monkeypatch.setenv("XELION_MCP_" + r, "ja")
    import config
    config.PAD = str(pad)
    config._cache.update(tijd=0.0, data=None, fout=None)
    return config


def test_persoon_krijgt_wat_er_staat(cfg):
    uit, fout = cfg.rechten("mehdi", [])
    assert fout is None
    assert uit["lezen"] and uit["aanmaken"] and uit["bijwerken"]
    assert uit["verwijderen"] is False


def test_onbekende_persoon_mag_niets(cfg):
    uit, _ = cfg.rechten("niemand", [])
    assert not any(uit.values()), "dicht tenzij opengezet"


def test_groep_telt_bij_persoon_op(cfg):
    # joan mag zelf alleen lezen; via telefoonbeheer komt er meer bij.
    uit, _ = cfg.rechten("joan", ["telefoonbeheer"])
    assert uit["lezen"] and uit["bijwerken"] and uit["verwijderen"]
    assert uit["aanmaken"] is False


def test_noodrem_wint_van_het_bestand(cfg, monkeypatch):
    monkeypatch.setenv("XELION_MCP_VERWIJDEREN", "nee")
    cfg._cache.update(tijd=0.0, data=None, fout=None)
    uit, _ = cfg.rechten("joan", ["telefoonbeheer"])
    assert uit["verwijderen"] is False, "noodrem moet altijd winnen"
    assert uit["bijwerken"] is True, "andere rechten blijven staan"


def test_lezen_heeft_geen_noodrem(cfg, monkeypatch):
    monkeypatch.delenv("XELION_MCP_AANMAKEN", raising=False)
    cfg._cache.update(tijd=0.0, data=None, fout=None)
    uit, _ = cfg.rechten("mehdi", [])
    assert uit["lezen"] is True
    assert uit["aanmaken"] is False, "zonder noodrem geen schrijfrecht"


def test_kapot_bestand_zet_alles_dicht(tmp_path, monkeypatch):
    pad = tmp_path / "stuk.yaml"
    pad.write_text("personen: [ dit is geen\n  geldige yaml", encoding="utf-8")
    monkeypatch.setenv("XELION_RECHTEN", str(pad))
    import config
    config.PAD = str(pad)
    config._cache.update(tijd=0.0, data=None, fout=None)
    uit, fout = config.rechten("mehdi", [])
    assert not any(uit.values()), "een kapot bestand mag nooit openzetten"
    assert fout, "en het moet zichtbaar gemeld worden"


def test_eisen_werpt_met_uitleg(cfg):
    with pytest.raises(ValueError) as e:
        cfg.eisen("joan", [], "verwijderen")
    assert "verwijderen" in str(e.value)


# ---- ast-toets op de tools ----------------------------------------------

WIJZIGENDE_TOOLS = {
    "t_contact_aanmaken": "aanmaken",
    "t_contact_bijwerken": "bijwerken",
    "t_contact_verwijderen": "verwijderen",
    "t_lijst_aanmaken": "aanmaken",
    "t_lijst_toevoegen": "bijwerken",
    "t_lijst_afhalen": "bijwerken",
}
LEZENDE_TOOLS = ("t_contact_zoeken", "t_contact", "t_lijsten", "t_gesprekken")


def _functies():
    boom = ast.parse(io.open(HIER / "tools.py", encoding="utf-8").read())
    uit = {}
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.FunctionDef):
            uit[knoop.name] = knoop
    return uit


def _geeist_recht(functie):
    """Welk recht deze functie via config.eisen(...) afdwingt."""
    for knoop in ast.walk(functie):
        if not isinstance(knoop, ast.Call):
            continue
        f = knoop.func
        if isinstance(f, ast.Attribute) and f.attr == "eisen":
            laatste = knoop.args[-1] if knoop.args else None
            if isinstance(laatste, ast.Constant):
                return laatste.value
    return None


@pytest.mark.parametrize("naam,recht", sorted(WIJZIGENDE_TOOLS.items()))
def test_wijzigende_tool_eist_zijn_recht(naam, recht):
    functies = _functies()
    assert naam in functies, "tool %s bestaat niet meer" % naam
    assert _geeist_recht(functies[naam]) == recht, (
        "%s moet config.eisen(..., '%s') aanroepen" % (naam, recht))


@pytest.mark.parametrize("naam", LEZENDE_TOOLS)
def test_lezende_tool_eist_lezen(naam):
    functies = _functies()
    assert _geeist_recht(functies[naam]) == "lezen"


def test_verwijderen_vraagt_om_bevestiging():
    """De zwaarste tool mag niet zonder expliciet ja doorgaan."""
    bron = io.open(HIER / "tools.py", encoding="utf-8").read()
    kop = bron[bron.index("def t_contact_verwijderen"):bron.index("def t_lijst_aanmaken")]
    assert 'a.get("bevestigd")' in kop
    # De bevestigingscheck moet VOOR de daadwerkelijke verwijdering staan.
    assert kop.index('bevestigd') < kop.index("BRON.contact_verwijderen")


def test_geen_tool_omzeilt_de_rechten():
    """Elke t_-functie behalve t_ik toetst iets."""
    for naam, functie in _functies().items():
        if not naam.startswith("t_") or naam == "t_ik":
            continue
        assert _geeist_recht(functie), "%s toetst geen enkel recht" % naam
