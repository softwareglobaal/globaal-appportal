#!/bin/sh
# Past nieuwe migraties uit db/migrations/ toe op de appportal-database.
# Houdt in public.schema_migrations bij wat al gedraaid is — dubbel draaien is veilig.
# Gebruik:  sh scripts/db-migrate.sh   (vanuit ~/appportal)
set -eu

PSQL="docker compose exec -T postgresql psql -U authentik -d appportal -v ON_ERROR_STOP=1"

$PSQL -q -c "CREATE TABLE IF NOT EXISTS public.schema_migrations (
    naam text PRIMARY KEY,
    toegepast_op timestamptz NOT NULL DEFAULT now()
);"

for f in db/migrations/[0-9]*.sql; do
  [ -e "$f" ] || { echo "geen migraties gevonden"; exit 0; }
  naam=$(basename "$f")
  al=$($PSQL -tA -c "SELECT 1 FROM public.schema_migrations WHERE naam = '$naam'")
  if [ "$al" = "1" ]; then
    echo "skip   $naam"
    continue
  fi
  echo "APPLY  $naam"
  $PSQL -f - < "$f"
  $PSQL -q -c "INSERT INTO public.schema_migrations (naam) VALUES ('$naam');"
done
echo "klaar."
