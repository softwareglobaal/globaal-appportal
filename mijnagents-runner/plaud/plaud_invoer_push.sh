#!/bin/zsh
# Plaud op de Mac: ophalen, manifest maken en de invoer voor De Plaudwacht naar de VM zetten
# (verbeteropdracht v1.0, §2). Draait via launchd be.globaal.plaud.ophalen (elk uur).
#
#  1. plaud_haal_alles.py  ophalen uit de Plaud-API naar het archief (met slot en tijdslimiet);
#                          schrijft altijd "00 status.json", ook bij een aanmeldfout
#  2. manifest.py          "00 manifest.json" uit het archief, per Plaud-id, met de echte toestand
#  3. rsync                alleen manifest, status, lijst en transcript.json naar de VM; nooit audio,
#                          nooit getekende links, nooit --delete
#
# Ook bij een fout in stap 1 lopen 2 en 3: de VM moet de status (authfout, bronfout) kunnen zien.
set -u
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin
HIER="${0:A:h}"
DOEL="${PLAUD_DOEL:-$HOME/TKN-buro Dropbox/Data uit Mehdi/Plaud}"
VM="${PLAUD_VM:-globaal:appportal/mijnagents-data/plaud-invoer}"
LOG="$HOME/Library/Logs/plaud-ophalen.log"

[ -d "$DOEL" ] || { echo "$(date '+%F %T') archief ontbreekt: $DOEL" >> "$LOG"; exit 1; }
# PLAUD-13 (T-0120): alleen uit een checkout op main, ook na de installatie. Zet iemand die checkout op een andere tak,
# dan draaide de Mac elk uur die tak; nu stopt de ronde hier, en meldt De Plaudwacht binnen drie uur dat de invoer oud is.
TAK="$(git -C "$HIER" rev-parse --abbrev-ref HEAD 2>/dev/null || echo onbekend)"
[ "$TAK" = "main" ] || { echo "$(date '+%F %T') niet gedraaid: de checkout staat op tak $TAK, niet op main" >> "$LOG"; exit 8; }

/usr/bin/python3 "$HIER/plaud_haal_alles.py" >> "$LOG" 2>&1
OPHALEN=$?
/usr/bin/python3 "$HIER/manifest.py" "$DOEL" >> "$LOG" 2>&1 || { echo "$(date '+%F %T') manifest mislukt" >> "$LOG"; exit 6; }
rsync -a --prune-empty-dirs \
  --include='*/' --include='transcript.json' --include='00 manifest.json' --include='00 status.json' \
  --include='00 plaud_lijst.json' --exclude='*' \
  -e "ssh -o BatchMode=yes -o ConnectTimeout=20" "$DOEL/" "$VM/" 2>>"$LOG"
PUSH=$?
echo "$(date '+%F %T') ophalen=$OPHALEN push=$PUSH" >> "$LOG"
[ $PUSH -ne 0 ] && exit 7
exit $OPHALEN
