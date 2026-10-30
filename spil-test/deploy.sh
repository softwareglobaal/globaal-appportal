#!/bin/sh
# Auto-deploy SPIL (test) (cron, elke 2 min):
#   */2 * * * * /home/ubuntu/appportal/spil-test/deploy.sh >> /home/ubuntu/deploy-spil-test.log 2>&1
# Nieuwe commits op main -> pull + rebuild. Met argument "nu" (ssh ashvand@... deploy)
# ook zonder nieuwe commit, zodat een mislukte build opnieuw kan.
set -eu

# namen-ctl en spil-ctl starten dit via sudo + runuser; dan klopt HOME niet en
# vindt git de inloggegevens niet.
export HOME=/home/ubuntu

CODE=/home/ubuntu/spil-test/code
COMPOSE=/home/ubuntu/appportal/spil-test/compose.yml

# Cron en een handmatige deploy mogen niet tegelijk bouwen.
exec 9>/tmp/deploy-spil-test.lock
flock -n 9 || { echo "$(date -Is) er loopt al een deploy"; exit 0; }

cd "$CODE"
git fetch --quiet origin main
if [ "${1:-}" != "nu" ] && [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
  exit 0
fi

git checkout -qf main
git reset --hard -q origin/main
versie=$(git rev-parse --short HEAD)

if [ ! -f Dockerfile ]; then
  echo "$(date -Is) $versie NIET uitgerold: geen Dockerfile in de hoofdmap"
  exit 0
fi

if docker compose -f "$COMPOSE" up -d --build; then
  echo "$(date -Is) deployed $versie"
else
  echo "$(date -Is) $versie MISLUKT: de vorige versie blijft draaien als die er was"
  exit 1
fi
