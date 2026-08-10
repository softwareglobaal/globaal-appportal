#!/bin/sh
# Auto-deploy Sales/Marketing-agents (siyanagents.globaal.be), cron elke 2 min.
# De monorepo wordt door de andere deploy-scripts al op origin/main gehouden;
# dit script herbouwt de container alleen als de map siyanagents/ echt
# veranderde (vergelijkt de tree-hash), zodat er niet onnodig gebouwd wordt.
set -eu
cd "$HOME/appportal"

NIEUW=$(git rev-parse HEAD:siyanagents 2>/dev/null || echo none)
MARK="$HOME/appportal/siyanagents-data/.built"
OUD=$(cat "$MARK" 2>/dev/null || echo none)
[ "$NIEUW" = "$OUD" ] && exit 0

docker compose up -d --build app-siyanagents
mkdir -p "$HOME/appportal/siyanagents-data"
echo "$NIEUW" > "$MARK"
echo "$(date -Is) siyanagents deployed ($NIEUW)"
