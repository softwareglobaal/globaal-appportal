"""Tests op de koppeling: waar mag de autorisatiecode naartoe, en wie mag wat.

Een te ruime `_redirect_ok` betekent dat een vreemde site de code van een
ingelogde collega kan opvangen en daarmee bij vijf Pipedrive-administraties
kan. Een te strakke betekent dat Claude Code op een werkplek niet kan koppelen.
Zelfde afweging als bij renovision-mcp, hier overgenomen omdat de inzet groter
is: dit gereedschap schrijft in de verkoopadministratie.

Draaien:  cd pipedrive-mcp && python -m pytest test_koppeling.py -q
"""
import pytest

import gereedschap as gs
from mcp_server import FIRMAS, TOOLS, _mag_binnen, _mag_schrijven, _redirect_ok


@pytest.mark.parametrize("uri", [
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    "https://console.anthropic.com/callback",
    "http://localhost:41234/callback",
    "http://127.0.0.1:8765/oauth/callback",
    "https://localhost:3000/cb",
])
def test_toegestane_bestemmingen(uri):
    assert _redirect_ok(uri), uri


@pytest.mark.parametrize("uri", [
    "https://claude.ai.kwaadaardig.nl/callback",   # lijkt op claude.ai
    "https://nepclaude.ai/callback",               # eindigt op 'claude.ai' zonder punt
    "http://claude.ai/api/mcp/auth_callback",      # geen https naar buiten
    "https://voorbeeld.nl/callback",
    "https://localhost.kwaadaardig.nl/cb",         # begint met localhost
    "ftp://localhost/cb",                          # loopback, maar geen http
    "javascript:alert(1)",
    "",
])
def test_geweigerde_bestemmingen(uri):
    assert not _redirect_ok(uri), uri


@pytest.mark.parametrize("groepen, verwacht", [
    (["pipedrive-editors"], True),
    (["admin"], True),
    (["sales", "admin"], True),
    (["Admin"], True),                 # Authentik-groepen zijn hoofdlettergevoelig
    (["pipedrive"], False),            # kijkgroep, geen schrijfrecht
    (["sales", "hr"], False),
    ([], False),
])
def test_schrijfrecht_zonder_namenlijst(groepen, verwacht, monkeypatch):
    """Geen MCP_GEBRUIKERS: dan beslissen de groepen, zoals eerst."""
    monkeypatch.delenv("MCP_GEBRUIKERS", raising=False)
    assert _mag_schrijven(groepen) is verwacht


# ---- De namenlijst: alleen Mehdi ----------------------------------------
@pytest.fixture
def alleen_mehdi(monkeypatch):
    monkeypatch.setenv("MCP_GEBRUIKERS", "mehdi")


def test_zonder_lijst_mag_iedereen_binnen(monkeypatch):
    monkeypatch.delenv("MCP_GEBRUIKERS", raising=False)
    assert _mag_binnen("wie-dan-ook")


@pytest.mark.parametrize("naam", ["mehdi", "Mehdi", " mehdi "])
def test_mehdi_komt_binnen(naam, alleen_mehdi):
    assert _mag_binnen(naam)


@pytest.mark.parametrize("naam", [
    "akadmin", "shaniel", "angela", "siyan", "marise",
    "mehdi2", "mehdiX", "", "   ", "admin",
])
def test_de_rest_komt_er_niet_in(naam, alleen_mehdi):
    assert not _mag_binnen(naam)


def test_wie_op_de_lijst_staat_mag_ook_schrijven(alleen_mehdi):
    """Anders zou Mehdi ook nog in een schrijfgroep moeten zitten."""
    assert _mag_schrijven([], "mehdi")
    assert not _mag_schrijven(["admin"], "siyan")   # groep helpt niet meer


def test_lijst_leest_meerdere_namen(monkeypatch):
    monkeypatch.setenv("MCP_GEBRUIKERS", "mehdi, akadmin;Siyan")
    for naam in ("mehdi", "akadmin", "siyan"):
        assert _mag_binnen(naam)
    assert not _mag_binnen("angela")


# ---- Wat Claude te zien krijgt -------------------------------------------
def test_elk_gereedschap_eist_een_firma():
    """De enige uitzondering is 'firmas', dat juist de keuzes opsomt."""
    for t in TOOLS:
        schema = t["inputSchema"]
        if t["name"] == "firmas":
            assert "firma" not in (schema.get("properties") or {})
            continue
        assert "firma" in schema["required"], t["name"]
        veld = schema["properties"]["firma"]
        assert veld["enum"] == list(FIRMAS), t["name"]


def test_beschrijvingen_dragen_de_regel_uit():
    """Claude leest deze teksten; hierin staat dat de firma gevraagd wordt."""
    for t in TOOLS:
        if t["name"] == "firmas":
            continue
        assert "vraag" in t["description"].lower(), t["name"]


def test_schrijvend_gereedschap_waarschuwt():
    """Wat de rechtencontrole als schrijvend ziet, moet dat ook zeggen."""
    schrijvend = [t for t in TOOLS if t["name"] in gs.SCHRIJVEND]
    assert len(schrijvend) == len(gs.SCHRIJVEND) == 10
    for t in schrijvend:
        assert "wijzigt gegevens" in t["description"], t["name"]


def test_aangeboden_gereedschap_bestaat_ook_echt():
    """Elk stuk gereedschap in de lijst moet uitvoerbaar zijn, en omgekeerd."""
    aangeboden = {t["name"] for t in TOOLS} - {"firmas"}
    assert aangeboden == set(gs.UITVOERING)
