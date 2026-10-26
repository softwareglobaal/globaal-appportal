"""Grendel op de wisgrendel (driehoeksoverleg 27-10-2026, punten L5 en M6).

claude-hooks/wisgrendel.py houdt in Claude Code het wissen tegen van een afspraak op de agenda van Lara en van een
afspraak uit een reeks, met een uitzondering: een eigen rit van de Agendawacht (ID rit en 32 hexadecimale tekens).
De test draait het script zoals Claude Code het doet (JSON op stdin) en kijkt ook na dat het ID van Lara en het
formaat van een rit-ID nog kloppen met agenda_wacht.py: verandert een van beide, dan wordt deze test rood.
Een test schrijft nooit in een echte agenda en gaat niet op het net.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"      # een test belt nooit echt (FR-55)

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
sys.path.insert(0, str(HIER / "claude-hooks"))
import agenda_wacht as W            # noqa: E402
import wisgrendel as WG             # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def hook(invoer, ruw=None):
    r = subprocess.run([sys.executable, str(HIER / "claude-hooks" / "wisgrendel.py")],
                       input=ruw if ruw is not None else json.dumps(invoer), capture_output=True, text=True, timeout=30)
    try:
        return r.returncode, json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None
    except (ValueError, KeyError):
        return r.returncode, {"fout": r.stdout}


def geweigerd(rc, uit):
    return (rc == 0 and bool(uit) and uit.get("hookEventName") == "PreToolUse" and uit.get("permissionDecision") == "deny"
            and "markeer, wis niet" in uit.get("permissionDecisionReason", ""))


def mcp(tool, **invoer):
    return {"hook_event_name": "PreToolUse", "tool_name": f"mcp__een-nummer__{tool}",
            "tool_input": invoer}


def bash(opdracht):
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": opdracht}}


# ---------- de bronnen: een ID van Lara, een formaat voor een rit ----------
taken = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
LARA = next(a["adres"] for a in taken["agendas"] if a.get("rol") == "lara")
LARA_HEX = LARA.split("@")[0]
LARA_URL = LARA.replace("@", "%40")
WERK = W.WERKAGENDA
RIT = W._nieuwe_rit()["id"]
API = "https://www.googleapis.com/calendar/v3/calendars"

check("bron: de agenda van Lara in agenda-taken.json is de agenda 'Lara' in KALENDERS",
      [k for k, n in W.KALENDERS.items() if n == "Lara"] == [LARA], LARA)
check("bron: de grendel leest hetzelfde ID van Lara (64 hexadecimale tekens)",
      WG.lara_id() == LARA_HEX and re.fullmatch(r"[0-9a-f]{64}", LARA_HEX or ""), str(WG.lara_id()))
check("bron: een nieuwe rit van de Agendawacht heeft het ID rit en 32 hexadecimale tekens",
      re.fullmatch(r"rit[0-9a-f]{32}", RIT) and WG.RIT_ID.fullmatch(RIT), RIT)
check("bron: de werkagenda is niet die van Lara", LARA_HEX not in WERK)

# ---------- MCP: delete_event ----------
check("MCP: wissen op de agenda van Lara met een gewoon ID wordt geweigerd",
      geweigerd(*hook(mcp("delete_event", calendarId=LARA, eventId="4kq9s0abc12def"))))
rc, uit = hook(mcp("delete_event", calendarId=LARA, eventId="4kq9s0abc12def"))
reden = (uit or {}).get("permissionDecisionReason", "")
check("MCP: de reden zegt wat in de plaats moet (vervalt (vakantie), Beschikbaar, na Mehdi's ja)",
      "vervalt (vakantie)" in reden and "Beschikbaar" in reden and "Mehdi's ja" in reden and "Lara" in reden, reden)
check("MCP: de reden heeft geen gedachtestreepje", "\u2014" not in reden and "\u2013" not in reden)
rc, uit = hook(mcp("delete_event", calendarId=LARA, eventId=RIT))
check("MCP: een eigen rit op de agenda van Lara mag weg", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(mcp("delete_event", calendar_id=LARA, event_id=RIT))
check("MCP: ook met calendar_id en event_id mag een eigen rit weg", rc == 0 and uit is None, str(uit)[:200])
check("MCP: calendar_id en event_id met een gewoon ID op Lara worden geweigerd",
      geweigerd(*hook(mcp("delete_event", calendar_id=LARA, event_id="abc123"))))
check("MCP: rit met een ID dat er bijna op lijkt (31 tekens) op Lara wordt geweigerd",
      geweigerd(*hook(mcp("delete_event", calendarId=LARA, eventId=RIT[:-1]))))
check("MCP: op Lara zonder eventId wordt geweigerd", geweigerd(*hook(mcp("delete_event", calendarId=LARA))))
check("MCP: een afspraak uit een reeks (x_20261028) op de werkagenda wordt geweigerd",
      geweigerd(*hook(mcp("delete_event", calendarId=WERK, eventId="x_20261028"))))
check("MCP: een afspraak uit een reeks (x_20261028T080000Z) op de werkagenda wordt geweigerd",
      geweigerd(*hook(mcp("delete_event", calendarId=WERK, eventId="x_20261028T080000Z"))))
check("MCP: een afspraak uit een reeks op de primaire agenda (zonder calendarId) wordt geweigerd",
      geweigerd(*hook(mcp("delete_event", eventId="x_20261028T080000Z"))))
rc, uit = hook(mcp("delete_event", calendarId=WERK, eventId="4kq9s0abc12def"))
check("MCP: een gewoon ID op de werkagenda mag (de ja van Mehdi blijft de regel)", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(mcp("delete_event", eventId="4kq9s0abc12def"))
check("MCP: zonder calendarId is het de primaire agenda, niet Lara: mag", rc == 0 and uit is None, str(uit)[:200])

# ---------- MCP: update_event met status cancelled ----------
check("MCP: update_event die op Lara annuleert wordt geweigerd",
      geweigerd(*hook(mcp("update_event", calendarId=LARA, eventId="abc123", status="cancelled"))))
check("MCP: update_event die een afspraak uit een reeks annuleert wordt geweigerd",
      geweigerd(*hook(mcp("update_event", calendarId=WERK, eventId="x_20261028", status="cancelled"))))
check("MCP: status cancelled dieper in de invoer telt ook",
      geweigerd(*hook(mcp("update_event", calendarId=LARA, eventId="abc123", event={"status": "Cancelled"}))))
rc, uit = hook(mcp("update_event", calendarId=LARA, eventId="abc123", summary="vervalt (vakantie) zwemmen",
                   availability="AVAILABILITY_FREE"))
check("MCP: markeren op Lara (titel, Beschikbaar) mag", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(mcp("update_event", calendarId=WERK, eventId="abc123", status="cancelled"))
check("MCP: annuleren van een gewoon ID op de werkagenda mag", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(mcp("list_events", calendarId=LARA))
check("MCP: lezen op Lara mag", rc == 0 and uit is None, str(uit)[:200])

# ---------- Bash ----------
check("Bash: curl -X DELETE op de %40-vorm van Lara wordt geweigerd",
      geweigerd(*hook(bash(f'curl -s -X DELETE "{API}/{LARA_URL}/events/4kq9s0abc12def?sendUpdates=none" '
                           '-H "Authorization: Bearer $TOK"'))))
check("Bash: --request=DELETE op de @-vorm van Lara wordt geweigerd",
      geweigerd(*hook(bash(f"curl --request=DELETE '{API}/{LARA}/events/abc123'"))))
check("Bash: python urllib method='DELETE' op Lara met een $VAR als ID wordt geweigerd",
      geweigerd(*hook(bash(f"python3 -c \"import urllib.request as u; u.urlopen(u.Request("
                           f"'{API}/{LARA_URL}/events/$EID', method='DELETE', headers={{'Authorization': 'Bearer x'}}))\""))))
rc, uit = hook(bash(f"for e in $(cat ids); do curl -X DELETE {API}/{LARA_URL}/events/$e; done"))
check("Bash: een lus op Lara wordt geweigerd en de reden noemt het onleesbare ID",
      geweigerd(rc, uit) and "niet uit de opdracht te lezen" in uit.get("permissionDecisionReason", ""), str(uit)[:300])
check("Bash: events().delete op Lara zonder leesbaar ID wordt geweigerd",
      geweigerd(*hook(bash(f"python3 -c \"s.events().delete(calendarId='{LARA}', eventId=eid).execute()\""))))
check("Bash: status cancelled via PATCH op Lara wordt geweigerd",
      geweigerd(*hook(bash(f"curl -X PATCH {API}/{LARA_URL}/events/abc123 -d '{{\"status\": \"cancelled\"}}'"))))
check("Bash: een opdracht met recurringEventId die wist wordt geweigerd",
      geweigerd(*hook(bash(f"python3 wis.py --kalender {WERK} --filter recurringEventId=abc && "
                           f"curl -X DELETE {API}/{WERK}/events/$E"))))
check("Bash: DELETE van een afspraak uit een reeks op de werkagenda wordt geweigerd",
      geweigerd(*hook(bash(f"curl -X DELETE {API}/mehdiprivewerkagenda%40gmail.com/events/abc_20261028T080000Z"))))
rc, uit = hook(bash(f"curl -X DELETE {API}/mehdiprivewerkagenda%40gmail.com/events/4kq9s0abc12def"))
check("Bash: DELETE op de werkagenda met een gewoon ID mag", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(bash(f"curl -X DELETE '{API}/{LARA_URL}/events/{RIT}?sendUpdates=none'"))
check("Bash: DELETE van een eigen rit op Lara mag", rc == 0 and uit is None, str(uit)[:200])
check("Bash: een eigen rit en een gewoon ID samen op Lara worden geweigerd",
      geweigerd(*hook(bash(f"curl -X DELETE {API}/{LARA_URL}/events/{RIT}; curl -X DELETE {API}/{LARA_URL}/events/abc123"))))
check("Bash: een ID uit een f-string (events/{eid}) op Lara wordt geweigerd",
      geweigerd(*hook(bash(f"python3 - <<'X'\nreq = Request(f'{API}/{LARA_URL}/events/{{eid}}', method=\"DELETE\")\nX"))))
rc, uit = hook(bash(f"curl -s '{API}/{LARA_URL}/events?timeMin=2026-10-27T00:00:00Z'"))
check("Bash: lezen op Lara mag", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(bash("ls -la"))
check("Bash: een gewone opdracht krijgt niets", rc == 0 and uit is None, str(uit)[:200])

# ---------- kapotte invoer, ander moment ----------
rc, uit = hook(None, ruw="geen json")
check("kapotte invoer: geen uitvoer en exitcode 0", rc == 0 and uit is None, str(uit)[:200])
for ruw in ("[]", "null", '"tekst"', '{"tool_name": "Bash", "tool_input": "x"}', '{"tool_name": 5}'):
    rc, uit = hook(None, ruw=ruw)
    check(f"vreemde invoer {ruw}: geen uitvoer en exitcode 0", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook({"hook_event_name": "UserPromptSubmit",
                "prompt": f"curl -X DELETE {API}/{LARA_URL}/events/abc_20261028 en wis de reeks van Lara"})
check("UserPromptSubmit: het script zegt nooit iets", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                "tool_input": {"command": f"curl -X DELETE {API}/{LARA_URL}/events/abc"}})
check("PostToolUse: het script zegt nooit iets", rc == 0 and uit is None, str(uit)[:200])

# ---------- het ID van Lara niet te lezen: elke genoemde agenda telt als de hare ----------
weg = HIER / "werkwijze" / "bestaat-niet.json"
check("zonder bron: wissen op een genoemde agenda wordt geweigerd",
      "misschien op de agenda van Lara" in (WG.beslis(mcp("delete_event", calendarId=WERK, eventId="abc"), weg) or ""))
check("zonder bron: een eigen rit mag nog altijd weg",
      WG.beslis(mcp("delete_event", calendarId=WERK, eventId=RIT), weg) is None)
check("zonder bron: de primaire agenda is nog altijd niet die van Lara",
      WG.beslis(mcp("delete_event", eventId="abc"), weg) is None)
check("zonder bron: een DELETE op een agenda in Bash wordt geweigerd",
      WG.beslis(bash(f"curl -X DELETE {API}/mehdiprivewerkagenda%40gmail.com/events/abc"), weg) is not None)

# ---------- laag 1 blijft een herinnering, de wisgrendel staat in de werkwijze en in de CI ----------
check("regels_vooraf.py blokkeert nooit", "permissionDecision" not in (HIER / "claude-hooks" / "regels_vooraf.py").read_text(encoding="utf-8"))
aanzetten = taken["leren_in_lagen"]["aanzetten"]
check("werkwijze: agenda-taken.json zegt hoe Mehdi de wisgrendel aanzet, met de waarschuwing over exitcode 2",
      "~/dev/globaal-appportal/mijnagents-runner/claude-hooks/wisgrendel.py" in aanzetten and "exitcode 2" in aanzetten, aanzetten[:200])
check("werkwijze: de grendel staat in de lijst met grendels",
      any(g.get("test") == "tests/test_wisgrendel.py" for g in taken["grendels"]))
_wk = (HIER / "werkwijze" / "agenda-wacht.md").read_text(encoding="utf-8")
check("werkwijze: agenda-wacht.md noemt het pad en de waarschuwing over exitcode 2",
      "python3 ~/dev/globaal-appportal/mijnagents-runner/claude-hooks/wisgrendel.py" in _wk and "exitcode 2" in _wk)
_ci = (HIER.parent / ".github" / "workflows" / "agenda-grendels.yml").read_text(encoding="utf-8")
check("CI: agenda-grendels draait deze test", "python3 mijnagents-runner/tests/test_wisgrendel.py" in _ci)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
