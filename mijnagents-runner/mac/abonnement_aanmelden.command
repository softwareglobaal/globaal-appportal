#!/bin/bash
# Claude op de server (VM globaal) aanmelden met het abonnement van Mehdi, voor de agents die Claude gebruiken zonder
# API-sleutel (koppelingen/claude_abonnement.py). Eenmalig, een jaar geldig. Dubbelklikken in Finder: je browser opent,
# je meldt je aan met je Claude-account en klikt op Authorize. Je kopieert of plakt niets.
# Het token gaat via ssh-stdin naar ~/appportal/.env op de VM (naam CLAUDE_CODE_OAUTH_TOKEN, alleen leesbaar voor de
# eigenaar), nooit in een log of de proceslijst. De opname van setup-token staat kort in een tijdelijk bestand (0600)
# en wordt overschreven en gewist.
set -u
CLAUDE="$HOME/.local/bin/claude"
[ -x "$CLAUDE" ] || CLAUDE="$(command -v claude || true)"
LOG="$(mktemp -t claude-aanmelding)"
opruimen() { rm -P -f "$LOG" 2>/dev/null || rm -f "$LOG"; }
trap opruimen EXIT
sluiten() { echo; read -r -p "Druk op Enter om dit venster te sluiten." _; }

if [ -z "$CLAUDE" ]; then
  echo "Claude-programma niet gevonden. Zeg het tegen Claude."; sluiten; exit 1
fi

echo "Claude aanmelden voor de agents op de server (een jaar geldig)."
echo "Je browser opent zo. Meld je aan met je Claude-account en klik op Authorize."
echo
script -q "$LOG" "$CLAUDE" setup-token
TOKEN="$(LC_ALL=C sed -E $'s/\x1b\\[[0-9;?]*[a-zA-Z]//g' "$LOG" | LC_ALL=C grep -o -E 'sk-ant-oat01-[A-Za-z0-9_-]+' | tail -1)"
opruimen
# De sleutel stond even op het scherm: scherm en terugrolgeschiedenis leegmaken (Codex, controle 17)
printf '\033[2J\033[3J\033[H'

if [ -z "$TOKEN" ]; then
  echo; echo "Er kwam geen sleutel terug. Niets bewaard. Zeg het tegen Claude."; sluiten; exit 1
fi

# Vervangt de regel CLAUDE_CODE_OAUTH_TOKEN in ~/appportal/.env (of voegt ze toe), daarna een korte proef op de VM.
if printf '%s\n' "$TOKEN" | ssh globaal 'set -e; read -r T; f=~/appportal/.env; umask 077
    grep -v "^CLAUDE_CODE_OAUTH_TOKEN=" "$f" > "$f.nieuw" || true
    printf "CLAUDE_CODE_OAUTH_TOKEN=%s\n" "$T" >> "$f.nieuw"; chmod --reference="$f" "$f.nieuw" 2>/dev/null || true
    chmod go-rwx "$f.nieuw"; mv "$f.nieuw" "$f"
    export CLAUDE_CODE_OAUTH_TOKEN="$T"; unset T ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
    t="$(mktemp -d)"; p="$HOME/.local/bin:/usr/bin:/bin"; c="$HOME/.local/bin/claude"; cd "$t"
    HOME="$t" PATH="$p" "$c" -p --safe-mode --restricted --strict-mcp-config \
      --no-session-persistence --tools "" "Antwoord met precies: OK" < /dev/null 2>/dev/null | grep -q OK
    cd /; rm -rf "$t"'; then
  echo; echo "Klaar: Claude op de server is aangemeld voor een jaar. Je mag dit venster sluiten."
else
  echo; echo "De aanmelding is niet gelukt of de proef faalde. Zeg het tegen Claude."
fi
unset TOKEN
sluiten
