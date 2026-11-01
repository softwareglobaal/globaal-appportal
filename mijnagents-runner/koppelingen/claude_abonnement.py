"""Claude via het abonnement van Mehdi, niet via de API-sleutel (Mehdi 01-11-2026: "de agent mag niet apart geld en
token en API kosten ... moet mijn claude account gebruiken").

De agent start Claude Code zonder scherm (`claude -p`) met het langlevende token van `claude setup-token` (een jaar
geldig), uit ~/appportal/.env onder de naam CLAUDE_CODE_OAUTH_TOKEN. `claude -p` kiest een API-sleutel boven die login;
daarom krijgt het kindproces alleen een korte lijst gewone variabelen en het token, nooit ANTHROPIC_API_KEY of een
ander geheim. Zonder token start niets: nooit terugvallen op de API.

Claude Code draait in een lege tijdelijke map, zonder CLAUDE.md, skills, hooks of MCP-servers (--safe-mode,
--restricted, --strict-mcp-config) en met alleen het gereedschap dat de oproep noemt. De waarde van het token komt nooit
in een log of een foutmelding.
"""
import json
import os
import shutil
import subprocess
import tempfile

from sleutelbron import BRON, waarde

TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
DOORLATEN = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "USER", "LOGNAME", "SHELL", "TMPDIR")
MODEL = os.environ.get("ABONNEMENT_MODEL", "opus")
AANMELDEN_NOOD = ("Claude op de VM is niet aangemeld met je abonnement: dubbelklik op de Mac "
                  "mijnagents-runner/mac/abonnement_aanmelden.command en meld je aan met je Claude-account")
AANMELDEN = ("invalid api key", "/login", "oauth", "authentication", "not logged in", "401", "unauthorized")


class Fout(RuntimeError):
    """Claude via het abonnement gaf geen bruikbaar antwoord. aanmelden: het token ontbreekt of wordt geweigerd; dan
    moet Mehdi opnieuw aanmelden (mac/abonnement_aanmelden.command)."""

    def __init__(self, tekst, aanmelden=False):
        super().__init__(tekst)
        self.aanmelden = aanmelden


def claude_pad():
    return shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")


def omgeving(token):
    """De omgeving van het kindproces: alleen DOORLATEN en het token. Geen API-sleutel, geen ander geheim."""
    env = {k: os.environ[k] for k in DOORLATEN if os.environ.get(k)}
    env[TOKEN] = token
    env["DISABLE_AUTOUPDATER"] = "1"
    return env


def opdracht(systeem, tools=(), model=MODEL, max_beurten=25):
    lijst = ",".join(tools)
    cmd = [claude_pad(), "-p", "--safe-mode", "--restricted", "--strict-mcp-config", "--no-session-persistence",
           "--tools", lijst, "--model", model, "--system-prompt", systeem,
           "--output-format", "stream-json", "--verbose", "--max-turns", str(max_beurten)]
    if lijst:
        cmd += ["--allowedTools", lijst]
    return cmd


def lees_stroom(uitvoer):
    """{tekst, gereedschap: [(naam, invoer)], tokens, beurten, stop, model, fout} uit de stream-json van `claude -p`."""
    gereedschap, resultaat, model = [], None, None
    for regel in (uitvoer or "").splitlines():
        try:
            d = json.loads(regel)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        if d.get("type") == "system" and d.get("model"):
            model = d["model"]
        elif d.get("type") == "assistant":
            for b in (d.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    gereedschap.append((b.get("name"), b.get("input") or {}))
        elif d.get("type") == "result":
            resultaat = d
    if resultaat is None:
        return {"tekst": "", "gereedschap": gereedschap, "tokens": 0, "beurten": 0, "stop": "geen antwoord",
                "model": model, "fout": "geen eindresultaat"}
    gebruik = resultaat.get("usage") or {}
    tokens = sum(int(gebruik.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                                     "cache_read_input_tokens"))
    fout = None
    if resultaat.get("is_error") or resultaat.get("subtype") != "success":
        fout = str(resultaat.get("result") or resultaat.get("subtype") or "fout")[:300]
    return {"tekst": str(resultaat.get("result") or ""), "gereedschap": gereedschap, "tokens": tokens,
            "beurten": int(resultaat.get("num_turns") or 0), "stop": resultaat.get("subtype"), "model": model, "fout": fout}


def _aanmelden(tekst):
    laag = str(tekst or "").lower()
    return any(w in laag for w in AANMELDEN)


def vraag(systeem, gebruiker, tools=(), model=MODEL, timeout=420, max_beurten=25, bestanden=None, bron=BRON):
    """Een vraag aan Claude op het abonnement. tools: namen uit Claude Code (WebSearch, WebFetch, Read). bestanden:
    {naam: bytes} die in de lege werkmap komen (voor Read). Geeft lees_stroom(); een Fout als er geen antwoord is."""
    token = waarde(bron, TOKEN)
    if not token:
        raise Fout(f"geen {TOKEN} in {bron}", aanmelden=True)
    with tempfile.TemporaryDirectory(prefix="claude-abonnement-") as werkmap:
        for naam, data in (bestanden or {}).items():
            with open(os.path.join(werkmap, os.path.basename(naam)), "wb") as f:
                f.write(data)
        try:
            p = subprocess.run(opdracht(systeem, tools, model, max_beurten), input=gebruiker, capture_output=True,
                               text=True, timeout=timeout, cwd=werkmap, env=omgeving(token))
        except subprocess.TimeoutExpired:
            raise Fout(f"geen antwoord binnen {int(timeout)} s") from None
        except OSError as e:
            raise Fout(f"Claude Code niet te starten ({type(e).__name__})") from None
    uit = lees_stroom(p.stdout)
    if uit["fout"] or p.returncode:
        reden = uit["fout"] or (p.stderr or "").strip()[-300:] or f"code {p.returncode}"
        raise Fout(f"Claude via het abonnement: {reden.replace(token, '[token]')}", aanmelden=_aanmelden(reden))
    return uit
