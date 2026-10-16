#!/bin/sh
# Auto-deploy van Mehdi's agent-omgeving (mijnagents.globaal.be), cron elke 2 min op de VM:
#   */2 * * * * sh /home/ubuntu/appportal/mijnagents/deploy.sh >> /home/ubuntu/deploy-mijnagents.log 2>&1
# Bouwt de container alleen opnieuw als de map mijnagents/ in HEAD echt veranderde (tree-hash in .built). Dit script
# trekt ~/appportal niet bij: de git pull op de VM is een aparte stap.
#
# Bewaakt sinds 16-10-2026 (Codex CX7-1, CX8-1, CX9-1/2/3 en CX10), naar het voorbeeld van de werfapp-uitrol:
# - Eén uitrol tegelijk: flock over het hele script. Een bouw die langer duurt dan twee minuten wordt niet ingehaald
#   door de volgende cronronde (op 13-10-2026 rolde dezelfde revisie zo twee keer kort na elkaar uit).
# - Elke docker-aanroep heeft een tijdslimiet en krijgt het slot (fd 9) niet mee, zodat het slot altijd vrijkomt.
# - Alleen een schone werkboom: wijkt mijnagents/ af van HEAD, dan geen bouw (anders klopt .built niet met wat draait).
# - Vóór de bouw wordt de image van het draaiende, gezonde bord bewaard als :vorige. Lukt die tag niet, dan geen bouw.
# - .built verschuift pas als /gezondheid twee keer na elkaar "ok": true geeft en de container de nieuwe image draait.
# - Faalt de bouw of blijft het bord ongezond, dan gaat de vorige image terug in dienst (--force-recreate als de
#   container een andere image draait), en ook die wordt op gezondheid en image nagekeken.
# - .herstel bestaat zolang het bord een niet-nagekeken image kan draaien. De volgende ronde herstelt dan eerst, ook
#   na een afgebroken ronde of een tagfout tijdens de terugrol. Lukt dat herstel niet, dan is er geen gezond bord om
#   te beschermen en mag een nieuwere revisie wel gebouwd worden (met dezelfde terugrolimage).
# - Een mislukte revisie komt in .mislukt (revisie, tijdstip, aantal pogingen) en wacht een afkoeling: 30 min na de
#   eerste poging, daarna telkens het dubbele, hoogstens 6 uur. Zo blokkeert een tijdelijke storing een goede revisie
#   nooit blijvend. Een nieuwe revisie wacht niet. Meteen opnieuw proberen (zichtbare vrijgave):
#     rm ~/appportal/mijnagents-data/.mislukt
# Images blijven bewaard; opruimen gebeurt alleen na een expliciete beslissing. Tests: mijnagents/test_bord_deploy.py.
set -eu

DATA="$HOME/appportal/mijnagents-data"
IMG="${BORD_IMAGE:-appportal-app-mijnagents}"
DIENST=app-mijnagents  # compose-dienst en container_name (docker-compose.override.yml)
URL="${BORD_GEZOND:-http://127.0.0.1:3022/gezondheid}"
POGINGEN="${BORD_POGINGEN:-12}"
WACHT="${BORD_WACHT:-5}"
BOUW_LIMIET="${BORD_BOUW_LIMIET:-1800}"
START_LIMIET="${BORD_START_LIMIET:-300}"
AFKOELING="${BORD_AFKOELING:-1800}"
AFKOELING_MAX="${BORD_AFKOELING_MAX:-21600}"

mkdir -p "$DATA"
exec 9>"$DATA/.deploy.lock"
flock -n 9 || exit 0
cd "$HOME/appportal"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%S+00:00) mijnagents: $*"; }
# docker met tijdslimiet (KILL 10 s na TERM); het slot (fd 9) gaat niet mee naar docker of naar wat docker start
dk() { t=$1; shift; timeout -k 10 "$t" docker "$@" 9>&-; }
image_van() { dk 60 image inspect -f '{{.Id}}' "$1" 2>/dev/null || true; }
draait() { dk 60 inspect -f '{{.Image}}' "$DIENST" 2>/dev/null || true; }
# schrijf <bestand> <inhoud>: in één keer, zodat een afgebroken ronde geen half bestand achterlaat
schrijf() { printf '%s\n' "$2" > "$1.tmp" && mv -f "$1.tmp" "$1"; }

# gezond [image-id]: /gezondheid geeft twee keer na elkaar "ok": true, en de container draait die image (als gegeven)
gezond() {
  i=0; ok=0
  while :; do
    if curl -fsS -m 5 "$URL" 2>/dev/null | grep -q '"ok": *true' && { [ -z "${1:-}" ] || [ "$(draait)" = "$1" ]; }; then
      ok=$((ok + 1))
      [ "$ok" -ge 2 ] && return 0
    else
      ok=0
    fi
    i=$((i + 1))
    [ "$i" -ge "$POGINGEN" ] && return 1
    sleep "$WACHT"
  done
}

# herstel <image-id>: die image weer als :latest en de container ermee; slaagt alleen als het bord dan gezond is
herstel() {
  if ! dk 60 image tag "$1" "$IMG:latest" || [ "$(image_van "$IMG:latest")" != "$1" ]; then
    log "terugzetten mislukt: $IMG:latest wijst niet naar $1 (docker image tag faalde)"
    return 1
  fi
  if [ "$(draait)" = "$1" ] && gezond "$1"; then
    return 0  # de container draaide die image nog: de bouw faalde voor hij vervangen werd
  fi
  dk "$START_LIMIET" compose up -d --no-build --force-recreate "$DIENST" \
    || log "docker compose up --force-recreate faalde; de gezondheidscontrole beslist"
  gezond "$1"
}

# wachttijd <poging>: afkoeling na die poging, verdubbeld per poging, hoogstens AFKOELING_MAX seconden
wachttijd() {
  w=$AFKOELING; k=1
  while [ "$k" -lt "$1" ] && [ "$w" -lt "$AFKOELING_MAX" ]; do w=$((w * 2)); k=$((k + 1)); done
  [ "$w" -le "$AFKOELING_MAX" ] || w=$AFKOELING_MAX
  echo "$w"
}

# afkoelen: waar als NIEUW in .mislukt staat en de afkoeling nog loopt; zet N op het nummer van de volgende poging
afkoelen() {
  N=1
  [ -f "$DATA/.mislukt" ] || return 1
  M_REV=; M_TIJD=; M_N=
  read -r M_REV M_TIJD M_N < "$DATA/.mislukt" || true
  [ "$M_REV" = "$NIEUW" ] || return 1
  case "$M_TIJD" in ''|*[!0-9]*) M_TIJD=0 ;; esac
  case "$M_N" in ''|*[!0-9]*) M_N=1 ;; esac
  N=$((M_N + 1))
  [ "$(date +%s)" -lt $((M_TIJD + $(wachttijd "$M_N"))) ]
}

terug() {
  schrijf "$DATA/.mislukt" "$NIEUW $(date +%s) $N" || log "kon .mislukt niet schrijven"
  log "UITROL MISLUKT bij $1 (revisie $NIEUW, poging $N); volgende poging na $(($(wachttijd "$N") / 60)) min, meteen opnieuw: rm $DATA/.mislukt"
  if [ -z "$VORIGE" ]; then
    log "geen vorige image om terug te zetten: nakijken op de server"
    exit 1
  fi
  if herstel "$VORIGE"; then
    rm -f "$DATA/.herstel"
    log "vorige image $VORIGE teruggezet en gezond; .built blijft $OUD"
  else
    log "OOK DE VORIGE IMAGE IS NIET GEZOND: nakijken op de server; de volgende ronde probeert eerst opnieuw te herstellen"
  fi
  exit 1
}

NIEUW=$(git rev-parse HEAD:mijnagents) || NIEUW=
if [ -z "$NIEUW" ]; then
  log "git rev-parse HEAD:mijnagents faalde; geen uitrol"
  exit 1
fi
OUD=$(cat "$DATA/.built" 2>/dev/null || echo none)

H_ID=; H_REV=; H_N=
if [ -f "$DATA/.herstel" ]; then
  read -r H_ID H_REV H_N < "$DATA/.herstel" || true
  if [ -z "$H_ID" ] || [ -z "$H_REV" ]; then
    log ".herstel is onleesbaar; weggehaald"
    rm -f "$DATA/.herstel"
  elif [ "$H_REV" = "$OUD" ]; then
    rm -f "$DATA/.herstel"  # die uitrol was geslaagd; alleen de opruiming ontbrak
  fi
fi
if [ ! -f "$DATA/.herstel" ]; then
  [ "$NIEUW" = "$OUD" ] && exit 0
  afkoelen && exit 0
fi

if ! dk 60 version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  log "docker niet bereikbaar; geen uitrol in deze ronde ($NIEUW)"
  exit 1
fi

# Herstel heeft voorrang op een nieuwe bouw.
STATUS=0
if [ -f "$DATA/.herstel" ]; then
  case "$H_N" in ''|*[!0-9]*) H_N=1 ;; esac
  schrijf "$DATA/.mislukt" "$H_REV $(date +%s) $H_N" || log "kon .mislukt niet schrijven"
  log "een vorige ronde liet revisie $H_REV niet nagekeken achter; eerst terug naar $H_ID"
  if herstel "$H_ID"; then
    rm -f "$DATA/.herstel"
    log "hersteld: $H_ID draait en is gezond; .built blijft $OUD"
  else
    STATUS=1
    log "HERSTEL MISLUKT: het bord is niet gezond op $H_ID; nakijken op de server"
  fi
  [ "$NIEUW" = "$OUD" ] && exit "$STATUS"
  afkoelen && exit "$STATUS"
fi

WERKBOOM=$(git status --porcelain -- mijnagents) || WERKBOOM="git status faalde"
if [ -n "$WERKBOOM" ]; then
  log "de werkboom mijnagents/ wijkt af van HEAD; geen bouw van $NIEUW tot dat nagekeken is:"
  echo "$WERKBOOM"
  exit 1
fi

# Terugrolimage: het draaiende bord als het gezond is, anders de laatst bekende goede image.
if [ -f "$DATA/.herstel" ]; then
  VORIGE=$H_ID
elif gezond; then
  VORIGE=$(draait)
  if [ -z "$VORIGE" ] || ! dk 60 image tag "$VORIGE" "$IMG:vorige" || [ "$(image_van "$IMG:vorige")" != "$VORIGE" ]; then
    log "de draaiende image kon niet als $IMG:vorige bewaard worden; geen bouw in deze ronde, het bord draait door"
    exit 1
  fi
else
  VORIGE=$(image_van "$IMG:vorige")
  log "het bord is voor de bouw niet gezond; terugrolimage: ${VORIGE:-geen}"
fi

if [ -n "$VORIGE" ] && ! schrijf "$DATA/.herstel" "$VORIGE $NIEUW $N"; then
  log "kon .herstel niet schrijven; geen bouw in deze ronde"
  exit 1
fi
dk "$BOUW_LIMIET" compose up -d --build "$DIENST" || terug "het bouwen"
NIEUW_ID=$(image_van "$IMG:latest")
if [ -z "$NIEUW_ID" ] || ! gezond "$NIEUW_ID"; then
  terug "de gezondheidscontrole"
fi
if ! schrijf "$DATA/.built" "$NIEUW"; then
  log "kon .built niet schrijven; de volgende ronde zet de vorige image terug"
  exit 1
fi
rm -f "$DATA/.mislukt" "$DATA/.herstel"
log "deployed ($NIEUW), gezond op $NIEUW_ID"
