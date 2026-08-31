"""Tests op de koppeling: waar mag de autorisatiecode naartoe.

Een te ruime `_redirect_ok` betekent dat een vreemde site de code van een
ingelogde collega kan opvangen en daarmee in diens werkruimte kan. Een te
strakke betekent dat Claude Code op een werkplek niet kan koppelen -- daar liep
het op 31-08-2026 op vast.

Draaien:  cd renovision-mcp && python -m pytest test_koppeling.py -q
"""
import pytest

from mcp_server import _redirect_ok


@pytest.mark.parametrize("uri", [
    # claude.ai in de browser
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    "https://console.anthropic.com/callback",
    # Claude Code op een werkplek: willekeurige poort op de eigen machine
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
