-- 197: rol en schema voor het regiebord (regie.globaal.be).
--
-- Ontwerp regiebord v0.2 (besluit X1) en v0.4: eigen app naar het patroon van 194 (prive), eigen schema met
-- eigen rol, toegang alleen voor de eigen Authentik-groep (REGIE_GROUPS). Deze migratie maakt alleen de rol,
-- het schema en de rechten. De tabellen (herinneringen, labels, niet vergeten, momentopnames van de Mac,
-- broninventaris) staan in de repo softwareglobaal/globaal-regie (db/NNN_*.sql) en worden bij het starten
-- toegepast door app/migreer.py onder de rol regie (transactie per bestand, databaseslot, checksum in
-- regie.migratie).
--
-- Eigen LOGIN-rol regie zonder wachtwoord in git (zoals 190 en 194): het wachtwoord wordt op de VM gezet met
-- ALTER ROLE en staat alleen in ~/appportal/.env als REGIE_DB_URL.
--
-- Rechten: eigenaar van schema regie, niets anders. Het bord leest zijn bronnen (mijnagents, ha-projecten)
-- alleen via hun API en krijgt dus op geen enkel ander schema rechten; wie dat ooit wil, doet dat met een
-- nieuwe migratie hier, niet in de app.
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'regie') THEN
        CREATE ROLE regie LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS regie AUTHORIZATION regie;
REVOKE ALL ON SCHEMA regie FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA regie TO regie;
ALTER ROLE regie SET search_path = regie;
COMMIT;
