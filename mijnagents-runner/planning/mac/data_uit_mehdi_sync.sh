#!/bin/zsh
# Data uit Mehdi: het archief van de agents op de Globaal-VM naar Mehdi's Dropbox halen.
# Draait via launchd (be.globaal.mijnagents.data-uit-mehdi) elke 30 minuten.
# Bron in de repo: mijnagents-runner/planning/mac/data_uit_mehdi_sync.sh; geïnstalleerd als ~/bin/data_uit_mehdi_sync.sh.
# Alleen ophalen en toevoegen; nooit iets wissen in Dropbox (geen --delete).
# Mehdi besliste op 12-09-2026: alles, ook privé (Locatie); delen met Shaniel regelt hij per submap.
set -u
setopt PIPE_FAIL   # een falende stap in een pipeline (find, shasum) laat de hele pipeline falen (Codex G6)
DOEL="$HOME/TKN-buro Dropbox/Data uit Mehdi"
BRON="globaal:appportal/mijnagents-data"
LOG="$HOME/Library/Logs/mijnagents-data-uit-mehdi.log"
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin

[ -d "$DOEL" ] || { echo "$(date '+%F %T') doelmap ontbreekt: $DOEL" >> "$LOG"; exit 1; }
# Een mislukte stap maakt de hele ronde mislukt (exit 1, 'fout' in het logboek), nooit 'klaar' (Codex F10, 26-10-2026).
FOUT=0
mislukt() { echo "$(date '+%F %T') fout: $1" >> "$LOG"; FOUT=1; }

haal() {  # haal <submap op VM> <submap in Dropbox>
  mkdir -p "$DOEL/$2"
  rsync -az --exclude='.dropbox_gespiegeld*' --exclude='.DS_Store' -e "ssh -o BatchMode=yes -o ConnectTimeout=20" \
    "$BRON/$1/" "$DOEL/$2/" 2>>"$LOG" || mislukt "rsync $1"
}

haal fathom Fathom
haal fathom-data "Fathom data"   # volledig Fathom-archief, plat (18-09-2026)
# Plaud niet meer van de VM halen (verbeteropdracht Plaud v1.0, 12-10-2026): het archief staat op deze Mac
# (plaud_haal_alles.py) en gaat de andere kant op naar de VM (plaud_invoer_push.sh, launchd be.globaal.plaud.ophalen).
# De oude VM-map gaf de jaarmap Plaud/2026/ naast het archief: twee archieven.
haal locatielogboek Locatie
# De dagvaststelling van De Dagbundelaar (26-10-2026): een bestand per dag, met vorige versies in versies/. Daarna een
# ontvangstbewijs terug naar de VM: de sha256 van elke dagkopie hier in Dropbox; De Dagbundelaar meldt een dag zonder
# gelijk bewijs als niet in Dropbox (ontwerp dagvaststelling v1.2, Codex D9 en E6).
haal dagboek Dagboek
if [ -d "$DOEL/Dagboek" ]; then
  ( cd "$DOEL/Dagboek" && find . -name '*.md' -not -path '*/versies/*' -exec shasum -a 256 {} + ) \
    | ssh -o BatchMode=yes -o ConnectTimeout=20 globaal \
      'cat > appportal/mijnagents-data/dagboek-ontvangst.txt.tmp && mv appportal/mijnagents-data/dagboek-ontvangst.txt.tmp appportal/mijnagents-data/dagboek-ontvangst.txt' \
      2>>"$LOG" || mislukt "ontvangstbewijs dagboek"
fi
haal bord Bord 2>/dev/null
# één map per agent (werkwijze, werkverslag, klaargezet, noden, voorstellen), uit de export van het bord
mkdir -p "$DOEL"
rsync -az -e "ssh -o BatchMode=yes -o ConnectTimeout=20" "$BRON/export/" "$DOEL/" 2>>"$LOG" || mislukt "rsync export"
# foto's van de iCloud-wacht staan al op deze Mac (app-map van Dropbox); lokaal bijkopiëren, nooit wissen
FOTOS="$HOME/TKN-buro Dropbox/H-Architects bvba/Apps/Mehdi Agents/Fotos"
[ -d "$FOTOS" ] && { mkdir -p "$DOEL/Fotos"; rsync -a --ignore-existing "$FOTOS/" "$DOEL/Fotos/" 2>>"$LOG" || mislukt "rsync Fotos"; }   # exports van het bord (agenda, dagen, gesprekken), zodra de server die maakt

echo "$(date '+%F %T') $([ $FOUT = 0 ] && echo klaar || echo fout): Fathom $(find "$DOEL/Fathom" -type f | wc -l | tr -d ' '), Fathom data $(find "$DOEL/Fathom data" -type f 2>/dev/null | wc -l | tr -d ' '), Plaud $(find "$DOEL/Plaud" -type f | wc -l | tr -d ' '), Locatie $(find "$DOEL/Locatie" -type f | wc -l | tr -d ' '), Fotos $(find "$DOEL/Fotos" -type f 2>/dev/null | wc -l | tr -d ' ')" >> "$LOG"
exit $FOUT
