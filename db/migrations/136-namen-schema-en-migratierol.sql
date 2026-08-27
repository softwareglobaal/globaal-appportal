-- 127: eigen schema 'namen' plus een ingeperkte migratierol voor Sufa
-- Aanleiding: Sufa wil zijn eigen schemawijzigingen kunnen afronden zonder
-- telkens via Shaniel te gaan (vraag 2026-08-27). De volledige runner
-- (scripts/db-migrate.sh) draait met de bevoorrechte rol over de hele
-- database en blijft daarom bij ons. In plaats daarvan krijgt de namenlijst
-- een eigen schema en een rol die ALLEEN daar eigenaar is; het commando
-- 'ssh sufa migrate' (scripts/sufa-namen/namen-migrate) past migraties uit de
-- repo globaal-namen toe met die rol. Wat die rol niet kan, kan de migratie
-- ook niet: dat is de hele grens.
--
-- De twee bestaande tabellen verhuizen mee van organisatie.* naar namen.*;
-- de app-queries in globaal-namen gaan in dezelfde werksessie mee.

BEGIN;

CREATE SCHEMA IF NOT EXISTS namen;

-- De rol: login met wachtwoord (echte waarde zet de beheerder op de VM met
-- ALTER ROLE; met CHANGE_ME kan er niemand in). Geen superuser, geen
-- createdb, geen createrole; twee verbindingen is genoeg voor een runner.
DO $do$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'namen_migratie') THEN
        CREATE ROLE namen_migratie LOGIN PASSWORD 'CHANGE_ME' CONNECTION LIMIT 2;
    END IF;
END $do$;
ALTER ROLE namen_migratie SET search_path = namen;

-- Tabellen verhuizen. Grants en de FK naar kern.persoon verhuizen mee.
ALTER TABLE IF EXISTS organisatie.namen_kolom SET SCHEMA namen;
ALTER TABLE IF EXISTS organisatie.namen_waarde SET SCHEMA namen;

-- Eigendom naar de migratierol: zijn migraties moeten ALTER TABLE kunnen
-- doen, en eigendom geldt alleen binnen dit schema.
ALTER SCHEMA namen OWNER TO namen_migratie;
ALTER TABLE namen.namen_kolom OWNER TO namen_migratie;
ALTER TABLE namen.namen_waarde OWNER TO namen_migratie;

-- De app-rollen opnieuw expliciet: portal leest, medewerker_writer schrijft.
GRANT USAGE ON SCHEMA namen TO portal, medewerker_writer;
GRANT SELECT ON namen.namen_kolom, namen.namen_waarde TO portal;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON namen.namen_kolom, namen.namen_waarde TO medewerker_writer;

-- Nieuwe tabellen die Sufa's migraties aanmaken krijgen dezelfde rechten
-- vanzelf, anders werkt zijn nieuwe tabel wel in de migratie maar niet in
-- de app.
ALTER DEFAULT PRIVILEGES FOR ROLE namen_migratie IN SCHEMA namen
    GRANT SELECT ON TABLES TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE namen_migratie IN SCHEMA namen
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO medewerker_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE namen_migratie IN SCHEMA namen
    GRANT USAGE, SELECT ON SEQUENCES TO medewerker_writer;

-- Naar kern mag hij verwijzen (FK's op persoon en afdeling), niet lezen:
-- REFERENCES volstaat voor een foreign key en zijn migratie-output komt in
-- logs die hij zelf kan inzien, dus SELECT op persoonsgegevens blijft dicht.
GRANT USAGE ON SCHEMA kern TO namen_migratie;
GRANT REFERENCES ON kern.persoon, kern.afdeling TO namen_migratie;

COMMIT;
