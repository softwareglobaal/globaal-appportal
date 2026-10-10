-- 190: rol en schema voor de Salesagent H-Architects.
--
-- Mehdi, 11-10-2026, keuze B: "beheer de databaserol en het schema centraal, en houd de
-- salesagent-tabellen en migraties in de eigen repo". Deze migratie maakt dus alleen de rol,
-- het schema en de rechten. De tabellen staan in de repo softwareglobaal/salesagent (db/NNN_*.sql)
-- en worden toegepast door salesagent/db/migreer.py onder de rol salesagent: elke migratie in een
-- eigen transactie, met een databaseslot en een checksum per bestand in sales.migratie. Die runner
-- voert zelf nooit schema- of rolbeheer uit.
--
-- Eigen LOGIN-rol salesagent zonder wachtwoord in git (zoals 184): het wachtwoord wordt op de VM
-- gezet met ALTER ROLE en staat alleen in ~/appportal/.env als SALESAGENT_DB_URL.
--
-- Rechten, zo smal mogelijk:
--   schema sales          eigenaar (tabellen, indexen, sequences van de salesagent)
--   schema communicatie   alleen lezen, vijf tabellen voor telefoongesprekken op de saleslijnen
--                         (regel R23, fase 0b stap 3); nooit schrijven
--   al de rest            niets: geen kern, geen andere app-schema's, geen CREATE op de databank
-- Wie de rechten verruimt, doet dat met een nieuwe migratie hier, niet in de app.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'salesagent') THEN
        CREATE ROLE salesagent LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;

CREATE SCHEMA IF NOT EXISTS sales AUTHORIZATION salesagent;
REVOKE ALL ON SCHEMA sales FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA sales TO salesagent;

ALTER ROLE salesagent SET search_path = sales;

GRANT USAGE ON SCHEMA communicatie TO salesagent;
GRANT SELECT ON communicatie.xelion_communicatie,
                communicatie.xelion_belvolgorde,
                communicatie.lijn_firma,
                communicatie.gesprek_transcript,
                communicatie.contact_herkenning
             TO salesagent;

COMMIT;
