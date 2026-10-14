#!/usr/bin/env bash
# Zet een Claude-abonnementstoken (uit `claude setup-token`, begint met sk-ant-oat) voor een host-dienst
# die de Claude CLI aanroept, en herstart die dienst.
#
#   bash ~/appportal/scripts/zet-claude-token.sh btw-dashboard
#
# Schrijft /etc/<dienst>.env (root 0600) met alleen CLAUDE_CODE_OAUTH_TOKEN; de dienst leest dat via
# EnvironmentFile (voor btw-dashboard: drop-in btw-dashboard.service.d/claude.conf). Interactief draaien:
# het token wordt niet getoond en komt niet in de shellgeschiedenis.
# HDS Betalingen heeft een eigen variant: ~/hds-betalingen/deploy/zet-api-sleutel.sh.
set -e
dienst="$1"
if [ -z "$dienst" ] || ! systemctl cat "$dienst.service" >/dev/null 2>&1; then
  echo "Gebruik: bash $0 <dienst>   (bestaande systemd-dienst, bv. btw-dashboard)"; exit 1
fi
read -rsp "Plak het token uit 'claude setup-token' (wordt niet getoond) en druk Enter: " token
echo
token=$(printf '%s' "$token" | tr -d '[:space:]')
case "$token" in
  sk-ant-oat*) ;;
  *) echo "Dit is geen token uit 'claude setup-token' (begint niet met sk-ant-oat). Niets gewijzigd."; exit 1 ;;
esac
printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$token" | sudo install -m 600 -o root -g root /dev/stdin "/etc/$dienst.env"
unset token
sudo systemctl restart "$dienst.service"
sleep 3
echo "Token staat in /etc/$dienst.env; $dienst: $(systemctl is-active "$dienst.service")"
