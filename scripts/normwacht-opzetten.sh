#!/bin/sh
# De Normwacht opzetten op de VM. Idempotent: twee keer draaien doet geen kwaad.
#
#   sh ~/appportal/scripts/normwacht-opzetten.sh
#
# Registreert de agent op het bord (de generator laat een bestaande runner en een
# bestaande registratie met rust), draait een droge ronde zodat je ziet wat hij
# zou melden, en drukt de cron-regel af. De cron zet je zelf, dat blijft een
# bewuste handeling.
set -u

RUNNER="$HOME/appportal/mijnagents-runner"
PY="$HOME/agents/.venv/bin/python"
[ -x "$PY" ] || PY=python3

cd "$RUNNER" || { echo "runner-map niet gevonden: $RUNNER"; exit 1; }

echo "== 1. Normwacht registreren op het bord =="
"$PY" nieuwe-agent.py \
  --naam normwacht \
  --label "De Normwacht" \
  --type regie \
  --rol "toetst elke agent aan de Agentnorm en houdt het logboek bij" \
  --mandaat "meten en melden; herstellen doet degene die de nood krijgt" \
  --cadans "elke ochtend 06:10" \
  --mag "het bord lezen" \
  --mag "per gezakte norm een nood zetten" \
  --mag "het logboek schrijven" \
  --grens "nooit een andere agent of zijn werkwijze aanpassen" \
  --grens "nooit een norm versoepelen omdat een agent zakt" \
  --grens "nooit iets versturen, verwijderen of pushen" \
  --tool "het bord lezen" \
  --tool "git lezen" \
  --werkwijze werkwijze/normwacht.md \
  --draait-op VM \
  --cron "10 6 * * *" || echo "(registratie overgeslagen of al aanwezig)"

echo
echo "== 2. Droge ronde: wat zou hij vandaag melden =="
"$PY" normwacht.py --droog

echo
echo "== 3. De cron-regel, als je hem wilt laten draaien =="
echo "    (crontab -l 2>/dev/null; echo '10 6 * * * cd $RUNNER && $PY normwacht.py >> \$HOME/normwacht.log 2>&1') | crontab -"
echo
echo "Staat hij er al in? Controleer met: crontab -l | grep normwacht"
