-- 062 - finance-schema: de Octopus-spiegel (stap 4 uit PLAN.md).
--
-- Spiegeltabellen voor wat de Octopus-API levert, plus de sync-status
-- (zelfde filosofie als communicatie.xelion_sync en kosten.desktime_sync:
-- de tool is de bron van waarheid, wij spiegelen read-only en versheid is
-- zichtbaar). De poller draait in de organisatie-app (beslissing stap 3:
-- datavolume is klein, DeskTime-precedent) en schrijft via de bestaande
-- rol medewerker_writer.

CREATE SCHEMA finance;

-- Sync-status per dossier (= boekhouding = firma via kosten.octopus_boekhouding).
CREATE TABLE finance.octopus_sync (
    dossier_id    integer PRIMARY KEY,
    dossier_naam  text NOT NULL DEFAULT '',
    btw_nummer    text NOT NULL DEFAULT '',
    laatste_run   timestamptz,
    laatste_ok    timestamptz,
    status        text NOT NULL DEFAULT '',
    detail        text NOT NULL DEFAULT '',
    boekingen     integer NOT NULL DEFAULT 0
);

CREATE TABLE finance.octopus_bookyear (
    dossier_id    integer NOT NULL,
    bookyear_id   integer NOT NULL,
    omschrijving  text NOT NULL DEFAULT '',
    begin_datum   date,
    eind_datum    date,
    gesloten      boolean NOT NULL DEFAULT false,
    ruw           jsonb NOT NULL DEFAULT '{}'::jsonb,
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier_id, bookyear_id)
);

-- Boekingen: aankoop/verkoop (soort 'buysell', met relatie en kopbedrag)
-- en financieel/divers (soort 'financialdivers', alles in de regels).
-- De regels (grootboekrekening, BTW, kostenplaats) gaan integraal mee als
-- jsonb; getypte kolommen alleen voor wat de views nodig hebben.
CREATE TABLE finance.octopus_boeking (
    dossier_id     integer NOT NULL,
    bookyear_id    integer NOT NULL,
    journal_key    text NOT NULL,
    document_nr    integer NOT NULL,
    soort          text NOT NULL,
    relatie_octopus_id text NOT NULL DEFAULT '',
    document_datum date,
    verval_datum   date,
    bedrag         numeric,
    valuta         text NOT NULL DEFAULT 'EUR',
    omschrijving   text NOT NULL DEFAULT '',
    referentie     text NOT NULL DEFAULT '',
    regels         jsonb NOT NULL DEFAULT '[]'::jsonb,
    ruw            jsonb NOT NULL DEFAULT '{}'::jsonb,
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier_id, bookyear_id, journal_key, document_nr, soort)
);
CREATE INDEX ix_fboeking_relatie ON finance.octopus_boeking (dossier_id, relatie_octopus_id);
CREATE INDEX ix_fboeking_datum   ON finance.octopus_boeking (document_datum);
CREATE INDEX ix_fboeking_journal ON finance.octopus_boeking (dossier_id, journal_key);

-- Grants expliciet per rol (les van migratie 031/056): lezen voor de
-- dashboards, schrijven alleen voor de sync via medewerker_writer.
GRANT USAGE ON SCHEMA finance TO portal, communicatie, kosten, vermogen, medewerker_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA finance TO portal, communicatie, kosten, vermogen;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA finance TO medewerker_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA finance
    GRANT SELECT ON TABLES TO portal, communicatie, kosten, vermogen;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('octopus_spiegel', 'Octopus-spiegel',
     'De automatische kopie van de Octopus-boekhouddata (boekjaren en boekingen per dossier) in het finance-schema, ververst door de poller in de organisatie-app. Octopus blijft de bron van waarheid: de spiegel is alleen-lezen richting Octopus en de sync-status toont per dossier hoe vers de data is. Een dag stilstand is een signaal, geen stilte.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
