#!/bin/sh
# Verzamelt git-activiteit per (dag, repo, auteur) in ontwikkeling.git_dag
# (migratie 074). Bron A van de ontwikkel-statistieken: output (commits en
# regels), geen tijd - die komt uit de Claude Code-hooks (bron B).
#
# Gebruik:  sh scripts/ontwikkeling-verzamel.sh [vanaf]
#   vanaf   git-datum, standaard "14 days ago"; eerste keer bv. "2026-01-01"
#           voor de historische backfill. Upserts zijn idempotent, dus een
#           venster dat overlapt is veilig.
#
# Draait op de VM-host (cron, zelfde patroon als de deploy-scripts) vanuit
# ~/appportal; schrijft via docker compose exec naar Postgres.
set -eu

VANAF="${1:-14 days ago}"
PSQL="docker compose exec -T postgresql psql -U authentik -d appportal -v ON_ERROR_STOP=1 -q"

# De checkouts op de VM zijn de bron. Bewust GEEN vaste lijst meer: die raakt
# achter zodra er een repo bijkomt (globaal-hr stond er daardoor niet in). We
# zoeken de git-checkouts en leiden de repo-naam af uit de remote-URL, zodat
# een nieuwe app vanzelf meetelt.
vind_repos() {
  for map in "$HOME"/* "$HOME"/appportal/*; do
    [ -d "$map/.git" ] || continue
    url=$(git -C "$map" config --get remote.origin.url 2>/dev/null) || continue
    [ -n "$url" ] || continue
    naam=$(basename "$url" .git)
    printf '%s|%s\n' "$map" "$naam"
  done | sort -u -t'|' -k2,2   # één checkout per repo (de eerste die we zien)
}

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

vind_repos | while IFS='|' read -r map repo; do
  [ -n "$map" ] || continue
  [ -d "$map/.git" ] || continue
  # Onbekende repo? Meteen als applicatie registreren, dan hoeft niemand
  # daaraan te denken bij een nieuwe app.
  printf "INSERT INTO ontwikkeling.app (repo, naam) VALUES ('%s', '%s') ON CONFLICT (repo) DO NOTHING;\n" \
         "$repo" "$repo" >> "$TMP"
  # Per commit een kopregel C|datum|email, daarna numstat-regels (plus TAB min
  # TAB pad). awk aggregeert naar dag+auteur.
  git -C "$map" log --since="$VANAF" --no-merges \
      --pretty="C|%ad|%ae" --date=short --numstat 2>/dev/null |
  awk -F'|' -v repo="$repo" '
    /^C\|/ { datum = $2; email = tolower($3); c[datum "|" email]++; next }
    NF && datum {
      split($0, kol, "\t");
      if (kol[1] ~ /^[0-9]+$/) plus[datum "|" email] += kol[1];
      if (kol[2] ~ /^[0-9]+$/) min[datum "|" email]  += kol[2];
    }
    END {
      for (k in c) {
        split(k, d, "|");
        # e-mail als SQL-string: quotes verdubbelen kan awk lastig; auteurs
        # zijn eigen teamleden, maar we weren aanhalingstekens voor de zekerheid.
        gsub(/\x27/, "", d[2]);
        printf "INSERT INTO ontwikkeling.git_dag (datum, repo, gebruiker, commits, regels_plus, regels_min) VALUES (\x27%s\x27, \x27%s\x27, \x27%s\x27, %d, %d, %d) ON CONFLICT (datum, repo, gebruiker) DO UPDATE SET commits = EXCLUDED.commits, regels_plus = EXCLUDED.regels_plus, regels_min = EXCLUDED.regels_min, bijgewerkt_op = now();\n",
               d[1], repo, d[2], c[k], plus[k] + 0, min[k] + 0;
      }
    }' >> "$TMP"
done

if [ -s "$TMP" ]; then
  $PSQL < "$TMP" >/dev/null
  echo "$(date -Is) ontwikkeling-verzamel: $(wc -l < "$TMP") dag-rijen bijgewerkt (vanaf: $VANAF)"
else
  echo "$(date -Is) ontwikkeling-verzamel: niets te doen"
fi
