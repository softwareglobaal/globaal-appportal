#!/usr/bin/env python3
"""Wisgrendel (driehoeksoverleg 27-10-2026, punten L5 en M6, goedgekeurd door Mehdi): wissen op de agenda van Lara en
wissen in een reeks houdt Claude Code tegen voor het gebeurt.

Een Claude Code-hook voor PreToolUse, naast regels_vooraf.py. Die zet alleen regels voor Claude; deze weigert echt.
Geweigerd wordt:
- een delete_event van een agenda-MCP op een afspraak uit een reeks (het ID eindigt op _JJJJMMDD of
  _JJJJMMDDTUUMMSSZ), op welke agenda ook;
- een delete_event op de agenda van Lara, behalve een eigen rit van de Agendawacht (rit en 32 hexadecimale tekens,
  zoals _nieuwe_rit in agenda_wacht.py ze maakt);
- een update_event die de status op 'cancelled' zet, op de agenda van Lara (zelfde uitzondering) of op een afspraak
  uit een reeks;
- een Bash-opdracht die in een agenda wist (DELETE, events().delete of status 'cancelled') en recurringEventId noemt,
  een afspraak uit een reeks, of de agenda van Lara met een ID dat geen eigen rit is;
- een Bash-opdracht die in een agenda wist zonder dat agenda en ID letterlijk in de opdracht staan: een variabele,
  $(...) of een onbekende agenda faalt dicht, ook op de werkagenda (Codex-controle 27-10-2026, punt 5);
- een wisopdracht met een ondoorzichtig doel ("$URL", $(cat url.txt), backticks, of in code een variabele als URL)
  als de opdracht ergens een agenda of Google noemt. Elk wisdoel telt apart: een veilige letterlijke URL elders in de
  opdracht (een echo na de ;) dekt een ondoorzichtig doel niet af (Codex-hertest 27-10-2026, punt 4).
Een geneste opdracht (de tekst na bash, sh of zsh -c, na eval, of
een shellscript dat zelf iets draait) krijgt dezelfde controle, tot drie lagen diep; dieper weigert de grendel zodra er
iets in staat dat wist, een agenda noemt of verder iets draait (Codex-hertest 2, 27-10-2026, punt 6).
Wissen is: DELETE (ook "method": "DELETE"), .delete( op een agenda-object, status cancelled (ook status='cancelled'),
/batch/calendar en events/<id>/move. Draait de opdracht een eigen script (python3, node, bash of sh met een bestand,
ook via bash < wis.sh, cat wis.sh | sh, source of . en ./script.sh) of stuurt ze een bestand mee (-d @body.json), dan kijkt de grendel dat bestand mee na als het bestaat en
kleiner is dan 200 kB; niet te lezen is niet blokkeren. Een script dat ongewijzigd in git staat (agenda_wacht.py, de
tests) is nagekeken code met eigen grendels en telt niet. Zonder agenda (calendarId) werkt de MCP op de primaire agenda,
en die is niet van Lara. Een wisopdracht zonder agenda en zonder Google (bv. gh api -X DELETE) laat de grendel door. De
eigen ritopruiming van de Agendawacht draait in Python op de VM, buiten Claude Code, en valt hier niet onder.

Het ID van Lara komt uit werkwijze/agenda-taken.json (de agenda met rol 'lara'); een tweede kopie staat nergens. Is het
niet te lezen, dan telt elke genoemde agenda als die van Lara. Kapotte invoer, een ander moment dan PreToolUse of iets
anders dan wissen: geen uitvoer en exitcode 0. Het script leest alleen, gaat niet op het net en vraagt git hoogstens of
een script ongewijzigd is vastgelegd. De grendel is tests/test_wisgrendel.py.

Aanzetten met een omhulsel dat nooit exitcode 2 geeft als dit bestand ontbreekt (zie AANZETTEN hieronder en
werkwijze/agenda-wacht.md): een kaal python3-pad naar een ontbrekend script blokkeert elke Bash- en MCP-opdracht.
"""
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
TAKEN = HIER.parent / "werkwijze" / "agenda-taken.json"
AANZETTEN = ("sh -c '[ -f \"$HOME/dev/globaal-appportal/mijnagents-runner/claude-hooks/wisgrendel.py\" ] && exec python3 "
             "\"$HOME/dev/globaal-appportal/mijnagents-runner/claude-hooks/wisgrendel.py\"; exit 0'")
MAX_BESTAND = 200_000

RIT_ID = re.compile(r"rit[0-9a-f]{32}")              # volledig: een eigen rit van de Agendawacht (_nieuwe_rit)
REEKS_ID = re.compile(r"_\d{8}(T\d{6}Z)?$")           # een afspraak uit een reeks: ID_JJJJMMDD of ID_JJJJMMDDTUUMMSSZ
MCP_WIS = re.compile(r"^mcp__.+__delete_event$")
MCP_WIJZIG = re.compile(r"^mcp__.+__update_event$")
BASH_WIS = re.compile(r"""-X\s*["']?DELETE|--request[ =]["']?DELETE|method\\?["']?\s*[:=]\s*\\?["']DELETE"""
                      r"""|\.request\(\s*["']DELETE["']|\b(requests|httpx)\.delete\b"""
                      r"""|\b(?:\w*calendar\w*|events?|cal)(?:\(\))?\.delete\("""
                      r"""|status\\?["']?\]?\s*[:=]\s*\\?["']cancel|/batch/calendar|\bevents/[^\s/?'"]+/move\b""", re.I)
GOOGLE = re.compile(r"googleapis\.com|google\.com", re.I)
TOLK = re.compile(r"(?:.*/)?(?:python[\d.]*|node|bash|sh|zsh)")
SHELL = re.compile(r"(?:.*/)?(?:bash|sh|zsh|dash)")
C_OPTIE = re.compile(r"-[A-Za-z]*[cm][A-Za-z]*")         # -c, -lc, -ec (en -m bij python): geen scriptbestand erna
CAT_UITVOER = re.compile(r"""(?:\beval|\b(?:source|bash|sh|zsh|dash|python[\d.]*|node)(?:\s+-\w+)*|(?:^|[\s;&|(])\.)"""
                         r"""\s+["']?(?:\$\(|`|<\()\s*cat\s+([^\s)`"';&|]+)""")
HEEL_CAT = re.compile(r"""\s*["']?(?:\$\(|`)\s*cat\s+([^\s)`"';&|]+)\s*(?:\)|`)["']?\s*""")
GENEST_MAX = 3
DRAAIT = re.compile(r"\b(?:source|eval|bash|sh|zsh|dash|python[\d.]*|node)\b|(?:^|[\s;&|(])\.\s")
SCRIPT = (".py", ".sh", ".js", ".mjs", ".cjs", ".bash", ".zsh")
VOORWOORD = {"sudo", "env", "exec", "time", "nohup", "command"}
OPERATOR = set(";&|()<>")
SCHEIDING = set(";&|()")                              # tussen twee opdrachten; < en > zijn omleidingen
WAARDE_OPTIES = {"-H", "--header", "-u", "--user", "-o", "--output", "-A", "--user-agent", "-b", "--cookie", "-c",
                 "--cookie-jar", "-e", "--referer", "-w", "--write-out", "-m", "--max-time", "--connect-timeout",
                 "--retry", "--oauth2-bearer", "-d", "--data", "--data-binary", "--data-raw", "--data-urlencode",
                 "--json", "-F", "--form", "-X", "--request"}
CODE_DOEL = re.compile(r"""\b(?:requests|httpx|session|client|s)\.delete\(\s*([^,)]*)"""
                       r"""|Request\(\s*([^,)]*),[^)]*method\s*=\s*\\?["']DELETE"""
                       r"""|\.request\(\s*\\?["']DELETE\\?["']\s*,\s*([^,)]*)"""
                       r"""|\bfetch\(\s*([^,)]*),[^)]*DELETE""", re.I)
LETTERLIJKE_URL = re.compile(r"""[rbu]?["'`]https?://[^"'`{}$]*["'`]""")
PAD_DEEL = r"""([^\s/?'"\\#&;|<>()]*)"""         # tot de volgende / ? of spatie; een $ of { blijft erin staan
AGENDA_IN_PAD = re.compile(r"\bcalendars/" + PAD_DEEL)
ID_IN_PAD = re.compile(r"\bevents/" + PAD_DEEL)


def _veld(naam):
    """naam=waarde of "naam": "waarde"; groep 1 is het aanhalingsteken (leeg: een variabele), groep 2 de waarde."""
    return re.compile(r"(?i:" + naam + r""")\\?["']?\s*[=:]\s*(\\?["']?)([^\s,)"'\\;&|]*)""")


AGENDA_IN_VELD = _veld("calendar_?id")
ID_IN_VELD = _veld("event_?id")
AGENDA_WOORD = re.compile(r"calendar|\bevents/|events\(\)|event_?id", re.I)
LETTERLIJKE_AGENDA = re.compile(r"[A-Za-z0-9._%@+-]+")
SCHOON_ID = re.compile(r"[A-Za-z0-9_]+")
RIT_TIP = (": gebruik het letterlijke rit-ID. De eigen ritopruiming van de Agendawacht draait in Python op de VM en valt "
           "hier niet onder")

REDEN = ("Wisgrendel: markeer, wis niet. Afspraken op de agenda van Lara en afspraken uit een reeks worden nooit gewist "
         "(Mehdi, driehoeksoverleg 27-10-2026, L5 en M6). Zet 'vervalt (vakantie)' vooraan in de titel en zet de afspraak "
         "op Beschikbaar, en dat pas na Mehdi's ja. Alleen een eigen rit van de Agendawacht (ID rit en 32 hexadecimale "
         "tekens) mag weg.")


def lara_id(pad=TAKEN):
    """Het hexadecimale deel (64 tekens) van het adres van Lara in agenda-taken.json, of None. Zo vangt de grendel
    zowel ...@group.calendar.google.com als ...%40group.calendar.google.com."""
    try:
        taken = json.loads(Path(pad).read_text(encoding="utf-8"))
        adres = next(a["adres"] for a in taken["agendas"] if a.get("rol") == "lara")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        return None
    m = re.match(r"([0-9a-f]{64})@", str(adres).lower())
    return m.group(1) if m else None


def _geannuleerd(x):
    """Zet deze invoer ergens de status op 'cancelled'?"""
    if isinstance(x, dict):
        return any((k == "status" and isinstance(v, str) and v.strip().lower() in ("cancelled", "canceled"))
                   or _geannuleerd(v) for k, v in x.items())
    if isinstance(x, list):
        return any(_geannuleerd(v) for v in x)
    return False


def _lara_oorzaak(lara, waarom="en is geen eigen rit"):
    if lara:
        return f"de afspraak staat op de agenda van Lara {waarom}"
    return (f"de afspraak staat misschien op de agenda van Lara {waarom} (haar ID is niet te lezen uit "
            "werkwijze/agenda-taken.json, dus telt elke genoemde agenda als de hare)")


def _mcp(naam, ti, pad):
    wis = bool(MCP_WIS.match(naam))
    if not isinstance(ti, dict) or not (wis or (MCP_WIJZIG.match(naam) and _geannuleerd(ti))):
        return None
    kal = str(ti.get("calendarId") or ti.get("calendar_id") or "").lower()
    eid = str(ti.get("eventId") or ti.get("event_id") or "")
    if REEKS_ID.search(eid):
        return f"het ID {eid} is een afspraak uit een reeks"
    lara = lara_id(pad)
    op_lara = (lara in kal) if lara else bool(kal) and kal != "primary"
    if op_lara and not RIT_ID.fullmatch(eid):
        return _lara_oorzaak(lara)
    return None


def _waarden(in_pad, in_veld, cmd):
    """Alle agenda's of ID's die de opdracht noemt; een veld zonder aanhalingstekens is een variabele en telt als '$'."""
    return in_pad.findall(cmd) + [w if q else "$" for q, w in in_veld.findall(cmd)]


def _woorden(cmd):
    """De woorden van een shellopdracht; een onvolledig aanhalingsteken valt terug op spaties en operatoren."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split, lex.commenters = True, ""
        return list(lex)
    except ValueError:
        return [w.strip("\"'") for w in re.findall(r"[^\s;&|()<>]+|[;&|()<>]+", cmd)]


def _segmenten(woorden):
    """De losse opdrachten (gescheiden door ; && || | & of haakjes), elk met de scheiding die erna komt."""
    stuk = []
    for w in woorden:
        if w and set(w) <= SCHEIDING:
            if stuk:
                yield stuk, w
            stuk = []
        else:
            stuk.append(w)
    if stuk:
        yield stuk, ""


def _pad(woord, basis):
    if not woord or "$" in woord or "`" in woord:
        return None
    p = Path(os.path.expanduser(woord))
    return p if p.is_absolute() else basis / p


def _lees(p):
    try:
        if p and p.is_file() and p.stat().st_size <= MAX_BESTAND:
            return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return None


def _bestanden(cmd, woorden, cwd):
    """De scripts die de opdracht draait en de bestanden die ze meestuurt (-d @body.json), als paden. Een script draait
    ook via een omleiding (bash < wis.sh), een pijp (cat wis.sh | sh), source of . (Codex-hertest 27-10-2026, punt 3)."""
    basis = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    scripts, data, vorige_cat, vorige_scheiding = [], [], None, ""
    for stuk, scheiding in _segmenten(woorden):
        k = 0
        while k < len(stuk) and (stuk[k] in VOORWOORD or re.fullmatch(r"\w+=\S*", stuk[k])):
            k += 1
        kop, arg = (stuk[k] if k < len(stuk) else ""), (stuk[k + 1] if k + 1 < len(stuk) else "")
        if kop == "cd" and arg:
            basis = _pad(arg, basis) or basis
        if kop in ("source", ".") and arg:
            scripts.append(_pad(arg, basis))
        elif kop.startswith(("./", "../", "/", "~/")) and kop.endswith(SCRIPT):
            scripts.append(_pad(kop, basis))
        tolk = next((i for i, w in enumerate(stuk) if TOLK.fullmatch(w)), None)
        if tolk is not None:
            j = tolk + 1
            while j < len(stuk) and stuk[j].startswith("-") and stuk[j] != "-" and not C_OPTIE.fullmatch(stuk[j]):
                j += 1
            if j < len(stuk) and not set(stuk[j]) <= OPERATOR and not stuk[j].startswith("-"):
                scripts.append(_pad(stuk[j], basis))
            scripts += [_pad(stuk[i + 1], basis) for i in range(tolk, len(stuk) - 1) if stuk[i] == "<"]
            if vorige_scheiding == "|" and vorige_cat:
                scripts.append(vorige_cat)
        for i, w in enumerate(stuk):
            volgend = stuk[i + 1] if i + 1 < len(stuk) else ""
            if w in ("-d", "--data", "--data-binary", "--json") and volgend.startswith("@"):
                data.append(_pad(volgend[1:], basis))
            m = re.match(r"(?:-d|--data=|--data-binary=|--json=)@(.+)", w)
            if m:
                data.append(_pad(m.group(1), basis))
        vorige_cat = _pad(arg, basis) if kop == "cat" and len(stuk) == k + 2 else None
        vorige_scheiding = scheiding
    # eval "$(cat wis.sh)", bash -c "$(cat wis.sh)", source <(cat wis.sh), of een geneste opdracht die alleen $(cat x) is
    scripts += [_pad(m.group(1), basis) for m in CAT_UITVOER.finditer(cmd)]
    m = HEEL_CAT.fullmatch(cmd)
    if m:
        scripts.append(_pad(m.group(1), basis))
    return [p for p in scripts if p], [p for p in data if p]


def _genest(woorden):
    """De geneste opdrachten: de tekst na bash, sh of zsh -c (ook -lc, -ec) en alles na eval."""
    uit = []
    for stuk, _ in _segmenten(woorden):
        for i, w in enumerate(stuk):
            if w == "eval" and i + 1 < len(stuk):
                uit.append(" ".join(stuk[i + 1:]))
                break
            if SHELL.fullmatch(w):
                for j in range(i + 1, len(stuk) - 1):
                    if not stuk[j].startswith("-"):
                        break
                    if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", stuk[j]):
                        uit.append(stuk[j + 1])
                        break
    return uit


def _shellscript(p, inhoud):
    """Draait dit bestand als shell (geen .py of .js, en geen python- of node-shebang)?"""
    eerste = inhoud.split("\n", 1)[0]
    return p.suffix.lower() not in (".py", ".js", ".mjs", ".cjs", ".ts") and not (
        eerste.startswith("#!") and re.search(r"python|node", eerste))


def _git(d, *args):
    return subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, timeout=5)


def _vastgelegd(p):
    """Staat dit script ongewijzigd in git, in deze repo (of een werkboom ervan)? Dan is het nagekeken code met eigen
    grendels en CI (agenda_wacht.py, de tests). Een script in een andere of geen repo telt nooit als nagekeken."""
    try:
        d = str(p.resolve().parent)
        gemeen = []
        for map_ in (str(HIER), d):
            r = _git(map_, "rev-parse", "--git-common-dir")
            if r.returncode:
                return False
            gemeen.append((Path(map_) / r.stdout.strip()).resolve())
        if gemeen[0] != gemeen[1] or _git(d, "ls-files", "--error-unmatch", "--", p.name).returncode:
            return False
        return _git(d, "diff", "--quiet", "HEAD", "--", p.name).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _ondoorzichtig(tekst):
    """Een wisdoel dat niet te lezen is: per losse opdracht een woord dat met $ of een backtick begint (geen waarde van
    -H, -d en dergelijke, en zonder calendars/ erin), of in code een delete-aanroep met een variabele als URL."""
    for stuk, _ in _segmenten(_woorden(tekst)):
        if not BASH_WIS.search(" ".join(stuk)):
            continue
        for i, w in enumerate(stuk):
            if not (i and stuk[i - 1] in WAARDE_OPTIES) and w.startswith(("$", "`")) and "calendars/" not in w:
                return w
    for m in CODE_DOEL.finditer(tekst):
        doel = next(g for g in m.groups() if g is not None).strip()
        if "calendars/" not in doel and not LETTERLIJKE_URL.fullmatch(doel):
            return doel or "?"
    return None


def _toets(tekst, lara):
    """De reden om deze tekst (opdracht, eventueel met script of meegestuurd bestand) te weigeren, of None."""
    if not BASH_WIS.search(tekst):
        return None
    laag = tekst.lower()
    if "recurringeventid" in laag:
        return "de opdracht noemt recurringEventId, dus een reeks"
    agenda = bool(AGENDA_WOORD.search(tekst) or (lara and lara in laag))
    if agenda or GOOGLE.search(tekst):
        doel = _ondoorzichtig(tekst)
        if doel:
            return (f"het doel van een wisopdracht is niet te lezen ({doel[:60]}) en de opdracht noemt een agenda of "
                    "Google: schrijf de URL met agenda en ID letterlijk in die wisopdracht zelf")
    if not agenda:
        return None                                  # wist niets in een agenda (bv. gh api -X DELETE op een branch)
    agendas = _waarden(AGENDA_IN_PAD, AGENDA_IN_VELD, tekst)
    ids = _waarden(ID_IN_PAD, ID_IN_VELD, tekst)
    reeks = [i for i in ids if REEKS_ID.search(i)]
    if reeks:
        return f"het ID {reeks[0]} is een afspraak uit een reeks"
    if not agendas or not all(LETTERLIJKE_AGENDA.fullmatch(a) for a in agendas):
        return ("de agenda is niet uit de opdracht te lezen (een variabele, $(...) of geen agenda), dus niet na te kijken "
                "of het die van Lara is: schrijf het adres van de agenda letterlijk in de opdracht")
    op_lara = (lara in laag) if lara else True
    if not ids or not all(SCHOON_ID.fullmatch(i) for i in ids):
        if op_lara:
            return _lara_oorzaak(lara, "en het ID is niet uit de opdracht te lezen (een variabele of een lus)") + RIT_TIP
        return ("het ID is niet uit de opdracht te lezen (een variabele of een lus), dus niet na te kijken of het een "
                "afspraak uit een reeks is: schrijf het ID letterlijk in de opdracht")
    if op_lara and not all(RIT_ID.fullmatch(i) for i in ids):
        return _lara_oorzaak(lara)
    return None


def _dieper(cmd, pad, cwd, diepte):
    """Dezelfde controle op een geneste opdracht; voorbij GENEST_MAX lagen weigert de grendel als er iets in staat dat
    wist, een agenda noemt of verder iets draait."""
    if diepte >= GENEST_MAX:
        if BASH_WIS.search(cmd) or AGENDA_WOORD.search(cmd) or DRAAIT.search(cmd):
            return ("de opdracht is te diep genest om na te kijken (bash -c, eval of source in elkaar): schrijf de "
                    "wisopdracht rechtstreeks")
        return None
    return _bash({"command": cmd}, pad, cwd, diepte + 1)


def _bash(ti, pad, cwd=None, diepte=0):
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(cmd, str):
        return None
    woorden = _woorden(cmd)
    scripts, data = _bestanden(cmd, woorden, cwd)
    tekst = cmd + "".join("\n" + inhoud for inhoud in map(_lees, data) if inhoud)
    lara = lara_id(pad) if BASH_WIS.search(tekst) or scripts else None   # alleen nodig als _toets verder kijkt
    oorzaak = _toets(tekst, lara)
    if oorzaak:
        return oorzaak
    for p in scripts:
        inhoud = _lees(p)
        if not inhoud:
            continue
        oorzaak = _toets(tekst + "\n" + inhoud, lara)
        if not oorzaak and _shellscript(p, inhoud):
            oorzaak = _dieper(inhoud, pad, cwd, diepte)
        if oorzaak and not _vastgelegd(p):
            return f"in het script {p}: {oorzaak}"
    for genest in _genest(woorden):
        oorzaak = _dieper(genest, pad, cwd, diepte)
        if oorzaak:
            return f"in de geneste opdracht '{genest[:60]}': {oorzaak}"
    return None


def beslis(invoer, pad=TAKEN):
    """De reden om te weigeren, of None als deze opdracht door mag."""
    if not isinstance(invoer, dict):
        return None
    gebeurtenis = invoer.get("hook_event_name") or ("PreToolUse" if "tool_name" in invoer else "UserPromptSubmit")
    naam = invoer.get("tool_name")
    if gebeurtenis != "PreToolUse" or not isinstance(naam, str):
        return None
    ti = invoer.get("tool_input")
    oorzaak = _bash(ti, pad, invoer.get("cwd")) if naam == "Bash" else _mcp(naam, ti, pad)
    return f"{REDEN} Geweigerd: {oorzaak}." if oorzaak else None


def main():
    try:
        invoer = json.load(sys.stdin)
    except ValueError:
        return 0
    reden = beslis(invoer)
    if reden:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reden}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
