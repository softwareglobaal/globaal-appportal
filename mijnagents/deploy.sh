#!/bin/sh
# Auto-deploy Mehdi's agent-omgeving (mijnagents.globaal.be), cron elke 2 min.
# Herbouwt de container alleen als de map mijnagents/ echt veranderde
# (vergelijkt de tree-hash), zodat er niet onnodig gebouwd wordt.
#
# Gezondheid en terugrol (Codex CX7-1, CX8-1, 16-10-2026): de huidige image wordt eerst bewaard als :vorige. Pas als
# /gezondheid na de bouw "ok": true geeft, wordt .built bijgewerkt. Blijft het nieuwe bord ongezond of start het niet, dan
# komt de vorige image terug (ook die wordt op gezondheid nagekeken) en staat de revisie in .mislukt: die wordt niet
# opnieuw gebouwd tot er een nieuwe revisie is. .built blijft dan op de laatste gezonde revisie staan.
set -eu
cd "$HOME/appportal"

IMG="${BORD_IMAGE:-appportal-app-mijnagents}"
DATA="$HOME/appportal/mijnagents-data"
NIEUW=$(git rev-parse HEAD:mijnagents 2>/dev/null || echo none)
MARK="$DATA/.built"
MISLUKT="$DATA/.mislukt"
OUD=$(cat "$MARK" 2>/dev/null || echo none)
[ "$NIEUW" = "$OUD" ] && exit 0
[ "$NIEUW" = "$(cat "$MISLUKT" 2>/dev/null || echo none)" ] && exit 0
mkdir -p "$DATA"

GEZOND="${BORD_GEZOND:-http://127.0.0.1:3022/gezondheid}"
gezond() {
  i=0
  until curl -fsS -m 5 "$GEZOND" 2>/dev/null | grep -q '"ok": *true'; do
    i=$((i + 1))
    [ "$i" -ge "${BORD_POGINGEN:-12}" ] && return 1
    sleep "${BORD_WACHT:-5}"
  done
  return 0
}

VORIGE=0
if docker image inspect "$IMG:latest" >/dev/null 2>&1; then
  docker image tag "$IMG:latest" "$IMG:vorige"
  VORIGE=1
fi
if docker compose up -d --build app-mijnagents && gezond; then
  echo "$NIEUW" > "$MARK"
  rm -f "$MISLUKT"
  echo "$(date -Is) mijnagents deployed ($NIEUW), gezond"
  exit 0
fi

echo "$NIEUW" > "$MISLUKT"
if [ "$VORIGE" = 1 ]; then
  docker image tag "$IMG:vorige" "$IMG:latest"
  docker compose up -d --no-build --force-recreate app-mijnagents || true
  if gezond; then
    echo "$(date -Is) mijnagents NIET gezond na de bouw ($NIEUW): vorige image teruggezet en gezond; .built blijft $OUD"
  else
    echo "$(date -Is) mijnagents NIET gezond na de bouw ($NIEUW), en ook de vorige image is niet gezond: nakijken"
  fi
else
  echo "$(date -Is) mijnagents NIET gezond na de bouw ($NIEUW) en geen vorige image om terug te zetten: nakijken"
fi
exit 1
