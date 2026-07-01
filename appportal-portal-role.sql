-- Per-app DB-rol voor de portal (governance — ONTWERP §14).
-- Draai dit in de appportal-database, met een wachtwoord meegegeven als psql-var:
--   docker compose exec -T postgresql psql -U authentik -d appportal \
--     -v pw="<sterk-wachtwoord>" -f - < appportal-portal-role.sql
--
-- v1 is READ-ONLY: de portal leest kern + de spokes voor de medewerkerspagina en
-- het 360-profiel. Schrijfrechten op kern (login-binding, offboarding) voegen we
-- pas toe wanneer die flows live gaan — dan komt hier GRANT INSERT/UPDATE op
-- kern.persoon bij, nog steeds NIETS op andere app-schema's.

CREATE ROLE portal LOGIN PASSWORD :'pw';

-- kern: alleen lezen op de hub.
GRANT USAGE ON SCHEMA kern TO portal;
GRANT SELECT ON kern.afdeling, kern.persoon TO portal;

-- spokes: alleen lezen (voor de 360-aggregatie). Breid uit per nieuw spoke-schema.
GRANT USAGE ON SCHEMA schuldentracker, omv TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA schuldentracker, omv TO portal;
ALTER DEFAULT PRIVILEGES IN SCHEMA schuldentracker, omv GRANT SELECT ON TABLES TO portal;

-- Connectiestring voor .env (APPPORTAL_DB_URL), binnen het docker-netwerk:
--   postgresql+psycopg://portal:<wachtwoord>@postgresql:5432/appportal
