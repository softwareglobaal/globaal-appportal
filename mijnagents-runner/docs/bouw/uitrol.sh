#!/bin/bash
# Uitrol van de afdeling Bouw op de VM (30-10-2026), na de merge naar main. Draait in ~/appportal.
# 1. main binnenhalen (alleen --ff-only, geen autostash);
# 2. de afdeling bouw op het bord (de lege afdeling harmoniebouw blijft ongemoeid, overleg K1);
# 3. de generator voor beide agents: agentkaart en werkwijze op het bord. De generator wil geen bestaande runner met
#    eigen code; hij draait daarom in een tijdelijke kopie zonder die runner, zodat de echte werkboom nooit wijzigt
#    (Codex X10, controle 3; de VM blijft gelijk aan GitHub, S1);
# 4. de eerste ronde met controle, zonder vraag (kost niets, toetst de normen). Geen cron: ze werken op verzoek.
set -euo pipefail
cd ~/appportal
# Codex X14: alleen met een schone werkboom, zodat het opzij zetten en terughalen van de runners geen ander werk raakt
if [ -n "$(git status --porcelain -- mijnagents-runner)" ]; then
  echo "STOP: mijnagents-runner heeft wijzigingen die niet in git staan"; git status --short -- mijnagents-runner; exit 1
fi
if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
  echo "STOP: ~/appportal staat niet op main maar op $(git rev-parse --abbrev-ref HEAD)"; exit 1
fi
git pull --ff-only origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "STOP: ~/appportal is na de pull niet gelijk aan origin/main"; exit 1
fi
git log --oneline -1
cd mijnagents-runner
PY=~/agents/.venv/bin/python
$PY -c "import pypdf" || { echo "STOP: pypdf ontbreekt in ~/agents/.venv (nodig voor De Offertevergelijker)"; exit 1; }
KOPIE=$(mktemp -d /tmp/bouw-uitrol.XXXXXX)
trap 'rm -rf "$KOPIE"' EXIT
cp -a . "$KOPIE/mijnagents-runner"
rm "$KOPIE/mijnagents-runner/aannemerszoeker.py" "$KOPIE/mijnagents-runner/offertevergelijker.py"

$PY - <<'PYEOF'
import sys
sys.path.insert(0, "koppelingen")
import bord
print("afdeling:", bord.call("/api/afdeling", {"naam": "bouw", "label": "Bouw", "volgorde": 25,
      "omschrijving": "Aannemers zoeken en offertes vergelijken, per vraag voor een firma: H-Architects of Harmonie Bouw."}))
PYEOF

(cd "$KOPIE/mijnagents-runner" && $PY nieuwe-agent.py --naam aannemerszoeker --label "De Aannemerszoeker" --type bouw \
  --rol "zoekt op verzoek firma's die een werk kunnen uitvoeren in een gebied, en zet per firma een prijsaanvraag klaar vanuit de juiste firma" \
  --mandaat "zoeken, keuren en mails als concept op het bord; nooit versturen of een firma contacteren" \
  --cadans "op verzoek" \
  --mag "op het web zoeken en websites en KBO-pagina's lezen" --mag "de eigen mappen en boekhouding van die ene firma lezen" \
  --mag "een aannemersverslag met conceptmails voor Mehdi klaarzetten" \
  --grens "nooit een mail versturen of een firma contacteren" \
  --grens "nooit een kenmerk van de andere firma in een stuk van de ene" \
  --grens "nooit de naam of het adres van een bouwheer naar buiten" \
  --levert-aan regisseur --draait-op VM --werkwijze werkwijze/aannemerszoeker.md)

(cd "$KOPIE/mijnagents-runner" && $PY nieuwe-agent.py --naam offertevergelijker --label "De Offertevergelijker" --type bouw \
  --rol "legt op verzoek de offertes van een lot naast elkaar en zet de verschillen en risico's op het bord" \
  --mandaat "lezen en vergelijken; nooit gunnen, aanbevelen, versturen of in Dropbox schrijven" \
  --cadans "op verzoek" \
  --mag "de offertemappen van die ene firma lezen" --mag "een offertevergelijking voor Mehdi klaarzetten" \
  --grens "nooit een inschrijver kiezen of aanbevelen" --grens "nooit iets in Dropbox schrijven" \
  --grens "nooit offerte-inhoud naar de AI zonder ja van Mehdi" --grens "nooit de andere firma noemen" \
  --levert-aan regisseur --draait-op VM --werkwijze werkwijze/offertevergelijker.md)
git status --short -- .
$PY nieuwe-agent.py --eerste-ronde aannemerszoeker --cron "# geen cron, op verzoek via De Regisseur"
$PY nieuwe-agent.py --eerste-ronde offertevergelijker --cron "# geen cron, op verzoek via De Regisseur"
