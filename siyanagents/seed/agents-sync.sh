#!/bin/sh
# Kopieert de rolbestanden van Siyans agents (~/.claude/agents op de Mac) naar
# siyanagents/agents/, zodat het bord per agent een collega-profiel kan tonen.
# Draaien op de Mac na een wijziging aan een agent, daarna committen en pushen.
set -eu
cd "$(dirname "$0")/.."
BRON="${1:-$HOME/.claude/agents}"
n=0
for f in "$BRON"/*.md; do
  cp "$f" agents/
  n=$((n+1))
done
echo "$n rolbestanden gekopieerd naar siyanagents/agents/"
