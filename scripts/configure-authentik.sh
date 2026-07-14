#!/bin/sh
# Applies scripts/setup-authentik.py inside the authentik-server container.
# Run from the AppPortal directory: sh scripts/configure-authentik.sh
set -eu
docker compose cp scripts/setup-authentik.py authentik-server:/tmp/setup.py
docker compose exec -T authentik-server ak shell -c "exec(open('/tmp/setup.py').read())"
