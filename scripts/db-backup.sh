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
# OFF-SITE (optioneel): staat S3_BACKUP_BUCKET in .env, dan wordt elke dump
# GPG-versleuteld (AES256, passphrase uit ~/.backup-passphrase, chmod 600 —
# bewaar hem óók in de wachtwoordkluis: zonder passphrase zijn de off-site
# backups waardeloos) en geüpload naar s3://$S3_BACKUP_BUCKET/. Opruimen daar
# doet de bucket zelf (lifecycle-regel, 30 dagen). De upload-sleutel mag
# ALLEEN PutObject — een gekaapte VM kan de off-site backups dus niet lezen
# of wissen. Vereist: awscli + gnupg (apt) en `aws configure`.
#
# Installatie (eenmalig, crontab -e):
#   15 3 * * * cd $HOME/appportal && sh scripts/db-backup.sh >> $HOME/backups/backup.log 2>&1
#
# Terugzetten (voorbeeld appportal):
#   docker compose exec -T postgresql pg_restore -U authentik -d appportal --clean --if-exists < ~/backups/appportal-DATUM.dump
# Terugzetten vanaf S3: download .dump.gpg via de AWS-console, dan
#   gpg -d --passphrase-file ~/.backup-passphrase --batch appportal-DATUM.dump.gpg > herstel.dump
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

# Off-site: versleuteld naar S3 (alleen als S3_BACKUP_BUCKET geconfigureerd is).
S3_BUCKET="${S3_BACKUP_BUCKET:-}"
if [ -z "$S3_BUCKET" ] && [ -f .env ]; then
    S3_BUCKET=$(grep '^S3_BACKUP_BUCKET=' .env | cut -d= -f2- || true)
fi
PASSFILE="${BACKUP_PASSPHRASE_FILE:-$HOME/.backup-passphrase}"
if [ -n "$S3_BUCKET" ]; then
    if [ ! -f "$PASSFILE" ]; then
        echo "$(date '+%F %T') FOUT off-site: $PASSFILE ontbreekt — geen upload" >&2
        exit 1
    fi
    for db in authentik appportal; do
        bestand="$BACKUP_DIR/$db-$STAMP.dump"
        gpg --batch --yes --symmetric --cipher-algo AES256 \
            --passphrase-file "$PASSFILE" -o "$bestand.gpg" "$bestand"
        aws s3 cp --only-show-errors "$bestand.gpg" "s3://$S3_BUCKET/$db-$STAMP.dump.gpg"
        rm -f "$bestand.gpg"
        echo "$(date '+%F %T') OK  off-site s3://$S3_BUCKET/$db-$STAMP.dump.gpg"
    done
fi

echo "$(date '+%F %T') klaar — $(ls "$BACKUP_DIR"/*.dump 2>/dev/null | wc -l) dumps aanwezig"
