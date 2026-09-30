#!/usr/bin/env python3
"""Laag 3 (FR-71): een correctie van Mehdi wordt eerst een regel, dan pas verder werken.

Claude Code-hook op UserPromptSubmit. Leest het bericht van Mehdi (JSON op stdin, veld "prompt"). Staat er een
correctiewoord in, dan krijgt Claude extra context mee: eerst de regel vastleggen in het foutenregister (met een
test), het geheugen en de werkwijze, en in het antwoord in één regel zeggen waar. Het bericht zelf wordt nergens
naartoe gestuurd; het script leest het alleen hier op de Mac.

Aanzetten (een keer, door Mehdi): in ~/.claude/settings.json onder "hooks" toevoegen:
  "UserPromptSubmit": [{"hooks": [{"type": "command",
      "command": "python3 ~/dev/globaal-appportal/mijnagents-runner/claude-hooks/correctie.py"}]}]
"""
import json
import re
import sys

WOORDEN = r"\b(fout(ief|en)?|dom(me|ste)?|waarom|altijd|nooit|niet de bedoeling|verkeerd|klopt niet|hoe komt|" \
          r"alweer|opnieuw fout|zelfde fout|begrijp .* niet|niet goed)\b"

try:
    prompt = (json.load(sys.stdin) or {}).get("prompt") or ""
except (ValueError, AttributeError):
    sys.exit(0)
if re.search(WOORDEN, prompt, re.I):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (
            "Dit bericht van Mehdi bevat een correctie. Voor je iets anders doet: (1) herstel het in de bron (code, "
            "sjabloon of werkwijze), niet alleen dit ene geval; (2) leg de regel vast: een nieuwe of bijgewerkte fout in "
            "werkwijze/foutenregister.json met een test als grendel als het de Agendawacht betreft, een feedbackgeheugen "
            "in ~/.claude/projects/-Users-mehdichegini-TKN-buro-Dropbox/memory/, en de werkwijze of JSON waar de regel "
            "hoort; (3) zeg in je antwoord in één regel waar het vastgelegd is. Vraag niet opnieuw wat Mehdi al besliste."
        )}}))
sys.exit(0)
