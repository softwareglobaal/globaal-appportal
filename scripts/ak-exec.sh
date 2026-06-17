#!/bin/sh
# Runs a python file inside authentik's Django shell:
#   sh scripts/ak-exec.sh scripts/somefile.py
set -eu
docker compose cp "$1" authentik-server:/tmp/ak-exec.py
docker compose exec -T authentik-server ak shell -c "exec(open('/tmp/ak-exec.py').read())"
