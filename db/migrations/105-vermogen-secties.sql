-- 105 — vermogen: dynamische secties (extra tabs, aan te maken via MCP/Claude).
--
-- Het vaste skelet (migratie 016: pand/verzekering/lening/syndicus) blijft
-- code + kolommen; dit zijn de VRIJE secties ernaast: de definitie (naam +
-- velden) staat in `sectie`, de inhoud als jsonb in `sectie_rij`. De webapp
-- toont ze als extra tabs, de MCP-tools (sectie_aanmaken enz.) beheren ze.
-- Veldtypes beperkt tot tekst/bedrag/pct/datum/keuze/lang: geen refs naar
-- kern, dus bewust géén nieuwe graaf-relaties.

CREATE TABLE vermogen.sectie (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            text NOT NULL UNIQUE
        CONSTRAINT ck_sectie_slug CHECK (slug ~ '^[a-z][a-z0-9-]{1,40}$'),
    naam            text NOT NULL,
    velden          jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{kolom,label,type,opties?,verplicht?}]
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

CREATE TABLE vermogen.sectie_rij (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sectie_id       uuid NOT NULL REFERENCES vermogen.sectie(id),
    data            jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {kolom: waarde}
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);
CREATE INDEX ix_sectie_rij_sectie ON vermogen.sectie_rij (sectie_id);

-- Rechten: zelfde patroon als 016 (de default privileges dekken dit al,
-- expliciet voor de duidelijkheid).
GRANT SELECT, INSERT, UPDATE, DELETE ON vermogen.sectie, vermogen.sectie_rij TO vermogen;
GRANT SELECT ON vermogen.sectie, vermogen.sectie_rij TO portal;

-- Audit zoals migratie 023: elke wijziging traceerbaar, ook die van Claude.
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON vermogen.sectie
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON vermogen.sectie_rij
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();
