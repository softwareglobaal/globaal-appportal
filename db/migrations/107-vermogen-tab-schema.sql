-- 107 — vermogen: de vier vaste tabs via MCP aanpasbaar (hybride skelet).
--
-- De kernkolommen van pand/verzekering/lening/syndicus blijven code +
-- migraties (FK's, rapportages, Second Brain bouwen erop). Daarbovenop:
--   - `extra` jsonb op elke vaste tabel: door Claude toegevoegde velden
--     (tab_bijwerken), zelfde veldtypes als secties incl. zachte refs.
--   - `tab_schema`: per vaste tab de aanpassingen: extra velddefinities,
--     wijzigingen op kernvelden (label, keuzeopties, verborgen, verplicht)
--     en de veldvolgorde. Kernvelden kunnen niet weg, alleen verborgen;
--     lening.soort houdt zijn check-constraint (opties daar = migratie).

ALTER TABLE vermogen.pand        ADD COLUMN extra jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE vermogen.verzekering ADD COLUMN extra jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE vermogen.lening      ADD COLUMN extra jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE vermogen.syndicus    ADD COLUMN extra jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE vermogen.tab_schema (
    tab             text PRIMARY KEY
        CONSTRAINT ck_tab_schema_tab CHECK (tab IN
            ('panden', 'verzekeringen', 'leningen', 'syndicus')),
    extra_velden    jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{kolom,label,type,...}]
    aanpassingen    jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {kolom:{label,opties,verborgen,verplicht}}
    volgorde        jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [kolom, ...]
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

GRANT SELECT, INSERT, UPDATE, DELETE ON vermogen.tab_schema TO vermogen;
GRANT SELECT ON vermogen.tab_schema TO portal;

CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON vermogen.tab_schema
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();
