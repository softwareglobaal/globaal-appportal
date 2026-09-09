#!/bin/sh
# Ververst seed/blok-a.json vanuit het organisatieregister (Postgres, schema kern).
# Draaien op de server vanuit ~/appportal, daarna committen en pushen; de
# deploy-cron van siyanagents herbouwt de container.
set -eu
cd "$(dirname "$0")/../.."
HIER="siyanagents/seed"
docker compose exec -T postgresql psql -U authentik -d appportal -At \
  < "$HIER/blok-a-export.sql" > "$HIER/blok-a.ruw.json"
python3 - "$HIER" <<'PY'
import json, sys, datetime
hier = sys.argv[1]
taken = json.load(open(f"{hier}/blok-a.ruw.json", encoding="utf-8"))
uit = {"bron": "organisatie.globaal.be/disciplines (schema kern, migratie 126)",
       "momentopname": datetime.date.today().isoformat(),
       "toelichting": ("Momentopname van blok A van het organisatieregister. Verversen met "
                       "seed/blok-a-export.sh; toewijzen gebeurt in het register zelf, niet hier."),
       "taken": taken}
json.dump(uit, open(f"{hier}/blok-a.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(taken)} taken weggeschreven naar {hier}/blok-a.json")
PY
rm -f "$HIER/blok-a.ruw.json"
