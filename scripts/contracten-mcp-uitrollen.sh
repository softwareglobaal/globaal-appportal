#!/bin/bash
# Zet het MCP-endpoint van het contractsysteem aan: sleutels in .env, code
# bijwerken, container herbouwen, nginx herladen en het resultaat controleren.
# Gebruik:  bash ~/appportal/scripts/contracten-mcp-uitrollen.sh <MCP_TOKEN> <MCP_SECRET>
# De twee waarden staan op de Mac in ~/Documents/contracten-mcp-secrets.txt.
set -euo pipefail
TOKEN="${1:?Gebruik: $0 <CONTRACTEN_MCP_TOKEN> <CONTRACTEN_MCP_SECRET>}"
SECRET="${2:?Gebruik: $0 <CONTRACTEN_MCP_TOKEN> <CONTRACTEN_MCP_SECRET>}"
ENVBESTAND="$HOME/appportal/.env"

zet() {
  if grep -q "^$1=" "$ENVBESTAND"; then
    sed -i "s|^$1=.*|$1=$2|" "$ENVBESTAND"
  else
    echo "$1=$2" >> "$ENVBESTAND"
  fi
}
zet CONTRACTEN_MCP_TOKEN "$TOKEN"
zet CONTRACTEN_MCP_SECRET "$SECRET"
echo "== sleutels staan in .env =="

cd "$HOME/appportal"
echo "== appportal bijwerken =="
git pull --ff-only
echo "== contract-systeem bijwerken =="
( cd contracten && (git checkout -q main || true) && git pull --ff-only && git log --oneline -1 )

echo "== app-contracten herbouwen =="
docker compose build app-contracten
docker compose up -d app-contracten
echo "== nginx config-test + herladen =="
docker compose exec -T nginx nginx -t && docker compose restart nginx

sleep 8
echo "== controle =="
if uit=$(curl -fsS "https://contracten.globaal.be/.well-known/oauth-protected-resource"); then
  echo "$uit"
  echo
  echo "IN ORDE. Koppel nu in claude.ai: https://contracten.globaal.be/mcp"
else
  echo "FOUT: geen JSON van /.well-known/oauth-protected-resource."
  echo "  - HTML-loginpagina?  nginx-template niet geladen: docker compose logs nginx | tail"
  echo "  - 404?               sleutels niet in de container: docker compose logs app-contracten | tail"
  exit 1
fi
