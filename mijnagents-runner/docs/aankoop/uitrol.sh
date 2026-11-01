#!/bin/bash
# Uitrol van De Prijsonderzoeker op de VM (30-10-2026), na de merge naar main. Draait in ~/appportal.
# 1. main binnenhalen (alleen --ff-only, geen autostash);
# 2. de afdeling aankoop op het bord;
# 3. de generator: agentkaart en werkwijze op het bord. De generator wil geen bestaande runner met eigen code, dus
#    de echte runner gaat even opzij en komt daarna terug uit git (de VM blijft gelijk aan GitHub, norm S1);
# 4. de eerste ronde met controle (zonder vraag: kost niets, toetst de normen). Geen cron: hij werkt op verzoek.
set -euo pipefail
cd ~/appportal
git pull --ff-only origin main
git log --oneline -1
cd mijnagents-runner
PY=~/agents/.venv/bin/python
trap 'git checkout -- prijsonderzoeker.py' EXIT

$PY - <<'PYEOF'
import sys
sys.path.insert(0, "koppelingen")
import bord
print("afdeling:", bord.call("/api/afdeling", {"naam": "aankoop", "label": "Aankoop", "volgorde": 60,
      "omschrijving": "Prijzen zoeken voor wat we willen kopen; later de aankoopwacht en de inventaris."}))
PYEOF

mv prijsonderzoeker.py /tmp/prijsonderzoeker.echt.py
$PY nieuwe-agent.py --naam prijsonderzoeker --label "De Prijsonderzoeker" --type aankoop \
  --rol "zoekt op verzoek waar iets het best te koop is: nieuw, tweedehands of op een veiling, in Europa of de wereld" \
  --mandaat "zoeken, vergelijken en een prijsverslag klaarzetten; nooit kopen, bieden of een verkoper contacteren" \
  --cadans "op verzoek" \
  --mag "op het web zoeken en aanbodpagina's lezen" --mag "een prijsverslag voor Mehdi klaarzetten" \
  --grens "nooit kopen, bestellen of bieden" --grens "nooit een verkoper contacteren of een account gebruiken" \
  --grens "alleen de productvraag naar de AI, nooit persoonsgegevens" \
  --levert-aan regisseur --draait-op VM --werkwijze werkwijze/prijsonderzoeker.md
git checkout -- prijsonderzoeker.py
trap - EXIT
git status --short
$PY nieuwe-agent.py --eerste-ronde prijsonderzoeker --cron "# geen cron, op verzoek via De Regisseur"
