#!/bin/sh
# De Contactwacht opzetten op de VM. Idempotent: twee keer draaien doet geen kwaad.
#
#   sh ~/appportal/scripts/contactwacht-opzetten.sh
#
# Maakt de afdeling Algemeen aan (bestaat ze al, dan werkt dit haar enkel bij), registreert
# De Contactwacht op het bord met zijn werkwijze, zet de werkwijze gelijk aan de repo, draait
# een eerste ronde, toetst hem aan de norm en zet de cron als die er nog niet staat.
# Versie 0.1 van de agent leest alleen; hij schrijft niets in Google Contacts.
set -u

RUNNER="$HOME/appportal/mijnagents-runner"
PY="$HOME/agents/.venv/bin/python"
[ -x "$PY" ] || PY=python3
cd "$RUNNER" || { echo "runner-map niet gevonden: $RUNNER"; exit 1; }

echo "== 1. Afdeling Algemeen =="
"$PY" - <<'EOF'
import sys
sys.path.insert(0, "koppelingen")
import bord
print(bord.call("/api/afdeling", {
    "naam": "algemeen", "label": "Algemeen", "volgorde": 12,
    "omschrijving": "Wat voor de hele groep geldt, boven de firma's (firmacode ALGE): "
                    "de contactendatabase en andere gedeelde gegevens.",
}))
EOF

echo
echo "== 2. De Contactwacht registreren =="
"$PY" nieuwe-agent.py \
  --naam contactwacht \
  --label "De Contactwacht" \
  --type algemeen \
  --rol "houdt de contactendatabase in lijn met de afspraken: wie iemand is, bij welke firma, welk dossier, welke dienst" \
  --mandaat "meten en voorstellen; schrijven in Google Contacts pas na goedkeuring, nooit in Xelion" \
  --cadans "elke werkdag 07:40" \
  --mag "de contactendatabase lezen" \
  --mag "voorstellen zetten" \
  --grens "nooit een contact verwijderen of archiveren" \
  --grens "nooit rechtstreeks in Xelion schrijven" \
  --grens "nooit iemand klant noemen zonder getekend document" \
  --tool "contactsync-index lezen" \
  --werkwijze werkwijze/contactwacht.md \
  --draait-op VM \
  --cron "40 7 * * 1-5" || echo "(registratie overgeslagen of al aanwezig)"

echo
echo "== 3. Werkwijze op het bord gelijk aan de repo =="
"$PY" werkwijze_naar_bord.py contactwacht --zet || true

echo
echo "== 4. Eerste ronde =="
"$PY" contactwacht.py

echo
echo "== 5. Toets aan de norm =="
"$PY" controle_agenten.py --agent contactwacht --uitleg || true

echo
echo "== 6. Cron =="
if crontab -l 2>/dev/null | grep -q "contactwacht.py"; then
  echo "staat er al"
else
  (crontab -l 2>/dev/null; echo "40 7 * * 1-5 cd $RUNNER && $PY contactwacht.py >> $HOME/contactwacht.log 2>&1") | crontab -
  echo "gezet: elke werkdag 07:40"
fi
