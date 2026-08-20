#!/bin/sh
# Draait een python-bestand in de Django-shell van authentik:
#   sh scripts/ak-exec.sh scripts/somefile.py
#
# Waarom `docker compose cp` en niet een pijp: een pijp lijkt eenvoudiger, maar
# `docker compose exec -T` geeft de EOF van die pijp niet betrouwbaar door aan
# het proces in de container. De `cat` daarbinnen blijft dan wachten en het
# script hangt tot de timeout, met een achtergebleven proces per poging
# (nagemeten 20-08-2026: vier stuks). Een cp heeft dat probleem niet.
#
# De retry staat er omdat diezelfde cp op 20-08-2026 twee keer achter elkaar
#   Error response from daemon: Could not find the file /proc/self/fd in container
# gaf en daarna uit zichzelf weer werkte. Niet reproduceerbaar, oorzaak
# onbekend, dus een tweede poging in plaats van een verklaring.
#
# De `< /dev/null` op de laatste regel houdt `ak shell` los van de stdin van de
# aanroeper; over ssh blijft dat kanaal anders open en hangt het commando.
set -eu

n=0
while :; do
    if docker compose cp "$1" authentik-server:/tmp/ak-exec.py; then
        break
    fi
    n=$((n + 1))
    if [ "$n" -ge 3 ]; then
        echo "ak-exec: kopieren naar de container lukt niet na $n pogingen" >&2
        exit 1
    fi
    echo "ak-exec: kopieren mislukt, poging $((n + 1)) van 3" >&2
    sleep 2
done

docker compose exec -T authentik-server \
    ak shell -c "exec(open('/tmp/ak-exec.py').read())" < /dev/null
