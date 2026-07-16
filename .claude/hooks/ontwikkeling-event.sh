#!/bin/sh
# Claude Code-hook: meldt een ontwikkel-event aan het platform voor de
# ontwikkel-statistieken (migratie 074, organisatie-dashboard tab
# Ontwikkeling). Alleen metadata: event-soort, repo, identiteit en
# sessie-id - nooit gespreksinhoud (privacy-lijn Shaniel 2026-07-16).
#
# Zonder ONTWIKKELING_TOKEN in de omgeving doet de hook niets; hij mag
# een sessie nooit blokkeren of vertragen (fire-and-forget, korte timeout).
EVENT="${1:-prompt}"
[ -n "${ONTWIKKELING_TOKEN:-}" ] || exit 0
URL="${ONTWIKKELING_URL:-https://organisatie.globaal.be/ontwikkeling/event}"

INVOER=$(cat 2>/dev/null || true)
SESSIE=$(printf '%s' "$INVOER" \
  | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
  | head -n 1)
REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
WIE=$(git config user.email 2>/dev/null)
[ -n "$WIE" ] || WIE=$(whoami 2>/dev/null || echo onbekend)

curl -s -m 4 -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-Ontwikkeling-Token: $ONTWIKKELING_TOKEN" \
  -d "{\"event\":\"$EVENT\",\"repo\":\"$REPO\",\"gebruiker\":\"$WIE\",\"sessie\":\"$SESSIE\"}" \
  >/dev/null 2>&1 &
exit 0
