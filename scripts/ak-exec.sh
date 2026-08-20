#!/bin/sh
# Draait een python-bestand in de Django-shell van authentik:
#   sh scripts/ak-exec.sh scripts/somefile.py
#   cat iets.py | sh scripts/ak-exec.sh /dev/stdin
#
# Twee dingen die hier niet vrijblijvend zijn, allebei op 20-08-2026 kapot
# gegaan en uitgezocht:
#
# 1. De bron gaat ALTIJD eerst naar een echt bestand. Roep je dit script aan met
#    /dev/stdin, dan is dat zelf een symlink naar /proc/self/fd/0, en `docker
#    cp` kopieert die symlink in plaats van de inhoud. Het doelpad in de
#    container werd daardoor een doodlopende symlink, en elke latere aanroep gaf
#    "Could not find the file /proc/self/fd in container". Dat stond er sinds
#    14 augustus en werkte al die tijd alleen bij toeval: `ak shell` las via die
#    symlink zijn eigen stdin, en daar stond het script in als je het erin pijpte.
#
# 2. Het doelbestand krijgt een unieke naam en wordt daarna opgeruimd, zodat een
#    kapot achtergelaten pad niet elke volgende aanroep meesleept.
#
# `< /dev/null` houdt `ak shell` los van de stdin van de aanroeper; over ssh
# blijft dat kanaal anders open en hangt het commando tot de timeout. Om
# dezelfde reden geen pijp naar `docker compose exec -T`: die geeft de EOF niet
# betrouwbaar door, en dan blijft er per poging een proces achter.
set -eu

bron=$(mktemp)
trap 'rm -f "$bron"' EXIT
cat "$1" > "$bron"

doel="/tmp/ak-exec-$$.py"
docker compose cp "$bron" "authentik-server:$doel"
docker compose exec -T authentik-server \
    ak shell -c "exec(open('$doel').read())" < /dev/null
docker compose exec -T authentik-server rm -f "$doel" < /dev/null || true
