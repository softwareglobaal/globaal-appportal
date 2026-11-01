#!/bin/bash
# Claude op de server (VM globaal) aanmelden met het abonnement van Mehdi, voor de agents die Claude gebruiken zonder
# API-sleutel (koppelingen/claude_abonnement.py). Eenmalig, een jaar geldig. Dubbelklikken in Finder: je browser opent,
# je meldt je aan met je Claude-account en klikt op Authorize. Je kopieert of plakt niets.
# Het token gaat via ssh-stdin naar ~/.config/prijsonderzoeker/claude-token op de VM (map 700, bestand 600), de plek
# die alle agents op het abonnement lezen (ook De Prijsonderzoeker), nooit in een log of de proceslijst. De opname van setup-token staat kort in een tijdelijk bestand (0600)
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

# Schrijft het tokenbestand op de VM (vervangt een oud token), daarna een korte proef op de VM.
if printf '%s\n' "$TOKEN" | ssh globaal 'set -e; read -r T; umask 077; d="$HOME/.config/prijsonderzoeker"
    mkdir -p "$d"; chmod 700 "$d"; printf "%s\n" "$T" > "$d/claude-token.nieuw"; chmod 600 "$d/claude-token.nieuw"
    mv "$d/claude-token.nieuw" "$d/claude-token"
    export CLAUDE_CODE_OAUTH_TOKEN="$T"; unset T ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
    # Proef zonder modelvraag en dus zonder kosten (Codex, controle 22): geen beheerde instellingen op de VM en
    # `claude auth status` meldt het abonnementstoken van Anthropic zelf, net als claude_abonnement.controleer_bron.
    for m in /etc/claude-code; do for n in managed-settings.json managed-settings.d managed-mcp.json; do
      [ ! -e "$m/$n" ] || exit 3; done; done
    t="$(mktemp -d)"; p="$HOME/.local/bin:/usr/bin:/bin"; c="$HOME/.local/bin/claude"; cd "$t"
    s="$(HOME="$t" CLAUDE_CONFIG_DIR="$t/.claude" PATH="$p" "$c" auth status --json < /dev/null 2>/dev/null)"
    cd /; rm -rf "$t"
    printf "%s" "$s" | grep -q "\"authMethod\": *\"oauth_token\"" && printf "%s" "$s" | grep -q "\"apiProvider\": *\"firstParty\"" \
      && ! printf "%s" "$s" | grep -q "apiKeySource"'; then
  echo; echo "Klaar: Claude op de server is aangemeld voor een jaar. Je mag dit venster sluiten."
else
  echo; echo "De aanmelding is niet gelukt of de proef faalde. Zeg het tegen Claude."
fi
unset TOKEN
sluiten
