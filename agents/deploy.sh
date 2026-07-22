#!/bin/sh
# Auto-deploy Agents-tegel (cron, elke 2 min). De monorepo wordt door de andere
# deploy-scripts al op origin/main gehouden; dit script herbouwt de container
# alleen als de map agents/ echt veranderde (vergelijkt de tree-hash), zodat
# er niet elke 2 minuten onnodig gebouwd wordt.
set -eu
cd "$HOME/appportal"

NIEUW=$(git rev-parse HEAD:agents 2>/dev/null || echo none)
MARK="$HOME/appportal/agents-data/.built"
OUD=$(cat "$MARK" 2>/dev/null || echo none)
[ "$NIEUW" = "$OUD" ] && exit 0

docker compose up -d --build app-agents
mkdir -p "$HOME/appportal/agents-data"
echo "$NIEUW" > "$MARK"
echo "$(date -Is) agents deployed ($NIEUW)"
