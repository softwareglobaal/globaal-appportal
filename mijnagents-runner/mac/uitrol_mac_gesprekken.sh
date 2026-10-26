#!/bin/zsh
# De WhatsApp-wacht en De Belwacht op Mehdi's Mac (ontwerp dagvaststelling v2.0, fase 2).
#
#   uitrol_mac_gesprekken.sh              de code naar origin/main in een eigen worktree, MacGesprekkenKopie bouwen als
#                                         zijn bron veranderde, de vier LaunchAgents plaatsen en de twee helpertaken
#                                         laden (alleen op vraag); de twee wachten blijven uit
#   uitrol_mac_gesprekken.sh aan          ook de twee wachten laden (elk uur): pas na een gecontroleerde eerste ronde
#   uitrol_mac_gesprekken.sh uit          de twee wachten uitzetten; de helper en zijn toestemming blijven
#   uitrol_mac_gesprekken.sh controleer   versie, cdhash van de helper en de stand van de vier taken
#
# REF=<commit> kiest een andere commit dan origin/main (alleen voor een proef).
# De helper wordt alleen opnieuw gebouwd als zijn bron veranderde. Een nieuwe helper heeft een nieuwe cdhash, en dan
# moet Mehdi hem opnieuw Full Disk Access geven (System Settings > Privacy & Security > Full Disk Access): de
# toestemming hangt aan precies dit programma, niet aan Python of de Terminal.
set -euo pipefail

modus=${1:-installeer}
REPO=${REPO:-$HOME/dev/globaal-appportal}
REF=${REF:-origin/main}
BASIS="$HOME/Library/Application Support/mijnagents"
WERK="$BASIS/repo"
HMAP="$BASIS/mac-gesprekken"
HELPER="$HMAP/MacGesprekkenKopie"
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

case $modus in
    installeer) ;;
    aan)
        for l in $WACHTEN; do laad $l; done
        print "De WhatsApp-wacht en De Belwacht staan aan (elk uur)."
        exit 0 ;;
    uit)
        for l in $WACHTEN; do /bin/launchctl bootout "gui/$uid/$l" >/dev/null 2>&1 || true; done
        print "De WhatsApp-wacht en De Belwacht staan uit."
        exit 0 ;;
    controleer)
        print "code: $(git -C "$WERK" rev-parse HEAD 2>/dev/null || print ontbreekt)"
        print "helper: $(/usr/bin/codesign -dv "$HELPER" 2>&1 | grep CDHash= || print ontbreekt)"
        for l in $HELPERTAKEN $WACHTEN; do
            if geladen $l; then
                print "$l: geladen, $(/bin/launchctl print "gui/$uid/$l" | grep -m1 'last exit code' | sed 's/^[[:space:]]*//')"
            else
                print "$l: niet geladen"
            fi
        done
        exit 0 ;;
    *)
        print -u2 "Gebruik: $0 [aan|uit|controleer]"
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

# 2. De helper, alleen als zijn bron veranderde.
bron="$WERK/mijnagents-runner/mac/kopie/macgesprekken_kopie.c"
nieuw=$(/usr/bin/shasum -a 256 "$bron" | cut -d' ' -f1)
mkdir -p -m 700 "$HMAP"
if [[ ! -x "$HELPER" || "$(cat "$HMAP/BRON_SHA256" 2>/dev/null)" != "$nieuw" ]]; then
    tmp=$(/usr/bin/mktemp -d)
    /usr/bin/cc -O2 -Wall -Wextra -Werror -o "$tmp/MacGesprekkenKopie" "$bron" -lsqlite3
    /usr/bin/codesign -s - -o runtime -i be.globaal.macgesprekkenkopie -f "$tmp/MacGesprekkenKopie"
    mv -f "$tmp/MacGesprekkenKopie" "$HELPER"
    rmdir "$tmp"
    print "$nieuw" > "$HMAP/BRON_SHA256"
    print "NIEUWE HELPER: geef $HELPER Full Disk Access (System Settings > Privacy & Security > Full Disk Access)."
fi

# 3. De LaunchAgents. De helpertaken laden (ze lopen alleen op vraag); een wacht die al aanstond, opnieuw laden.
mkdir -p "$LOGS"
for l in $HELPERTAKEN $WACHTEN; do
    cp "$WERK/mijnagents-runner/mac/$l.plist" "$AGENTS/$l.plist"
done
for l in $HELPERTAKEN; do laad $l; done
for l in $WACHTEN; do
    if geladen $l; then laad $l; fi
done
print "Geïnstalleerd: $sha"
/usr/bin/codesign -dv "$HELPER" 2>&1 | grep CDHash=
