#!/usr/bin/env bash
# Rolt de AppPortal-stack uit vanaf de huidige git-staat. Eén commando i.p.v. handwerk.
set -euo pipefail
cd "$(dirname "$0")"
echo "== git pull =="
git pull --ff-only || echo "(nog geen remote of geen wijzigingen)"
echo "== docker compose up -d =="
docker compose up -d
echo "== nginx config-test + herladen =="
docker compose exec -T nginx nginx -t && docker compose restart nginx
echo "== klaar =="
