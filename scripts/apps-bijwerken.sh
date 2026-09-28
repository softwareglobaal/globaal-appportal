#!/bin/sh
# Zet nieuwe apps uit apps.yaml vanzelf klaar. Draait via cron op de VM.
#
#   */5 * * * * cd ~/appportal && sh scripts/apps-bijwerken.sh
#
# Stil als er niets te doen is. Bij werk of bij een fout schrijft hij naar
# ~/apps-bijwerken.log.
#
# Wat dit script WEL doet: een app die in apps.yaml staat maar nog geen
# nginx-blok of compose-service heeft, alsnog aanmaken en starten.
#
# Wat het BEWUST NIET doet, en waarom:
#
#   Bestaande apps aanraken. Alleen wat ontbreekt wordt aangemaakt;
#   nieuwe-app.py weigert te overschrijven. Een app die al draait kan hier dus
#   niet door omvallen.
#
#   Apps verwijderen. Haal je een entry uit apps.yaml, dan blijft alles staan.
#   Weghalen is een bewuste handeling, geen bijwerking van een cron.
#
#   nginx herladen zonder test. Eerst nginx -t; zakt die, dan blijft de oude
#   configuratie draaien en staat de fout in het log. Dat is precies het risico
#   dat auto-deploy op deze repo lang tegenhield.
#
#   De rest van de stack uitrollen. Migraties, compose-wijzigingen met de hand
#   en nginx-sjablonen die iemand zelf heeft aangepast blijven handwerk.
set -eu

cd "$(dirname "$0")/.."
LOG=$HOME/apps-bijwerken.log
SLOT=$HOME/.apps-bijwerken.slot

log() { echo "$(date -Is) $*" >> "$LOG"; }

# Twee cron-rondes tegelijk zouden elkaar in de weg zitten.
if ! mkdir "$SLOT" 2>/dev/null; then
    exit 0
fi
trap 'rmdir "$SLOT" 2>/dev/null || true' EXIT

VOOR=$(git rev-parse HEAD)
if ! git pull --quiet --ff-only 2>>"$LOG"; then
    log "FOUT: git pull mislukt"
    exit 1
fi
NA=$(git rev-parse HEAD)

# Welke actieve apps missen nog hun nginx-blok of compose-service?
ONTBREEKT=$(python3 scripts/apps-ontbrekend.py) || {
    log "FOUT: apps-ontbrekend.py gaf een fout"
    exit 1
}
if [ -z "$ONTBREEKT" ]; then
    exit 0
fi

log "nieuwe apps gevonden: $ONTBREEKT (commit $NA)"
[ "$VOOR" = "$NA" ] && log "let op: geen nieuwe commit, apps.yaml liep al voor op de stack"

for APP in $ONTBREEKT; do
    log "$APP: nginx-blok, compose-service en Authentik"
    if ! python3 scripts/nieuwe-app.py "$APP" --schrijf --registreer >>"$LOG" 2>&1; then
        log "FOUT: $APP aanmaken mislukt, overgeslagen"
        continue
    fi
    if ! docker compose up -d "app-$APP" >>"$LOG" 2>&1; then
        log "FOUT: app-$APP starten mislukt"
        continue
    fi
    log "$APP: service draait"
done

# Pas herladen als de configuratie klopt. Zakt de test, dan blijft nginx staan
# zoals hij stond en is alleen de nieuwe app nog niet bereikbaar.
if docker compose exec -T nginx nginx -t >>"$LOG" 2>&1; then
    docker compose up -d --force-recreate nginx >>"$LOG" 2>&1
    log "nginx herladen"
else
    log "FOUT: nginx -t zakt, NIET herladen. Oude configuratie blijft draaien."
    exit 1
fi

log "klaar"
