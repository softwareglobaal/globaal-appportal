#!/bin/zsh
# Zet de Mac-planning van Plaud uit de repo (verbeteropdracht v1.0). Vult de plist in met deze checkout en $HOME, laadt
# hem opnieuw en toont of launchd hem kent. Wist niets anders.
# PLAUD-13 (T-0120): alleen vanuit een checkout op main. Tot 01-11-2026 draaide de taak uit een checkout op een featuretak,
# en dan draait de Mac elk uur wat er toevallig op die tak staat. Geen pad van één toestel in de plist: __REPO__ en __HOME__
# vult dit script in.
set -eu
REPO="$(git -C "${0:A:h}" rev-parse --show-toplevel)"
TAK="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
if [ "$TAK" != "main" ]; then
  echo "Niet gezet: $REPO staat op tak '$TAK', niet op main. Draai dit script vanuit een checkout op main." >&2
  exit 2
fi
BRON="${0:A:h}/be.globaal.plaud.ophalen.plist"
DOEL="$HOME/Library/LaunchAgents/be.globaal.plaud.ophalen.plist"
mkdir -p "${DOEL:h}"
sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" "$BRON" > "$DOEL.nieuw"
plutil -lint "$DOEL.nieuw"
mv "$DOEL.nieuw" "$DOEL"
launchctl bootout "gui/$(id -u)/be.globaal.plaud.ophalen" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DOEL"
launchctl print "gui/$(id -u)/be.globaal.plaud.ophalen" | grep -E "state|last exit|runs" || true
