#!/bin/sh
# Onderhoud van de VM in een keer, stand 28-10-2026. Draaien vanuit ~/appportal:
#
#   git pull && sh scripts/vm-onderhoud.sh
#
# Vier stappen, elk los: valt er een uit, dan lopen de andere gewoon door. Aan het
# eind staat per stap wat er gebeurde. Alles komt ook in ~/vm-onderhoud.log.
#
# 1. Schijf: alleen de build cache van Docker weg (docker builder prune). Dat is
#    cache, die bouwt Docker zelf weer op. NOOIT volumes: zes renovision-volumes
#    staan als ongebruikt maar bevatten het werk van zes collega's (TODO.md,
#    "Schijfruimte op de VM").
# 2. Authentik: scripts/add-locatie-app.py staat alleen op de VM. Het script
#    commit alleen dat bestand en pusht het naar een eigen branch
#    (vm-locatie-script), nooit naar main en zonder iets anders aan te raken.
# 3. Authentik: de groepen inventariseren (alleen lezen, wijzigt niets). De
#    uitkomst komt in ~/inventaris-groepen.txt, niet in git: de repo is publiek.
# 4. Uptime-Kuma: een Telegram-melding op elke monitor (scripts/kuma-telegram.py).
#    Eerst een kopie van de databank, Kuma staat hooguit een halve minuut stil.
set -u
cd "$HOME/appportal" || exit 1
if [ -z "${VM_ONDERHOUD_LOG:-}" ]; then
    VM_ONDERHOUD_LOG=1 sh "$0" 2>&1 | tee -a "$HOME/vm-onderhoud.log"
    exit
fi
echo "== vm-onderhoud $(date '+%Y-%m-%d %H:%M') =="
UITSLAG=""

# 1. Build cache
echo; echo "-- 1. schijf"
df -h / | tail -1
if docker builder prune -f > /tmp/vm-onderhoud-prune.txt 2>&1; then
    tail -1 /tmp/vm-onderhoud-prune.txt
    UITSLAG="$UITSLAG\n1. schijf: build cache opgeruimd, nu $(df -h / | awk 'NR==2{print $5" gebruikt, "$4" vrij"}')"
else
    cat /tmp/vm-onderhoud-prune.txt
    UITSLAG="$UITSLAG\n1. schijf: MISLUKT, zie hierboven"
fi
df -h / | tail -1

# 2. add-locatie-app.py naar git
echo; echo "-- 2. add-locatie-app.py"
BESTAND=scripts/add-locatie-app.py
if [ ! -f "$BESTAND" ]; then
    UITSLAG="$UITSLAG\n2. locatiescript: niet gevonden op de VM, niets gedaan"
elif git ls-files --error-unmatch "$BESTAND" > /dev/null 2>&1 && git diff --quiet -- "$BESTAND"; then
    UITSLAG="$UITSLAG\n2. locatiescript: stond al in git, niets gedaan"
else
    TAK=$(git rev-parse --abbrev-ref HEAD)
    TMPIDX=$(mktemp)
    # Eigen index: de werkkopie en wat er al klaarstaat op de VM blijven ongemoeid.
    if GIT_INDEX_FILE="$TMPIDX" git read-tree HEAD \
        && GIT_INDEX_FILE="$TMPIDX" git add "$BESTAND" \
        && BOOM=$(GIT_INDEX_FILE="$TMPIDX" git write-tree) \
        && COMMIT=$(git commit-tree "$BOOM" -p HEAD -m "chore: add-locatie-app.py van de VM in git (stond alleen op de VM sinds 09-09-2026)") \
        && git push origin "$COMMIT:refs/heads/vm-locatie-script"; then
        UITSLAG="$UITSLAG\n2. locatiescript: gepusht naar branch vm-locatie-script (VM-tak $TAK ongewijzigd)"
    else
        UITSLAG="$UITSLAG\n2. locatiescript: push MISLUKT, zie hierboven"
    fi
    rm -f "$TMPIDX"
fi

# 3. Groepen inventariseren
echo; echo "-- 3. groepen"
if sh scripts/ak-exec.sh scripts/inventariseer-groepen.py > "$HOME/inventaris-groepen.txt" 2>&1; then
    UITSLAG="$UITSLAG\n3. groepen: $(grep -c '^- ' "$HOME/inventaris-groepen.txt") regels in ~/inventaris-groepen.txt"
else
    tail -5 "$HOME/inventaris-groepen.txt"
    UITSLAG="$UITSLAG\n3. groepen: MISLUKT, zie hierboven"
fi

# 4. Uptime-Kuma meldingen
echo; echo "-- 4. uptime-kuma"
KUMA=$(docker ps -a --format '{{.Names}}' | grep -i 'uptime-kuma' | head -1)
WERK=$(mktemp -d)
if [ -z "$KUMA" ]; then
    UITSLAG="$UITSLAG\n4. kuma: geen uptime-kuma-container gevonden"
elif ! docker cp "$KUMA:/app/data/kuma.db" "$WERK/kuma.db.voor" > /dev/null 2>&1; then
    UITSLAG="$UITSLAG\n4. kuma: geen /app/data/kuma.db (andere databank?), niets gedaan"
else
    BACKUP="$HOME/kuma.db.backup-$(date +%Y%m%d-%H%M%S)"
    docker stop "$KUMA" > /dev/null
    docker cp "$KUMA:/app/data/kuma.db" "$WERK/kuma.db"
    if docker cp "$KUMA:/app/data/kuma.db-wal" "$WERK/kuma.db-wal" > /dev/null 2>&1 && [ -s "$WERK/kuma.db-wal" ]; then
        docker start "$KUMA" > /dev/null
        UITSLAG="$UITSLAG\n4. kuma: databank niet netjes afgesloten (wal), niets gedaan, Kuma draait weer"
    else
        cp "$WERK/kuma.db" "$BACKUP"
        if python3 scripts/kuma-telegram.py "$WERK/kuma.db"; then
            docker cp "$WERK/kuma.db" "$KUMA:/app/data/kuma.db"
            docker start "$KUMA" > /dev/null
            UITSLAG="$UITSLAG\n4. kuma: Telegram-melding op alle monitors, kopie in $BACKUP"
        else
            docker start "$KUMA" > /dev/null
            UITSLAG="$UITSLAG\n4. kuma: niets gewijzigd, zie hierboven; Kuma draait weer"
        fi
    fi
fi
rm -rf "$WERK"

echo; echo "== uitslag =="
printf '%b\n' "$UITSLAG"
