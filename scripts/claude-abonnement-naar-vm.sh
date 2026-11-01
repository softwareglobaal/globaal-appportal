#!/usr/bin/env bash
# Zet Mehdi's Claude-abonnement op de VM voor De Prijsonderzoeker, zodat die geen API-kost meer maakt
# (overleg 14 van 01-11-2026, mijnagents-runner/docs/aankoop/rapport-14-abonnement.md: A5, X5, K5, X8, K8).
#
# Draait op de laptop:  bash scripts/claude-abonnement-naar-vm.sh
#   1. `claude setup-token`: de browser opent; kies het werkaccount (mch@h-architects.be) en klik Authorize.
#   2. Het token staat dan in deze terminal: driemaal klikken erop, Cmd+C, daarna Cmd+V bij de vraag en Enter.
#
# Het token wordt niet getoond bij het plakken, komt niet in een bestand op de laptop, niet in de shellgeschiedenis en
# niet op een opdrachtregel (ssh krijgt het via stdin). Op de VM staat het in ~/.config/prijsonderzoeker/claude-token
# (map 700, bestand 600), los van ~/appportal/.env. Daarna een korte proef op de VM zonder API-sleutel.
set -euo pipefail
VM="${VM:-globaal}"
command -v claude >/dev/null || { echo "claude staat niet op deze Mac."; exit 1; }

echo "Stap 1: de browser opent. Kies het account mch@h-architects.be en klik op Authorize."
claude setup-token
echo
read -rsp "Stap 2: driemaal klikken op het token hierboven, Cmd+C, dan hier Cmd+V en Enter: " invoer
echo
token=$(printf '%s' "$invoer" | tr -d '[:space:]' | grep -oE 'sk-ant-oat[A-Za-z0-9_-]+' | head -1 || true)
unset invoer
if [ -z "$token" ]; then
  echo "Geen token gevonden (het begint met sk-ant-oat). Niets gewijzigd."
  exit 1
fi
printf '%s\n' "$token" | ssh "$VM" 'umask 077; d="$HOME/.config/prijsonderzoeker"; mkdir -p "$d" && chmod 700 "$d" &&
  cat > "$d/claude-token.nieuw" && chmod 600 "$d/claude-token.nieuw" && mv "$d/claude-token.nieuw" "$d/claude-token"'
unset token
if command -v pbcopy >/dev/null; then printf '' | pbcopy; fi     # het token niet op het klembord laten staan

echo "Het token staat op de VM. Proef via het abonnement, zonder API-sleutel:"
ssh "$VM" '~/agents/.venv/bin/python ~/appportal/mijnagents-runner/prijsonderzoeker.py --proef-abonnement'
