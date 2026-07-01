# Database `appportal` — schema in git

De `appportal`-database (naast `authentik` in dezelfde Postgres-container) is de
centrale gebruikersdatabase (schema `kern`) plus de spoke-schema's (`kosten`, `omv`,
`schuldentracker`). **Dit is de bron van waarheid voor het schema** — de live DB volgt
deze bestanden, niet andersom.

## Regel (vanaf 2026-07-01)

> **Geen ad-hoc `psql` meer voor schemawijzigingen.** Elke wijziging = een genummerd
> bestand in `db/migrations/`, gecommit vóór het draaien, toegepast met
> `scripts/db-migrate.sh`.

## Bestanden

| Bestand | Wat |
|---|---|
| `000-baseline.sql` | Volledige schema-staat per 2026-07-01 (`pg_dump --schema-only --no-owner`). Nulpunt — wordt nooit meer gewijzigd. |
| `roles.sql` | De app-rollen (`portal`, `kosten`, `medewerker_writer`) met placeholder-wachtwoorden. Rollen zijn cluster-niveau en zitten dus niet in de baseline. |
| `seed-afdeling-firma.sql` | Lookup-data: 13 afdelingen + 13 firma's. Idempotent. |
| `migrations/NNN-*.sql` | Alle wijzigingen ná de baseline, oplopend genummerd. |

De persoon-seed (34 medewerkers, met namen/e-mails) staat bewust **niet** in de repo;
die leeft in de lokale ontwerpmap ("AppPortal - Centrale Gebruikersdatabase").

## Verse deploy

```bash
# 1) Rollen (eerst wachtwoorden invullen in een kopie — niet committen!)
docker compose exec -T postgresql psql -U authentik -d postgres -f - < db/roles.sql
# 2) Database + baseline
docker compose exec -T postgresql createdb -U authentik appportal
docker compose exec -T postgresql psql -U authentik -d appportal -v ON_ERROR_STOP=1 -f - < db/000-baseline.sql
# 3) Lookups + alle migraties
docker compose exec -T postgresql psql -U authentik -d appportal -v ON_ERROR_STOP=1 -f - < db/seed-afdeling-firma.sql
sh scripts/db-migrate.sh
```

## Wijziging doorvoeren (dagelijks werk)

```bash
# 1) maak db/migrations/002-mijn-wijziging.sql (volgende vrije nummer)
# 2) commit het bestand
# 3) pas toe:
sh scripts/db-migrate.sh
```

De runner houdt in `public.schema_migrations` bij wat al toegepast is en slaat dat
over — dubbel draaien kan geen kwaad.
