#!/bin/bash
# Zet de Google Routes-sleutel voor de Agendawacht: reistijden op live verkeer
# in plaats van de vaste filefactor per vertrekuur.
# Gebruik:  bash ~/appportal/scripts/agendawacht-routes-sleutel.sh <API_KEY>
#
# De sleutel komt alleen in ~/appportal/.env terecht, nooit in git, chat of een
# document. Het script schrijft pas weg als Google de sleutel aanvaardt: de
# Agendawacht slikt een mislukte aanroep stil en valt terug op de filefactor,
# dus een foute sleutel zou anders pas weken later opvallen.
set -euo pipefail
SLEUTEL="${1:?Gebruik: $0 <api_key>}"
ENVBESTAND="$HOME/appportal/.env"

# 1. Proefrit Leuven -> Mechelen, met dezelfde velden als agenda_wacht.py.
echo "Sleutel proberen bij Google Routes..."
ANTWOORD=$(curl -s -X POST 'https://routes.googleapis.com/directions/v2:computeRoutes' \
  -H 'Content-Type: application/json' \
  -H "X-Goog-Api-Key: $SLEUTEL" \
  -H 'X-Goog-FieldMask: routes.duration' \
  -d '{"origin":{"location":{"latLng":{"latitude":50.8798,"longitude":4.7005}}},
       "destination":{"location":{"latLng":{"latitude":51.0603,"longitude":4.3604}}},
       "travelMode":"DRIVE","routingPreference":"TRAFFIC_AWARE_OPTIMAL"}')
if ! printf '%s' "$ANTWOORD" | grep -q '"duration"'; then
  echo "De sleutel werkt nog niet. Antwoord van Google (sleutel gemaskeerd):" >&2
  printf '%s\n' "$ANTWOORD" | sed "s|$SLEUTEL|***|g" | head -20 >&2
  echo "" >&2
  echo "Na te kijken in console.cloud.google.com, project mehdi-agents:" >&2
  echo "  - Billing gekoppeld (zonder Billing werkt ook het gratis deel niet)" >&2
  echo "  - Routes API staat op Enable" >&2
  echo "  - Sleutelbeperking: Application restrictions None, API restrictions alleen Routes API" >&2
  echo "Er is niets weggeschreven." >&2
  exit 1
fi
echo "Sleutel werkt, Google gaf een rijtijd terug."

# 2. Wegschrijven, idempotent en zonder de sleutel door sed te halen.
umask 077
TIJDELIJK=$(mktemp "$HOME/.env-routes.XXXXXX")
trap 'rm -f "$TIJDELIJK"' EXIT
grep -v "^GOOGLE_ROUTES_KEY=" "$ENVBESTAND" > "$TIJDELIJK" || true
printf 'GOOGLE_ROUTES_KEY=%s\n' "$SLEUTEL" >> "$TIJDELIJK"
install -m 600 "$TIJDELIJK" "$ENVBESTAND"
echo "Sleutel staat in $ENVBESTAND."

# 3. Controleren langs dezelfde weg die de Agendawacht zelf neemt.
cd "$HOME/appportal/mijnagents-runner"
"$HOME/agents/.venv/bin/python" - <<'PY'
import datetime
import sys

sys.path[:0] = ["koppelingen", "."]
import agenda_wacht as aw

vertrek = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=8).astimezone()
minuten, factor = aw.rijtijd_min([50.8798, 4.7005], [51.0603, 4.3604], vertrek)
print(f"Proef Leuven -> Mechelen, morgen 08:00: {minuten} min (factor {factor})")
if factor != "live":
    print("LET OP: nog steeds de filefactor. De sleutel wordt niet gelezen.", file=sys.stderr)
    sys.exit(1)
PY

echo ""
echo "Klaar. Vanaf de volgende ronde (werkdagen 06:30, daarna elke twee uur) staat"
echo "'live verkeer Google' in de nieuwe reistijdblokken. Niets te herstarten:"
echo "agenda_wacht.py draait per ronde als vers proces uit cron."
