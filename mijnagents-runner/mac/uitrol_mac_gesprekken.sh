#!/bin/zsh
# De WhatsApp-wacht en De Belwacht op Mehdi's Mac (ontwerp dagvaststelling v2.0, fase 2).
#
#   uitrol_mac_gesprekken.sh              eerst de wachten uit, dan de code naar origin/main in een eigen worktree,
#                                         MacGesprekkenKopie bouwen als zijn bron veranderde, de LaunchAgents plaatsen
#                                         en de twee helpertaken laden (alleen op vraag). De vorige versie blijft als
#                                         geheel bewaard. De wachten blijven uit tot een nieuwe proef geslaagd is
#   uitrol_mac_gesprekken.sh proef        de toegangsproef onder launchd met het exacte programma (beide helpertaken
#                                         via launchctl, uitkomst ok) en een eigen, door het bord bevestigde ronde van
#                                         elke wacht; slaagt alles, dan een proefbewijs voor precies deze helper en code
#   uitrol_mac_gesprekken.sh aan          de twee wachten laden (elk uur), alleen met een proefbewijs dat bij de
#                                         huidige helper en code hoort
#   uitrol_mac_gesprekken.sh uit          de twee wachten uitzetten; de helper en zijn toestemming blijven
#   uitrol_mac_gesprekken.sh terug        de vorige versie als geheel terugzetten (code, helper, LaunchAgents); de
#                                         wachten blijven uit tot een nieuwe proef
#   uitrol_mac_gesprekken.sh controleer   versie, cdhash, proefbewijs en de stand van de vier taken
#
# REF=<commit> kiest een andere commit dan origin/main (alleen voor een proef).
# De toestemming (Full Disk Access) hangt aan de cdhash van precies dit programma, niet aan Python of de Terminal. Een
# nieuwe helper moet Mehdi dus opnieuw toestemming geven (System Settings > Privacy & Security > Full Disk Access);
# daarom bouwt deze uitrol alleen opnieuw als de bron veranderde (Codex Q7, R4 tot R6).
# De paden en gereedschappen zijn te vervangen voor tests/test_mac_gesprekken.py (drie uitrollen na elkaar en terug).
set -euo pipefail

modus=${1:-installeer}
REPO=${REPO:-$HOME/dev/globaal-appportal}
REF=${REF:-origin/main}
PY=${PY:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}
BASIS=${BASIS:-$HOME/Library/Application Support/mijnagents}
AGENTS=${AGENTS:-$HOME/Library/LaunchAgents}
LOGS=${LOGS:-$HOME/Library/Logs/mijnagents}
LAUNCHCTL=${LAUNCHCTL:-/bin/launchctl}
CODESIGN=${CODESIGN:-/usr/bin/codesign}
CC=${CC:-/usr/bin/cc}
WERK="$BASIS/repo"
HMAP="$BASIS/mac-gesprekken"
HELPER="$HMAP/MacGesprekkenKopie"
VORIG="$HMAP/vorige"          # de vorige versie als geheel: COMMIT, de helper, BRON_SHA256 en de LaunchAgents
PROEF="$HMAP/PROEF"
uid=$(id -u)
HELPERTAKEN=(be.globaal.mijnagents.kopie-whatsapp be.globaal.mijnagents.kopie-telefoon)
WACHTEN=(be.globaal.mijnagents.whatsapp-wacht be.globaal.mijnagents.belwacht)
ALLE=($HELPERTAKEN $WACHTEN)

laad() {
    # eerst uit, dan aan: zo geldt een gewijzigde plist
    "$LAUNCHCTL" bootout "gui/$uid/$1" >/dev/null 2>&1 || true
    "$LAUNCHCTL" bootstrap "gui/$uid" "$AGENTS/$1.plist"
}

geladen() {
    "$LAUNCHCTL" print "gui/$uid/$1" >/dev/null 2>&1
}

wachten_uit() {
    # bootout stopt ook een ronde die nog loopt; de gedeelde ronde meldt dan fout (N11)
    for l in $WACHTEN; do "$LAUNCHCTL" bootout "gui/$uid/$l" >/dev/null 2>&1 || true; done
    rm -f "$PROEF"
}

stempel() {
    # waaraan het proefbewijs hoort: de cdhash van de helper en de commit van de code
    print "$("$CODESIGN" -dv "$HELPER" 2>&1 | grep -m1 CDHash= | cut -d= -f2) $(git -C "$WERK" rev-parse HEAD)"
}

bewaar_vorige() {
    # de versie die nu staat, als een geheel; pas na een volledige kopie vervangt ze de vorige
    [[ -d "$WERK" && -x "$HELPER" ]] || return 0
    rm -rf "$VORIG.nieuw"
    mkdir -m 700 "$VORIG.nieuw"
    git -C "$WERK" rev-parse HEAD > "$VORIG.nieuw/COMMIT"
    cp -p "$HELPER" "$HMAP/BRON_SHA256" "$VORIG.nieuw/"
    for l in $ALLE; do
        [[ -f "$AGENTS/$l.plist" ]] && cp -p "$AGENTS/$l.plist" "$VORIG.nieuw/"
    done
    rm -rf "$VORIG"
    mv "$VORIG.nieuw" "$VORIG"
}

case $modus in
    installeer) ;;
    proef)
        rm -f "$PROEF"
        "$PY" -I -c "
import sys
sys.path.insert(0, sys.argv[1] + '/koppelingen')
import mac_gesprekken as M
try:
    for kanaal in ('whatsapp', 'telefoon'):
        # het pad van de wacht zelf: aanvraag, launchctl kickstart, de status van precies die aanvraag
        pad, ts = M.kopie_vragen(kanaal)
        M.wis(pad)
        print(f'toegangsproef {kanaal}: ok onder launchd ({ts:%H:%M:%S} UTC)')
    for runner, naam in (('whatsapp_wacht.py', 'whatsapp-wacht'), ('belwacht.py', 'belwacht')):
        print(f'proefronde {naam}: ronde-id {M.proefronde(sys.argv[1] + \"/\" + runner, naam)} bevestigd')
except M.MacFout as e:
    sys.exit(f'proef mislukt: {e.nood}')
" "$WERK/mijnagents-runner"
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
        [[ -f "$VORIG/COMMIT" && -x "$VORIG/MacGesprekkenKopie" ]] || { print -u2 "Geen vorige versie bewaard"; exit 1; }
        wachten_uit
        for l in $HELPERTAKEN; do "$LAUNCHCTL" bootout "gui/$uid/$l" >/dev/null 2>&1 || true; done
        git -C "$WERK" checkout -q --detach "$(cat "$VORIG/COMMIT")"
        cp -p "$VORIG/MacGesprekkenKopie" "$HELPER"
        cp -p "$VORIG/BRON_SHA256" "$HMAP/BRON_SHA256"
        for l in $ALLE; do
            if [[ -f "$VORIG/$l.plist" ]]; then cp -p "$VORIG/$l.plist" "$AGENTS/$l.plist"; else rm -f "$AGENTS/$l.plist"; fi
        done
        for l in $HELPERTAKEN; do [[ -f "$AGENTS/$l.plist" ]] && laad $l; done
        print "Vorige versie teruggezet ($(cat "$VORIG/COMMIT")); de wachten staan uit. Daarna: $0 proef en $0 aan."
        exit 0 ;;
    controleer)
        print "code: $(git -C "$WERK" rev-parse HEAD 2>/dev/null || print ontbreekt)"
        print "helper: $("$CODESIGN" -dv "$HELPER" 2>&1 | grep CDHash= || print ontbreekt)"
        if [[ -f "$PROEF" && "$(cat "$PROEF")" == "$(stempel)" ]]; then print "proef: geslaagd voor deze versie"
        else print "proef: ontbreekt of hoort bij een andere versie"; fi
        for l in $ALLE; do
            if geladen $l; then print "$l: geladen"; else print "$l: niet geladen"; fi
        done
        exit 0 ;;
    *)
        print -u2 "Gebruik: $0 [proef|aan|uit|terug|controleer]"
        exit 64 ;;
esac

# 0. Eerst de wachten uit (Codex R4): geen ronde draait op code of een helper die nog niet beproefd is.
wachten_uit

# 1. De code: een eigen worktree, losgekoppeld op REF. Nooit de werkmap van een sessie.
git -C "$REPO" fetch -q origin
sha=$(git -C "$REPO" rev-parse "$REF^{commit}")
mkdir -p -m 700 "$BASIS" "$HMAP"
if [[ -d "$WERK" ]]; then
    [[ -z "$(git -C "$WERK" status --porcelain)" ]] || { print -u2 "$WERK heeft eigen wijzigingen; niets gedaan"; exit 1; }
    [[ "$(git -C "$WERK" rev-parse HEAD)" == "$sha" ]] || bewaar_vorige
    git -C "$WERK" checkout -q --detach "$sha"
else
    git -C "$REPO" worktree add -q --detach "$WERK" "$sha"
fi

# 2. De helper, alleen als zijn bron veranderde.
bron="$WERK/mijnagents-runner/mac/kopie/macgesprekken_kopie.c"
nieuw=$(/usr/bin/shasum -a 256 "$bron" | cut -d' ' -f1)
helper_nieuw=0
if [[ ! -x "$HELPER" || "$(cat "$HMAP/BRON_SHA256" 2>/dev/null)" != "$nieuw" ]]; then
    tmp=$(/usr/bin/mktemp -d)
    "$CC" -O2 -Wall -Wextra -Werror -o "$tmp/MacGesprekkenKopie" "$bron" -lsqlite3
    "$CODESIGN" -s - -o runtime -i be.globaal.macgesprekkenkopie -f "$tmp/MacGesprekkenKopie"
    mv -f "$tmp/MacGesprekkenKopie" "$HELPER"
    rmdir "$tmp"
    print "$nieuw" > "$HMAP/BRON_SHA256"
    helper_nieuw=1
fi

# 3. De LaunchAgents; de helpertaken laden (ze lopen alleen op vraag).
mkdir -p "$LOGS" "$AGENTS"
for l in $ALLE; do
    cp "$WERK/mijnagents-runner/mac/$l.plist" "$AGENTS/$l.plist"
done
for l in $HELPERTAKEN; do laad $l; done
print "Geïnstalleerd: $sha"
"$CODESIGN" -dv "$HELPER" 2>&1 | grep CDHash= || true
if (( helper_nieuw )); then
    print "NIEUWE HELPER: Mehdi geeft $HELPER Full Disk Access (System Settings > Privacy & Security > Full Disk Access)."
fi
print "De wachten staan uit. Daarna: $0 proef, nalezen, en $0 aan."
