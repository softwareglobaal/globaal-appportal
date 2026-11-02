#!/bin/zsh
# De Browserwacht op Mehdi's laptop (T-0077, overleg 2026-11-02-websitewacht): het ene programma met Full Disk Access
# is BrowserWacht.app (starter/browserwacht.c), met de SHA-256 van browser_wacht.py erin gebakken. Alles staat in de
# eigen map van de gebruiker, zonder sudo. De toestemming hangt aan de cdhash van de starter: elke nieuwe bouw vraagt
# Mehdi opnieuw om Full Disk Access (System Settings > Privacy & Security > Full Disk Access: oude regel met min weg,
# nieuwe met plus erbij). Daarom bouwt dit script alleen opnieuw als de bron veranderde.
#
#   uitrol_browser_wacht.sh              script en starter uit origin/main bijwerken (bouwen alleen bij een nieuwe
#                                         bron), LaunchAgent klaarzetten maar niet laden; de wacht staat daarna uit
#   uitrol_browser_wacht.sh proef        de toegangsproef onder launchd met precies dit programma (--proef, alleen
#                                         leesbaar of niet, nooit sitenamen): leest het Chrome-profiel? Dan een
#                                         proefbewijs voor deze cdhash; anders de stap voor Mehdi, met het pad van de
#                                         app op zijn klembord
#   uitrol_browser_wacht.sh aan          de wacht laden (elk uur), alleen met een proefbewijs van deze cdhash
#   uitrol_browser_wacht.sh uit          de wacht uitzetten; de starter en zijn toestemming blijven
#   uitrol_browser_wacht.sh controleer   versie, cdhash, proefbewijs en de stand in launchd
#
# REF=<commit> kiest een andere commit dan origin/main (alleen voor een proef).
set -euo pipefail

modus=${1:-installeer}
REPO=${REPO:-$HOME/dev/globaal-appportal}
REF=${REF:-origin/main}
BASIS=${BASIS:-$HOME/Library/Application Support/mijnagents/browser-wacht}
AGENTS=${AGENTS:-$HOME/Library/LaunchAgents}
LOGS=${LOGS:-$HOME/Library/Logs/mijnagents}
LABEL=be.globaal.mijnagents.browser
APP="$BASIS/BrowserWacht.app"
STARTER="$APP/Contents/MacOS/browserwacht"
SCRIPT="$BASIS/browser_wacht.py"
C=mijnagents-runner/mac/starter/browserwacht.c
INFO=mijnagents-runner/mac/starter/Info-browserwacht.plist
WACHT=mijnagents-runner/mac/browser_wacht.py

fout() { print -r -- "uitrol_browser_wacht: $*" >&2; exit 2; }
cdhash() { /usr/bin/codesign -dvvv "$1" 2>&1 | /usr/bin/sed -n 's/^CDHash=//p' | head -1; }
geladen() { /bin/launchctl print "gui/$(id -u)/$1" > /dev/null 2>&1; }
# Uitzetten en nakijken dat launchd de taak echt kwijt is (Codex 02-11, punt 2).
bootout_zeker() {
    /bin/launchctl bootout "gui/$(id -u)/$1" 2>/dev/null || true
    for i in {1..10}; do geladen "$1" || return 0; sleep 1; done
    fout "$1 blijft geladen in launchd"
}

bron_ophalen() {
    git -C "$REPO" fetch -q origin
    sha=$(git -C "$REPO" rev-parse "$REF")
    werk=$(mktemp -d)
    for f in "$C" "$INFO" "$WACHT"; do
        git -C "$REPO" show "$sha:$f" > "$werk/${f:t}"
    done
    script_hash=$(/usr/bin/shasum -a 256 "$werk/browser_wacht.py" | cut -c1-64)
    bron_hash=$(cat "$werk/browserwacht.c" "$werk/Info-browserwacht.plist" "$werk/browser_wacht.py" | /usr/bin/shasum -a 256 | cut -c1-64)
}

installeer() {
    bron_ophalen
    mkdir -p "$BASIS" "$LOGS"; chmod 700 "$BASIS"
    # Altijd eerst uit: na installeer staat de wacht uit tot een proef en aan (ook bij een ongewijzigde bron).
    bootout_zeker "$LABEL"
    if [[ -f "$BASIS/BRON_SHA256" && "$(cat "$BASIS/BRON_SHA256")" == "$bron_hash" && -x "$STARTER" ]]; then
        print -r -- "bron ongewijzigd ($sha[1,8]); starter blijft (cdhash $(cdhash "$APP")); wacht staat uit tot aan"
    else
        nieuw="$werk/BrowserWacht.app"
        mkdir -p "$nieuw/Contents/MacOS"
        /usr/bin/plutil -lint "$werk/Info-browserwacht.plist" > /dev/null
        /usr/bin/install -m 644 "$werk/Info-browserwacht.plist" "$nieuw/Contents/Info.plist"
        /usr/bin/cc -O2 -Wall -Wextra -Wno-deprecated-declarations -DSCRIPT_SHA256="\"$script_hash\"" \
            "$werk/browserwacht.c" -o "$nieuw/Contents/MacOS/browserwacht"
        /usr/bin/codesign -s - --force --options runtime --identifier be.globaal.browserwacht "$nieuw"
        /usr/bin/codesign --verify --strict "$nieuw"
        [[ -d "$APP" ]] && { rm -rf "$BASIS/BrowserWacht.oud.app"; mv "$APP" "$BASIS/BrowserWacht.oud.app"; }
        /usr/bin/install -m 600 "$werk/browser_wacht.py" "$SCRIPT"
        mv "$nieuw" "$APP"
        print -r -- "$bron_hash" > "$BASIS/BRON_SHA256"
        print -r -- "$sha" > "$BASIS/VERSIE"
        rm -f "$BASIS/PROEF"
        print -r -- "nieuwe starter gebouwd uit $sha[1,8], cdhash $(cdhash "$APP"); Mehdi moet opnieuw Full Disk Access geven, daarna: proef"
    fi
    cat > "$AGENTS/$LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$STARTER</string></array>
  <key>StartCalendarInterval</key><array><dict><key>Minute</key><integer>40</integer></dict></array>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGS/browser_wacht.log</string>
  <key>StandardErrorPath</key><string>$LOGS/browser_wacht.log</string>
</dict>
</plist>
PLIST
    rm -rf "$werk"
}

proef() {
    [[ -x "$STARTER" ]] || fout "geen starter; eerst installeer"
    /usr/bin/codesign --verify --strict "$APP" || fout "handtekening van $APP klopt niet"
    cd_voor=$(cdhash "$APP")
    [[ -n "$cd_voor" ]] || fout "geen cdhash"
    # Codex 02-11, punt 3: de uitvoer in een verse privemap, en het bewijs alleen als de app voor en na de proef
    # dezelfde cdhash heeft.
    proefmap=$(mktemp -d "$BASIS/proef.XXXXXX"); chmod 700 "$proefmap"
    uit="$proefmap/uit"
    plist="$proefmap/proef.plist"
    cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL.proef</string>
  <key>ProgramArguments</key><array><string>$STARTER</string><string>--proef</string></array>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$uit</string><key>StandardErrorPath</key><string>$uit</string>
</dict></plist>
PLIST
    bootout_zeker "$LABEL.proef"
    /bin/launchctl bootstrap "gui/$(id -u)" "$plist"
    /bin/launchctl kickstart "gui/$(id -u)/$LABEL.proef"
    for i in {1..30}; do
        [[ -s "$uit" ]] && ! /bin/launchctl print "gui/$(id -u)/$LABEL.proef" 2>/dev/null | grep -q "state = running" && break
        sleep 1
    done
    bootout_zeker "$LABEL.proef"
    uitkomst=$(cat "$uit" 2>/dev/null || true)
    rm -rf "$proefmap"
    cd_na=$(cdhash "$APP")
    if [[ "$uitkomst" == *'"proef": "ok"'* && "$cd_voor" == "$cd_na" ]]; then
        print -r -- "$cd_na" > "$BASIS/PROEF"
        print -r -- "proef ok onder launchd: het Chrome-profiel is leesbaar (cdhash $cd_na); nu: aan"
    else
        print -r -- "proef mislukt: $(print -r -- "$uitkomst" | grep -m1 'BrowserWacht:\|"reden"' || print -r -- "$uitkomst" | head -c 200)"
        print -r -- "$APP" | /usr/bin/pbcopy
        print -r -- "Stap voor Mehdi: System Settings > Privacy & Security > Full Disk Access: BrowserWacht met min (-) weg als hij er staat, dan plus (+), Command Shift G, Command V (het pad staat op het klembord), Open. Daarna opnieuw: proef"
        exit 1
    fi
}

aan() {
    /usr/bin/codesign --verify --strict "$APP" || fout "handtekening van $APP klopt niet"
    [[ -f "$BASIS/PROEF" && "$(cat "$BASIS/PROEF")" == "$(cdhash "$APP")" ]] || fout "geen proefbewijs voor deze starter; eerst proef"
    bootout_zeker "$LABEL"
    /bin/launchctl bootstrap "gui/$(id -u)" "$AGENTS/$LABEL.plist"
    /bin/launchctl kickstart "gui/$(id -u)/$LABEL"
    print -r -- "Browserwacht aan (elk uur om :40); log $LOGS/browser_wacht.log"
}

uit() {
    bootout_zeker "$LABEL"
    print -r -- "Browserwacht uit (nagekeken in launchd); starter en toestemming blijven"
}

controleer() {
    print -r -- "versie: $(cat "$BASIS/VERSIE" 2>/dev/null || print geen)"
    print -r -- "cdhash: $([[ -d "$APP" ]] && cdhash "$APP" || print geen)"
    print -r -- "proefbewijs: $(cat "$BASIS/PROEF" 2>/dev/null || print geen)"
    print -r -- "launchd: $(/bin/launchctl list 2>/dev/null | grep -q "$LABEL\$" && print geladen || print niet geladen)"
    print -r -- "script: $(/usr/bin/shasum -a 256 "$SCRIPT" 2>/dev/null | cut -c1-16 || print geen)"
}

case "$modus" in
    installeer) installeer ;;
    proef) proef ;;
    aan) aan ;;
    uit) uit ;;
    controleer) controleer ;;
    *) fout "onbekende opdracht $modus (installeer, proef, aan, uit, controleer)" ;;
esac
