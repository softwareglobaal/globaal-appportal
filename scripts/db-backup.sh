#!/bin/sh
# Nachtelijke backup van de databases in de postgresql-container.
#
#  - authentik  : alle Authentik-state (users, groepen, providers, outposts)
#  - appportal  : de centrale gebruikersdatabase + spokes (kern/kosten/omv/…)
#
# Dumps in custom formaat (-Fc: gecomprimeerd, selectief te restoren met
# pg_restore), gedateerd in ~/backups/, en alles ouder dan RETENTIE_DAGEN
# wordt opgeruimd. Draaien kan altijd — een lopende dump stoort de apps niet.
#
# Installatie (eenmalig, crontab -e):
#   15 3 * * * cd $HOME/appportal && sh scripts/db-backup.sh >> $HOME/backups/backup.log 2>&1
#
# Terugzetten (voorbeeld appportal):
#   docker compose exec -T postgresql pg_restore -U authentik -d appportal --clean --if-exists < ~/backups/appportal-DATUM.dump
set -eu

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
RETENTIE_DAGEN="${RETENTIE_DAGEN:-14}"
STAMP=$(date +%Y%m%d-%H%M)

mkdir -p "$BACKUP_DIR"

for db in authentik appportal; do
    bestand="$BACKUP_DIR/$db-$STAMP.dump"
    docker compose exec -T postgresql pg_dump -U authentik -d "$db" -Fc > "$bestand"
    echo "$(date '+%F %T') OK  $bestand ($(du -h "$bestand" | cut -f1))"
done

# Rotatie: dumps ouder dan RETENTIE_DAGEN weg.
find "$BACKUP_DIR" -name '*.dump' -mtime +"$RETENTIE_DAGEN" -delete

echo "$(date '+%F %T') klaar — $(ls "$BACKUP_DIR"/*.dump 2>/dev/null | wc -l) dumps aanwezig"
