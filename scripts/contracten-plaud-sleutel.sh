#!/bin/bash
# Zet de Plaud-transcriptiesleutels (dev.plaud.ai) voor het contractsysteem.
# Gebruik:  bash ~/appportal/scripts/contracten-plaud-sleutel.sh <CLIENT_ID> <API_KEY>
set -euo pipefail
CLIENT_ID="${1:?Gebruik: $0 <client_id> <api_key>}"
API_KEY="${2:?Gebruik: $0 <client_id> <api_key>}"
ENVBESTAND="$HOME/appportal/.env"
for PAAR in "PLAUD_CLIENT_ID=$CLIENT_ID" "PLAUD_API_KEY=$API_KEY"; do
  NAAM="${PAAR%%=*}"
  if grep -q "^$NAAM=" "$ENVBESTAND"; then
    sed -i "s|^$NAAM=.*|$PAAR|" "$ENVBESTAND"
  else
    echo "$PAAR" >> "$ENVBESTAND"
  fi
done
cd "$HOME/appportal"
docker compose up -d app-contracten
echo "Klaar. Op de Mac: zet dezelfde sleutels in ~/.config/contract-systeem/plaud.json"
