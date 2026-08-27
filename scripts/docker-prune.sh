#!/bin/sh
# Wekelijkse Docker-opruiming: build-cache ouder dan 7 dagen plus dangling images.
# Raakt draaiende containers en hun images niet. Aanleiding: schijf 90% vol op
# 27-08-2026 door 11 GB build-cache die bij elke deploy aangroeit.
set -eu

DOCKER="docker"
if ! $DOCKER info >/dev/null 2>&1; then
    DOCKER="sudo docker"
fi

echo "[$(date -u +'%F %T')] start, vooraf: $(df -h / | awk 'NR==2 {print $3 " gebruikt, " $4 " vrij"}')"
$DOCKER builder prune -af --filter until=168h
$DOCKER image prune -f
echo "[$(date -u +'%F %T')] klaar, daarna: $(df -h / | awk 'NR==2 {print $3 " gebruikt, " $4 " vrij"}')"
