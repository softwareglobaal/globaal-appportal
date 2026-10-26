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
- een Bash-opdracht die wist (DELETE, events().delete of status 'cancelled') en recurringEventId noemt, een afspraak
  uit een reeks, of de agenda van Lara met een ID dat geen eigen rit is of dat niet uit de opdracht te lezen is (een
  variabele, een lus).
Zonder agenda (calendarId) werkt de MCP op de primaire agenda, en die is niet van Lara.

Het ID van Lara komt uit werkwijze/agenda-taken.json (de agenda met rol 'lara'); een tweede kopie staat nergens. Is het
niet te lezen, dan telt elke genoemde agenda als die van Lara. Kapotte invoer, een ander moment dan PreToolUse of iets
anders dan wissen: geen uitvoer en exitcode 0. Het script leest alleen dat ene bestand in de repo en gaat niet op het
net. De grendel is tests/test_wisgrendel.py.
"""
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
TAKEN = HIER.parent / "werkwijze" / "agenda-taken.json"

RIT_ID = re.compile(r"rit[0-9a-f]{32}")              # volledig: een eigen rit van de Agendawacht (_nieuwe_rit)
REEKS_ID = re.compile(r"_\d{8}(T\d{6}Z)?$")           # een afspraak uit een reeks: ID_JJJJMMDD of ID_JJJJMMDDTUUMMSSZ
MCP_WIS = re.compile(r"^mcp__.+__delete_event$")
MCP_WIJZIG = re.compile(r"^mcp__.+__update_event$")
BASH_WIS = re.compile(r"""-X\s*["']?DELETE|--request[ =]["']?DELETE|method\s*=\s*["']DELETE["']"""
                      r"""|\.request\(\s*["']DELETE["']|\b(requests|httpx)\.delete\b|events\(\)\.delete"""
                      r"""|\\?["']status\\?["']\s*:\s*\\?["']cancell?ed""", re.I)
ID_IN_PAD = re.compile(r"""events/([^\s/?'"\\#&;|<>()]*)""")
ID_IN_VELD = re.compile(r"""(?i:event_?id)\\?["']?\s*[=:]\s*\\?["']([^"'\\]*)\\?["']""")
SCHOON_ID = re.compile(r"[A-Za-z0-9_]+")

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


def _bash(ti, pad):
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(cmd, str) or not BASH_WIS.search(cmd):
        return None
    laag = cmd.lower()
    if "recurringeventid" in laag:
        return "de opdracht noemt recurringEventId, dus een reeks"
    ids = ID_IN_PAD.findall(cmd) + ID_IN_VELD.findall(cmd)
    reeks = [i for i in ids if REEKS_ID.search(i)]
    if reeks:
        return f"het ID {reeks[0]} is een afspraak uit een reeks"
    lara = lara_id(pad)
    op_lara = (lara in laag) if lara else "calendar" in laag
    if op_lara and (not ids or not all(SCHOON_ID.fullmatch(i) for i in ids)):
        return _lara_oorzaak(lara, "en het ID is niet uit de opdracht te lezen (een variabele of een lus)")
    if op_lara and not all(RIT_ID.fullmatch(i) for i in ids):
        return _lara_oorzaak(lara)
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
    oorzaak = _bash(ti, pad) if naam == "Bash" else _mcp(naam, ti, pad)
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
