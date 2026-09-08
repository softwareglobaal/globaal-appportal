-- Leesrechten voor de portal-MCP op de Authentik-database.
--
-- Draaien vanuit ~/appportal, mét een sterk wachtwoord als psql-variabele:
--   docker compose exec -T postgresql psql -U authentik -d authentik \
--       -v pw="<sterk-wachtwoord>" -f - < portal-mcp/rol-authentik.sql
--
-- Draai hierna ook portal-mcp/rol-appportal.sql op de appportal-database; de
-- rol is clusterbreed, de rechten staan per database.
--
-- Waarom hier een leesrol en geen API-token: de Authentik-API kan een cataloog
-- van alle applicaties alleen aan een superuser geven (`superuser_full_list` en
-- `for_user` staan allebei achter `request.user.is_superuser`). Een admin-token
-- in .env kan ook schrijven: gebruikers aanmaken, groepen wijzigen, tokens
-- uitgeven. Vier tabellen alleen-lezen is een veel kleiner risico.
--
-- Op `authentik_core_user` staan de rechten per kolom. Daar staan
-- wachtwoord-hashes in, en die horen niet binnen bereik van deze server te
-- liggen; `id`, `username` en `is_active` zijn genoeg.

-- Aanmaken of het wachtwoord bijzetten, in twee stappen met \gexec. Geen
-- DO-blok: psql vult `:'pw'` niet in binnen dollar-quotes, dus daar zou het
-- wachtwoord letterlijk de tekst ":'pw'" worden.
SELECT format('CREATE ROLE mcp_lezer LOGIN PASSWORD %L', :'pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_lezer')
\gexec

SELECT format('ALTER ROLE mcp_lezer LOGIN PASSWORD %L', :'pw')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_lezer')
\gexec

GRANT CONNECT ON DATABASE authentik TO mcp_lezer;
GRANT USAGE ON SCHEMA public TO mcp_lezer;

-- De cataloog en de rechten. Meer heeft de MCP hier niet nodig.
GRANT SELECT ON authentik_core_application TO mcp_lezer;
GRANT SELECT ON authentik_policies_policybinding TO mcp_lezer;
GRANT SELECT ON authentik_core_group TO mcp_lezer;
GRANT SELECT ON authentik_core_user_groups TO mcp_lezer;

-- Alleen deze drie kolommen; niet de wachtwoord-hash, niet de attributen.
GRANT SELECT (id, username, is_active) ON authentik_core_user TO mcp_lezer;

-- Nieuwe tabellen in deze database krijgen bewust GEEN rechten: een
-- Authentik-upgrade hoort de leesrol niet ongemerkt te verbreden.
