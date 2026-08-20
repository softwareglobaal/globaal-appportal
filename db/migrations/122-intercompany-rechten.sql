-- 122: intercompany - rechten op nieuwe tabellen, nu en later.
--
-- Migratie 118 deed `GRANT ... ON ALL TABLES IN SCHEMA intercompany`. Dat geldt
-- alleen voor de tabellen die op dat moment bestonden. Tabel `reeks` uit
-- migratie 121 kreeg dus niets, en het tabblad Te factureren gaf meteen na de
-- deploy een 500 met "permission denied for table reeks".
--
-- Twee dingen: de ontbrekende rechten alsnog, en ALTER DEFAULT PRIVILEGES zodat
-- elke volgende tabel in dit schema ze automatisch krijgt. Anders herhaalt dit
-- zich bij de eerstvolgende migratie die een tabel toevoegt, en dan opnieuw
-- pas zichtbaar in productie.
--
-- De default privileges gelden voor tabellen die door dezelfde rol worden
-- aangemaakt als degene die dit uitvoert. Migraties draaien als `authentik`,
-- en dat is ook de rol die de tabellen aanmaakt, dus dat sluit aan.

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA intercompany
    TO intercompany_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intercompany TO intercompany_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA intercompany TO portal;

ALTER DEFAULT PRIVILEGES IN SCHEMA intercompany
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO intercompany_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA intercompany
    GRANT USAGE, SELECT ON SEQUENCES TO intercompany_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA intercompany
    GRANT SELECT ON TABLES TO portal;
