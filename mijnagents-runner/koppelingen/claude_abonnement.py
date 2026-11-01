"""Claude via het abonnement van Mehdi, niet via de API-sleutel (Mehdi 01-11-2026: "de agent mag niet apart geld en
token en API kosten ... moet mijn claude account gebruiken").

De agent start Claude Code zonder scherm (`claude -p`) met het langlevende token van `claude setup-token` (een jaar
geldig). Het token staat op een plek voor alle agents: ~/.config/prijsonderzoeker/claude-token (map 700, bestand 600),
dezelfde als De Prijsonderzoeker (aankoop/onderzoek.py, TOKEN_BESTAND), zodat Mehdi een keer aanmeldt. Zonder token
start niets: nooit terugvallen op de API. Grendels tegen aparte kosten (Codex, controle 17 en 18):
  - het kindproces krijgt alleen een korte lijst gewone variabelen en het token, nooit ANTHROPIC_API_KEY of een ander
    geheim, en een eigen lege HOME en configuratiemap: geen instellingen, apiKeyHelper of opgeslagen login van de
    server telt mee;
  - voor elke vraag zegt `claude auth status` (zonder model, zonder kosten) in precies die omgeving hoe Claude Code zou
    aanmelden; alleen "oauth_token" bij Anthropic zelf mag (gemeten 01-11-2026: met een API-sleutel zegt het "api_key");
    anders start er niets;
  - meldt Claude Code bij de start toch een andere bron (apiKeySource niet "none"), dan stopt de code het proces meteen;
  - meldt het abonnement extra verbruik (isUsingOverage), een waarschuwing of een bereikte limiet, dan stopt de code het
    proces meteen en onthoudt ze dat tot het venster voorbij is (LIMIET_BESTAND): de volgende vraag start dan niet. Op
    01-11-2026 stond extra verbruik op het account aan (overageStatus "allowed"); dat het nooit een euro kost,
    garandeert alleen Mehdi door extra verbruik in zijn account uit te zetten.

Claude Code draait in een lege tijdelijke map, zonder CLAUDE.md, skills, hooks of MCP-servers (--safe-mode,
--restricted, --strict-mcp-config) en met alleen het gereedschap dat de oproep noemt. Het token staat alleen in de
omgeving van dat ene kindproces (leesbaar voor dezelfde gebruiker, zoals het tokenbestand zelf), nooit in een log of een
foutmelding.
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time

import re

TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
TOKEN_BESTAND = os.path.expanduser(os.environ.get("PRIJS_TOKEN_BESTAND", "~/.config/prijsonderzoeker/claude-token"))
BEHEERD = ("/etc/claude-code", "/Library/Application Support/ClaudeCode")
DOORLATEN = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "USER", "LOGNAME", "SHELL")
MODEL = os.environ.get("ABONNEMENT_MODEL", "opus")
AANMELDEN_NOOD = ("Claude op de VM is niet aangemeld met je abonnement: dubbelklik op de Mac "
                  "mijnagents-runner/mac/abonnement_aanmelden.command en meld je aan met je Claude-account")
LIMIET_NOOD = "Je Claude-abonnement zit aan zijn limiet: de agents wachten tot het weer kan, zonder extra verbruik"
BRON_NOOD = "Claude op de VM zou niet op het abonnement draaien: niets gestart, kijk claude_abonnement na"
LIMIET_BESTAND = os.path.expanduser(os.environ.get("ABONNEMENT_LIMIET", "~/.cache/claude-abonnement/limiet.json"))
GRENS = 0.9          # boven dit deel van een venster start de code geen nieuwe vraag (ruimte voor Mehdi zelf)
AANMELDEN = ("invalid api key", "/login", "oauth", "authentication", "not logged in", "401", "unauthorized")


class Fout(RuntimeError):
    """Claude via het abonnement gaf geen bruikbaar antwoord. soort: "aanmelden" (token ontbreekt of wordt geweigerd;
    Mehdi meldt opnieuw aan met mac/abonnement_aanmelden.command), "limiet" (limiet, waarschuwing of extra verbruik),
    "bron" (Claude Code zou niet op het abonnement draaien) of "tijd" (te weinig tijd in de ronde). Met een soort wacht de
    vraag (wacht); zonder soort is de vraag mislukt."""

    def __init__(self, tekst, soort=None):
        super().__init__(tekst)
        self.soort = soort

    aanmelden = property(lambda self: self.soort == "aanmelden")
    limiet = property(lambda self: self.soort == "limiet")
    wacht = property(lambda self: self.soort is not None)


def lees_token(bestand=None):
    """Het abonnementstoken uit het gedeelde bestand, of "" als het er niet is. Een bestand dat anderen kunnen lezen,
    telt niet (rechten 600, zoals bij De Prijsonderzoeker)."""
    bestand = bestand or TOKEN_BESTAND
    try:
        if os.stat(bestand).st_mode & 0o077:
            return ""
        with open(bestand, encoding="utf-8") as f:
            m = re.search(r"sk-ant-oat[\w-]+", f.read())
    except OSError:
        return ""
    return m.group(0) if m else ""


def beheerde_instellingen(mappen=None):
    """Beheerde instellingen van Claude Code op deze machine; die gaan voor alles en kunnen een sleutel opleggen."""
    return [os.path.join(m, n) for m in (BEHEERD if mappen is None else mappen) for n in ("managed-settings.json", "managed-settings.d", "managed-mcp.json")
            if os.path.exists(os.path.join(m, n))]


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
        staat["limiet"] = info
        return limiet_reden(info)
    elif d.get("type") == "assistant":
        for b in (d.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                staat["gereedschap"] = staat.get("gereedschap", 0) + 1
        if max_gereedschap and staat.get("gereedschap", 0) > max_gereedschap:
            return f"meer dan {max_gereedschap} zoek- of leesbeurten: gestopt"
    return None


def limiet_reden(info):
    """De reden om te stoppen of niet te starten volgens een rate_limit_info, of None. Een waarschuwing telt ook:
    Claude Code stopt dan voor het abonnement op is (Codex, controle 18)."""
    if not isinstance(info, dict):
        return None
    if info.get("isUsingOverage"):
        return "limiet: het abonnement zou extra verbruik aanrekenen"
    if info.get("status") != "allowed":          # ook een onbekende status stopt (Codex, controle 19)
        return f"limiet: het abonnement staat op {info.get('status')}"
    for naam, venster in (info.get("unifiedWindows") or {}).items():
        if isinstance(venster, dict) and float(venster.get("utilization") or 0) >= GRENS:
            return f"limiet: {int(100 * float(venster['utilization']))} procent van het venster {naam} gebruikt"
    return None


def _einde(info):
    tijden = [info.get("resetsAt")] + [v.get("resetsAt") for v in (info.get("unifiedWindows") or {}).values()
                                       if isinstance(v, dict)]
    return max([float(t) for t in tijden if t] or [0])


def onthoud_limiet(info, bestand=None):
    """True als de limiet bewaard is; False als dat niet lukt (dan start geen nieuwe vraag, zie limiet_schrijfbaar)."""
    bestand = bestand or LIMIET_BESTAND
    try:
        os.makedirs(os.path.dirname(bestand), exist_ok=True)
        with open(bestand, "w", encoding="utf-8") as f:
            json.dump({"info": info, "gezien": time.time()}, f)
        return True
    except OSError:
        return False


def limiet_schrijfbaar(bestand=None):
    """Kan de code een limiet onthouden? Zonder dat start geen vraag (Codex, controle 19 en 20): anders zou een volgende
    vraag na extra verbruik toch starten. Een echte schrijfproef: het bestand zelf moet open kunnen om te schrijven, en
    een proefbestand ernaast moet echt op schijf komen (een volle schijf of quotum valt zo op)."""
    bestand = bestand or LIMIET_BESTAND
    proef = bestand + ".proef"
    try:
        os.makedirs(os.path.dirname(bestand), exist_ok=True)
        with open(bestand, "a", encoding="utf-8"):
            pass
        with open(proef, "w", encoding="utf-8") as f:
            f.write("x" * 4096)
            f.flush()
            os.fsync(f.fileno())
        os.remove(proef)
        return True
    except OSError:
        return False


def bekende_limiet(bestand=None, nu=None):
    """De reden om niet te starten volgens de laatst geziene limiet, zolang haar venster loopt (zonder eindtijd: een
    uur); anders None."""
    try:
        with open(bestand or LIMIET_BESTAND, encoding="utf-8") as f:
            d = json.load(f) or {}
        info, gezien = d.get("info") or {}, float(d.get("gezien") or 0)
    except (OSError, ValueError, AttributeError, TypeError):
        return None
    reden = limiet_reden(info)
    return reden if reden and (nu or time.time()) < (_einde(info) or gezien + 3600) else None


def controleer_bron(env, cwd, run=subprocess.run):
    """None als `claude auth status` in precies deze omgeving het abonnementstoken van Anthropic zelf meldt; anders de
    reden. Dit roept geen model aan en kost niets. Beheerde instellingen op de machine tellen als een andere bron."""
    gevonden = beheerde_instellingen()
    if gevonden:
        return f"bron: beheerde instellingen van Claude Code gevonden ({', '.join(gevonden)})"
    try:
        p = run([claude_pad(), "auth", "status"], capture_output=True, text=True, timeout=30, cwd=cwd, env=env)
        d = json.loads(p.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return "aanmelden: de aanmelding van Claude Code is niet te lezen"
    if not d.get("loggedIn"):
        return "aanmelden: Claude Code is niet aangemeld"
    if d.get("authMethod") != "oauth_token" or d.get("apiProvider") != "firstParty" or d.get("apiKeySource"):
        return f"bron: Claude Code zou aanmelden met {d.get('authMethod')} ({d.get('apiKeySource') or d.get('apiProvider')})"
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


def draai(cmd, invoer, timeout, cwd, env, max_gereedschap=None, staat=None):
    """(stdout, stderr, returncode, stopreden): Claude Code met bewaking per regel; bij een reden of na de timeout
    stopt de code het hele proces. staat krijgt de laatst geziene limiet."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd,
                         env=env, start_new_session=True)
    uit, fout, reden = [], [], []
    staat = {} if staat is None else staat

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


def vraag(systeem, gebruiker, tools=(), model=MODEL, timeout=420, max_beurten=25, bestanden=None, bron=None,
          max_gereedschap=None):
    """Een vraag aan Claude op het abonnement. tools: namen uit Claude Code (WebSearch, WebFetch, Read). bestanden:
    {naam: bytes} die in de lege werkmap komen (voor Read). max_gereedschap: harde grens op het aantal oproepen van
    gereedschap. bron: het tokenbestand (standaard TOKEN_BESTAND). Geeft lees_stroom(); een Fout als er geen antwoord
    is of als een grendel het proces stopte."""
    token = lees_token(bron)
    if not token:
        raise Fout(f"geen abonnementstoken in {bron or TOKEN_BESTAND} (rechten 600)", "aanmelden")
    if not limiet_schrijfbaar():
        raise Fout(f"Claude via het abonnement: de limiet is niet te onthouden in {LIMIET_BESTAND}", "bron")
    gekend = bekende_limiet()
    if gekend:
        raise Fout(f"Claude via het abonnement: {gekend} (nog niet voorbij)", "limiet")
    staat = {}
    with tempfile.TemporaryDirectory(prefix="claude-abonnement-") as werkmap, \
            tempfile.TemporaryDirectory(prefix="claude-thuis-") as thuis:
        env = omgeving(token, thuis)
        reden = controleer_bron(env, werkmap)
        if reden:
            soort, _, tekst = reden.partition(": ")
            raise Fout(f"Claude via het abonnement: {tekst}", soort)
        for naam, data in (bestanden or {}).items():
            with open(os.path.join(werkmap, os.path.basename(naam)), "wb") as f:
                f.write(data)
        try:
            stdout, stderr, code, reden = draai(opdracht(systeem, tools, model, max_beurten), gebruiker, timeout, werkmap,
                                                env, max_gereedschap, staat)
        except OSError as e:
            raise Fout(f"Claude Code niet te starten ({type(e).__name__})") from None
    if staat.get("limiet") is not None and not onthoud_limiet(staat["limiet"]) and limiet_reden(staat["limiet"]):
        raise Fout("Claude via het abonnement: limiet gezien maar niet te onthouden", "limiet")
    if reden:
        soort = "limiet" if reden.startswith("limiet") else "bron" if "abonnement draaien" in reden else None
        raise Fout(f"Claude via het abonnement: {reden}", soort)
    uit = lees_stroom(stdout)
    if uit["fout"] or code:
        reden = uit["fout"] or (stderr or "").strip()[-300:] or f"code {code}"
        raise Fout(f"Claude via het abonnement: {reden.replace(token, '[token]')}",
                   "aanmelden" if _aanmelden(reden) else None)
    return uit
