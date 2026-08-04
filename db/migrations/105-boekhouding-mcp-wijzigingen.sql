-- 105: logboek van wat er via de MCP-connector gewijzigd is.
--
-- De connector was tot nu toe alleen-lezen. Op verzoek (Shaniel, 04-08-2026)
-- krijgt hij schrijf-tools. Zodra een gesprek iets kan veranderen, hoort
-- terug te vinden te zijn wie wat wanneer deed, ook als het via een chat ging.
-- Onze eigen tabellen hebben dat al in hun kolommen; wijzigingen in Octopus
-- zelf niet, want dat is hun systeem. Dit is dus vooral het spoor naar buiten.
--
-- Bewust geen koppeling aan kern.persoon: de MCP-identiteit is een
-- Authentik-gebruikersnaam en die kan ook een dienstaccount zijn.

CREATE TABLE IF NOT EXISTS boekhouding.mcp_wijziging (
    id          bigserial PRIMARY KEY,
    moment      timestamptz NOT NULL DEFAULT now(),
    door        text NOT NULL,
    tool        text NOT NULL,
    dossier_id  integer,
    doelwit     text NOT NULL DEFAULT '',
    argumenten  jsonb NOT NULL DEFAULT '{}'::jsonb,
    resultaat   text NOT NULL DEFAULT '',
    gelukt      boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS ix_mcp_wijziging_moment
    ON boekhouding.mcp_wijziging (moment DESC);
CREATE INDEX IF NOT EXISTS ix_mcp_wijziging_dossier
    ON boekhouding.mcp_wijziging (dossier_id, moment DESC);

GRANT SELECT, INSERT ON boekhouding.mcp_wijziging TO boekhouding_writer;
GRANT USAGE, SELECT ON SEQUENCE boekhouding.mcp_wijziging_id_seq TO boekhouding_writer;
GRANT SELECT ON boekhouding.mcp_wijziging TO portal;
