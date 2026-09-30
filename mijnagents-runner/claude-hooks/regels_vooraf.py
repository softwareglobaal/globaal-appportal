#!/usr/bin/env python3
"""Laag 1 (FR-72): de drie harde regels die bij een handeling horen, op het moment dat Claude ze nodig heeft.

Een Claude Code-hook voor twee momenten:
- UserPromptSubmit: gaat het bericht van Mehdi over de agenda, Calendly, de server, wissen of mail, dan staan de
  regels voor Claude voor hij iets doet;
- PreToolUse: een schrijfopdracht naar de agenda, Calendly of de server krijgt de regels mee als herinnering
  (Claude Code zet die naast het resultaat, dus voor de controle en de volgende stap).

De vaste regels en de patronen staan in regels.json naast dit script (in de repo, met een test). De weekconsolidatie
op de server (laag 4) zet er per categorie hoogstens twee regels van de week bij, via
Data uit Mehdi/Agendawacht/regels-vooraf.json; weghalen of verzwakken kan ze niet. Het script leest alleen.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
WEEK = Path.home() / "TKN-buro Dropbox/Data uit Mehdi/Agendawacht/regels-vooraf.json"


WEEK_GELDIG_DAGEN = 14
WEEK_MAX = 2


def _lees(pad):
    try:
        return json.loads(pad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def regels(week_pad=WEEK, nu=None):
    """De vaste regels uit regels.json (patronen en regels, altijd), aangevuld met hoogstens twee regels van de
    week per categorie. De weekconsolidatie kan zo een regel toevoegen, maar nooit een vaste regel of een patroon
    weghalen of verzwakken; een weekbestand ouder dan twee weken telt niet meer."""
    vast = _lees(HIER / "regels.json").get("categorieen") or []
    week = _lees(week_pad) if week_pad and Path(week_pad).is_file() else {}
    try:
        leeftijd = ((nu or datetime.now(timezone.utc)) - datetime.fromisoformat(week.get("gemaakt", ""))).days
    except (TypeError, ValueError):
        leeftijd = None
    extra = {}
    if leeftijd is not None and 0 <= leeftijd <= WEEK_GELDIG_DAGEN:
        for c in week.get("categorieen") or []:
            extra[c.get("naam")] = [str(r)[:240] for r in (c.get("regels") or []) if str(r).strip()][:WEEK_MAX]
    return [{**c, "regels": list(c.get("regels") or [])[:3], "week": extra.get(c.get("naam"), [])} for c in vast]


def kies(tekst, veld, maximum=2):
    uit = []
    for c in regels():
        patroon = c.get(veld) or ""
        if patroon and re.search(patroon, tekst or ""):
            uit.append(c)
        if len(uit) >= maximum:
            break
    return uit


def tekst_voor(c):
    alle = c["regels"] + c.get("week", [])
    return f"Harde regels voor {c['naam']}: " + " ".join(f"({i + 1}) {r}" for i, r in enumerate(alle))


def main():
    try:
        invoer = json.load(sys.stdin) or {}
    except ValueError:
        return 0
    gebeurtenis = invoer.get("hook_event_name") or ("PreToolUse" if "tool_name" in invoer else "UserPromptSubmit")
    if gebeurtenis == "UserPromptSubmit":
        gekozen = kies(invoer.get("prompt") or "", "bericht")
    else:
        ti = invoer.get("tool_input") or {}
        tekst = f"{invoer.get('tool_name', '')} {ti.get('command') if isinstance(ti, dict) and ti.get('command') else json.dumps(ti, ensure_ascii=False)}"
        gekozen = kies(tekst, "opdracht", maximum=1)
    if not gekozen:
        return 0
    delen = [tekst_voor(c) for c in gekozen]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": gebeurtenis,
                                             "additionalContext": "\n".join(delen)[:9000]}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
