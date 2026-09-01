#!/bin/bash
# Zet de PandaDoc-PRODUCTIEsleutel voor het contractsysteem en herstart de app.
# Gebruik:  bash ~/appportal/scripts/contracten-pandadoc-sleutel.sh <API-SLEUTEL>
# De sleutel haal je uit het echte PandaDoc-account: Settings > API > Production key.
set -euo pipefail
SLEUTEL="${1:?Gebruik: $0 <PandaDoc-productiesleutel>}"
ENVBESTAND="$HOME/appportal/.env"
if grep -q '^CONTRACTEN_PANDADOC_KEY=' "$ENVBESTAND"; then
  sed -i "s|^CONTRACTEN_PANDADOC_KEY=.*|CONTRACTEN_PANDADOC_KEY=$SLEUTEL|" "$ENVBESTAND"
else
  echo "CONTRACTEN_PANDADOC_KEY=$SLEUTEL" >> "$ENVBESTAND"
fi
cd "$HOME/appportal"
docker compose up -d app-contracten
sleep 8
docker exec appportal-app-contracten-1 python3 -c "
import sys; sys.path.insert(0,'/app/webapp')
import pandadoc
m = pandadoc._request('GET', '/members/current')
d = pandadoc._request('GET', '/documents?count=1')
naam = (d.get('results') or [{}])[0].get('name', '')
print('PandaDoc-account:', m.get('email'))
print('Testmodus ([DEV]):', 'JA - dit is nog een sandbox-sleutel!' if naam.startswith('[DEV]') else 'nee - productie, klaar voor klanten')"
echo "Klaar. Vergeet de Mac niet: zet dezelfde sleutel in ~/.config/contract-systeem/pandadoc_token"
