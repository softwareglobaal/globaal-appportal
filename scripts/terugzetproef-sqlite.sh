#!/bin/sh
# Terugzetproef van de SQLite-back-ups (werf.db en mijnagents.db), op een aparte plek.
#
#   sh scripts/terugzetproef-sqlite.sh            de nieuwste lokale back-up van elk
#
# Pakt de nieuwste werf-*.sqlite.gz en mijnagents-*.sqlite.gz uit ~/backups uit naar een
# tijdelijke map, doet een integrity_check en vergelijkt per tabel het aantal rijen met
# de live databank (alleen lezend). De live databank en de back-up worden niet gewijzigd.
# Verschillen zijn normaal voor tabellen die sinds de back-up groeiden; een tabel die in
# de back-up ontbreekt of een mislukte integriteitscontrole is een fout.
# Aanleiding: nulmeting werfbezoekketen 01-10-2026, er was nooit een terugzetproef gedaan.
set -eu

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
WERK=$(mktemp -d)
trap 'rm -rf "$WERK"' EXIT
FOUT=0

for paar in "werf:$HOME/appportal/werfverslag-data/werf.db" "mijnagents:$HOME/appportal/mijnagents-data/mijnagents.db"; do
    naam=${paar%%:*}; live=${paar#*:}
    laatste=$(ls -t "$BACKUP_DIR"/"$naam"-*.sqlite.gz 2>/dev/null | head -1 || true)
    if [ -z "$laatste" ]; then
        echo "FOUT $naam: geen back-up gevonden in $BACKUP_DIR"; FOUT=1; continue
    fi
    gunzip -c "$laatste" > "$WERK/$naam.db"
    integriteit=$(sqlite3 "$WERK/$naam.db" "PRAGMA integrity_check;")
    echo "== $naam: $(basename "$laatste"), integriteit: $integriteit"
    [ "$integriteit" = "ok" ] || FOUT=1
    for tabel in $(sqlite3 -readonly "$live" "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name;"); do
        l=$(sqlite3 -readonly "$live" "select count(*) from \"$tabel\";")
        if b=$(sqlite3 "$WERK/$naam.db" "select count(*) from \"$tabel\";" 2>/dev/null); then
            echo "   $tabel: live $l, terugzet $b"
        else
            echo "   FOUT $tabel ontbreekt in de back-up"; FOUT=1
        fi
    done
done

[ "$FOUT" = 0 ] && echo "terugzetproef geslaagd" || { echo "terugzetproef MISLUKT"; exit 1; }
