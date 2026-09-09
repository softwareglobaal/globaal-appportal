-- Migratie 146: schema uitgaven (AI-abonnementen-dashboard).
--
-- App: uitgaven.globaal.be, repo softwareglobaal/globaal-uitgaven, poort 3013.
-- Toont alleen AI-abonnementen (Claude, ChatGPT, ElevenLabs, Wispr, ...).
--
-- Twee lagen, bewust APART zodat geen som ze bij elkaar optelt:
--   verwachting = betaling/abonnement (uit de mail en de boekhouding)
--   realiteit   = kaart (wat er werkelijk is afgeschreven)
--
-- Idempotent: alles met IF NOT EXISTS, veilig om opnieuw te draaien.

CREATE SCHEMA IF NOT EXISTS uitgaven;

-- Leveranciers -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS uitgaven.leverancier (
    id          bigserial PRIMARY KEY,
    sleutel     text NOT NULL UNIQUE,
    naam        text NOT NULL,
    soort       text NOT NULL DEFAULT 'software',
    partij_id   uuid,
    aangemaakt  timestamptz NOT NULL DEFAULT now(),
    -- Alleen AI-leveranciers komen in beeld; de rest blijft bewaard maar
    -- verborgen (verbergen, niet wissen).
    is_ai       boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS leverancier_ai ON uitgaven.leverancier (is_ai);

-- Abonnementen -------------------------------------------------------------
-- Boven de streep: afgeleid/gedeclareerd door de importers, bij elke run
-- overschreven. Onder de streep: handmatige curatie, nooit aangeraakt.
CREATE TABLE IF NOT EXISTS uitgaven.abonnement (
    id              bigserial PRIMARY KEY,
    leverancier_id  bigint NOT NULL REFERENCES uitgaven.leverancier(id),
    firma           text NOT NULL,
    sleutel         text NOT NULL UNIQUE,
    ritme           text NOT NULL,
    bedrag          numeric(12,2) NOT NULL,
    eerste_betaling date NOT NULL,
    laatste_betaling date NOT NULL,
    aantal_betalingen int NOT NULL,
    totaal          numeric(12,2) NOT NULL,
    actief          boolean NOT NULL,
    afgeleid_op     timestamptz NOT NULL DEFAULT now(),
    herkomst        text NOT NULL DEFAULT 'patroon',   -- patroon | mail | boekhouding | handmatig
    valuta          text NOT NULL DEFAULT 'EUR',
    bevestigd       date,
    account         text,
    -- handmatig ------------------------------------------------------------
    plan            text,
    persoon_id      uuid,
    opzegdatum      date,
    notitie         text,
    bijgewerkt_op   timestamptz
);

-- Betalingen (de verwachting) ----------------------------------------------
CREATE TABLE IF NOT EXISTS uitgaven.betaling (
    id              bigserial PRIMARY KEY,
    vingerafdruk    text NOT NULL UNIQUE,
    firma           text NOT NULL,
    kaart           text,
    account         text,
    datum           date NOT NULL,
    datum_verrekend date,
    bedrag          numeric(12,2) NOT NULL,
    valuta          text NOT NULL DEFAULT 'EUR',
    betaalwijze     text NOT NULL DEFAULT 'kaart',
    omschrijving    text NOT NULL,
    leverancier_id  bigint REFERENCES uitgaven.leverancier(id),
    abonnement_id   bigint REFERENCES uitgaven.abonnement(id) ON DELETE SET NULL,
    soort           text,
    dubbel_van      bigint REFERENCES uitgaven.betaling(id),
    bron            text NOT NULL,
    import_run_id   bigint,
    geimporteerd_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS betaling_lev_datum ON uitgaven.betaling (leverancier_id, datum);
CREATE INDEX IF NOT EXISTS betaling_firma ON uitgaven.betaling (firma);
CREATE INDEX IF NOT EXISTS betaling_abo ON uitgaven.betaling (abonnement_id);
CREATE INDEX IF NOT EXISTS betaling_account ON uitgaven.betaling (account);
CREATE INDEX IF NOT EXISTS betaling_natuurlijk
    ON uitgaven.betaling (kaart, datum, datum_verrekend, bedrag, omschrijving);

-- Kaart (de realiteit) -----------------------------------------------------
CREATE TABLE IF NOT EXISTS uitgaven.kaart (
    id             bigserial PRIMARY KEY,
    vingerafdruk   text NOT NULL UNIQUE,
    datum          date NOT NULL,
    firma          text,
    vendor         text NOT NULL,
    leverancier_id bigint REFERENCES uitgaven.leverancier(id),
    categorie      text,
    bedrag         numeric(12,2) NOT NULL,
    valuta         text NOT NULL DEFAULT 'EUR',
    omschrijving   text,
    bron           text,
    import_run_id  bigint,
    geimporteerd_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS kaart_lev_datum ON uitgaven.kaart (leverancier_id, datum);
CREATE INDEX IF NOT EXISTS kaart_maand ON uitgaven.kaart (datum);

-- Levenscyclus: opzegging, mislukte betaling, pauze, schorsing -------------
CREATE TABLE IF NOT EXISTS uitgaven.gebeurtenis (
    id             bigserial PRIMARY KEY,
    account        text NOT NULL,
    abonnement_id  bigint REFERENCES uitgaven.abonnement(id) ON DELETE SET NULL,
    datum          date NOT NULL,
    soort          text NOT NULL,
    omschrijving   text NOT NULL,
    bron           text NOT NULL DEFAULT 'mail',
    vingerafdruk   text NOT NULL UNIQUE
);

-- Import-runs --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS uitgaven.import_run (
    id            bigserial PRIMARY KEY,
    gestart_op    timestamptz NOT NULL DEFAULT now(),
    klaar_op      timestamptz,
    bron          text NOT NULL,
    bestanden     int NOT NULL DEFAULT 0,
    gelezen       int NOT NULL DEFAULT 0,
    nieuw         int NOT NULL DEFAULT 0,
    dubbel        int NOT NULL DEFAULT 0,
    overgeslagen  jsonb NOT NULL DEFAULT '[]',
    fout          text
);

-- Rol ----------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'uitgaven') THEN
        CREATE ROLE uitgaven LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA uitgaven TO uitgaven;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA uitgaven TO uitgaven;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA uitgaven TO uitgaven;
ALTER DEFAULT PRIVILEGES IN SCHEMA uitgaven
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO uitgaven;
ALTER DEFAULT PRIVILEGES IN SCHEMA uitgaven
    GRANT USAGE, SELECT ON SEQUENCES TO uitgaven;

-- Leesrecht op de identiteits-hub, voor het koppelen van personen.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'kern') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA kern TO uitgaven';
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA kern TO uitgaven';
    END IF;
END $$;
