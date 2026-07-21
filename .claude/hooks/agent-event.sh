#!/bin/sh
# Meldt een agent-event aan het organisatie-dashboard (migratie 077, tab
# Ontwikkeling, blok Agent-team). De orkestrerende hoofdsessie meldt
# "start" bij het spawnen van een rol en "klaar" of "fout" (met het
# tokenverbruik) zodra het resultaat binnen is. De agents melden niet
# zelf: alleen de orkestrator kent het verbruik van een afgeronde taak.
#
# Gebruik: agent-event.sh <architect|bouwer|reviewer|verifier> \
#              <start|klaar|fout> "<taakomschrijving>" [tokens]
#
# Zonder ONTWIKKELING_TOKEN doet het script niets; het mag een sessie
# nooit blokkeren of vertragen (fire-and-forget, korte timeout).
ROL="${1:-}"; EVENT="${2:-}"; TAAK="${3:-}"; TOKENS="${4:-}"
[ -n "${ONTWIKKELING_TOKEN:-}" ] || exit 0
URL="${ONTWIKKELING_AGENT_URL:-https://organisatie.globaal.be/ontwikkeling/agent-event}"

REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
WIE=$(git config user.email 2>/dev/null)
[ -n "$WIE" ] || WIE=$(whoami 2>/dev/null || echo onbekend)
# Vrije tekst veilig maken voor JSON: aanhalingstekens en backslashes eruit.
TAAK=$(printf '%s' "$TAAK" | tr -d '"\\' | cut -c1-200)

DATA="{\"rol\":\"$ROL\",\"event\":\"$EVENT\",\"taak\":\"$TAAK\",\"repo\":\"$REPO\",\"gebruiker\":\"$WIE\""
case "$TOKENS" in
  ''|*[!0-9]*) ;;
  *) DATA="$DATA,\"tokens\":$TOKENS" ;;
esac
DATA="$DATA}"

curl -s -m 4 -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-Ontwikkeling-Token: $ONTWIKKELING_TOKEN" \
  -d "$DATA" \
  >/dev/null 2>&1 &
exit 0
