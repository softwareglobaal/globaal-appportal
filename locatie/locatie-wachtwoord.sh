#!/bin/zsh
# Toont wat je nodig hebt om de iPhone in te stellen, in een venster op het
# scherm, zodat het niet in de terminal of in een chat belandt.
#
#   Kopieer wachtwoord   -> voor het Password-veld in OwnTracks
#   Kopieer header       -> voor "Get contents of URL" in de Opdrachten-app,
#                           die kent geen gebruikersnaam en wachtwoord maar
#                           werkt met een Authorization-header
#
# Het klembord van de Mac is via Universal Clipboard ook op de iPhone
# beschikbaar, dus plakken kan direct.
#
# Zelfde patroon als onemail-setup.sh, maar omgekeerd: dat vraagt een
# wachtwoord, dit toont er een.

bestand="$HOME/TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude/Locatielogboek/werkbestanden/mehdi-iphone.otrc"

if [ ! -f "$bestand" ]; then
  osascript -e 'display alert "Locatielogboek" message "Het bestand mehdi-iphone.otrc is niet gevonden." as critical'
  exit 1
fi

lees() {
  /usr/bin/python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['$1'])" "$bestand"
}
ww=$(lees password)
url=$(lees url)
gebruiker=$(lees username)
header=$(/usr/bin/python3 -c "
import base64, sys
print('Basic ' + base64.b64encode((sys.argv[1] + ':' + sys.argv[2]).encode()).decode())
" "$gebruiker" "$ww")

antwoord=$(osascript <<EOF 2>/dev/null
tell application "System Events"
    activate
    set resultaat to display dialog "OwnTracks, Settings:

Mode        HTTP
URL         $url
UserID      $gebruiker
TrackerID   MC

Wachtwoord (of gebruik de knop):" default answer "$ww" with title "Locatielogboek" buttons {"Sluit", "Kopieer header", "Kopieer wachtwoord"} default button "Kopieer wachtwoord" with icon note
    return button returned of resultaat
end tell
EOF
)

case "$antwoord" in
  "Kopieer wachtwoord")
    printf '%s' "$ww" | pbcopy
    osascript -e 'display notification "Wachtwoord op het klembord. Plak het in het Password-veld van OwnTracks." with title "Locatielogboek"' 2>/dev/null
    ;;
  "Kopieer header")
    printf '%s' "$header" | pbcopy
    osascript -e 'display notification "Authorization-header op het klembord. Plak hem in de Opdrachten-app bij Headers." with title "Locatielogboek"' 2>/dev/null
    ;;
esac

unset ww header
