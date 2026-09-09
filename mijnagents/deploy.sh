#!/bin/sh
# Auto-deploy Mehdi's agent-omgeving (mijnagents.globaal.be), cron elke 2 min.
# Herbouwt de container alleen als de map mijnagents/ echt veranderde
# (vergelijkt de tree-hash), zodat er niet onnodig gebouwd wordt.
set -eu
cd "$HOME/appportal"

NIEUW=$(git rev-parse HEAD:mijnagents 2>/dev/null || echo none)
MARK="$HOME/appportal/mijnagents-data/.built"
OUD=$(cat "$MARK" 2>/dev/null || echo none)
[ "$NIEUW" = "$OUD" ] && exit 0

docker compose up -d --build app-mijnagents
mkdir -p "$HOME/appportal/mijnagents-data"
echo "$NIEUW" > "$MARK"
echo "$(date -Is) mijnagents deployed ($NIEUW)"
