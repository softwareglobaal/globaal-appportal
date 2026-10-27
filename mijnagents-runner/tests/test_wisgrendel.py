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
import tempfile
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

# ---------- Bash: agenda en ID moeten letterlijk in de opdracht staan (Codex-controle 27-10-2026, punt 5) ----------
rc, uit = hook(bash(f'LARA_CAL="{LARA_URL}"; curl -s -X DELETE "{API}/$LARA_CAL/events/abc123" -H "Authorization: Bearer $TOK"'))
check("Bash: een agenda uit $LARA_CAL wordt geweigerd en de reden vraagt het adres letterlijk",
      geweigerd(rc, uit) and "agenda is niet uit de opdracht te lezen" in uit.get("permissionDecisionReason", ""), str(uit)[:300])
check("Bash: een agenda uit ${CAL} wordt geweigerd",
      geweigerd(*hook(bash(f'curl -X DELETE "{API}/${{CAL}}/events/abc123"'))))
check("Bash: een agenda uit $(cat x) wordt geweigerd",
      geweigerd(*hook(bash(f'curl -X DELETE "{API}/$(cat x)/events/abc123"'))))
check("Bash: een agenda uit `cat x` wordt geweigerd",
      geweigerd(*hook(bash(f'curl -X DELETE "{API}/`cat x`/events/abc123"'))))
check("Bash: een variabele agenda wordt ook met een rit-ID geweigerd",
      geweigerd(*hook(bash(f'curl -X DELETE "{API}/$CAL/events/{RIT}"'))))
check("Bash: events().delete met calendarId uit een variabele wordt geweigerd",
      geweigerd(*hook(bash(f"python3 -c \"s.events().delete(calendarId=cal, eventId='abc123').execute()\""))))
check("Bash: wissen in de agendalijst (calendarList, geen calendars/) wordt geweigerd",
      geweigerd(*hook(bash("curl -X DELETE https://www.googleapis.com/calendar/v3/users/me/calendarList/abc"))))
rc, uit = hook(bash(f'curl -X DELETE "{API}/{LARA_URL}/events/$RIT_ID"'))
_r = (uit or {}).get("permissionDecisionReason", "")
check("Bash: een variabel ID op Lara blijft geweigerd, met de raad: het letterlijke rit-ID, de ritopruiming draait op de VM",
      geweigerd(rc, uit) and "letterlijke rit-ID" in _r and "op de VM" in _r, _r[-300:])
rc, uit = hook(bash(f'curl -X DELETE "{API}/mehdiprivewerkagenda%40gmail.com/events/$E"'))
check("Bash: een variabel ID op de werkagenda wordt geweigerd (een reeks is dan niet na te kijken)",
      geweigerd(rc, uit) and "ID is niet uit de opdracht te lezen" in uit.get("permissionDecisionReason", ""), str(uit)[:300])
rc, uit = hook(bash(f"curl -X DELETE '{API}/{WERK}/events/4kq9s0abc12def?sendUpdates=none'"))
check("Bash: een letterlijke werkagenda (@-vorm) met een letterlijk gewoon ID mag", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(bash(f"python3 -c \"s.events().delete(calendarId='{WERK}', eventId='4kq9s0abc12def').execute()\""))
check("Bash: events().delete met letterlijke werkagenda en letterlijk ID mag", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(bash(f"curl -X DELETE {API}/primary/events/4kq9s0abc12def"))
check("Bash: de primaire agenda met een letterlijk gewoon ID mag", rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(bash("gh api -X DELETE repos/softwareglobaal/globaal-appportal/git/refs/heads/oud"))
check("Bash: een wisopdracht buiten de agenda (gh api) laat de grendel door", rc == 0 and uit is None, str(uit)[:200])

# ---------- Bash: nieuwe wisvormen (review 27-10-2026, punt 2b) ----------
check('Bash: "method": "DELETE" (ook JSON of JavaScript) op Lara wordt geweigerd',
      geweigerd(*hook(bash(f"node -e 'fetch(\"{API}/{LARA_URL}/events/abc123\", {{\"method\": \"DELETE\"}})'"))))
check("Bash: method: 'DELETE' zonder aanhalingstekens rond de sleutel op Lara wordt geweigerd",
      geweigerd(*hook(bash(f"node -e \"fetch('{API}/{LARA_URL}/events/abc123', {{method: 'DELETE'}})\""))))
check("Bash: .delete( op een agenda-object (cal.delete) op Lara wordt geweigerd",
      geweigerd(*hook(bash(f"python3 -c \"cal.delete(calendar_id='{LARA}', event_id='abc123')\""))))
check("Bash: calendarList().delete( zonder ID wordt geweigerd",
      geweigerd(*hook(bash(f"python3 -c \"s.calendarList().delete(calendarId='{LARA}').execute()\""))))
rc, uit = hook(bash("python3 -c \"cache.delete('x')\""))
check("Bash: .delete( op iets anders dan een agenda mag", rc == 0 and uit is None, str(uit)[:200])
check("Bash: status='cancelled' in Python op Lara wordt geweigerd",
      geweigerd(*hook(bash(f"python3 -c \"ev['status'] = 'cancelled'; s.events().update(calendarId='{LARA}', "
                           f"eventId='abc123', body=ev).execute()\""))))
check("Bash: /batch/calendar zonder leesbare inhoud wordt geweigerd",
      geweigerd(*hook(bash("curl -X POST https://www.googleapis.com/batch/calendar/v3 --data-binary @/bestaat/niet.txt"))))
check("Bash: events/<id>/move van Lara naar de werkagenda wordt geweigerd",
      geweigerd(*hook(bash(f"curl -X POST '{API}/{LARA_URL}/events/abc123/move?destination={WERK}'"))))

# ---------- Bash: een ondoorzichtig doel (review 27-10-2026, punt 2c) ----------
rc, uit = hook(bash('curl -X DELETE "$URL"'))
check('Bash: DELETE op "$URL" zonder agenda of Google mag', rc == 0 and uit is None, str(uit)[:200])
rc, uit = hook(bash('curl -X DELETE "$(cat url.txt)" -H "Authorization: Bearer $TOK"'))
check("Bash: DELETE op $(cat url.txt) zonder agenda of Google mag", rc == 0 and uit is None, str(uit)[:200])
check('Bash: DELETE op "$URL" met een agendawoord ergens in de opdracht wordt geweigerd',
      geweigerd(*hook(bash('curl -X DELETE "$URL"  # de dubbele afspraak uit de calendar halen'))))
rc, uit = hook(bash('TOK=$(curl -s https://oauth2.googleapis.com/token -d x); curl -X DELETE "$URL" -H "Authorization: Bearer $TOK"'))
check('Bash: DELETE op "$URL" met een Google-host in de opdracht wordt geweigerd',
      geweigerd(rc, uit) and "niet te lezen" in uit.get("permissionDecisionReason", ""), str(uit)[:300])
check("Bash: DELETE op `cat url.txt` met een Google-host wordt geweigerd",
      geweigerd(*hook(bash("curl -X DELETE `cat url.txt` -H 'x-host: www.googleapis.com'"))))
rc, uit = hook(bash('curl -X DELETE https://gmail.googleapis.com/gmail/v1/users/me/labels/Label_1 -H "Authorization: Bearer $TOK"'))
check("Bash: een letterlijke Google-URL buiten de agenda laat de wisgrendel door", rc == 0 and uit is None, str(uit)[:200])

# ---------- Bash: een eigen script of een meegestuurd bestand wordt mee nagekeken (review 27-10-2026, punt 2a) ----------
with tempfile.TemporaryDirectory() as _d:
    d = Path(_d)
    (d / "wis.py").write_text(f"import urllib.request as u\nu.urlopen(u.Request('{API}/{LARA_URL}/events/abc123', "
                              "method='DELETE'))\n", encoding="utf-8")
    (d / "wis.sh").write_text(f"#!/bin/sh\ncurl -X DELETE '{API}/{LARA_URL}/events/abc123'\n", encoding="utf-8")
    (d / "wis.sh").chmod(0o755)
    (d / "wis.js").write_text(f"fetch('{API}/{LARA_URL}/events/abc123', {{method: 'DELETE'}})\n", encoding="utf-8")
    (d / "lees.py").write_text(f"import urllib.request as u\nu.urlopen('{API}/{LARA_URL}/events')\n", encoding="utf-8")
    (d / "groot.py").write_text((d / "wis.py").read_text() + "#" * (WG.MAX_BESTAND + 1) + "\n", encoding="utf-8")
    (d / "rit.py").write_text(f"import urllib.request as u\nu.urlopen(u.Request('{API}/{LARA_URL}/events/{RIT}', "
                              "method='DELETE'))\n", encoding="utf-8")
    (d / "annuleer.json").write_text('{"status": "cancelled"}', encoding="utf-8")
    (d / "batch.txt").write_text(f"--b\nDELETE /calendar/v3/calendars/{LARA_URL}/events/abc123\n--b--\n", encoding="utf-8")
    rc, uit = hook(bash(f"python3 {d}/wis.py"))
    check("script: python3 met een Lara-wisopdracht in het bestand wordt geweigerd en de reden noemt het script",
          geweigerd(rc, uit) and "in het script" in uit.get("permissionDecisionReason", ""), str(uit)[:300])
    check("script: een relatief pad tegenover cwd wordt nagekeken",
          geweigerd(*hook({**bash("python3 -u wis.py --dag 2026-10-28"), "cwd": str(d)})))
    check("script: cd <map> && python3 wis.py wordt nagekeken", geweigerd(*hook(bash(f"cd {d} && python3 wis.py"))))
    check("script: bash wis.sh wordt nagekeken", geweigerd(*hook(bash(f"bash {d}/wis.sh"))))
    check("script: ./wis.sh wordt nagekeken", geweigerd(*hook({**bash("./wis.sh"), "cwd": str(d)})))
    check("script: node wis.js wordt nagekeken", geweigerd(*hook(bash(f"node {d}/wis.js"))))
    rc, uit = hook(bash(f"python3 {d}/lees.py"))
    check("script: een script dat alleen leest mag", rc == 0 and uit is None, str(uit)[:200])
    rc, uit = hook(bash(f"python3 {d}/rit.py"))
    check("script: een script dat een letterlijke eigen rit op Lara wist mag", rc == 0 and uit is None, str(uit)[:200])
    rc, uit = hook(bash(f"python3 {d}/groot.py"))
    check("script: een bestand boven 200 kB wordt niet gelezen en niet geblokkeerd", rc == 0 and uit is None, str(uit)[:200])
    rc, uit = hook(bash(f"python3 {d}/bestaat-niet.py"))
    check("script: een bestand dat niet bestaat blokkeert niet", rc == 0 and uit is None, str(uit)[:200])
    rc, uit = hook(bash(f"git add {d}/wis.py && cat {d}/wis.py"))
    check("script: een bestand dat alleen genoemd wordt (git add, cat) wordt niet nagekeken", rc == 0 and uit is None, str(uit)[:200])
    check("bestand: -X PATCH met -d @body.json die status cancelled zet op Lara wordt geweigerd",
          geweigerd(*hook(bash(f"curl -X PATCH {API}/{LARA_URL}/events/abc123 -d @{d}/annuleer.json"))))
    check("bestand: --data @body.json werkt ook", geweigerd(*hook(bash(f"curl -X PUT {API}/{LARA_URL}/events/abc123 --data @{d}/annuleer.json"))))
    rc, uit = hook(bash(f"curl -X PATCH {API}/{LARA_URL}/events/abc123 -d @{d}/ontbreekt.json"))
    check("bestand: een meegestuurd bestand dat niet bestaat blokkeert niet", rc == 0 and uit is None, str(uit)[:200])
    check("bestand: /batch/calendar met een DELETE op Lara in de inhoud wordt geweigerd",
          geweigerd(*hook(bash(f"curl -X POST https://www.googleapis.com/batch/calendar/v3 --data-binary @{d}/batch.txt"))))
    _g = ["git", "-C", str(d), "-c", "user.name=proef", "-c", "user.email=proef@voorbeeld.be"]
    if subprocess.run(_g[:3] + ["init", "-q"], capture_output=True).returncode == 0:
        subprocess.run(_g + ["add", "wis.py"], capture_output=True)
        subprocess.run(_g + ["commit", "-q", "-m", "proef"], capture_output=True)
        check("script: vastgelegd in een andere repo telt niet als nagekeken", geweigerd(*hook(bash(f"python3 {d}/wis.py"))))

# vastgelegd in deze repo en ongewijzigd: nagekeken code met eigen grendels (de tests zelf noemen Lara en DELETE)
_eigen = HIER / "tests" / "test_wisgrendel.py"
_schoon = (subprocess.run(["git", "-C", str(_eigen.parent), "ls-files", "--error-unmatch", _eigen.name], capture_output=True).returncode == 0
           and subprocess.run(["git", "-C", str(_eigen.parent), "diff", "--quiet", "HEAD", "--", _eigen.name]).returncode == 0)
rc, uit = hook({**bash("python3 tests/test_wisgrendel.py"), "cwd": str(HIER)})
check("script: een test die ongewijzigd in deze repo staat mag draaien (gewijzigd: geweigerd tot hij vastgelegd is)",
      (rc == 0 and uit is None) if _schoon else geweigerd(rc, uit), f"schoon={_schoon} {str(uit)[:200]}")

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
check("werkwijze: agenda-taken.json geeft precies de aanzetopdracht met omhulsel, en zegt waarom (exitcode 2)",
      WG.AANZETTEN in aanzetten and "exitcode 2" in aanzetten, aanzetten[-400:])
check("werkwijze: de grendel staat in de lijst met grendels",
      any(g.get("test") == "tests/test_wisgrendel.py" for g in taken["grendels"]))
_wk = (HIER / "werkwijze" / "agenda-wacht.md").read_text(encoding="utf-8")
check("werkwijze: agenda-wacht.md geeft precies de aanzetopdracht met omhulsel, en zegt waarom (exitcode 2)",
      WG.AANZETTEN in _wk and "exitcode 2" in _wk)

# ---------- aanzetten: het omhulsel geeft nooit exitcode 2 (review 27-10-2026, punt 1) ----------
_lara_wis = json.dumps(mcp("delete_event", calendarId=LARA, eventId="abc123"))
with tempfile.TemporaryDirectory() as leeg:
    r = subprocess.run(WG.AANZETTEN, shell=True, input=_lara_wis, capture_output=True, text=True,
                       env={**os.environ, "HOME": leeg}, timeout=30)
    check("aanzetten: ontbreekt het script, dan exitcode 0 en geen uitvoer", r.returncode == 0 and not r.stdout.strip(),
          f"{r.returncode} {r.stdout[:100]} {r.stderr[:100]}")
    r = subprocess.run(f'python3 "{leeg}/dev/globaal-appportal/mijnagents-runner/claude-hooks/wisgrendel.py"', shell=True,
                       input=_lara_wis, capture_output=True, text=True, timeout=30)
    check("aanzetten: een kaal python3-pad naar een ontbrekend script geeft exitcode 2 (daarom het omhulsel)", r.returncode == 2)
with tempfile.TemporaryDirectory() as thuis:
    (Path(thuis) / "dev").mkdir()
    (Path(thuis) / "dev" / "globaal-appportal").symlink_to(HIER.parent, target_is_directory=True)
    r = subprocess.run(WG.AANZETTEN, shell=True, input=_lara_wis, capture_output=True, text=True,
                       env={**os.environ, "HOME": thuis}, timeout=30)
    try:
        _uit = json.loads(r.stdout)["hookSpecificOutput"]
    except (ValueError, KeyError):
        _uit = None
    check("aanzetten: met het echte pad komt de weigering van de hook door het omhulsel", geweigerd(r.returncode, _uit),
          f"{r.returncode} {r.stdout[:200]} {r.stderr[:200]}")
_ci = (HIER.parent / ".github" / "workflows" / "agenda-grendels.yml").read_text(encoding="utf-8")
check("CI: agenda-grendels draait deze test", "python3 mijnagents-runner/tests/test_wisgrendel.py" in _ci)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
