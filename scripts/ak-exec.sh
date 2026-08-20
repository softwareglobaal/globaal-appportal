#!/bin/sh
# Draait een python-bestand in de Django-shell van authentik:
#   sh scripts/ak-exec.sh scripts/somefile.py
#
# Het bestand gaat via een pijp naar binnen en niet via `docker compose cp`.
# Reden: op 20-08-2026 gaf die cp twee keer achter elkaar
#   Error response from daemon: Could not find the file /proc/self/fd in container
# waarna hij uit zichzelf weer werkte. Niet reproduceerbaar, ook niet met een
# gelijktijdige deploy erdoorheen, dus de oorzaak is onbekend. Een pijp heeft
# die stap simpelweg niet nodig, en dat is genoeg reden om hem niet te gebruiken
# in een script dat anderen draaien.
#
# De `< /dev/null` op de tweede regel is niet vrijblijvend: zonder die
# afsluiting erft `ak shell` de stdin van de aanroeper. Draai je dit over ssh,
# dan blijft dat kanaal open en hangt het commando tot de timeout.
set -eu
cat "$1" | docker compose exec -T authentik-server sh -c 'cat > /tmp/ak-exec.py'
docker compose exec -T authentik-server \
    ak shell -c "exec(open('/tmp/ak-exec.py').read())" < /dev/null
