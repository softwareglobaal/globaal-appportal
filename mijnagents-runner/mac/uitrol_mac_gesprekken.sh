#!/bin/zsh
# De WhatsApp-wacht en De Belwacht op Mehdi's Mac (ontwerp dagvaststelling v2.0, fase 2).
#
#   uitrol_mac_gesprekken.sh              de code naar origin/main in een eigen worktree, MacGesprekkenKopie bouwen als
#                                         zijn bron veranderde, de LaunchAgents plaatsen en de twee helpertaken laden
#                                         (alleen op vraag). Een nieuwe helper of een gewijzigde wacht zet de wachten
#                                         uit tot een nieuwe proef geslaagd is
#   uitrol_mac_gesprekken.sh proef        de toegangsproef onder launchd met het exacte programma (beide helpertaken
#                                         via launchctl, uitkomst ok) en een eerste ronde van elke wacht; slaagt alles,
#                                         dan een proefbewijs voor precies deze helper en deze code
#   uitrol_mac_gesprekken.sh aan          de twee wachten laden (elk uur), alleen met een proefbewijs dat bij de
#                                         huidige helper en code hoort
#   uitrol_mac_gesprekken.sh uit          de twee wachten uitzetten; de helper en zijn toestemming blijven
#   uitrol_mac_gesprekken.sh terug        de vorige helper en LaunchAgents terugzetten; de wachten blijven uit
#   uitrol_mac_gesprekken.sh controleer   versie, cdhash, proefbewijs en de stand van de vier taken
#
# REF=<commit> kiest een andere commit dan origin/main (alleen voor een proef).
# De toestemming (Full Disk Access) hangt aan de cdhash van precies dit programma, niet aan Python of de Terminal. Een
# nieuwe helper moet Mehdi dus opnieuw toestemming geven (System Settings > Privacy & Security > Full Disk Access);
# daarom bouwt deze uitrol alleen opnieuw als de bron veranderde, en bewaart hij de vorige (Codex Q7).
set -euo pipefail

modus=${1:-installeer}
REPO=${REPO:-$HOME/dev/globaal-appportal}
REF=${REF:-origin/main}
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
BASIS="$HOME/Library/Application Support/mijnagents"
WERK="$BASIS/repo"
HMAP="$BASIS/mac-gesprekken"
HELPER="$HMAP/MacGesprekkenKopie"
VORIG="$HMAP/vorige"
PROEF="$HMAP/PROEF"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/mijnagents"
uid=$(id -u)
HELPERTAKEN=(be.globaal.mijnagents.kopie-whatsapp be.globaal.mijnagents.kopie-telefoon)
WACHTEN=(be.globaal.mijnagents.whatsapp-wacht be.globaal.mijnagents.belwacht)

laad() {
    # eerst uit, dan aan: zo geldt een gewijzigde plist
    /bin/launchctl bootout "gui/$uid/$1" >/dev/null 2>&1 || true
    /bin/launchctl bootstrap "gui/$uid" "$AGENTS/$1.plist"
}

geladen() {
    /bin/launchctl print "gui/$uid/$1" >/dev/null 2>&1
}

wachten_uit() {
    for l in $WACHTEN; do /bin/launchctl bootout "gui/$uid/$l" >/dev/null 2>&1 || true; done
}

stempel() {
    # waaraan het proefbewijs hoort: de cdhash van de helper en de commit van de code
    print "$(/usr/bin/codesign -dv "$HELPER" 2>&1 | grep -m1 CDHash= | cut -d= -f2) $(git -C "$WERK" rev-parse HEAD)"
}

case $modus in
    installeer) ;;
    proef)
        rm -f "$PROEF"
        for set in whatsapp telefoon; do
            # het pad van de wacht zelf: aanvraag schrijven, launchctl kickstart, wachten op de status van die aanvraag
            "$PY" -I -c "
import sys
sys.path.insert(0, sys.argv[1])
import mac_gesprekken as M
try:
    pad, ts = M.kopie_vragen(sys.argv[2])
except M.MacFout as e:
    sys.exit(f'toegangsproef {sys.argv[2]}: {e.nood}')
M.wis(pad)
print(f'toegangsproef {sys.argv[2]}: ok onder launchd ({ts:%H:%M:%S} UTC)')
" "$WERK/mijnagents-runner/koppelingen" "$set"
        done
        "$PY" -I "$WERK/mijnagents-runner/whatsapp_wacht.py"
        "$PY" -I "$WERK/mijnagents-runner/belwacht.py"
        stempel > "$PROEF"
        print "Proef geslaagd. Lees het werkverslag op het bord na en zet de wachten dan aan met: $0 aan"
        exit 0 ;;
    aan)
        [[ -f "$PROEF" && "$(cat "$PROEF")" == "$(stempel)" ]] ||
            { print -u2 "Geen geslaagde proef voor deze helper en deze code: eerst $0 proef"; exit 1; }
        for l in $WACHTEN; do laad $l; done
        print "De WhatsApp-wacht en De Belwacht staan aan (elk uur)."
        exit 0 ;;
    uit)
        wachten_uit
        print "De WhatsApp-wacht en De Belwacht staan uit."
        exit 0 ;;
    terug)
        [[ -x "$VORIG/MacGesprekkenKopie" ]] || { print -u2 "Geen vorige helper bewaard"; exit 1; }
        wachten_uit
        rm -f "$PROEF"
        cp -p "$VORIG/MacGesprekkenKopie" "$HELPER"
        cp -p "$VORIG/BRON_SHA256" "$HMAP/BRON_SHA256" 2>/dev/null || true
        for p in "$VORIG"/*.plist(N); do cp -p "$p" "$AGENTS/"; done
        for l in $HELPERTAKEN; do laad $l; done
        print "Vorige helper en LaunchAgents teruggezet; de wachten staan uit. Daarna: $0 proef en $0 aan."
        exit 0 ;;
    controleer)
        print "code: $(git -C "$WERK" rev-parse HEAD 2>/dev/null || print ontbreekt)"
        print "helper: $(/usr/bin/codesign -dv "$HELPER" 2>&1 | grep CDHash= || print ontbreekt)"
        if [[ -f "$PROEF" && "$(cat "$PROEF")" == "$(stempel)" ]]; then print "proef: geslaagd voor deze versie"
        else print "proef: ontbreekt of hoort bij een andere versie"; fi
        for l in $HELPERTAKEN $WACHTEN; do
            if geladen $l; then
                print "$l: geladen, $(/bin/launchctl print "gui/$uid/$l" | grep -m1 'last exit code' | sed 's/^[[:space:]]*//')"
            else
                print "$l: niet geladen"
            fi
        done
        exit 0 ;;
    *)
        print -u2 "Gebruik: $0 [proef|aan|uit|terug|controleer]"
        exit 64 ;;
esac

# 1. De code: een eigen worktree, losgekoppeld op REF. Nooit de werkmap van een sessie.
git -C "$REPO" fetch -q origin
sha=$(git -C "$REPO" rev-parse "$REF^{commit}")
mkdir -p -m 700 "$BASIS"
if [[ -d "$WERK" ]]; then
    [[ -z "$(git -C "$WERK" status --porcelain)" ]] || { print -u2 "$WERK heeft eigen wijzigingen; niets gedaan"; exit 1; }
    git -C "$WERK" checkout -q --detach "$sha"
else
    git -C "$REPO" worktree add -q --detach "$WERK" "$sha"
fi

# 2. De helper, alleen als zijn bron veranderde; de vorige blijft bewaard voor terug.
bron="$WERK/mijnagents-runner/mac/kopie/macgesprekken_kopie.c"
nieuw=$(/usr/bin/shasum -a 256 "$bron" | cut -d' ' -f1)
mkdir -p -m 700 "$HMAP" "$VORIG"
helper_nieuw=0
if [[ ! -x "$HELPER" || "$(cat "$HMAP/BRON_SHA256" 2>/dev/null)" != "$nieuw" ]]; then
    tmp=$(/usr/bin/mktemp -d)
    /usr/bin/cc -O2 -Wall -Wextra -Werror -o "$tmp/MacGesprekkenKopie" "$bron" -lsqlite3
    /usr/bin/codesign -s - -o runtime -i be.globaal.macgesprekkenkopie -f "$tmp/MacGesprekkenKopie"
    if [[ -x "$HELPER" ]]; then
        cp -p "$HELPER" "$VORIG/MacGesprekkenKopie"
        cp -p "$HMAP/BRON_SHA256" "$VORIG/BRON_SHA256" 2>/dev/null || true
    fi
    mv -f "$tmp/MacGesprekkenKopie" "$HELPER"
    rmdir "$tmp"
    print "$nieuw" > "$HMAP/BRON_SHA256"
    helper_nieuw=1
fi

# 3. De LaunchAgents. Een plist die verandert, wordt eerst bewaard. De helpertaken laden (ze lopen alleen op vraag).
mkdir -p "$LOGS"
wacht_gewijzigd=0
for l in $HELPERTAKEN $WACHTEN; do
    nieuw_plist="$WERK/mijnagents-runner/mac/$l.plist"
    if [[ -f "$AGENTS/$l.plist" ]] && ! cmp -s "$nieuw_plist" "$AGENTS/$l.plist"; then
        cp -p "$AGENTS/$l.plist" "$VORIG/$l.plist"
        (( ${WACHTEN[(Ie)$l]} )) && wacht_gewijzigd=1
    fi
    cp "$nieuw_plist" "$AGENTS/$l.plist"
done
for l in $HELPERTAKEN; do laad $l; done
if (( helper_nieuw || wacht_gewijzigd )); then
    wachten_uit
    rm -f "$PROEF"
fi
print "Geïnstalleerd: $sha"
/usr/bin/codesign -dv "$HELPER" 2>&1 | grep CDHash=
if (( helper_nieuw )); then
    print "NIEUWE HELPER: Mehdi geeft $HELPER Full Disk Access (System Settings > Privacy & Security > Full Disk Access). Daarna: $0 proef"
elif (( wacht_gewijzigd )); then
    print "De wachten veranderden en staan uit. Daarna: $0 proef en $0 aan"
fi
