-- 194: rol en schema voor de privé-uitgaven van Mehdi (prive.globaal.be).
--
-- Driehoeksoverleg P1, 19-10-2026 (punt X1/K1, 3-0): aparte app, eigen schema met eigen rol, alleen Mehdi.
-- Deze migratie maakt alleen de rol, het schema en de rechten. De tabellen staan in de repo
-- softwareglobaal/globaal-prive (db/NNN_*.sql) en worden bij het starten toegepast door app/migreer.py
-- onder de rol prive (transactie per bestand, databaseslot, checksum in prive.migratie).
--
-- Eigen LOGIN-rol prive zonder wachtwoord in git (zoals 190): het wachtwoord wordt op de VM gezet met
-- ALTER ROLE en staat alleen in ~/appportal/.env als PRIVE_DB_URL.
--
-- Rechten: eigenaar van schema prive, niets anders. Geen enkele andere app-rol krijgt hier rechten;
-- wie dat ooit wil (bv. een lezende rol voor de portaalconnector), doet dat met een nieuwe migratie.
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prive') THEN
        CREATE ROLE prive LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS prive AUTHORIZATION prive;
REVOKE ALL ON SCHEMA prive FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA prive TO prive;
ALTER ROLE prive SET search_path = prive;
COMMIT;

