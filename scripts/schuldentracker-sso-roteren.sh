#!/usr/bin/env bash
# Roteert SSO_SHARED_SECRET, het geheim tussen de portal-nginx en de
# schuldentracker (kop X-SSO-Secret), en zet het op zijn juiste plek: alleen in
# de twee .env-bestanden op de VM, nooit in git (22-10-2026). Herbruikbaar voor
# elke volgende rotatie.
#
# Wat het doet, in deze volgorde:
#   1. weigert in de drukke uren (06:55-07:45 en 12:55-13:45 UTC) en kijkt alle
#      voorwaarden na; tot hier is niets gewijzigd;
#   2. zet 41-schuldentracker.conf.template op de versie van origin/main als die
#      op de VM nog een letterlijke waarde heeft (alleen dat bestand, geen pull);
#   3. schrijft een nieuw willekeurig geheim in ~/appportal/.env en
#      ~/Finance/Schuldentracker/.env (backups ernaast, rechten 600);
#   4. proefstart van nginx met de nieuwe config (nginx -t in een wegwerpcontainer);
#   5. herstart de schuldentracker en maakt de nginx-container opnieuw aan;
#   6. kijkt na: oud geheim geweigerd, nieuw geheim aanvaard, portal bereikbaar.
# Faalt iets vanaf stap 2, dan zet het script alles terug zoals het was.
# Het geheim verschijnt nergens: niet op het scherm, niet in een
# commandoregel (ps), alleen in de twee .env-bestanden.
#
# Draaien vanaf de Mac, meteen na het mergen van de PR:
#   ssh globaal 'cd ~/appportal && git fetch -q origin main && bash <(git show origin/main:scripts/schuldentracker-sso-roteren.sh)'
set -euo pipefail
umask 077

PORTAL_DIR="${PORTAL_DIR:-$HOME/appportal}"
TRACKER_DIR="${TRACKER_DIR:-$HOME/Finance/Schuldentracker}"
PORTAL_ENV="$PORTAL_DIR/.env"
TRACKER_ENV="$TRACKER_DIR/.env"
TEMPLATE_REL="nginx/templates/41-schuldentracker.conf.template"
TEMPLATE="$PORTAL_DIR/$TEMPLATE_REL"
SLEUTEL="SSO_SHARED_SECRET"
TRACKER_URL="http://172.17.0.1:5050/"
STAMP="$(date +%Y%m%d-%H%M%S)"
BAK=".bak-$STAMP-sso-rotatie"

fail() { echo "GESTOPT: $*" >&2; echo "Er is niets gewijzigd." >&2; exit 1; }
stap() { echo "[$1] $2"; }
lees_geheim() { grep "^$SLEUTEL=" "$1" | tail -1 | cut -d= -f2- || true; }
heeft_hex() { grep -qE '[0-9A-Fa-f]{32,}'; }
heeft_verwijzing() { grep -qF "\${$SLEUTEL}"; }
http_code() { curl -s -o /dev/null --max-time 10 -w '%{http_code}' "$@" || true; }

# --- 1) Voorwaarden, nog niets gewijzigd -------------------------------------
nu=$((10#$(date -u +%H%M)))
if { [ "$nu" -ge 655 ] && [ "$nu" -lt 745 ]; } || { [ "$nu" -ge 1255 ] && [ "$nu" -lt 1345 ]; }; then
    if [ "$nu" -lt 1000 ]; then na="07:45"; else na="13:45"; fi
    fail "drukke ronde van de agents (06:55-07:45 en 12:55-13:45 UTC). Probeer na $na UTC opnieuw."
fi
command -v openssl >/dev/null || fail "openssl ontbreekt"
[ -f "$PORTAL_ENV" ] || fail "$PORTAL_ENV niet gevonden"
[ -f "$TRACKER_ENV" ] || fail "$TRACKER_ENV niet gevonden"
[ -f "$TEMPLATE" ] || fail "$TEMPLATE niet gevonden"
sudo -n -l /usr/bin/systemctl restart schuldentracker.service >/dev/null 2>&1 \
    || fail "sudo mag schuldentracker.service niet herstarten zonder wachtwoord"
cd "$PORTAL_DIR"
NGINX_ID="$(docker compose ps -q nginx 2>/dev/null || true)"
[ -n "$NGINX_ID" ] || fail "nginx-container draait niet"

git fetch -q origin main || fail "git fetch origin main mislukt"
tpl_main="$(git show "origin/main:$TEMPLATE_REL" 2>/dev/null)" || fail "template niet gevonden op origin/main"
if printf '%s\n' "$tpl_main" | heeft_hex || ! printf '%s\n' "$tpl_main" | heeft_verwijzing; then
    fail "origin/main heeft de template-fix nog niet: eerst de PR mergen"
fi

TEMPLATE_GEWIJZIGD=0
if heeft_hex < "$TEMPLATE" || ! heeft_verwijzing < "$TEMPLATE"; then
    git diff --quiet HEAD -- "$TEMPLATE_REL" \
        || fail "$TEMPLATE_REL heeft lokale wijzigingen op de VM; eerst bekijken"
    TEMPLATE_GEWIJZIGD=1
fi

OUD="$(lees_geheim "$TRACKER_ENV")"
[ -n "$OUD" ] || fail "geen $SLEUTEL in $TRACKER_ENV"
NIEUW="$(openssl rand -hex 32)"
[ "${#NIEUW}" -eq 64 ] && [ "$NIEUW" != "$OUD" ] || fail "nieuw geheim kon niet gemaakt worden"
stap 1/6 "voorwaarden in orde"

# Schrijft $WAARDE onder $SLEUTEL in een .env. De waarde gaat via de omgeving
# van awk, niet als argument: zo blijft ze uit ps.
zet_geheim() {
    local bestand="$1" tmp voor na
    [ -n "$WAARDE" ] || return 1
    tmp="$(mktemp "$bestand.tmp.XXXXXX")" || return 1
    WAARDE="$WAARDE" SLEUTEL="$SLEUTEL" awk '
        BEGIN { k = ENVIRON["SLEUTEL"]; w = ENVIRON["WAARDE"] }
        index($0, k "=") == 1 { if (!gezet) print k "=" w; gezet = 1; next }
        { print }
        END { if (!gezet) print k "=" w }' "$bestand" > "$tmp" || { rm -f "$tmp"; return 1; }
    # Nooit een half bestand terugschrijven: alle andere regels moeten er nog zijn.
    voor="$(grep -vc "^$SLEUTEL=" "$bestand" || true)"
    na="$(grep -vc "^$SLEUTEL=" "$tmp" || true)"
    [ "$voor" = "$na" ] || { rm -f "$tmp"; return 1; }
    cat "$tmp" > "$bestand" || { rm -f "$tmp"; return 1; }
    rm -f "$tmp"
    chmod 600 "$bestand"
}

# Terug naar de oude toestand. Beide .env-bestanden krijgen het oude geheim van
# de tracker, ook ~/appportal/.env: dan past het paar bij elke versie van de
# template (oude met de letterlijke waarde, of nieuwe met de verwijzing).
terugdraaien() {
    echo "TERUGDRAAIEN: de oude toestand wordt hersteld." >&2
    [ -f "$PORTAL_ENV$BAK" ] && cp -p "$PORTAL_ENV$BAK" "$PORTAL_ENV"
    [ -f "$TRACKER_ENV$BAK" ] && cp -p "$TRACKER_ENV$BAK" "$TRACKER_ENV"
    WAARDE="$OUD"; zet_geheim "$PORTAL_ENV"; zet_geheim "$TRACKER_ENV"
    if [ "$TEMPLATE_GEWIJZIGD" = 1 ]; then
        git checkout HEAD -- "$TEMPLATE_REL"
    fi
    if [ "${1:-}" = herstart ]; then
        sudo -n /usr/bin/systemctl restart schuldentracker.service || true
        docker compose up -d --no-deps --force-recreate nginx >/dev/null 2>&1 || true
    fi
    unset NIEUW OUD WAARDE
    echo "Teruggedraaid. Geef deze uitvoer aan Claude." >&2
    exit 1
}

# --- 2) Template op de versie van origin/main --------------------------------
if [ "$TEMPLATE_GEWIJZIGD" = 1 ]; then
    git checkout origin/main -- "$TEMPLATE_REL" || terugdraaien
    stap 2/6 "template leest het geheim nu uit .env (versie origin/main)"
else
    stap 2/6 "template las het geheim al uit .env"
fi

# --- 3) Nieuw geheim in beide .env-bestanden ---------------------------------
cp -p "$PORTAL_ENV" "$PORTAL_ENV$BAK" && cp -p "$TRACKER_ENV" "$TRACKER_ENV$BAK" || terugdraaien
chmod 600 "$PORTAL_ENV$BAK" "$TRACKER_ENV$BAK"
WAARDE="$NIEUW"
zet_geheim "$PORTAL_ENV" && zet_geheim "$TRACKER_ENV" || terugdraaien
[ "$(lees_geheim "$PORTAL_ENV")" = "$NIEUW" ] && [ "$(lees_geheim "$TRACKER_ENV")" = "$NIEUW" ] \
    || terugdraaien
stap 3/6 "nieuw geheim in beide .env-bestanden (backups: .env$BAK, rechten 600)"

# --- 4) Proefstart: nieuwe config testen zonder de live nginx te raken -------
if ! proef="$(docker compose run --rm --no-deps -T nginx nginx -t 2>&1)"; then
    printf '%s\n' "$proef" | sed -E 's/[0-9A-Fa-f]{32,}/<GEMASKEERD>/g' | tail -15 >&2
    terugdraaien
fi
stap 4/6 "proefstart nginx -t geslaagd"

# --- 5) Herstarten -----------------------------------------------------------
BASE_DOMAIN="$(grep '^BASE_DOMAIN=' "$PORTAL_ENV" | tail -1 | cut -d= -f2-)"
sudo -n /usr/bin/systemctl restart schuldentracker.service || terugdraaien herstart
docker compose up -d --no-deps --force-recreate nginx >/dev/null 2>&1 || terugdraaien herstart
NGINX_ID="$(docker compose ps -q nginx 2>/dev/null || true)"
for _ in $(seq 1 40); do
    if [ -n "$NGINX_ID" ] \
        && [ "$(docker inspect -f '{{.State.Running}}' "$NGINX_ID" 2>/dev/null)" = true ] \
        && [ "$(http_code "https://portal.$BASE_DOMAIN/")" != 000 ] \
        && [ "$(http_code "$TRACKER_URL")" != 000 ]; then
        break
    fi
    sleep 1
    NGINX_ID="$(docker compose ps -q nginx 2>/dev/null || true)"
done
stap 5/6 "schuldentracker herstart, nginx opnieuw aangemaakt"

# --- 6) Nakijken; elke fout draait alles terug -------------------------------
fouten=0
controle() {  # $1 = omschrijving; de rest is het commando dat moet slagen
    local wat="$1"; shift
    if "$@"; then echo "  PASS  $wat"; else echo "  FAIL  $wat"; fouten=$((fouten + 1)); fi
}
# Kop via stdin (curl -H @-), niet als argument: blijft uit ps.
code_met_geheim() { printf 'X-SSO-Secret: %s\n' "$1" | http_code -H @- "$TRACKER_URL"; }
is() { [ "$1" = "$2" ]; }
bereikbaar() { [ "$1" != 000 ] && [ "${1#5}" = "$1" ]; }
nieuw_in_nginx() {
    [ "$(printf %s "$NIEUW" | sha256sum | cut -d' ' -f1)" \
        = "$(docker exec "$NGINX_ID" sh -c 'printf %s "$SSO_SHARED_SECRET" | sha256sum' 2>/dev/null | cut -d' ' -f1)" ]
}
nieuw_in_config() {
    docker exec "$NGINX_ID" sh -c \
        'v="$SSO_SHARED_SECRET"; [ -n "$v" ] || exit 1; case "$(cat /etc/nginx/conf.d/41-schuldentracker.conf)" in *"\"$v\""*) exit 0;; esac; exit 1'
}
oud_weg_uit_nginx() {
    printf '%s\n' "$OUD" | docker exec -i "$NGINX_ID" sh -c \
        'read -r o; for f in $(find /etc/nginx -type f); do case "$(cat "$f")" in *"$o"*) exit 1;; esac; done; exit 0'
}
template_zonder_hex() { ! heeft_hex < "$TEMPLATE"; }

controle "nginx draait en de config is geldig" docker exec "$NGINX_ID" nginx -t -q
controle "nginx kreeg het nieuwe geheim uit .env" nieuw_in_nginx
controle "gerenderde nginx-config gebruikt het nieuwe geheim" nieuw_in_config
controle "oud geheim staat nergens meer in de nginx-config" oud_weg_uit_nginx
controle "geen letterlijke waarde in de template op de VM" template_zonder_hex
c="$(http_code -H 'X-authentik-username: akadmin' "$TRACKER_URL")"
controle "rechtstreeks zonder geheim geweigerd ($c)" is "$c" 403
c="$(code_met_geheim "$OUD")"
controle "oud geheim geweigerd ($c)" is "$c" 403
c="$(code_met_geheim "$NIEUW")"
controle "nieuw geheim aanvaard ($c)" eval '[ "$c" != 403 ] && bereikbaar "$c"'
c="$(http_code "https://schuldentracker.$BASE_DOMAIN/")"
controle "schuldentracker.$BASE_DOMAIN bereikbaar via de portal ($c)" bereikbaar "$c"
c="$(http_code "https://portal.$BASE_DOMAIN/")"
controle "portal.$BASE_DOMAIN bereikbaar ($c)" bereikbaar "$c"

if [ "$fouten" -gt 0 ]; then
    echo "$fouten controle(s) gefaald." >&2
    terugdraaien herstart
fi
unset NIEUW OUD WAARDE
stap 6/6 "klaar: het oude geheim is waardeloos, het nieuwe staat alleen in de twee .env-bestanden"
