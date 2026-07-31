-- 106 — vermogen: layout-instellingen + eigen (read-only) MCP-tools.
--
-- Vervolg op 105 (dynamische secties): Claude kan via MCP nu ook de layout
-- sturen (dashboardtitel, tabvolgorde, aantal lijstkolommen, eigen css) en
-- eigen raadpleeg-tools definiëren (opgeslagen SELECT-queries met parameters,
-- afgedwongen read-only bij uitvoering). Schrijven blijft via de vaste,
-- gevalideerde tools; code blijft via git.

CREATE TABLE vermogen.instelling (
    sleutel         text PRIMARY KEY,     -- titel / tab_volgorde / lijst_kolommen / css
    waarde          jsonb NOT NULL,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

CREATE TABLE vermogen.mcp_tool (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam            text NOT NULL UNIQUE
        CONSTRAINT ck_mcp_tool_naam CHECK (naam ~ '^[a-z][a-z0-9_]{2,40}$'),
    beschrijving    text NOT NULL,
    sql_tekst       text NOT NULL,                       -- één SELECT/WITH-query
    parameters      jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{naam,type,verplicht?}]
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

GRANT SELECT, INSERT, UPDATE, DELETE ON vermogen.instelling, vermogen.mcp_tool TO vermogen;
GRANT SELECT ON vermogen.instelling, vermogen.mcp_tool TO portal;

-- Audit zoals migratie 023 (instelling heeft geen id-kolom: rij_id blijft
-- daar leeg, oud/nieuw tonen de sleutel).
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON vermogen.instelling
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON vermogen.mcp_tool
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();
