#!/bin/sh
# Zet de ontwikkel-statistieken op een macOS- of Linux-machine (Claude Code).
# Tegenhanger van installeer-ontwikkeling-hook.ps1; zelfde stappen, zelfde
# uitkomst.
#
# De hooks melden alleen metadata aan het organisatie-dashboard: sessie-id,
# repo, identiteit, machine en of het een start, prompt of einde is. De
# tijdmeter stuurt uitsluitend een optelsom per applicatie per dag. Nooit
# gespreksinhoud, nooit bestandsnamen.
#
# Draaien (in de map waar dit script staat):
#     sh installeer-ontwikkeling-hook.sh -t "<token>" -e "jij@globaal.be" -n "Jouw Naam"
#
# Idempotent: nog eens draaien overschrijft alleen onze eigen hook-regels en
# ons eigen blok in het shellprofiel. Bestaande hooks blijven staan.
#
# Waarom het e-mailadres erbij: een gedeeld GitHub-account is geen probleem,
# want de auteur staat PER COMMIT in git. Maar dan moet elke machine wel een
# eigen git-identiteit hebben, anders belandt het werk op een gedeeld adres en
# valt het op niemand.
set -eu

TOKEN=""; EMAIL=""; NAAM=""
while [ $# -gt 0 ]; do
  case "$1" in
    -t|--token) TOKEN="${2:-}"; shift 2 ;;
    -e|--email) EMAIL="${2:-}"; shift 2 ;;
    -n|--naam)  NAAM="${2:-}";  shift 2 ;;
    *) echo "onbekende optie: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$TOKEN" ] || [ -z "$EMAIL" ]; then
  echo "Gebruik: sh installeer-ontwikkeling-hook.sh -t <token> -e <e-mail> [-n \"Naam\"]" >&2
  exit 1
fi
case "$EMAIL" in
  *?@?*.?*) ;;
  *) echo "FOUT: '$EMAIL' ziet er niet uit als een e-mailadres." >&2; exit 1 ;;
esac

# 1. Python moet aanroepbaar zijn; zonder python falen de hooks stil.
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "FOUT: python3 staat niet op het PATH. Installeer Python en probeer opnieuw." >&2
  exit 1
fi
echo "Python gevonden: $PY"

HIER=$(cd "$(dirname "$0")" && pwd)
HOOKDIR="$HOME/.claude/hooks"
mkdir -p "$HOOKDIR"

# 2. De twee scripts uit de repo kopieren. Een bron, geen tweede versie: een
#    inline kopie liep hier eerder achter en stuurde de machinenaam niet mee.
for bestand in ontwikkeling-event.py ontwikkeling-tijd.py; do
  if [ ! -f "$HIER/$bestand" ]; then
    echo "FOUT: $bestand staat niet naast dit script." >&2
    exit 1
  fi
  cp "$HIER/$bestand" "$HOOKDIR/$bestand"
  echo "Geschreven: $HOOKDIR/$bestand"
done

# 3. Token en identiteit in het shellprofiel, in een blok dat we kunnen
#    terugvinden. Ook meteen in deze shell, zodat de proef hieronder werkt.
PROFIEL="$HOME/.zprofile"
[ -n "${ZSH_VERSION:-}" ] || case "${SHELL:-}" in
  */bash) PROFIEL="$HOME/.bash_profile" ;;
esac
touch "$PROFIEL"
BEGIN="# >>> ontwikkel-statistieken >>>"
EIND="# <<< ontwikkel-statistieken <<<"
TMP=$(mktemp)
awk -v b="$BEGIN" -v e="$EIND" '
  $0 == b { skip = 1 } !skip { print } $0 == e { skip = 0 }' "$PROFIEL" > "$TMP"
{
  echo "$BEGIN"
  echo "export ONTWIKKELING_TOKEN='$TOKEN'"
  echo "export ONTWIKKELING_GEBRUIKER='$EMAIL'"
  echo "$EIND"
} >> "$TMP"
mv "$TMP" "$PROFIEL"
chmod 600 "$PROFIEL"
export ONTWIKKELING_TOKEN="$TOKEN"
export ONTWIKKELING_GEBRUIKER="$EMAIL"
echo "Token en identiteit gezet in $PROFIEL (leesbaar voor jou alleen)."

# De globale git-identiteit is de hoofdsleutel: die reist mee met elke commit,
# ook als er via een gedeeld GitHub-account gepusht wordt.
git config --global user.email "$EMAIL"
[ -z "$NAAM" ] || git config --global user.name "$NAAM"
GITMAIL=$(git config --global user.email)
echo "Git-identiteit: $GITMAIL"

# 4. De hooks koppelen in settings.json, zonder andere hooks weg te gooien.
#    Het patchen gebeurt in Python: jq staat op macOS niet standaard.
SETTINGS="$HOME/.claude/settings.json"
[ ! -f "$SETTINGS" ] || cp "$SETTINGS" "$SETTINGS.bak-$(date +%Y%m%d-%H%M%S)"
PY="$PY" HOOKDIR="$HOOKDIR" SETTINGS="$SETTINGS" "$PY" - <<'PYEOF'
import json
import os

py = os.environ["PY"]
hookdir = os.environ["HOOKDIR"]
pad = os.environ["SETTINGS"]
event = '%s "%s/ontwikkeling-event.py"' % (py, hookdir)
tijd = '%s "%s/ontwikkeling-tijd.py"' % (py, hookdir)

try:
    with open(pad, encoding="utf-8") as f:
        s = json.load(f)
except Exception:
    s = {}
if not isinstance(s, dict):
    s = {}
hooks = s.setdefault("hooks", {})

slots = {"SessionStart": "start", "UserPromptSubmit": "prompt",
         "Stop": "einde", "SessionEnd": "einde"}
for slot, arg in slots.items():
    stappen = [{"type": "command", "command": event + " " + arg, "timeout": 10}]
    # Bij het einde van een sessie ook de tijdmeter: die leest de transcripts en
    # stuurt alleen een optelsom per applicatie per dag.
    if slot == "SessionEnd":
        stappen.append({"type": "command", "command": tijd, "timeout": 120})
    # Bestaande regels van ONZE hooks eruit, andere hooks laten staan.
    bestaand = []
    for regel in hooks.get(slot) or []:
        eigen = any("ontwikkeling-event" in (h.get("command") or "")
                    or "ontwikkeling-tijd" in (h.get("command") or "")
                    for h in (regel.get("hooks") or []))
        if not eigen:
            bestaand.append(regel)
    hooks[slot] = bestaand + [{"matcher": "", "hooks": stappen}]

os.makedirs(os.path.dirname(pad), exist_ok=True)
with open(pad, "w", encoding="utf-8") as f:
    json.dump(s, f, indent=2, ensure_ascii=False)
print("Hooks gekoppeld in: " + pad)
PYEOF

# 5. Proefmelding, zodat we meteen weten of het werkt.
echo '{"session_id":"installatietest"}' | "$PY" "$HOOKDIR/ontwikkeling-event.py" start || true

MACHINE=$("$PY" -c 'import platform; print(platform.node())')
echo ""
echo "Klaar. Meld deze twee regels door aan AI en ICT:"
echo "  identiteit: $GITMAIL"
echo "  machine:    $MACHINE"
echo ""
echo "Die twee worden gekoppeld aan jouw persoon (ontwikkeling.gebruiker_koppeling"
echo "en machine_koppeling); tot dan staat je werk op de tab Ontwikkeling onder"
echo "'Nog te koppelen'."
echo ""
echo "Open een NIEUWE terminal en herstart Claude Code; de instellingen en de"
echo "omgevingsvariabelen worden bij het opstarten gelezen."
