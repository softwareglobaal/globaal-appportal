#!/bin/sh
# Auto-deploy van Mehdi's agent-omgeving (mijnagents.globaal.be), cron elke 2 min op de VM:
#   */2 * * * * sh /home/ubuntu/appportal/mijnagents/deploy.sh >> /home/ubuntu/deploy-mijnagents.log 2>&1
# Bouwt het bord alleen opnieuw als de map mijnagents/ in HEAD veranderde (tree-hash in .built). Dit script trekt
# ~/appportal niet bij: de git pull op de VM is een aparte stap.
#
# Bewaakt sinds 16-10-2026 (Codex CX7-1, CX8-1, CX9-1/2/3, CX10 en BU-1 tot BU-13), naar het voorbeeld van de werfapp:
# - Eén uitrol tegelijk: flock over het hele script. Wie het bord met de hand opnieuw opbouwt, neemt hetzelfde slot:
#     flock ~/appportal/mijnagents-data/.deploy.lock docker compose up -d ... app-mijnagents
# - Elke docker-aanroep heeft een tijdslimiet (KILL 10 s na TERM) en krijgt het slot (fd 9) niet mee.
# - Gebouwd wordt precies de vastgelegde commit: git archive van HEAD:mijnagents naar een eigen map, los van de
#   werkboom (geen genegeerde of niet vastgelegde bestanden, een git pull tijdens de bouw verandert niets). De image
#   draagt de tree-hash als label mijnagents.tree.
# - CI-grendel: mijnagents/deploy_ci.py eist een geslaagde run van bord-grendels op main voor exact deze commit.
#   Rood, lopend, ontbrekend of GitHub onbereikbaar: geen bouw, de volgende ronde kijkt opnieuw.
# - Zonder bestaande mijnagents.db geen bouw. Direct vóór het vervangen van de container een kopie (sqlite3 .backup,
#   integrity_check, minstens één actieve agent, gzip) in ~/backups/voor-uitrol/; mislukt ze, dan start de nieuwe image
#   niet. De terugrol hieronder zet alleen de image terug, niet de databank. Terugzetten gebeurt met de hand, met het
#   bord gestopt (zie scripts/terugzetproef-sqlite.sh). De kopieën vallen onder de rotatie van scripts/db-backup.sh.
# - Vóór de bouw wordt de image van het draaiende, gezonde bord bewaard als :vorige (eerst het ID, dan gezondheid voor
#   precies dat ID, dan de tag, dan nacontrole). Lukt dat niet, dan geen bouw.
# - .built verschuift pas als /gezondheid drie keer na elkaar een volledig JSON-antwoord met "ok": true en minstens één
#   actieve agent geeft, en de container de nieuwe image draait (met het juiste label).
# - Faalt de bouw, de start of de gezondheid, dan gaat de vorige image terug in dienst (--force-recreate als de container
#   een andere image draait), en ook die wordt op gezondheid en image nagekeken.
# - .herstel bestaat zolang het bord een niet-nagekeken image kan draaien. Een volgende ronde kijkt eerst wat er echt
#   draait: de nieuwe revisie gezond (dan alsnog .built), de vorige image gezond (dan niets), anders terugzetten. Lukt
#   dat herstel niet, dan is er geen gezond bord te beschermen en mag een nieuwere revisie wel gebouwd worden.
# - Een mislukte revisie komt in .mislukt (revisie, tijdstip, aantal pogingen) en wacht: 30 min na de eerste poging,
#   daarna telkens het dubbele, hoogstens 6 uur. Een nieuwe revisie wacht niet. Meteen opnieuw (zichtbare vrijgave):
#     rm ~/appportal/mijnagents-data/.mislukt
# - Zonder nieuwe revisie kijkt elke ronde of de container draait wat .built zegt (anders volgt .built de werkelijkheid
#   en wordt HEAD opnieuw uitgerold) en één keer naar /gezondheid, met een logregel als dat verandert.
# Images blijven bewaard; opruimen gebeurt alleen na een expliciete beslissing.
# Tests: mijnagents/test_bord_deploy.py en test_deploy_ci.py, in de CI via .github/workflows/bord-grendels.yml.
set -eu

DATA="$HOME/appportal/mijnagents-data"
DB="$DATA/mijnagents.db"
IMG="${BORD_IMAGE:-appportal-app-mijnagents}"
DIENST=app-mijnagents  # compose-dienst en container_name (docker-compose.override.yml)
URL="${BORD_GEZOND:-http://127.0.0.1:3022/gezondheid}"
POGINGEN="${BORD_POGINGEN:-12}"
STABIEL="${BORD_STABIEL:-3}"
WACHT="${BORD_WACHT:-5}"
BOUW_LIMIET="${BORD_BOUW_LIMIET:-1800}"
START_LIMIET="${BORD_START_LIMIET:-300}"
AFKOELING="${BORD_AFKOELING:-1800}"
AFKOELING_MAX="${BORD_AFKOELING_MAX:-21600}"
KOPIE_MAP="${BORD_KOPIE_MAP:-$HOME/backups/voor-uitrol}"
KOPIE_MIN_VRIJ_MB="${BORD_KOPIE_MIN_VRIJ_MB:-500}"
CI_PY="$(cd "$(dirname "$0")" && pwd)/deploy_ci.py"

mkdir -p "$DATA"
exec 9>"$DATA/.deploy.lock"
flock -n 9 || exit 0
cd "$HOME/appportal"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%S+00:00) mijnagents: $*"; }
tijdstip() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -r "$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "@$1"; }
# docker met tijdslimiet (KILL 10 s na TERM); het slot (fd 9) gaat niet mee naar docker of naar wat docker start
dk() { t=$1; shift; timeout -k 10 "$t" docker "$@" 9>&-; }
image_van() { dk 60 image inspect -f '{{.Id}}' "$1" 2>/dev/null || true; }
boom_van() { dk 60 image inspect -f '{{index .Config.Labels "mijnagents.tree"}}' "$1" 2>/dev/null || true; }
draait() { dk 60 container inspect -f '{{.Image}}' "$DIENST" 2>/dev/null || true; }
# schrijf <bestand> <inhoud>: in één keer, zodat een afgebroken ronde geen half bestand achterlaat
schrijf() { printf '%s\n' "$2" > "$1.tmp" && mv -f "$1.tmp" "$1"; }
# ok_json <antwoord>: een volledig JSON-object met "ok": true (booleaans) en minstens één actieve agent; een bord op een
# lege of verkeerde databank geeft ook "ok": true, maar met 0 agents (BU-12)
ok_json() {
  printf '%s' "$1" | python3 -c 'import json, sys
try:
    d = json.loads(sys.stdin.read())
except ValueError:
    sys.exit(1)
sys.exit(0 if isinstance(d, dict) and d.get("ok") is True and type(d.get("agents")) is int and d["agents"] >= 1 else 1)'
}
probe() { antw=$(curl -fsS -m 5 "$URL" 2>/dev/null) && ok_json "$antw"; }

# gezond [image-id]: STABIEL keer na elkaar een geslaagde probe, en de container draait die image (als gegeven)
gezond() {
  i=0; ok=0
  while :; do
    if probe && { [ -z "${1:-}" ] || [ "$(draait)" = "$1" ]; }; then
      ok=$((ok + 1))
      [ "$ok" -ge "$STABIEL" ] && return 0
    else
      ok=0
    fi
    i=$((i + 1))
    [ "$i" -ge "$POGINGEN" ] && return 1
    sleep "$WACHT"
  done
}

# bewaak: zonder uitrol nagaan dat de container draait wat .built zegt (BU-11) en één probe doen. Draait er iets anders,
# dan volgt .built de werkelijkheid (het label, of "onbekend") en rolt deze of de volgende ronde de revisie van HEAD uit.
# Een regel in het log alleen als de toestand verandert.
bewaak() {
  R_ID=$(draait)
  # alleen handelen op een geslaagde inspectie: een haperende docker zet .built niet om
  if [ -n "$R_ID" ] && R_BOOM=$(dk 60 image inspect -f '{{index .Config.Labels "mijnagents.tree"}}' "$R_ID" 2>/dev/null); then
    R_BOOM=${R_BOOM:-onbekend}  # een image zonder label (van voor 16-10-2026, of met de hand gebouwd)
    if [ "$R_BOOM" != "$OUD" ]; then
      log "LET OP: de container draait $R_ID met revisie $R_BOOM, maar .built zei $OUD; .built volgt nu wat draait"
      schrijf "$DATA/.built" "$R_BOOM" || log "kon .built niet schrijven"
      OUD=$R_BOOM
    fi
  fi
  if probe; then
    if [ -f "$DATA/.ongezond" ]; then
      rm -f "$DATA/.ongezond"
      log "het bord is weer gezond (revisie $OUD)"
    fi
  elif [ ! -f "$DATA/.ongezond" ]; then
    : > "$DATA/.ongezond"
    log "LET OP: /gezondheid faalt bij een ongewijzigde revisie ($OUD); de uitrol doet daar niets aan, nakijken op de server"
  fi
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

# kopie_databank: sqlite3 .backup (consistent, ook met een open WAL), integrity_check, minstens één actieve agent, gzip.
# De terugrol zet alleen de image terug; deze kopie is het herstelpunt voor de databank (met de hand terugzetten).
kopie_databank() {
  mkdir -p "$KOPIE_MAP" || return 1
  KOPIE="$KOPIE_MAP/mijnagents-voor-uitrol-$(date -u +%Y%m%dT%H%M%SZ)-$(echo "$NIEUW" | cut -c1-12).sqlite"
  nodig=$(( $(wc -c < "$DB") / 512 + KOPIE_MIN_VRIJ_MB * 1024 ))  # KB: twee keer de databank (kopie en gzip) plus marge
  vrij=$(df -Pk "$KOPIE_MAP" | awk 'NR == 2 { print $4 }')
  if [ "${vrij:-0}" -lt "$nodig" ]; then
    log "te weinig vrije ruimte voor een kopie van de databank ($vrij KB vrij, $nodig KB nodig)"
    return 1
  fi
  agents=
  if timeout -k 10 600 sqlite3 -readonly "$DB" ".backup '$KOPIE'" 9>&- \
     && [ "$(timeout -k 10 600 sqlite3 "$KOPIE" 'PRAGMA integrity_check;' 9>&-)" = ok ] \
     && agents=$(timeout -k 10 60 sqlite3 "$KOPIE" 'SELECT COUNT(*) FROM agent WHERE actief=1;' 9>&-) \
     && [ "${agents:-0}" -ge 1 ] 2>/dev/null \
     && timeout -k 10 600 gzip -f "$KOPIE" 9>&-; then
    log "kopie van de databank ($agents actieve agents): $KOPIE.gz"
    return 0
  fi
  rm -f "$KOPIE"
  log "kopie van de databank mislukt of onvolledig (actieve agents: ${agents:-?})"
  return 1
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

# markeer_mislukt <revisie> <poging>
markeer_mislukt() {
  nu=$(date +%s)
  schrijf "$DATA/.mislukt" "$1 $nu $2" || log "kon .mislukt niet schrijven"
  log "revisie $1 telt als mislukt (poging $2); volgende poging vanaf $(tijdstip $((nu + $(wachttijd "$2"))))," \
      "meteen opnieuw: rm $DATA/.mislukt"
}

terug() {
  log "UITROL MISLUKT bij $1 (revisie $NIEUW, commit $SHA, poging $N)"
  markeer_mislukt "$NIEUW" "$N"
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

SHA=$(git rev-parse HEAD) || SHA=
NIEUW=
[ -n "$SHA" ] && { NIEUW=$(git rev-parse "$SHA:mijnagents") || NIEUW=; }
if [ -z "$NIEUW" ]; then
  log "git rev-parse van HEAD of HEAD:mijnagents faalde; geen uitrol"
  exit 1
fi
OUD=$(cat "$DATA/.built" 2>/dev/null || echo none)

H_ID=; H_REV=; H_N=
if [ -f "$DATA/.herstel" ]; then
  read -r H_ID H_REV H_N < "$DATA/.herstel" || true
  case "$H_N" in ''|*[!0-9]*) H_N=1 ;; esac
  if [ -z "$H_ID" ] || [ -z "$H_REV" ]; then
    log ".herstel is onleesbaar; weggehaald"
    rm -f "$DATA/.herstel"
  fi
fi
if [ ! -f "$DATA/.herstel" ]; then
  if [ "$NIEUW" = "$OUD" ] || afkoelen; then
    bewaak
    if [ "$NIEUW" = "$OUD" ] || afkoelen; then exit 0; fi
  fi
fi

if ! dk 60 version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  log "docker niet bereikbaar; geen uitrol in deze ronde ($NIEUW)"
  exit 1
fi

# Een onderbroken ronde gaat voor: eerst kijken wat er echt draait.
STATUS=0
if [ -f "$DATA/.herstel" ]; then
  R_ID=$(draait)
  if [ -n "$R_ID" ] && [ "$(boom_van "$R_ID")" = "$H_REV" ] && gezond "$R_ID"; then
    schrijf "$DATA/.built" "$H_REV"
    rm -f "$DATA/.herstel" "$DATA/.mislukt"
    OUD=$H_REV
    log "een vorige ronde stopte na een gezonde uitrol van $H_REV; nu als gebouwd gemarkeerd"
  else
    if [ -n "$R_ID" ] && [ "$R_ID" = "$H_ID" ] && gezond "$H_ID"; then
      log "een vorige ronde stopte voor de nieuwe image draaide; de vorige image $H_ID draait gezond"
    else
      log "een vorige ronde liet revisie $H_REV niet nagekeken achter; eerst terug naar $H_ID"
      markeer_mislukt "$H_REV" "$H_N"
    fi
    # herstel zet ook :latest terug op $H_ID en kijkt na; draait $H_ID al gezond, dan zonder nieuwe container (BU-10)
    if herstel "$H_ID"; then
      rm -f "$DATA/.herstel"
      if [ "$OUD" = "$H_REV" ]; then  # .built mag niet de revisie noemen die niet draait (BU-10)
        OUD=$(boom_van "$H_ID"); OUD=${OUD:-onbekend}
        schrijf "$DATA/.built" "$OUD" || log "kon .built niet schrijven"
      fi
      log "hersteld: $H_ID draait en is gezond; .built is $OUD"
    else
      STATUS=1
      log "HERSTEL MISLUKT: het bord is niet gezond op $H_ID; nakijken op de server"
    fi
  fi
  [ "$NIEUW" = "$OUD" ] && exit "$STATUS"
  afkoelen && exit "$STATUS"
fi

# CI-grendel op exact deze commit. Een melding alleen als de reden verandert.
if CI=$(timeout -k 10 180 python3 "$CI_PY" --sha "$SHA" 2>&1 9>&-); then
  rm -f "$DATA/.ci_wacht"
else
  if [ "$(cat "$DATA/.ci_wacht" 2>/dev/null)" != "$SHA $CI" ]; then
    schrijf "$DATA/.ci_wacht" "$SHA $CI" || true
    log "CI blokkeert de uitrol van $SHA: $CI; de volgende ronde kijkt opnieuw"
  fi
  exit 1
fi

# Bron: precies deze tree, los van de werkboom.
BRON=$(mktemp -d "${TMPDIR:-/tmp}/mijnagents-bron.XXXXXX")
trap 'rm -rf "${BRON:?}" "${BRON:?}.tar"' EXIT
if ! git archive --format=tar -o "$BRON.tar" "$NIEUW" || ! tar -xf "$BRON.tar" -C "$BRON"; then
  log "git archive van $NIEUW mislukt; geen uitrol in deze ronde"
  exit 1
fi

# Zonder de bestaande databank geen uitrol: het nieuwe bord zou een lege aanmaken (BU-12).
if [ ! -f "$DB" ] || [ ! -r "$DB" ]; then
  log "de databank $DB ontbreekt of is niet leesbaar; geen uitrol in deze ronde"
  exit 1
fi

# Terugrolimage: het draaiende bord als het gezond is, anders de laatst bekende goede image.
if [ -f "$DATA/.herstel" ]; then
  VORIGE=$H_ID
else
  R_ID=$(draait)
  if [ -n "$R_ID" ] && gezond "$R_ID"; then
    if ! dk 60 image tag "$R_ID" "$IMG:vorige" || [ "$(image_van "$IMG:vorige")" != "$R_ID" ] || [ "$(draait)" != "$R_ID" ]; then
      log "de draaiende image kon niet als $IMG:vorige bewaard worden; geen bouw in deze ronde, het bord draait door"
      exit 1
    fi
    VORIGE=$R_ID
  else
    VORIGE=$(image_van "$IMG:vorige")
    log "het bord is voor de bouw niet gezond; terugrolimage: ${VORIGE:-geen}"
  fi
fi

if [ -n "$VORIGE" ] && ! schrijf "$DATA/.herstel" "$VORIGE $NIEUW $N"; then
  log "kon .herstel niet schrijven; geen bouw in deze ronde"
  exit 1
fi
dk "$BOUW_LIMIET" build -t "$IMG:latest" --label "mijnagents.tree=$NIEUW" \
  --label "org.opencontainers.image.revision=$SHA" "$BRON" || terug "het bouwen"
NIEUW_ID=$(image_van "$IMG:latest")
if [ -z "$NIEUW_ID" ] || [ "$(boom_van "$NIEUW_ID")" != "$NIEUW" ]; then
  terug "de bouw (de image draagt revisie $NIEUW niet)"
fi
# Kopie direct vóór het vervangen van de container (BU-13). Mislukt ze, dan start de nieuwe image niet: :latest gaat
# terug naar de draaiende image en de volgende ronde probeert opnieuw (geen .mislukt: de revisie zelf faalde niet).
if ! kopie_databank; then
  if [ -n "$VORIGE" ] && herstel "$VORIGE"; then
    rm -f "$DATA/.herstel"
  fi
  log "geen uitrol in deze ronde: zonder kopie van de databank start de nieuwe image niet"
  exit 1
fi
dk "$START_LIMIET" compose up -d --no-build --force-recreate "$DIENST" || terug "het starten"
gezond "$NIEUW_ID" || terug "de gezondheidscontrole"
if ! schrijf "$DATA/.built" "$NIEUW"; then
  log "kon .built niet schrijven; de volgende ronde ziet de gezonde nieuwe image en markeert dan"
  exit 1
fi
rm -f "$DATA/.mislukt" "$DATA/.herstel" "$DATA/.ongezond"
log "deployed ($NIEUW, commit $SHA), gezond op $NIEUW_ID"
