#!/usr/bin/env bash
# Afgedwongen opdracht van de sleutel claude_manager_lees (Claude Code Manager).
# Staat in authorized_keys als command="...", dus elke ssh-aanroep met die
# sleutel komt hier uit. Alleen de opdrachten hieronder bestaan; niets uit
# SSH_ORIGINAL_COMMAND gaat ooit door een shell.
set -u
export LC_ALL=C

MAX_BYTES=60000
TIJD=25

read -r -a a <<<"${SSH_ORIGINAL_COMMAND:-}"
n=${#a[@]}
wat="${a[0]:-}"

logger -t claude-manager-lees -- "${SSH_ORIGINAL_COMMAND:-}" 2>/dev/null || true

weiger() {
    echo "geweigerd: $1" >&2
    exit 64
}
naam_ok() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_.@-]{0,100}$ ]]; }
regels_ok() { [[ "$1" =~ ^[1-9][0-9]{0,3}$ ]] && ((10#$1 <= 1000)); }
aantal() { [[ "$n" -eq "$1" ]] || weiger "verkeerd aantal argumenten voor $wat"; }

case "$wat" in
    uptime)
        aantal 1
        uptime
        ;;
    schijf)
        aantal 1
        df -h -x tmpfs -x devtmpfs -x overlay -x squashfs -x fuse.rclone
        ;;
    geheugen)
        aantal 1
        free -m
        ;;
    containers)
        aantal 1
        timeout "$TIJD" docker ps -a --format '{{.Names}}\t{{.Status}}'
        ;;
    stats)
        aantal 1
        timeout "$TIJD" docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'
        ;;
    logs)
        aantal 3
        naam_ok "${a[1]}" || weiger "ongeldige containernaam"
        regels_ok "${a[2]}" || weiger "ongeldig aantal regels"
        timeout "$TIJD" docker logs --tail "${a[2]}" "${a[1]}" 2>&1 | head -c "$MAX_BYTES"
        ;;
    mislukt)
        aantal 1
        systemctl list-units --failed --no-pager --plain
        ;;
    dienst)
        aantal 2
        naam_ok "${a[1]}" || weiger "ongeldige dienstnaam"
        timeout "$TIJD" systemctl status --no-pager -n 20 -- "${a[1]}" 2>&1 | head -c "$MAX_BYTES"
        ;;
    journaal)
        aantal 3
        naam_ok "${a[1]}" || weiger "ongeldige dienstnaam"
        regels_ok "${a[2]}" || weiger "ongeldig aantal regels"
        timeout "$TIJD" journalctl --no-pager -n "${a[2]}" -u "${a[1]}" 2>&1 | head -c "$MAX_BYTES"
        ;;
    *)
        weiger "onbekende opdracht"
        ;;
esac
