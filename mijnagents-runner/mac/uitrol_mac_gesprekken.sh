#!/bin/zsh
# De WhatsApp-wacht, De Belwacht en (sinds 31-10-2026) De Sms-wacht op Mehdi's Mac (ontwerp dagvaststelling v2.0,
# fase 2). De Sms-wacht heeft een eigen proefbewijs (PROEF_SMS): staat Messages nog niet klaar, dan blijven WhatsApp en
# telefoon gewoon werken. Sinds 01-11-2026 (T-0120 VOL-11) ook De Websitewacht en De YouTube-wacht: ze lezen de set
# browser van dezelfde helper, met een eigen proefbewijs (PROEF_BROWSER), en De Belwacht en De Sms-wacht krijgen de
# namen uit het adresboek van Contacts (TEL-9). Een nieuwe helper, dus een keer Full Disk Access opnieuw (zie onder).
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
# Een slot voor alle opdrachten behalve controleer (Codex S4): installeer, proef, aan, uit en terug lopen nooit samen.
# De code wisselt alleen als beide wachten echt uit launchd zijn en geen ronde loopt; hun rondeslot blijft vast tijdens
# de wissel (S3).
# De paden en gereedschappen zijn te vervangen voor tests/test_mac_gesprekken.py (drie uitrollen na elkaar en terug).
set -euo pipefail

SCRIPT=${0:A}                 # het pad van dit script; in een functie is $0 in zsh de functienaam
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
LOCKF=${LOCKF:-/usr/bin/lockf}
WERK="$BASIS/repo"
HMAP="$BASIS/mac-gesprekken"
HELPER="$HMAP/MacGesprekkenKopie"
VORIG="$HMAP/vorige"          # de vorige versie als geheel: COMMIT, de helper, BRON_SHA256 en de LaunchAgents
PROEF="$HMAP/PROEF"
PROEF_SMS="$HMAP/PROEF_SMS"
PROEF_BROWSER="$HMAP/PROEF_BROWSER"
uid=$(id -u)
HELPERTAKEN=(be.globaal.mijnagents.kopie-whatsapp be.globaal.mijnagents.kopie-telefoon be.globaal.mijnagents.kopie-sms
             be.globaal.mijnagents.kopie-browser)
WACHTEN=(be.globaal.mijnagents.whatsapp-wacht be.globaal.mijnagents.belwacht be.globaal.mijnagents.sms-wacht)
# De Websitewacht en De YouTube-wacht (WEB-1, YT-1): korte rondes zonder rondeslot, wel uit voor elke wissel
LOSSE_WACHTEN=(be.globaal.mijnagents.browser be.globaal.mijnagents.youtube)
ALLE=($HELPERTAKEN $WACHTEN $LOSSE_WACHTEN)

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
    for l in $WACHTEN $LOSSE_WACHTEN; do "$LAUNCHCTL" bootout "gui/$uid/$l" >/dev/null 2>&1 || true; done
    rm -f "$PROEF" "$PROEF_SMS" "$PROEF_BROWSER"
}

wachten_echt_uit() {
    # Codex S3: een bootout die faalt, mag niet stil voorbijgaan; staat een wacht nog in launchd, dan wisselt niets
    wachten_uit
    for l in $WACHTEN $LOSSE_WACHTEN; do
        if geladen $l; then print -u2 "$l staat nog in launchd; niets gewisseld"; exit 1; fi
    done
}

met_rondesloten() {
    # de wissel loopt met de rondesloten van beide wachten vast (zoals mac_gesprekken.slot ze neemt); loopt er nog een
    # ronde, dan geeft lockf meteen 75 en wisselt niets
    mkdir -p -m 700 "$BASIS/whatsapp-wacht" "$BASIS/belwacht" "$BASIS/sms-wacht"
    exec "$LOCKF" -k -t 0 "$BASIS/whatsapp-wacht/ronde.lock" "$LOCKF" -k -t 0 "$BASIS/belwacht/ronde.lock" \
        "$LOCKF" -k -t 0 "$BASIS/sms-wacht/ronde.lock" /bin/zsh "$SCRIPT" "$@"
}

stempel() {
    # waaraan het proefbewijs hoort: de cdhash van de helper en de commit van de code. TEL-7 (T-0067): -dv toont geen
    # CDHash, pas -dvvv; ^CDHash= laat de regels CandidateCDHash staan
    print "$("$CODESIGN" -dvvv "$HELPER" 2>&1 | grep -m1 '^CDHash=' | cut -d= -f2) $(git -C "$WERK" rev-parse HEAD)"
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

if [[ $modus != controleer && -z ${UITROL_SLOT:-} ]]; then
    mkdir -p -m 700 "$BASIS" "$HMAP"
    # Codex U2: een sleutel per uitrol; alleen wie hem kent (dit proces en zijn kinderen), kan de wissel starten
    export UITROL_SLOT=1 UITROL_SLEUTEL=$(/usr/bin/od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
    exec "$LOCKF" -k -t 0 "$HMAP/.uitrol.lock" /bin/zsh "$SCRIPT" "$@"
fi
vast() {
    # houdt iemand (de lockf boven mij) dit slot vast? lockf -t 0 moet dan meteen falen
    ! "$LOCKF" -k -t 0 "$1" /usr/bin/true >/dev/null 2>&1
}
# Codex T2: UITROL_SLOT alleen zegt niets; het slot moet echt vastzitten, en voor de wissel ook de rondesloten.
if [[ $modus != controleer ]]; then
    vast "$HMAP/.uitrol.lock" || { print -u2 "Het uitrolslot zit niet vast; niets gedaan"; exit 64; }
fi
if [[ $modus == __* ]]; then
    vast "$BASIS/whatsapp-wacht/ronde.lock" && vast "$BASIS/belwacht/ronde.lock" && vast "$BASIS/sms-wacht/ronde.lock" ||
        { print -u2 "De rondesloten zitten niet vast; niets gewisseld"; exit 64; }
    [[ -n ${UITROL_SLEUTEL:-} && "$(cat "$HMAP/.uitrol.sleutel" 2>/dev/null)" == "$UITROL_SLEUTEL" ]] ||
        { print -u2 "Deze wissel hoort niet bij de uitrol die de sloten houdt; niets gewisseld"; exit 64; }
elif [[ $modus != controleer ]]; then
    (umask 077; print -r -- "${UITROL_SLEUTEL:-}" > "$HMAP/.uitrol.sleutel")
fi

case $modus in
    installeer)
        wachten_echt_uit
        met_rondesloten __installeer ;;
    __installeer) ;;
    proef)
        rm -f "$PROEF" "$PROEF_SMS" "$PROEF_BROWSER"
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
    # TEL-9: het adresboek van Contacts is een extra bron; zonder blijven de namen van WhatsApp
    import json
    print('adresboek van Contacts:', json.loads((M.KOPIE / 'telefoon' / 'status.json').read_text()).get('extra'))
    for runner, naam in (('whatsapp_wacht.py', 'whatsapp-wacht'), ('belwacht.py', 'belwacht')):
        print(f'proefronde {naam}: ronde-id {M.proefronde(sys.argv[1] + \"/\" + runner, naam)} bevestigd')
except M.MacFout as e:
    sys.exit(f'proef mislukt: {e.nood}')
" "$WERK/mijnagents-runner"
        stempel > "$PROEF"
        print "Proef WhatsApp en telefoon geslaagd."
        if "$PY" -I -c "
import sys
sys.path.insert(0, sys.argv[1] + '/koppelingen')
import mac_gesprekken as M
try:
    pad, ts = M.kopie_vragen('sms')
    M.wis(pad)
    print(f'toegangsproef sms: ok onder launchd ({ts:%H:%M:%S} UTC)')
    print(f'proefronde sms-wacht: ronde-id {M.proefronde(sys.argv[1] + \"/sms_wacht.py\", \"sms-wacht\")} bevestigd')
except M.MacFout as e:
    sys.exit(f'proef sms mislukt: {e.nood}')
" "$WERK/mijnagents-runner"; then
            stempel > "$PROEF_SMS"
            print "Proef sms geslaagd."
        else
            print -u2 "De Sms-wacht blijft uit; WhatsApp en telefoon kunnen wel aan."
        fi
        # YT-1 en WEB-1: de set browser onder launchd, en beide wachten droog (niets naar het bord)
        if "$PY" -I -c "
import sys
sys.path.insert(0, sys.argv[1] + '/koppelingen')
import mac_gesprekken as M
try:
    bezoeken, gelezen, onleesbaar = M.browser_kopie(0)
except M.MacFout as e:
    sys.exit(f'proef browser mislukt: {e.nood}')
print('toegangsproef browser: ok onder launchd; gelezen: ' + (', '.join(f'{b} ({n})' for b, n in gelezen.items()) or 'niets')
      + (f'; onleesbaar: {onleesbaar}' if onleesbaar else '') + f'; {len(bezoeken)} bezoeken')
if not gelezen:
    sys.exit('proef browser mislukt: geen enkele browser gelezen')
" "$WERK/mijnagents-runner" && "$PY" -I "$WERK/mijnagents-runner/mac/browser_wacht.py" --droog --dagen 2 >/dev/null &&
            "$PY" -I "$WERK/mijnagents-runner/mac/youtube_wacht.py" --droog --dagen 2 >/dev/null; then
            stempel > "$PROEF_BROWSER"
            print "Proef browser geslaagd (De Websitewacht en De YouTube-wacht droog)."
        else
            print -u2 "De Websitewacht en De YouTube-wacht blijven uit; de andere wachten kunnen wel aan."
        fi
        print "Lees het werkverslag op het bord na en zet de wachten dan aan met: $0 aan"
        exit 0 ;;
    aan)
        [[ -f "$PROEF" && "$(cat "$PROEF")" == "$(stempel)" ]] ||
            { print -u2 "Geen geslaagde proef voor deze helper en deze code: eerst $0 proef"; exit 1; }
        for l in be.globaal.mijnagents.whatsapp-wacht be.globaal.mijnagents.belwacht; do laad $l; done
        print "De WhatsApp-wacht en De Belwacht staan aan (elk uur)."
        if [[ -f "$PROEF_SMS" && "$(cat "$PROEF_SMS")" == "$(stempel)" && -f "$AGENTS/be.globaal.mijnagents.sms-wacht.plist" ]]; then
            laad be.globaal.mijnagents.sms-wacht
            print "De Sms-wacht staat aan (elk uur)."
        else
            print "De Sms-wacht blijft uit: geen geslaagde sms-proef voor deze versie."
        fi
        if [[ -f "$PROEF_BROWSER" && "$(cat "$PROEF_BROWSER")" == "$(stempel)" ]]; then
            for l in $LOSSE_WACHTEN; do if [[ -f "$AGENTS/$l.plist" ]]; then laad $l; fi; done
            print "De Websitewacht en De YouTube-wacht staan aan (elk uur)."
        else
            print "De Websitewacht en De YouTube-wacht blijven uit: geen geslaagde browserproef voor deze versie."
        fi
        exit 0 ;;
    uit)
        wachten_uit
        print "De WhatsApp-wacht, De Belwacht, De Sms-wacht, De Websitewacht en De YouTube-wacht staan uit."
        exit 0 ;;
    terug)
        [[ -f "$VORIG/COMMIT" && -x "$VORIG/MacGesprekkenKopie" ]] || { print -u2 "Geen vorige versie bewaard"; exit 1; }
        wachten_echt_uit
        met_rondesloten __terug ;;
    __terug)
        for l in $HELPERTAKEN; do "$LAUNCHCTL" bootout "gui/$uid/$l" >/dev/null 2>&1 || true; done
        git -C "$WERK" checkout -q --detach "$(cat "$VORIG/COMMIT")"
        cp -p "$VORIG/MacGesprekkenKopie" "$HELPER"
        cp -p "$VORIG/BRON_SHA256" "$HMAP/BRON_SHA256"
        for l in $ALLE; do
            if [[ -f "$VORIG/$l.plist" ]]; then cp -p "$VORIG/$l.plist" "$AGENTS/$l.plist"; else rm -f "$AGENTS/$l.plist"; fi
        done
        for l in $HELPERTAKEN; do if [[ -f "$AGENTS/$l.plist" ]]; then laad $l; fi; done
        print "Vorige versie teruggezet ($(cat "$VORIG/COMMIT")); de wachten staan uit. Daarna: $0 proef en $0 aan."
        exit 0 ;;
    controleer)
        print "code: $(git -C "$WERK" rev-parse HEAD 2>/dev/null || print ontbreekt)"
        print "helper: $("$CODESIGN" -dvvv "$HELPER" 2>&1 | grep -m1 '^CDHash=' || print ontbreekt)"
        if [[ -f "$PROEF" && "$(cat "$PROEF")" == "$(stempel)" ]]; then print "proef: geslaagd voor deze versie"
        else print "proef: ontbreekt of hoort bij een andere versie"; fi
        if [[ -f "$PROEF_SMS" && "$(cat "$PROEF_SMS")" == "$(stempel)" ]]; then print "proef sms: geslaagd voor deze versie"
        else print "proef sms: ontbreekt of hoort bij een andere versie"; fi
        if [[ -f "$PROEF_BROWSER" && "$(cat "$PROEF_BROWSER")" == "$(stempel)" ]]; then
            print "proef browser: geslaagd voor deze versie"
        else print "proef browser: ontbreekt of hoort bij een andere versie"; fi
        for l in $ALLE; do
            if geladen $l; then print "$l: geladen"; else print "$l: niet geladen"; fi
        done
        exit 0 ;;
    *)
        print -u2 "Gebruik: $0 [proef|aan|uit|terug|controleer]"
        exit 64 ;;
esac

# 0. De wachten zijn uit (Codex R4, S3) en hun rondesloten zijn vast: geen ronde draait op code of een helper die nog
#    niet beproefd is.

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
    # een versie van voor de Sms-wacht (REF of terug) heeft haar plists niet
    if [[ -f "$WERK/mijnagents-runner/mac/$l.plist" ]]; then cp "$WERK/mijnagents-runner/mac/$l.plist" "$AGENTS/$l.plist"
    else rm -f "$AGENTS/$l.plist"; fi
done
for l in $HELPERTAKEN; do if [[ -f "$AGENTS/$l.plist" ]]; then laad $l; fi; done
print "Geïnstalleerd: $sha"
"$CODESIGN" -dvvv "$HELPER" 2>&1 | grep -m1 '^CDHash=' || true
if (( helper_nieuw )); then
    # De toestemming hangt aan de cdhash: uit en aan zetten werkt niet, alleen weghalen en opnieuw toevoegen
    print "NIEUWE HELPER: Mehdi geeft $HELPER opnieuw Full Disk Access:"
    print "  1. System Settings > Privacy & Security > Full Disk Access"
    print "  2. MacGesprekkenKopie aanklikken en op - klikken (de oude weg)"
    print "  3. Op + klikken, Cmd+Shift+G, dit pad plakken, Open: $HELPER"
    print "  4. De schakelaar van MacGesprekkenKopie staat aan"
fi
print "De wachten staan uit. Daarna: $0 proef, nalezen, en $0 aan."
