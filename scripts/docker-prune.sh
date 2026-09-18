#!/bin/sh
# Dagelijkse Docker-opruiming: de volledige build-cache plus dangling images.
# Raakt draaiende containers en hun images niet. Aanleiding: schijf 90% vol op
# 27-08-2026 door 11 GB build-cache die bij elke deploy aangroeit. Sinds 17-09-2026
# dagelijks. Sinds 18-09-2026 zonder until-filter: bij ~6 GB verse cache per dag
# is de cache nooit oud genoeg om weggesneden te worden voor de schijf vol is.
# De prijs is een koude eerste build per dag; schijf is de knellende grens, niet bouwtijd.
set -eu

DOCKER="docker"
if ! $DOCKER info >/dev/null 2>&1; then
    DOCKER="sudo docker"
fi

echo "[$(date -u +'%F %T')] start, vooraf: $(df -h / | awk 'NR==2 {print $3 " gebruikt, " $4 " vrij"}')"
$DOCKER builder prune -af
$DOCKER image prune -f
echo "[$(date -u +'%F %T')] klaar, daarna: $(df -h / | awk 'NR==2 {print $3 " gebruikt, " $4 " vrij"}')"
