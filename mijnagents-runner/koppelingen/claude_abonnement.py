"""Claude via het abonnement van Mehdi, niet via de API-sleutel (Mehdi 01-11-2026: "de agent mag niet apart geld en
token en API kosten ... moet mijn claude account gebruiken").

De agent start Claude Code zonder scherm (`claude -p`) met het langlevende token van `claude setup-token` (een jaar
geldig), uit ~/appportal/.env onder de naam CLAUDE_CODE_OAUTH_TOKEN. Zonder token start niets: nooit terugvallen op de
API. Drie grendels tegen aparte kosten (Codex, controle 17):
  - het kindproces krijgt alleen een korte lijst gewone variabelen en het token, nooit ANTHROPIC_API_KEY of een ander
    geheim, en een eigen lege HOME en configuratiemap: geen instellingen, apiKeyHelper of opgeslagen login van de
    server telt mee;
  - meldt Claude Code bij de start een andere bron dan het abonnement (apiKeySource niet "none"), dan stopt de code het
    proces voor er een vraag vertrekt;
  - meldt het abonnement extra verbruik (isUsingOverage) of een bereikte limiet, dan stopt de code het proces meteen:
    hoogstens die ene beurt valt buiten het abonnement. Op 01-11-2026 stond extra verbruik op het account aan
    (overageStatus "allowed"); uitzetten kan alleen Mehdi in zijn account.

Claude Code draait in een lege tijdelijke map, zonder CLAUDE.md, skills, hooks of MCP-servers (--safe-mode,
--restricted, --strict-mcp-config) en met alleen het gereedschap dat de oproep noemt. Het token staat alleen in de
omgeving van dat ene kindproces (leesbaar voor dezelfde gebruiker, zoals ~/appportal/.env zelf), nooit in een log of een
foutmelding.
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading

from sleutelbron import BRON, waarde

TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
DOORLATEN = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "USER", "LOGNAME", "SHELL")
MODEL = os.environ.get("ABONNEMENT_MODEL", "opus")
AANMELDEN_NOOD = ("Claude op de VM is niet aangemeld met je abonnement: dubbelklik op de Mac "
                  "mijnagents-runner/mac/abonnement_aanmelden.command en meld je aan met je Claude-account")
LIMIET_NOOD = "Je Claude-abonnement zit aan zijn limiet: de agents wachten tot het weer kan, zonder extra verbruik"
AANMELDEN = ("invalid api key", "/login", "oauth", "authentication", "not logged in", "401", "unauthorized")


class Fout(RuntimeError):
    """Claude via het abonnement gaf geen bruikbaar antwoord. aanmelden: het token ontbreekt of wordt geweigerd; dan
    moet Mehdi opnieuw aanmelden (mac/abonnement_aanmelden.command). limiet: het abonnement zit aan zijn limiet of zou
    extra verbruik vragen; dan wacht de vraag."""

    def __init__(self, tekst, aanmelden=False, limiet=False):
        super().__init__(tekst)
        self.aanmelden = aanmelden
        self.limiet = limiet


def claude_pad():
    return shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")


def omgeving(token, thuis):
    """De omgeving van het kindproces: alleen DOORLATEN, een eigen lege HOME en het token. Geen API-sleutel, geen ander
    geheim, geen instellingen of login uit de echte HOME."""
    env = {k: os.environ[k] for k in DOORLATEN if os.environ.get(k)}
    env.update({"HOME": thuis, "CLAUDE_CONFIG_DIR": os.path.join(thuis, ".claude"),
                "XDG_CONFIG_HOME": os.path.join(thuis, ".config"), "TMPDIR": thuis, TOKEN: token,
                "DISABLE_AUTOUPDATER": "1"})
    if not env.get("PATH"):
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    return env


def opdracht(systeem, tools=(), model=MODEL, max_beurten=25):
    lijst = ",".join(tools)
    cmd = [claude_pad(), "-p", "--safe-mode", "--restricted", "--strict-mcp-config", "--no-session-persistence",
           "--tools", lijst, "--model", model, "--system-prompt", systeem,
           "--output-format", "stream-json", "--verbose", "--max-turns", str(max_beurten)]
    if lijst:
        cmd += ["--allowedTools", lijst]
    return cmd


def bewaking(regel, staat, max_gereedschap=None):
    """De reden om Claude Code meteen te stoppen, of None. staat: {"gereedschap": aantal} over de regels heen."""
    try:
        d = json.loads(regel)
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    if d.get("type") == "system" and d.get("subtype") == "init":
        bron = d.get("apiKeySource")
        if bron != "none":
            return f"Claude zou niet op het abonnement draaien (bron {bron}): gestopt voor de eerste vraag"
    elif d.get("type") == "rate_limit_event":
        info = d.get("rate_limit_info") or {}
        if info.get("isUsingOverage"):
            return "limiet: het abonnement zou extra verbruik aanrekenen"
        if info.get("status") not in (None, "allowed", "allowed_warning"):
            return f"limiet: het abonnement staat op {info.get('status')}"
    elif d.get("type") == "assistant":
        for b in (d.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                staat["gereedschap"] = staat.get("gereedschap", 0) + 1
        if max_gereedschap and staat.get("gereedschap", 0) > max_gereedschap:
            return f"meer dan {max_gereedschap} zoek- of leesbeurten: gestopt"
    return None


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


def _stop(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)       # ook de kindprocessen van Claude Code
    except OSError:
        try:
            p.kill()
        except OSError:
            pass


def draai(cmd, invoer, timeout, cwd, env, max_gereedschap=None):
    """(stdout, stderr, returncode, stopreden): Claude Code met bewaking per regel; bij een reden of na de timeout
    stopt de code het hele proces."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd,
                         env=env, start_new_session=True)
    uit, fout, staat, reden = [], [], {}, []

    def lees():
        for regel in p.stdout:
            uit.append(regel)
            r = None if reden else bewaking(regel, staat, max_gereedschap)
            if r:
                reden.append(r)
                _stop(p)

    lezers = [threading.Thread(target=lees, daemon=True),
              threading.Thread(target=lambda: fout.extend(p.stderr), daemon=True)]
    for t in lezers:
        t.start()
    try:
        p.stdin.write(invoer)
        p.stdin.close()
    except OSError:
        pass
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        reden.append(reden[0] if reden else f"geen antwoord binnen {int(timeout)} s")
        _stop(p)
        p.wait()
    for t in lezers:
        t.join(5)
    return "".join(uit), "".join(fout), p.returncode, (reden[0] if reden else None)


def _aanmelden(tekst):
    laag = str(tekst or "").lower()
    return any(w in laag for w in AANMELDEN)


def vraag(systeem, gebruiker, tools=(), model=MODEL, timeout=420, max_beurten=25, bestanden=None, bron=BRON,
          max_gereedschap=None):
    """Een vraag aan Claude op het abonnement. tools: namen uit Claude Code (WebSearch, WebFetch, Read). bestanden:
    {naam: bytes} die in de lege werkmap komen (voor Read). max_gereedschap: harde grens op het aantal oproepen van
    gereedschap. Geeft lees_stroom(); een Fout als er geen antwoord is of als een grendel het proces stopte."""
    token = waarde(bron, TOKEN)
    if not token:
        raise Fout(f"geen {TOKEN} in {bron}", aanmelden=True)
    with tempfile.TemporaryDirectory(prefix="claude-abonnement-") as werkmap, \
            tempfile.TemporaryDirectory(prefix="claude-thuis-") as thuis:
        for naam, data in (bestanden or {}).items():
            with open(os.path.join(werkmap, os.path.basename(naam)), "wb") as f:
                f.write(data)
        try:
            stdout, stderr, code, reden = draai(opdracht(systeem, tools, model, max_beurten), gebruiker, timeout, werkmap,
                                                omgeving(token, thuis), max_gereedschap)
        except OSError as e:
            raise Fout(f"Claude Code niet te starten ({type(e).__name__})") from None
    if reden:
        raise Fout(f"Claude via het abonnement: {reden}", limiet=reden.startswith("limiet"))
    uit = lees_stroom(stdout)
    if uit["fout"] or code:
        reden = uit["fout"] or (stderr or "").strip()[-300:] or f"code {code}"
        raise Fout(f"Claude via het abonnement: {reden.replace(token, '[token]')}", aanmelden=_aanmelden(reden))
    return uit
