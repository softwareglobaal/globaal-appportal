#!/bin/zsh
# Op Mehdi's Mac: haal de laatste groen geteste main-versie op, werk de iCloudWacht-app
# en twee LaunchAgents bij en controleer de uitkomst. Bestaande versies blijven als
# backup beschikbaar. Gebruik --herbouw-starter als de starterbron verandert
# of de geïnstalleerde app de controle niet doorstaat.
# sudo installeert het Python-script, VERSIE en de app in
# /Library/Application Support/iCloudWacht als root:wheel. Geef Full Disk Access
# pas aan die app, nadat --controleer 'gelijk' meldt.
set -euo pipefail

REPO=${REPO:-$HOME/dev/globaal-appportal}
DATA=${DATA:-$HOME/Library/Application Support/iCloudWacht}
GH=${GH:-/opt/homebrew/bin/gh}
ROOT_DATA='/Library/Application Support/iCloudWacht'
APP="$ROOT_DATA/iCloudWacht.app"
oude_app="$HOME/Applications/iCloudWacht.app"
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
[[ "$APP" == *.app && ! -L "$APP" ]] || { print -u2 -- "APP moet een echte .app-map zijn"; exit 1; }

werk=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/icloud-uitrol.XXXXXXXX")
app_backup=''
app_backed=0
app_new=0
app_stage=''
oude_app_backup=''
oude_app_backed=0
root_changed=0
root_old_script=0
root_old_versie=0
manifest_changed=0
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
    if [[ -n "$app_stage" && -d "$app_stage" ]]; then
        /usr/bin/sudo /bin/mv "$app_stage" "$root_backup/iCloudWacht.onvolledig.app" ||
            print -u2 -- 'Onvolledige app kon niet apart worden gezet'
    fi
    if (( app_new )) && [[ -d "$APP" ]]; then
        /usr/bin/sudo /bin/mv "$APP" "$root_backup/iCloudWacht.mislukt.app" ||
            print -u2 -- 'Nieuwe app kon niet apart worden gezet'
    fi
    if (( app_backed )) && [[ -d "$app_backup" ]]; then
        /usr/bin/sudo /bin/mv "$app_backup" "$APP" ||
            print -u2 -- 'Vorige app kon niet worden teruggezet'
    fi
    if (( oude_app_backed )) && [[ -d "$oude_app_backup" ]]; then
        /bin/mv "$oude_app_backup" "$oude_app" ||
            print -u2 -- 'Vorige app in Applications kon niet worden teruggezet'
    fi
    if (( manifest_changed )); then
        if [[ -f "$root_backup/STARTER_HASHES.oud" ]]; then
            /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 \
                "$root_backup/STARTER_HASHES.oud" "$ROOT_DATA/STARTER_HASHES" ||
                print -u2 -- 'Vorige starterhashes konden niet worden teruggezet'
        else
            /usr/bin/sudo /bin/rm -f "$ROOT_DATA/STARTER_HASHES" || true
        fi
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
    trap '' HUP INT TERM
    if (( code != 0 && (root_changed || app_backed || app_new || oude_app_backed || manifest_changed || ${#plist_changed[@]} > 0) )) ||
       [[ -n "$app_stage" && -d "$app_stage" ]]; then
        terugzetten
    fi
    /bin/rm -rf -- "$werk"
    exit "$code"
}
trap opruimen EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$modus" == --controleer ]]; then
    [[ -f "$ROOT_DATA/VERSIE" && ! -L "$ROOT_DATA/VERSIE" ]] ||
        { print -u2 -- 'Geïnstalleerde versie ontbreekt'; exit 1; }
    sha=$(<"$ROOT_DATA/VERSIE")
    [[ "$sha" =~ '^[[:xdigit:]]{40}$' ]] ||
        { print -u2 -- 'Ongeldige geïnstalleerde versie'; exit 1; }
    git -C "$REPO" cat-file -e "$sha^{commit}" ||
        { print -u2 -- 'Geïnstalleerde commit ontbreekt lokaal'; exit 1; }
else
    [[ -x "$GH" ]] || { print -u2 -- "gh ontbreekt: $GH"; exit 1; }
    git -C "$REPO" fetch -q origin main
    # De eerste ouder is de gepubliceerde main-lijn, inclusief de merge-commit.
    sha=$(git -C "$REPO" log -1 --first-parent --format=%H origin/main -- "$PY" mijnagents-runner/mac/starter)
    [[ -n "$sha" ]] || { print -u2 -- 'Geen gepubliceerde iCloud-versie'; exit 1; }
    geslaagd=$(cd "$REPO" && "$GH" run list -R softwareglobaal/globaal-appportal \
        --workflow verslag-grendels.yml --commit "$sha" --branch main --event push \
        --json status,conclusion --limit 1 \
        --jq '.[0] | select(.status == "completed" and .conclusion == "success") | .conclusion')
    [[ "$geslaagd" == success ]] || { print -u2 -- "Nieuwste push-CI op main ontbreekt of is niet groen voor $sha"; exit 1; }
fi

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
"$PYTHON_VAST" -I -B - "$werk/icloud_wacht.py" <<'PYCONTROLE'
import ast
import pathlib
import sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
PYCONTROLE
/usr/bin/plutil -lint "$werk/Info.plist" >/dev/null
/usr/bin/plutil -lint "$werk/Entitlements.plist" >/dev/null
print -r -- "$sha" > "$werk/VERSIE"
starter_hash=$(git -C "$REPO" show "$sha:$C" | /usr/bin/shasum -a 256 | /usr/bin/awk '{print $1}')
starter="$APP/Contents/MacOS/icloudwacht"
hashpad="$APP/Contents/Resources/starter.sha256"
manifestpad="$ROOT_DATA/STARTER_HASHES"
verse_starter="$werk/iCloudWacht.app/Contents/MacOS/icloudwacht"
launchagents="$HOME/Library/LaunchAgents"
uid=$(/usr/bin/id -u)

veilig_rootpad() {
    "$PYTHON_VAST" -I -B - "$ROOT_DATA" <<'PYPAD'
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

veilig_apppad() {
    "$PYTHON_VAST" -I -B - "${1:-$APP}" <<'PYPAD'
import os
import stat
import sys

app = sys.argv[1]
try:
    root = os.lstat(app)
except OSError:
    raise SystemExit(1)
if not stat.S_ISDIR(root.st_mode):
    raise SystemExit(1)
for directory, dirs, files in os.walk(app, followlinks=False):
    for path in [directory] + [os.path.join(directory, name) for name in dirs + files]:
        st = os.lstat(path)
        if st.st_uid != 0 or st.st_gid != 0 or st.st_mode & 0o022 or not (
                stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):
            raise SystemExit(1)
PYPAD
}

app_bron_en_binary_juist() {
    [[ -f "$hashpad" && ! -L "$hashpad" && "$(<"$hashpad")" == "$starter_hash" ]] || return 1
    "$PYTHON_VAST" -I -B - "$manifestpad" "$starter" "$starter_hash" <<'PYHASH' || return 1
import hashlib
import json
import os
import stat
import sys

manifest, binary, bron = sys.argv[1:]
try:
    st = os.lstat(manifest)
    if st.st_uid != 0 or st.st_gid != 0 or st.st_mode & 0o022 or not stat.S_ISREG(st.st_mode):
        raise ValueError('onveilig manifest')
    with open(manifest, encoding='utf-8') as f:
        hashes = json.load(f)
    with open(binary, 'rb') as f:
        werkelijk = hashlib.sha256(f.read()).hexdigest()
except (OSError, ValueError, TypeError):
    raise SystemExit(1)
raise SystemExit(0 if hashes == {'bron': bron, 'binary': werkelijk} else 1)
PYHASH
    if [[ "$modus" == --controleer ]]; then
        [[ -f "$verse_starter" ]] && /usr/bin/cmp -s "$verse_starter" "$starter"
    fi
}

veilig_pythonpad() {
    "$PYTHON_VAST" -I -B - "$PYTHON_VAST" <<'PYPAD'
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
    "$PYTHON_VAST" -I -B - "$1" <<'PYCODE'
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
segmenten = subprocess.run(['/usr/bin/otool', '-l', app + '/Contents/MacOS/icloudwacht'], capture_output=True)
beperkt = re.search(rb'segname __RESTRICT\b', segmenten.stdout) is not None
goed = (verify.returncode == display.returncode == entitlements.returncode == segmenten.returncode == 0
        and beperkt
        and flags is not None and b'runtime' in flags.group(1).split(b',')
        and identiteit is not None and identiteit.group(1) == b'be.globaal.icloudwacht'
        and rechten == {'com.apple.security.automation.apple-events': True})
raise SystemExit(0 if goed else 1)
PYCODE
}

plist_juist() {
    "$PYTHON_VAST" -I -B - "$1" "$starter" "$2" <<'PYPLIST'
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
    "$PYTHON_VAST" -I -B - "$1" "$starter" <<'PYPLIST'
import plistlib
import sys
with open(sys.argv[1], 'rb') as f:
    args = plistlib.load(f).get('ProgramArguments')
raise SystemExit(0 if isinstance(args, list) and args and args[0] == sys.argv[2] else 1)
PYPLIST
}

bouw_verse_app() {
    local nieuw="$werk/iCloudWacht.app"
    /bin/mkdir -p "$nieuw/Contents/MacOS" "$nieuw/Contents/Resources"
    # __RESTRICT: dyld negeert DYLD_*-variabelen, ook waar de geharde runtime dat niet afdwingt.
    /usr/bin/cc -O2 -Wall -Werror -Wl,-sectcreate,__RESTRICT,__restrict,/dev/null \
        "$werk/icloudwacht.c" -o "$verse_starter"
    [[ "$(git -C "$REPO" hash-object "$werk/icloudwacht.c")" == "$starter_blob" ]] ||
        { print -u2 -- 'Starterbron veranderde tijdens de bouw'; return 1; }
    /usr/bin/install -m 644 "$werk/Info.plist" "$nieuw/Contents/Info.plist"
    print -r -- "$starter_hash" > "$nieuw/Contents/Resources/starter.sha256"
    /usr/bin/codesign -s - --force --options runtime \
        --entitlements "$werk/Entitlements.plist" --identifier be.globaal.icloudwacht "$nieuw"
    handtekening_veilig "$nieuw" || { print -u2 -- 'Geharde app-handtekening ongeldig'; return 1; }
}

if [[ "$modus" == --controleer ]]; then
    bouw_verse_app
fi

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
    if ! veilig_apppad; then
        print -r -- 'App ontbreekt of is niet geheel root:wheel zonder schrijfrechten voor anderen' >> "$rapport"
    elif [[ ! -x "$starter" ]] || ! handtekening_veilig "$APP"; then
        print -r -- 'Starter ontbreekt of handtekening mist geharde runtime of veilige rechten' >> "$rapport"
    fi
    if ! app_bron_en_binary_juist; then
        print -r -- 'Starterbron of binary verschilt van de vers gebouwde starter' >> "$rapport"
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
if ! "$PYTHON_VAST" -I -B - "$ROOT_DATA" <<'PYPAD'
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
if [[ -e "$APP" || -L "$APP" ]] && [[ ! -d "$APP" || -L "$APP" ]]; then
    print -u2 -- "Onveilig app-pad: $APP"
    exit 1
fi
if [[ -d "$APP" && "$modus" != --herbouw-starter ]]; then
    if ! veilig_apppad || ! app_bron_en_binary_juist ||
       ! handtekening_veilig "$APP" ||
       ! /usr/bin/cmp -s "$werk/Info.plist" "$APP/Contents/Info.plist"; then
        print -u2 -- 'Starter gewijzigd of ongeldig; controleer de app-rechten en gebruik --herbouw-starter'
        exit 1
    fi
fi

bouw_app=0
if [[ ! -d "$APP" || "$modus" == --herbouw-starter ]]; then
    bouw_app=1
fi

/usr/bin/sudo -v
/bin/mkdir -p "$DATA" "$DATA/app-bak" "$DATA/plist-bak"
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
    # Bron en bouw blijven onder een private root-map. Een ander proces van de
    # Mac-gebruiker kan zo noch de compilerinvoer noch de referentiebinary wisselen.
    /usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 700 "$root_backup"
    root_bouw="$root_backup/bouw"
    app_stage="$root_bouw/iCloudWacht.app"
    /usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 700 "$root_bouw"
    /usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 755 \
        "$app_stage" "$app_stage/Contents" "$app_stage/Contents/MacOS" "$app_stage/Contents/Resources"
    /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 "$werk/icloudwacht.c" "$root_bouw/icloudwacht.c"
    /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 "$werk/Info.plist" "$app_stage/Contents/Info.plist"
    /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 "$werk/Entitlements.plist" "$root_bouw/Entitlements.plist"
    [[ "$(/usr/bin/sudo /usr/bin/git hash-object "$root_bouw/icloudwacht.c")" == "$starter_blob" &&
       "$(/usr/bin/sudo /usr/bin/git hash-object "$app_stage/Contents/Info.plist")" == "$info_blob" &&
       "$(/usr/bin/sudo /usr/bin/git hash-object "$root_bouw/Entitlements.plist")" == "$entitlements_blob" ]] ||
        { print -u2 -- 'Private root-bron wijkt af van de gepubliceerde commit'; exit 1; }
    /usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 \
        /usr/bin/cc -O2 -Wall -Werror -Wl,-sectcreate,__RESTRICT,__restrict,/dev/null \
        "$root_bouw/icloudwacht.c" -o "$app_stage/Contents/MacOS/icloudwacht"
    /usr/bin/sudo "$PYTHON_VAST" -I -B - "$root_bouw/icloudwacht.c" \
        "$app_stage/Contents/Resources/starter.sha256" <<'PYBRON'
import hashlib
import pathlib
import sys
bron = hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()
pathlib.Path(sys.argv[2]).write_text(bron + '\n', encoding='ascii')
PYBRON
    /usr/bin/sudo /usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 \
        /usr/bin/codesign -s - --force --options runtime \
        --entitlements "$root_bouw/Entitlements.plist" --identifier be.globaal.icloudwacht "$app_stage"
    /usr/bin/sudo /usr/sbin/chown -R root:wheel "$app_stage"
    /usr/bin/sudo /bin/chmod -RN "$app_stage"
    /usr/bin/sudo /bin/chmod -R go-w "$app_stage"
    /usr/bin/sudo /usr/bin/codesign --verify --strict "$app_stage" ||
        { print -u2 -- 'Private root-app heeft geen geldige handtekening'; exit 1; }
    /usr/bin/sudo "$PYTHON_VAST" -I -B - "$root_bouw/icloudwacht.c" \
        "$app_stage/Contents/MacOS/icloudwacht" "$root_bouw/STARTER_HASHES" <<'PYHASH'
import hashlib
import json
import pathlib
import sys
bron, binary, doel = map(pathlib.Path, sys.argv[1:])
doel.write_text(json.dumps({'bron': hashlib.sha256(bron.read_bytes()).hexdigest(),
                            'binary': hashlib.sha256(binary.read_bytes()).hexdigest()},
                           sort_keys=True) + '\n', encoding='ascii')
PYHASH
    if [[ -d "$APP" ]]; then
        # Eerst een zelfstandige kopie; de verplaatste originele app is de terugzetversie.
        /usr/bin/sudo /usr/bin/ditto "$APP" "$root_backup/iCloudWacht.kopie.app"
        app_backup="$root_backup/iCloudWacht.oud.app"
        app_backed=1
        /usr/bin/sudo /bin/mv "$APP" "$app_backup"
    fi
    app_new=1
    /usr/bin/sudo /bin/mv "$app_stage" "$APP"
    app_stage=''
    if [[ -f "$manifestpad" ]]; then
        /usr/bin/sudo /bin/cp -p "$manifestpad" "$root_backup/STARTER_HASHES.oud"
    fi
    manifest_changed=1
    /usr/bin/sudo /usr/bin/install -o root -g wheel -m 644 "$root_bouw/STARTER_HASHES" "$manifestpad"
fi
veilig_apppad && app_bron_en_binary_juist && handtekening_veilig "$APP" ||
    { print -u2 -- 'Geïnstalleerde root-app wijkt af of heeft onveilige rechten'; exit 1; }

# De vorige app blijft als kopie bewaard; de oude FDA-route wordt uit Applications gehaald.
if [[ -e "$oude_app" || -L "$oude_app" ]]; then
    [[ -d "$oude_app" && ! -L "$oude_app" ]] ||
        { print -u2 -- "Onveilig oud app-pad: $oude_app"; exit 1; }
    /bin/cp -Rp "$oude_app" "$DATA/app-bak/iCloudWacht.kopie.$stempel.app"
    oude_app_backup="$DATA/app-bak/iCloudWacht.oud.$stempel.app"
    oude_app_backed=1
    /bin/mv "$oude_app" "$oude_app_backup"
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
    args=$("$PYTHON_VAST" -I -B - "$starter" "$label" <<'PYARGS'
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
