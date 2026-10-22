#!/bin/sh
# Auto-deploy Mehdi's agent-omgeving (mijnagents.globaal.be), cron elke 2 min.
# Herbouwt de container alleen als de map mijnagents/ echt veranderde
# (vergelijkt de tree-hash), zodat er niet onnodig gebouwd wordt.
# RZ4-07 (herstelcontrole van Codex, 22-10-2026): de markering .built komt pas
# na een geslaagde routetoets op de nieuw gestarte container: /gezondheid
# (leest de databank, schrijft niets) geeft ok true en de bordpagina / antwoordt,
# op 127.0.0.1:3022 (de poort uit docker-compose.override.yml), met een
# time-out per aanroep en zes pogingen. Faalt de toets, dan geen markering, een
# logregel en exit 1: de volgende tik bouwt en toetst opnieuw. Tot dan gold een
# container die niet werkte als gebouwd, en zette
# mijnagents-runner/planning/gesprekken_cron_zetten.py de planning toch.
set -eu
cd "$HOME/appportal"

NIEUW=$(git rev-parse HEAD:mijnagents 2>/dev/null || echo none)
MARK="$HOME/appportal/mijnagents-data/.built"
OUD=$(cat "$MARK" 2>/dev/null || echo none)
[ "$NIEUW" = "$OUD" ] && exit 0

docker compose up -d --build app-mijnagents

BORD="http://127.0.0.1:3022"
POGINGEN=6
routetoets() {
  curl -fsS --max-time 5 "$BORD/gezondheid" 2>/dev/null | grep -Eq '"ok": ?true' &&
    curl -fsS --max-time 5 -o /dev/null "$BORD/" 2>/dev/null
}
poging=1
until routetoets; do
  if [ "$poging" -ge "$POGINGEN" ]; then
    echo "$(date -Is) mijnagents NIET als gebouwd gemarkeerd ($NIEUW): routetoets op $BORD (/gezondheid en /) faalde na $POGINGEN pogingen; de volgende tik probeert opnieuw"
    exit 1
  fi
  poging=$((poging + 1))
  sleep 5
done
mkdir -p "$HOME/appportal/mijnagents-data"
echo "$NIEUW" > "$MARK"
echo "$(date -Is) mijnagents deployed ($NIEUW)"
