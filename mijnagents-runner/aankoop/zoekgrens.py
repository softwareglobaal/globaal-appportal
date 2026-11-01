#!/usr/bin/env python3
"""PreToolUse-hook van De Prijsonderzoeker (overleg 14, A3): telt de zoekopdrachten van claude -p en weigert vanaf
de opdracht na de grens, zodat het model afrondt met wat het las.

    zoekgrens.py <tellerbestand> <grens>

Het tellerbestand staat in de tijdelijke map van de vraag.
"""
import json
import sys


def tel(pad, grens):
    """Telt een zoekopdracht; geeft het weigerantwoord voor Claude Code, of None als het nog mag."""
    try:
        with open(pad, encoding="utf-8") as f:
            n = int(f.read().strip() or 0)
    except (OSError, ValueError):
        n = 0
    n += 1
    with open(pad, "w", encoding="utf-8") as f:
        f.write(str(n))
    if n <= grens:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": f"Zoekgrens van {grens} bereikt: rond af met wat je las."}}


if __name__ == "__main__":
    sys.stdin.read()                  # de hook krijgt de toolvraag op stdin; de teller heeft ze niet nodig
    uit = tel(sys.argv[1], int(sys.argv[2]))
    if uit:
        print(json.dumps(uit))
