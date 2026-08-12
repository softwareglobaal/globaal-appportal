-- 115: schema `quickbooks` - koppeling met QuickBooks Online voor HDS (Suriname).
--
-- Tweede boekhoudsysteem naast Octopus. Octopus doet de Belgische firma's
-- (schema `boekhouding`, migratie 102); QuickBooks doet HDS. De connector is
-- een MCP-server op quickbooks.globaal.be, zodat Claude de boekhouding kan
-- lezen en een beperkte set gegevens kan bijwerken.
--
-- Lagen (ontwerp-prompt docs/prompt-dashboard-ontwerp.md):
--   entiteiten = koppeling (de verbinding met een QuickBooks-bedrijf)
--   relaties   = koppeling.kern_firma_id (naar kern.firma)
--   views      = queries in de app, niets opgeslagen
--
-- Bewust GEEN spiegel van de boekhouding zelf. De privacyverklaring op
-- quickbooks.globaal.be/privacy belooft dat er geen staande kopie van de
-- QuickBooks-gegevens op onze server staat, en dat is hier dus ook een
-- schemabeslissing en niet alleen een belofte: er is nergens een tabel om
-- facturen of relaties in te bewaren.
--
-- Discipline: financial management.

CREATE SCHEMA IF NOT EXISTS quickbooks;

-- Koppeling: één rij per verbonden QuickBooks-bedrijf. Het realm_id is het
-- bedrijfsnummer dat Intuit toekent en is de sleutel in al hun API-paden.
--
-- De refresh token roteert bij elk gebruik en verloopt na 100 dagen zonder
-- gebruik. Daarom staat hier vernieuwd_op: daarmee is te zien of een koppeling
-- stil aan het verlopen is voordat hij echt dood is.
CREATE TABLE IF NOT EXISTS quickbooks.koppeling (
    realm_id            text PRIMARY KEY,
    bedrijfsnaam        text NOT NULL DEFAULT '',
    land                text NOT NULL DEFAULT '',
    valuta              text NOT NULL DEFAULT '',
    kern_firma_id       uuid REFERENCES kern.firma(id) ON DELETE SET NULL,
    toegang_token       text NOT NULL DEFAULT '',
    toegang_verloopt_op timestamptz,
    ververs_token       text NOT NULL DEFAULT '',
    ververs_verloopt_op timestamptz,
    vernieuwd_op        timestamptz,
    gekoppeld_op        timestamptz NOT NULL DEFAULT now(),
    gekoppeld_door      text NOT NULL DEFAULT '',
    actief              boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS ix_quickbooks_koppeling_kern
    ON quickbooks.koppeling (kern_firma_id);

-- Logboek van wat er via de connector gebeurde. Twee redenen: de vragenlijst
-- van Intuit legt vast dat we foutinformatie bewaren en het intuit_tid uit de
-- antwoordheaders vastleggen (dat is hun sleutel bij support), en bij een
-- schrijfactie hoort terug te vinden wie het deed.
CREATE TABLE IF NOT EXISTS quickbooks.gebeurtenis (
    id          bigserial PRIMARY KEY,
    moment      timestamptz NOT NULL DEFAULT now(),
    realm_id    text,
    door        text NOT NULL DEFAULT '',
    tool        text NOT NULL DEFAULT '',
    methode     text NOT NULL DEFAULT '',
    pad         text NOT NULL DEFAULT '',
    schrijft    boolean NOT NULL DEFAULT false,
    status      integer,
    intuit_tid  text NOT NULL DEFAULT '',
    fout        text NOT NULL DEFAULT '',
    gelukt      boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS ix_quickbooks_gebeurtenis_moment
    ON quickbooks.gebeurtenis (moment DESC);
CREATE INDEX IF NOT EXISTS ix_quickbooks_gebeurtenis_schrijft
    ON quickbooks.gebeurtenis (schrijft, moment DESC) WHERE schrijft;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quickbooks_writer') THEN
        CREATE ROLE quickbooks_writer LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA quickbooks TO quickbooks_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA quickbooks TO quickbooks_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA quickbooks TO quickbooks_writer;
GRANT USAGE ON SCHEMA kern TO quickbooks_writer;
GRANT SELECT ON kern.firma TO quickbooks_writer;
GRANT USAGE ON SCHEMA quickbooks TO portal;
GRANT SELECT ON quickbooks.gebeurtenis TO portal;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('realm_id', 'Realm ID',
     'Het bedrijfsnummer dat Intuit aan een QuickBooks Online-bedrijf toekent. Komt terug '
     'in elk API-pad en is de sleutel van een koppeling in het schema quickbooks.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
