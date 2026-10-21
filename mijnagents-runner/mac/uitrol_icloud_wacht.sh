#!/bin/zsh
# Op Mehdi's Mac: haal de laatste groen geteste main-versie op, werk de iCloudWacht-app
# en twee LaunchAgents bij en controleer de uitkomst. Bestaande versies blijven als
# backup beschikbaar. Alleen bij een gewijzigde starter is --herbouw-starter nodig.
# sudo installeert /Library/Application Support/iCloudWacht als root:wheel-map;
# het Python-script en VERSIE daarin worden eveneens eigendom van root:wheel.
set -euo pipefail

REPO=${REPO:-$HOME/dev/globaal-appportal}
APP=${APP:-$HOME/Applications/iCloudWacht.app}
DATA=${DATA:-$HOME/Library/Application Support/iCloudWacht}
GH=${GH:-/opt/homebrew/bin/gh}
ROOT_DATA='/Library/Application Support/iCloudWacht'
PYTHON_VAST='/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9'
PY=mijnagents-runner/mac/icloud_wacht.py
C=mijnagents-runner/mac/starter/icloudwacht.c
INFO=mijnagents-runner/mac/starter/Info.plist
ENTITLEMENTS=mijnagents-runner/mac/starter/Entitlements.plist

if (( $# > 1 )) || { (( $# == 1 )) && [[ "$1" != --controleer && "$1" != --herbouw-starter ]]; }; then
    print -u2 -- "Gebruik: $0 [--controleer|--herbouw-starter]"
    exit 64
fi
modus=${1:-uitrol}
[[ -d "$REPO/.git" ]] || { print -u2 -- "Repo ontbreekt: $REPO"; exit 1; }
[[ -x "$GH" ]] || { print -u2 -- "gh ontbreekt: $GH"; exit 1; }
[[ "$APP" == *.app && ! -L "$APP" ]] || { print -u2 -- "APP moet een echte .app-map zijn"; exit 1; }

werk=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/icloud-uitrol.XXXXXXXX")
app_backup=''
app_backed=0
app_new=0
root_changed=0
root_old_script=0
root_old_versie=0
plist_changed=()
typeset -A was_loaded
stempel=$(/bin/date '+%Y%m%dT%H%M%S').$$

bootstrap_met_herhaling() {
    local plist=$1 poging
    for poging in 1 2 3; do
        /bin/launchctl bootstrap "gui/$uid" "$plist" && return 0
        (( poging == 3 )) && break
        /bin/sleep 1
    done
    return 1
}

terugzetten() {
    local label plist backup
    print -u2 -- 'Uitrol mislukt; vorige toestand wordt teruggezet.'
    if (( app_new )) && [[ -d "$APP" ]]; then
        /bin/mv "$APP" "$DATA/app-bak/iCloudWacht.mislukt.$stempel.app" ||
            print -u2 -- 'Nieuwe app kon niet apart worden gezet'
    fi
    if (( app_backed )); then
        /bin/mv "$app_backup" "$APP" || print -u2 -- 'Vorige app kon niet worden teruggezet'
    fi
    if (( root_changed )); then
        /usr/bin/sudo /bin/rm -f "$ROOT_DATA/icloud_wacht.py.nieuw.$stempel" \
            "$ROOT_DATA/VERSIE.nieuw.$stempel" || true
        if (( root_old_script )); then
            /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 \
                "$root_backup/icloud_wacht.py" "$ROOT_DATA/icloud_wacht.py" ||
                print -u2 -- 'Vorig root-script kon niet worden teruggezet'
        else
            /usr/bin/sudo /bin/rm -f "$ROOT_DATA/icloud_wacht.py" || true
        fi
        if (( root_old_versie )); then
            /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 \
                "$root_backup/VERSIE" "$ROOT_DATA/VERSIE" ||
                print -u2 -- 'Vorige root-versie kon niet worden teruggezet'
        else
            /usr/bin/sudo /bin/rm -f "$ROOT_DATA/VERSIE" || true
        fi
    fi
    for label in "${plist_changed[@]}"; do
        plist="$launchagents/$label.plist"
        backup="$DATA/plist-bak/$label.$stempel.plist"
        /bin/cp -p "$backup" "$plist" || print -u2 -- "Terugzetten plist mislukt: $plist"
        /bin/launchctl bootout "gui/$uid/$label" >/dev/null 2>&1 || true
        if [[ "${was_loaded[$label]:-0}" == 1 ]]; then
            bootstrap_met_herhaling "$plist" || print -u2 -- "Herstart vorige LaunchAgent mislukt: $label"
        fi
    done
}

opruimen() {
    local code=$?
    trap - EXIT
    if (( code != 0 && (root_changed || app_backed || app_new || ${#plist_changed[@]} > 0) )); then
        terugzetten
    fi
    /bin/rm -rf -- "$werk"
    exit "$code"
}
trap opruimen EXIT

git -C "$REPO" fetch -q origin main
# De eerste ouder is de gepubliceerde main-lijn, inclusief de merge-commit.
sha=$(git -C "$REPO" log -1 --first-parent --format=%H origin/main -- "$PY" mijnagents-runner/mac/starter)
[[ -n "$sha" ]] || { print -u2 -- 'Geen gepubliceerde iCloud-versie'; exit 1; }
geslaagd=$(cd "$REPO" && "$GH" run list -R softwareglobaal/globaal-appportal \
    --workflow verslag-grendels.yml --commit "$sha" --branch main --event push \
    --json status,conclusion --limit 1 \
    --jq '.[0] | select(.status == "completed" and .conclusion == "success") | .conclusion')
[[ "$geslaagd" == success ]] || { print -u2 -- "Nieuwste push-CI op main ontbreekt of is niet groen voor $sha"; exit 1; }

git -C "$REPO" show "$sha:$PY" > "$werk/icloud_wacht.py"
git -C "$REPO" show "$sha:$C" > "$werk/icloudwacht.c"
git -C "$REPO" show "$sha:$INFO" > "$werk/Info.plist"
git -C "$REPO" show "$sha:$ENTITLEMENTS" > "$werk/Entitlements.plist"
python_blob=$(git -C "$REPO" rev-parse "$sha:$PY")
starter_blob=$(git -C "$REPO" rev-parse "$sha:$C")
info_blob=$(git -C "$REPO" rev-parse "$sha:$INFO")
entitlements_blob=$(git -C "$REPO" rev-parse "$sha:$ENTITLEMENTS")
[[ "$(git -C "$REPO" hash-object "$werk/icloud_wacht.py")" == "$python_blob" &&
   "$(git -C "$REPO" hash-object "$werk/icloudwacht.c")" == "$starter_blob" &&
   "$(git -C "$REPO" hash-object "$werk/Info.plist")" == "$info_blob" &&
   "$(git -C "$REPO" hash-object "$werk/Entitlements.plist")" == "$entitlements_blob" ]] ||
    { print -u2 -- 'Opgehaalde bron wijkt af van de gepubliceerde commit'; exit 1; }
/usr/bin/python3 - "$werk/icloud_wacht.py" <<'PYCONTROLE'
import ast
import pathlib
import sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
PYCONTROLE
/usr/bin/plutil -lint "$werk/Info.plist" >/dev/null
/usr/bin/plutil -lint "$werk/Entitlements.plist" >/dev/null
print -r -- "$sha" > "$werk/VERSIE"
starter_hash=$(/usr/bin/shasum -a 256 "$werk/icloudwacht.c" | /usr/bin/awk '{print $1}')
starter="$APP/Contents/MacOS/icloudwacht"
hashpad="$APP/Contents/Resources/starter.sha256"
launchagents="$HOME/Library/LaunchAgents"
uid=$(/usr/bin/id -u)

veilig_rootpad() {
    /usr/bin/python3 - "$ROOT_DATA" <<'PYPAD'
import os
import stat
import sys
root = sys.argv[1]
for path, is_dir in [('/', True), ('/Library', True),
                     ('/Library/Application Support', True), (root, True),
                     (root + '/icloud_wacht.py', False), (root + '/VERSIE', False)]:
    try:
        st = os.lstat(path)
    except OSError:
        raise SystemExit(1)
    if st.st_uid != 0 or st.st_mode & 0o022 or not (
            stat.S_ISDIR(st.st_mode) if is_dir else stat.S_ISREG(st.st_mode)):
        raise SystemExit(1)
PYPAD
}

veilig_pythonpad() {
    /usr/bin/python3 - "$PYTHON_VAST" <<'PYPAD'
import os
import stat
import sys
path = sys.argv[1]
parts = path.split('/')[1:]
root = os.lstat('/')
if root.st_uid != 0 or root.st_mode & 0o022 or not stat.S_ISDIR(root.st_mode):
    raise SystemExit(1)
current = ''
for index, part in enumerate(parts):
    current += '/' + part
    try:
        st = os.lstat(current)
    except OSError:
        raise SystemExit(1)
    is_file = index == len(parts) - 1
    if st.st_uid != 0 or st.st_mode & 0o022 or not (
            stat.S_ISREG(st.st_mode) if is_file else stat.S_ISDIR(st.st_mode)):
        raise SystemExit(1)
    if is_file and not st.st_mode & stat.S_IXUSR:
        raise SystemExit(1)
PYPAD
}

handtekening_veilig() {
    "$PYTHON_VAST" - "$1" <<'PYCODE'
import plistlib
import re
import subprocess
import sys

app = sys.argv[1]
codesign = '/usr/bin/codesign'
verify = subprocess.run([codesign, '--verify', '--strict', app], capture_output=True)
display = subprocess.run([codesign, '-d', '--verbose=4', app], capture_output=True)
entitlements = subprocess.run([codesign, '-d', '--entitlements', ':-', app], capture_output=True)
flags = re.search(rb'^CodeDirectory .*flags=0x[0-9a-fA-F]+\(([^)]*)\)',
                  display.stderr, re.MULTILINE)
identiteit = re.search(rb'^Identifier=([^\r\n]+)', display.stderr, re.MULTILINE)
try:
    rechten = plistlib.loads(entitlements.stdout)
except (ValueError, TypeError):
    rechten = None
goed = (verify.returncode == display.returncode == entitlements.returncode == 0
        and flags is not None and b'runtime' in flags.group(1).split(b',')
        and identiteit is not None and identiteit.group(1) == b'be.globaal.icloudwacht'
        and rechten == {'com.apple.security.automation.apple-events': True})
raise SystemExit(0 if goed else 1)
PYCODE
}

plist_juist() {
    /usr/bin/python3 - "$1" "$starter" "$2" <<'PYPLIST'
import plistlib
import sys
try:
    with open(sys.argv[1], 'rb') as f:
        actual = plistlib.load(f).get('ProgramArguments')
except (OSError, ValueError):
    raise SystemExit(1)
expected = [sys.argv[2]] + (['--taken'] if sys.argv[3].endswith('-taken') else [])
raise SystemExit(0 if actual == expected else 1)
PYPLIST
}

plist_starter_als_eerste_arg() {
    /usr/bin/python3 - "$1" "$starter" <<'PYPLIST'
import plistlib
import sys
with open(sys.argv[1], 'rb') as f:
    args = plistlib.load(f).get('ProgramArguments')
raise SystemExit(0 if isinstance(args, list) and args and args[0] == sys.argv[2] else 1)
PYPLIST
}

controleer() {
    local rapport="$werk/verschillen.txt" label plist
    : > "$rapport"
    if ! veilig_rootpad; then
        print -r -- "Root-script, versie of een padcomponent ontbreekt of heeft onveilige rechten" >> "$rapport"
    else
        for naam in icloud_wacht.py VERSIE; do
            if ! /usr/bin/cmp -s "$werk/$naam" "$ROOT_DATA/$naam"; then
                /usr/bin/diff -u "$werk/$naam" "$ROOT_DATA/$naam" >> "$rapport" || true
            fi
        done
    fi
    veilig_pythonpad || print -r -- 'Vaste root-eigen Python 3.9 ontbreekt of heeft onveilige rechten' >> "$rapport"
    if [[ ! -x "$starter" ]] || ! handtekening_veilig "$APP"; then
        print -r -- 'Starter ontbreekt of handtekening mist geharde runtime of veilige rechten' >> "$rapport"
    fi
    if [[ ! -f "$hashpad" || "$(<"$hashpad")" != "$starter_hash" ]]; then
        print -r -- 'Starterbron verschilt van de app' >> "$rapport"
    fi
    if [[ ! -f "$APP/Contents/Info.plist" ]] ||
       ! /usr/bin/cmp -s "$werk/Info.plist" "$APP/Contents/Info.plist"; then
        print -r -- 'Info.plist verschilt of ontbreekt' >> "$rapport"
    fi
    for label in be.globaal.mijnagents.icloud be.globaal.mijnagents.icloud-taken; do
        plist="$launchagents/$label.plist"
        plist_juist "$plist" "$label" || print -r -- "LaunchAgent wijkt af: $plist" >> "$rapport"
    done
    if [[ -s "$rapport" ]]; then
        /usr/bin/sed -n '1,40p' "$rapport"
        return 1
    fi
    print -r -- 'gelijk'
}

if [[ "$modus" == --controleer ]]; then
    controleer
    exit $?
fi

veilig_pythonpad || { print -u2 -- "Vaste root-eigen Python 3.9 ontbreekt of is onveilig: $PYTHON_VAST"; exit 1; }

# Alle fouten die zonder sudo zichtbaar zijn worden vóór de eerste wijziging gemeld.
for label in be.globaal.mijnagents.icloud be.globaal.mijnagents.icloud-taken; do
    plist="$launchagents/$label.plist"
    [[ -f "$plist" && ! -L "$plist" ]] || { print -u2 -- "LaunchAgent ontbreekt: $plist"; exit 1; }
    /usr/bin/plutil -lint "$plist" >/dev/null
    if plist_starter_als_eerste_arg "$plist" && ! plist_juist "$plist" "$label"; then
        print -u2 -- "LaunchAgent heeft al de starter, maar onjuiste overige argumenten: $plist"
        exit 1
    fi
done
if ! /usr/bin/python3 - "$ROOT_DATA" <<'PYPAD'
import os, stat, sys
for path in ('/', '/Library', '/Library/Application Support'):
    st = os.lstat(path)
    if st.st_uid != 0 or st.st_mode & 0o022 or not stat.S_ISDIR(st.st_mode):
        raise SystemExit(1)
root = sys.argv[1]
if os.path.lexists(root):
    st = os.lstat(root)
    if st.st_uid != 0 or st.st_mode & 0o022 or not stat.S_ISDIR(st.st_mode):
        raise SystemExit(1)
    for name in ('icloud_wacht.py', 'VERSIE'):
        path = root + '/' + name
        if os.path.lexists(path):
            st = os.lstat(path)
            if st.st_uid != 0 or st.st_mode & 0o022 or not stat.S_ISREG(st.st_mode):
                raise SystemExit(1)
PYPAD
then
    print -u2 -- "Onveilige root-map: $ROOT_DATA"
    exit 1
fi
if [[ -d "$APP" && "$modus" != --herbouw-starter ]]; then
    if [[ ! -f "$hashpad" || "$(<"$hashpad")" != "$starter_hash" ]] ||
       ! handtekening_veilig "$APP" ||
       ! /usr/bin/cmp -s "$werk/Info.plist" "$APP/Contents/Info.plist"; then
        print -u2 -- 'Starter gewijzigd; controleer de app-rechten en gebruik --herbouw-starter'
        exit 1
    fi
fi

bouw_app=0
if [[ ! -d "$APP" || "$modus" == --herbouw-starter ]]; then
    bouw_app=1
    nieuw="$werk/iCloudWacht.app"
    /bin/mkdir -p "$nieuw/Contents/MacOS" "$nieuw/Contents/Resources"
    /usr/bin/cc -O2 -Wall -Werror "$werk/icloudwacht.c" -o "$nieuw/Contents/MacOS/icloudwacht"
    [[ "$(git -C "$REPO" hash-object "$werk/icloudwacht.c")" == "$starter_blob" ]] ||
        { print -u2 -- 'Starterbron veranderde tijdens de bouw'; exit 1; }
    /usr/bin/install -m 644 "$werk/Info.plist" "$nieuw/Contents/Info.plist"
    print -r -- "$starter_hash" > "$nieuw/Contents/Resources/starter.sha256"
    /usr/bin/codesign -s - --force --options runtime \
        --entitlements "$werk/Entitlements.plist" --identifier be.globaal.icloudwacht "$nieuw"
    handtekening_veilig "$nieuw" || { print -u2 -- 'Geharde app-handtekening ongeldig'; exit 1; }
fi

/usr/bin/sudo -v
/bin/mkdir -p "$DATA" "$DATA/app-bak" "$DATA/plist-bak" "${APP:h}"
/bin/chmod 700 "$DATA"
/usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 755 "$ROOT_DATA"
/usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 700 "$ROOT_DATA/backups"
root_backup="$ROOT_DATA/backups/$stempel"
if [[ ! -f "$ROOT_DATA/icloud_wacht.py" || ! -f "$ROOT_DATA/VERSIE" ]] ||
   ! /usr/bin/cmp -s "$werk/icloud_wacht.py" "$ROOT_DATA/icloud_wacht.py" ||
   ! /usr/bin/cmp -s "$werk/VERSIE" "$ROOT_DATA/VERSIE"; then
    /usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 700 "$root_backup"
    if [[ -f "$ROOT_DATA/icloud_wacht.py" ]]; then
        /usr/bin/sudo /bin/cp -p "$ROOT_DATA/icloud_wacht.py" "$root_backup/icloud_wacht.py"
        root_old_script=1
    fi
    if [[ -f "$ROOT_DATA/VERSIE" ]]; then
        /usr/bin/sudo /bin/cp -p "$ROOT_DATA/VERSIE" "$root_backup/VERSIE"
        root_old_versie=1
    fi
    root_changed=1
    /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 "$werk/icloud_wacht.py" "$ROOT_DATA/icloud_wacht.py.nieuw.$stempel"
    /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 "$werk/VERSIE" "$ROOT_DATA/VERSIE.nieuw.$stempel"
    [[ "$(git -C "$REPO" hash-object "$ROOT_DATA/icloud_wacht.py.nieuw.$stempel")" == "$python_blob" &&
       "$(<"$ROOT_DATA/VERSIE.nieuw.$stempel")" == "$sha" ]] ||
        { print -u2 -- 'Root-kopie wijkt af van de gepubliceerde commit'; exit 1; }
    /usr/bin/sudo /bin/mv -f "$ROOT_DATA/icloud_wacht.py.nieuw.$stempel" "$ROOT_DATA/icloud_wacht.py"
    /usr/bin/sudo /bin/mv -f "$ROOT_DATA/VERSIE.nieuw.$stempel" "$ROOT_DATA/VERSIE"
fi
veilig_rootpad || { print -u2 -- 'Root-script heeft na installatie onveilige rechten'; exit 1; }

if (( bouw_app )); then
    if [[ -d "$APP" ]]; then
        # Eerst een zelfstandige kopie; de verplaatste originele app is de terugzetversie.
        /bin/cp -Rp "$APP" "$DATA/app-bak/iCloudWacht.kopie.$stempel.app"
        app_backup="$DATA/app-bak/iCloudWacht.$stempel.app"
        /bin/mv "$APP" "$app_backup"
        app_backed=1
    fi
    /bin/mv "$nieuw" "$APP"
    app_new=1
fi

for label in be.globaal.mijnagents.icloud be.globaal.mijnagents.icloud-taken; do
    plist="$launchagents/$label.plist"
    plist_juist "$plist" "$label" && continue
    if plist_starter_als_eerste_arg "$plist"; then
        print -u2 -- "LaunchAgent gebruikt al de starter, maar heeft onjuiste overige argumenten: $plist"
        exit 1
    fi
    backup="$DATA/plist-bak/$label.$stempel.plist"
    /bin/cp -p "$plist" "$backup"
    if /bin/launchctl print "gui/$uid/$label" >/dev/null 2>&1; then
        was_loaded[$label]=1
    else
        was_loaded[$label]=0
    fi
    plist_changed+=("$label")
    args=$(/usr/bin/python3 - "$starter" "$label" <<'PYARGS'
import json, sys
print(json.dumps([sys.argv[1]] + (['--taken'] if sys.argv[2].endswith('-taken') else [])))
PYARGS
)
    /usr/bin/plutil -replace ProgramArguments -json "$args" "$plist"
    /bin/launchctl bootout "gui/$uid/$label" >/dev/null 2>&1 || true
    bootstrap_met_herhaling "$plist" || { print -u2 -- "Herstart mislukt: $label"; exit 1; }
done

# Alleen de gewijzigde taakagent meteen starten; de gewone ronde blijft op schema.
if [[ " ${plist_changed[*]} " == *' be.globaal.mijnagents.icloud-taken '* ]]; then
    /bin/launchctl kickstart "gui/$uid/be.globaal.mijnagents.icloud-taken" || true
fi
controleer || { print -u2 -- 'Nacontrole van de Mac-uitrol mislukt'; exit 1; }
print -r -- "iCloudWacht $sha uitgerold. Controleer zo nodig Full Disk Access en Photos Automation voor $APP."
