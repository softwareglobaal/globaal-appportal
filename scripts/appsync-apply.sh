#!/bin/sh
# Host-side apply for appsync. Run from the AppPortal repo root (where
# docker-compose.yml and .env live). Makes the files that appsync wrote into
# apps.d/, nginx/templates/, certs/extra-subdomains and authentik/blueprints/
# actually live:
#   1. reissue the TLS cert so the new subdomain is in the SAN (certgen is
#      idempotent — it only regenerates when the subdomain set changed);
#   2. reload nginx so the new server block + cert take effect.
# The portal tile (apps.d) and the Authentik blueprint are picked up
# automatically (portal merges apps.d per request; Authentik watches /blueprints).
#
# Triggered by the systemd path unit vm/appsync-apply.path, or run by hand.
set -eu

# Resolve the repo root: the directory this script lives in, one level up.
REPO_ROOT="${APPSYNC_REPO_ROOT_HOST:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
cd "$REPO_ROOT"

echo "appsync-apply: reissuing certificate (certgen)…"
docker compose up -d certgen

echo "appsync-apply: reloading nginx…"
# nginx -t first so a bad generated block never takes the proxy down.
if docker compose exec -T nginx nginx -t; then
    docker compose exec -T nginx nginx -s reload
    echo "appsync-apply: done."
else
    echo "appsync-apply: nginx config test FAILED — not reloading. Check 50-autoapps.conf.template." >&2
    exit 1
fi
