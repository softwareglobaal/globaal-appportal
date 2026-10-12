#!/bin/zsh
# Zet de Mac-planning van Plaud uit de repo (verbeteropdracht v1.0). Kopieert de plist, laadt hem
# opnieuw en toont of launchd hem kent. Wist niets anders.
set -eu
BRON="${0:A:h}/be.globaal.plaud.ophalen.plist"
DOEL="$HOME/Library/LaunchAgents/be.globaal.plaud.ophalen.plist"
plutil -lint "$BRON"
cp "$BRON" "$DOEL"
launchctl bootout "gui/$(id -u)/be.globaal.plaud.ophalen" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DOEL"
launchctl print "gui/$(id -u)/be.globaal.plaud.ophalen" | grep -E "state|last exit|runs" || true
