#!/bin/sh
# Auto-deploy van Mehdi's agent-omgeving (mijnagents.globaal.be), cron elke 2 min op de VM:
#   */2 * * * * sh /home/ubuntu/appportal/mijnagents/deploy.sh >> /home/ubuntu/deploy-mijnagents.log 2>&1
# Bouwt het bord alleen opnieuw als de map mijnagents/ in HEAD veranderde (tree-hash in .built, het nagekeken image-ID in
# .built_id). Dit script trekt ~/appportal niet bij: de git pull op de VM is een aparte stap.
#
# Bewaakt sinds 16-10-2026 (Codex CX7-1, CX8-1, CX9-1/2/3, CX10 en BU-1 tot BU-18), naar het voorbeeld van de werfapp:
# - Eén uitrol tegelijk: flock over het hele script.
# - Pauze: zolang ~/appportal/mijnagents-data/.pauze bestaat, doet het script niets (geen uitrol, herstel of bewaking).
#   Wie het bord met de hand terugzet of herbouwt, pauzeert eerst onder hetzelfde slot en heft de pauze daarna bewust op:
#     flock ~/appportal/mijnagents-data/.deploy.lock touch ~/appportal/mijnagents-data/.pauze
#     rm ~/appportal/mijnagents-data/.pauze
# - Elke docker-aanroep heeft een tijdslimiet (KILL 10 s na TERM) en krijgt het slot (fd 9) niet mee.
# - Gebouwd wordt precies de vastgelegde commit: git archive van HEAD:mijnagents naar een eigen map, los van de
#   werkboom. De image draagt de tree-hash als label mijnagents.tree en de commit als org.opencontainers.image.revision.
# - CI-grendel: mijnagents/deploy_ci.py eist een geslaagde run van bord-grendels op main voor exact deze commit.
#   Rood, lopend, ontbrekend of GitHub onbereikbaar: geen bouw, de volgende ronde kijkt opnieuw.
# - Voor de bouw: een bestaande, leesbare mijnagents.db en ruimte voor een kopie; de image van het draaiende, gezonde bord
#   als :vorige (eerst het ID, dan gezondheid voor dat ID, dan de tag, dan nacontrole). Anders geen bouw.
# - De bouw krijgt de tag :kandidaat. :latest en de container blijven onaangeroerd tot de wissel; een mislukte bouw raakt
#   het draaiende bord dus niet.
# - Direct voor de wissel een kopie van de databank (sqlite3 .backup, integrity_check, minstens één actieve agent, gzip)
#   in ~/backups/voor-uitrol/, en de nacontrole dat nog dezelfde image draait. Mislukt een van beide: geen wissel.
#   De terugrol zet alleen de image terug, niet de databank; terugzetten gebeurt met de hand, met het bord gestopt
#   (zie scripts/terugzetproef-sqlite.sh). De kopieën vallen onder de rotatie van scripts/db-backup.sh (14 dagen).
# - De wissel: :kandidaat wordt :latest, de container start opnieuw. .built verschuift pas als /gezondheid drie keer na
#   elkaar een volledig JSON-antwoord met "ok": true en minstens één actieve agent geeft, op precies die image.
# - Faalt de start of de gezondheid, dan gaat de vorige image terug in dienst en ook die wordt nagekeken.
# - .herstel bestaat alleen rond de wissel. Een volgende ronde kijkt eerst wat er echt draait: de nieuwe revisie gezond
#   (dan alsnog .built), de vorige image gezond (dan :latest terug), anders terugzetten. Lukt dat herstel niet, dan is er
#   geen gezond bord te beschermen en mag een nieuwere revisie wel gebouwd worden.
# - Een mislukte revisie komt in .mislukt (revisie, tijdstip, aantal pogingen) en wacht: 30 min na de eerste poging,
#   daarna telkens het dubbele, hoogstens 6 uur. Een nieuwe revisie wacht niet. Meteen opnieuw (zichtbare vrijgave):
#     rm ~/appportal/mijnagents-data/.mislukt
# - Zonder uitrol neemt het script alleen waar: draait de container niet het image-ID uit .built_id (of, zonder
#   .built_id, niet de revisie uit .built), of faalt /gezondheid, dan één logregel bij elke verandering (.afwijking).
#   Het verandert dan niets: een handmatige toestand blijft staan tot een nieuwe revisie of een bewuste ingreep.
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

# bewaak: zonder uitrol alleen waarnemen (BU-11, BU-14, BU-15, BU-16). Vergelijkt het draaiende image-ID met .built_id
# (of, voor een uitrol van voor 16-10-2026 zonder .built_id, het label met .built) en doet één probe. Een afwijking komt
# één keer in het log en in .afwijking; .built verandert niet en er wordt niets uitgerold, herstart of teruggezet.
bewaak() {
  afw=
  R_ID=$(draait)
  B_ID=$(cat "$DATA/.built_id" 2>/dev/null || true)
  if [ -n "$R_ID" ]; then
    if [ -n "$B_ID" ]; then
      [ "$R_ID" = "$B_ID" ] || afw="de container draait $R_ID, .built zegt revisie $OUD op $B_ID"
    elif R_BOOM=$(dk 60 image inspect -f '{{index .Config.Labels "mijnagents.tree"}}' "$R_ID" 2>/dev/null) \
         && [ -n "$R_BOOM" ] && [ "$R_BOOM" != "$OUD" ]; then
      afw="de container draait revisie $R_BOOM, .built zegt $OUD"
    fi
  fi
  probe || afw="${afw:+$afw; }/gezondheid faalt"
  if [ "$afw" != "$(cat "$DATA/.afwijking" 2>/dev/null || true)" ]; then
    if [ -n "$afw" ]; then
      schrijf "$DATA/.afwijking" "$afw" || true
      log "LET OP: $afw; de uitrol verandert hier niets aan, nakijken op de server"
    else
      rm -f "$DATA/.afwijking"
      log "weer in orde: de container draait wat .built zegt ($OUD) en /gezondheid slaagt"
    fi
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
# ruimte_ok: genoeg vrije ruimte voor een kopie (twee keer de databank, kopie en gzip, plus marge)
ruimte_ok() {
  mkdir -p "$KOPIE_MAP" || return 1
  nodig=$(( $(wc -c < "$DB") / 512 + KOPIE_MIN_VRIJ_MB * 1024 ))  # KB
  vrij=$(df -Pk "$KOPIE_MAP" | awk 'NR == 2 { print $4 }')
  if [ "${vrij:-0}" -lt "$nodig" ]; then
    log "te weinig vrije ruimte voor een kopie van de databank ($vrij KB vrij, $nodig KB nodig)"
    return 1
  fi
}

kopie_databank() {
  ruimte_ok || return 1
  KOPIE="$KOPIE_MAP/mijnagents-voor-uitrol-$(date -u +%Y%m%dT%H%M%SZ)-$(echo "$NIEUW" | cut -c1-12).sqlite"
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

# mislukt <reden>: de revisie faalde voor de wissel; container en :latest zijn niet aangeraakt
mislukt() {
  log "UITROL MISLUKT bij $1 (revisie $NIEUW, commit $SHA, poging $N); het bord draait ongewijzigd door"
  markeer_mislukt "$NIEUW" "$N"
  exit 1
}

# afbreken <reden>: geen wissel in deze ronde en geen .mislukt (de revisie zelf faalde niet). De container wordt niet
# aangeraakt (BU-17); alleen een halverwege mislukte wisseltag gaat terug. Een .herstel uit een eerdere ronde blijft staan.
afbreken() {
  if [ -n "$LATEST_VOOR" ] && [ "$(image_van "$IMG:latest")" != "$LATEST_VOOR" ]; then
    dk 60 image tag "$LATEST_VOOR" "$IMG:latest" 2>/dev/null || log "kon $IMG:latest niet terugzetten op $LATEST_VOOR"
  fi
  if [ "$HERSTEL_GESCHREVEN" = 1 ] && { [ -z "$LATEST_VOOR" ] || [ "$(image_van "$IMG:latest")" = "$LATEST_VOOR" ]; }; then
    rm -f "$DATA/.herstel"
  fi
  log "geen wissel in deze ronde: $1; het bord draait ongewijzigd door, de volgende ronde probeert opnieuw"
  exit 1
}

# terug <reden>: de revisie faalde na de wissel; de vorige image gaat terug in dienst
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

if [ -f "$DATA/.pauze" ]; then
  if [ ! -f "$DATA/.pauze_gemeld" ]; then
    : > "$DATA/.pauze_gemeld"
    log "gepauzeerd: geen uitrol, herstel of bewaking tot rm $DATA/.pauze"
  fi
  exit 0
fi
if [ -f "$DATA/.pauze_gemeld" ]; then
  rm -f "$DATA/.pauze_gemeld"
  log "pauze opgeheven: de uitrol loopt weer"
fi

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
    exit 0
  fi
fi

if ! dk 60 version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  log "docker niet bereikbaar; geen uitrol in deze ronde ($NIEUW)"
  exit 1
fi

# Een onderbroken ronde gaat voor: eerst kijken wat er echt draait.
STATUS=0; HERSTEL_GESCHREVEN=0; LATEST_VOOR=; VORIGE=
if [ -f "$DATA/.herstel" ]; then
  R_ID=$(draait)
  if [ -n "$R_ID" ] && [ "$(boom_van "$R_ID")" = "$H_REV" ] && gezond "$R_ID"; then
    schrijf "$DATA/.built" "$H_REV" && schrijf "$DATA/.built_id" "$R_ID"
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
        { schrijf "$DATA/.built" "$OUD" && schrijf "$DATA/.built_id" "$H_ID"; } || log "kon .built niet schrijven"
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

# Voorwaarden voor de bouw: de bestaande databank (zonder haar zou het nieuwe bord een lege aanmaken, BU-12) en ruimte
# voor de kopie (BU-18).
if [ ! -f "$DB" ] || [ ! -r "$DB" ]; then
  log "de databank $DB ontbreekt of is niet leesbaar; geen uitrol in deze ronde"
  exit 1
fi
if ! ruimte_ok; then
  log "geen uitrol in deze ronde: geen ruimte voor de kopie van de databank"
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

# De bouw als :kandidaat (BU-17): :latest en de container blijven onaangeroerd tot de wissel.
dk "$BOUW_LIMIET" build -t "$IMG:kandidaat" --label "mijnagents.tree=$NIEUW" \
  --label "org.opencontainers.image.revision=$SHA" "$BRON" || mislukt "het bouwen"
KANDIDAAT=$(image_van "$IMG:kandidaat")
if [ -z "$KANDIDAAT" ] || [ "$(boom_van "$KANDIDAAT")" != "$NIEUW" ]; then
  mislukt "de bouw (de image draagt revisie $NIEUW niet)"
fi

# Direct voor de wissel: een kopie van de databank (BU-13) en de nacontrole dat nog dezelfde image draait.
kopie_databank || afbreken "zonder kopie van de databank"
if [ -n "$VORIGE" ] && [ ! -f "$DATA/.herstel" ] && [ "$(draait)" != "$VORIGE" ]; then
  afbreken "de draaiende image is tijdens de bouw veranderd"
fi

# De wissel.
if [ -n "$VORIGE" ]; then
  schrijf "$DATA/.herstel" "$VORIGE $NIEUW $N" || afbreken "kon .herstel niet schrijven"
  HERSTEL_GESCHREVEN=1
fi
LATEST_VOOR=$(image_van "$IMG:latest")
if ! dk 60 image tag "$KANDIDAAT" "$IMG:latest" || [ "$(image_van "$IMG:latest")" != "$KANDIDAAT" ]; then
  afbreken "de tag $IMG:latest kon niet naar de kandidaat wijzen"
fi
dk "$START_LIMIET" compose up -d --no-build --force-recreate "$DIENST" || terug "het starten"
gezond "$KANDIDAAT" || terug "de gezondheidscontrole"
if ! schrijf "$DATA/.built" "$NIEUW" || ! schrijf "$DATA/.built_id" "$KANDIDAAT"; then
  log "kon .built niet schrijven; de volgende ronde ziet de gezonde nieuwe image en markeert dan"
  exit 1
fi
rm -f "$DATA/.mislukt" "$DATA/.herstel" "$DATA/.afwijking"
log "deployed ($NIEUW, commit $SHA), gezond op $KANDIDAAT"
