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
# Pas als gebouwd markeren als het bord na de bouw echt antwoordt (Codex CX7-1, 16-10-2026). Zakt het, dan blijft .built
# op de vorige revisie staan en probeert de volgende cronronde opnieuw; de fout staat in het log.
GEZOND="${BORD_GEZOND:-http://127.0.0.1:3022/gezondheid}"
i=0
until curl -fsS -m 5 "$GEZOND" 2>/dev/null | grep -q '"ok": *true'; do
  i=$((i + 1))
  if [ "$i" -ge "${BORD_POGINGEN:-12}" ]; then
    echo "$(date -Is) mijnagents NIET gezond na de bouw ($NIEUW); .built niet bijgewerkt, volgende ronde opnieuw"
    exit 1
  fi
  sleep "${BORD_WACHT:-5}"
done
echo "$NIEUW" > "$MARK"
echo "$(date -Is) mijnagents deployed ($NIEUW), gezond"
