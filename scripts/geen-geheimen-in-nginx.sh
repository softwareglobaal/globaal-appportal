#!/usr/bin/env sh
# Grendel: geen letterlijke geheimen in de nginx-configuratie (22-10-2026).
#
# De repo is publiek. Een geheim hoort in de .env op de VM en komt via
# ${NAAM} in een *.conf.template terecht (envsubst bij de start van nginx).
# Dit script faalt op elke hex-reeks van 32 tekens of meer onder nginx/, de
# vorm van `openssl rand -hex`. De gevonden waarde wordt nooit getoond, alleen
# bestand en regel: een CI-log van een publieke repo is ook publiek.
#
#   sh scripts/geen-geheimen-in-nginx.sh [map]     (standaard: nginx)
set -eu

map="${1:-nginx}"
[ -d "$map" ] || { echo "FOUT: map $map bestaat niet" >&2; exit 2; }

treffers="$(grep -rnIE '[0-9A-Fa-f]{32,}' "$map" | sed -E 's/[0-9A-Fa-f]{32,}/<GEMASKEERD>/g' || true)"
if [ -n "$treffers" ]; then
    echo "FOUT: letterlijke hex-reeks (32+ tekens) in de nginx-configuratie:" >&2
    echo "$treffers" >&2
    echo "Zet de waarde in de .env op de VM en verwijs ernaar met \${NAAM}," >&2
    echo "zoals 41-schuldentracker.conf.template met \${SSO_SHARED_SECRET}." >&2
    echo "Een waarde die ooit gepusht is, geldt als uitgelekt: roteren." >&2
    exit 1
fi
echo "OK: geen letterlijke hex-geheimen onder $map/"
