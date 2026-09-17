#!/bin/sh
# Dagelijkse Docker-opruiming: build-cache ouder dan 48 uur plus dangling images.
# Raakt draaiende containers en hun images niet. Aanleiding: schijf 90% vol op
# 27-08-2026 door 11 GB build-cache die bij elke deploy aangroeit. Sinds 17-09-2026
# dagelijks: bij het huidige deploytempo groeit de cache in vier dagen naar 5 GB.
set -eu

DOCKER="docker"
if ! $DOCKER info >/dev/null 2>&1; then
    DOCKER="sudo docker"
fi

echo "[$(date -u +'%F %T')] start, vooraf: $(df -h / | awk 'NR==2 {print $3 " gebruikt, " $4 " vrij"}')"
$DOCKER builder prune -af --filter until=48h
$DOCKER image prune -f
echo "[$(date -u +'%F %T')] klaar, daarna: $(df -h / | awk 'NR==2 {print $3 " gebruikt, " $4 " vrij"}')"
