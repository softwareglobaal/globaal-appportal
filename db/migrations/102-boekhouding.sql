-- 102: schema `boekhouding` - de twee finance-werkstromen van Joan, overgenomen
-- van haar lokale scripts (Facturatie en OV analyse, aanlevering 2026-07-30) en
-- herbouwd als stack-app op boekhouding.globaal.be.
--
-- Twee werkstromen, een schema:
--   Factureren  = verkoopfacturen aanmaken in Octopus vanuit Monday. Octopus
--                 blijft de bron van waarheid voor de factuur zelf; wij houden
--                 hier alleen bij wat deze app heeft aangemaakt en wie erop
--                 drukte, zodat een factuur altijd terug te voeren is op een mens.
--   Openstaand  = openstaande posten en de wachtrekening per firma opvolgen.
--                 De posten zelf zijn een spiegel (weggooibaar, elke verversing
--                 opnieuw); de notities van mensen leven apart en overleven dat.
--
-- Lagen (ontwerp-prompt docs/prompt-dashboard-ontwerp.md):
--   entiteiten = firma, post, markering, factuur
--   relaties   = firma.kern_firma_id (naar kern), post/markering.dossier_id,
--                factuur.dossier_id
--   views      = queries in de app, niets opgeslagen
--
-- Bewust NIET in de graaf (`_GRAAF_SCHEMAS` in graaf.py blijft ongewijzigd):
-- post, factuur en verversing zijn transactioneel of logboek, markering is een
-- notitie, en firma is dezelfde firma-laag die de graaf al tekent via
-- kosten.octopus_boekhouding (migratie 059). Een schema toevoegen dat alleen
-- dubbele of transactionele knopen oplevert maakt de graaf drukker, niet beter.
--
-- Discipline: financial management, met accounts receivable eronder.
-- Eigen LOGIN-rol boekhouding_writer (wachtwoord via ALTER ROLE op de VM).

CREATE SCHEMA IF NOT EXISTS boekhouding;

-- Firma: de Octopus-dossiers waar deze app mee werkt. Het dossiernummer is de
-- sleutel omdat dat is wat de Octopus-API teruggeeft; kern_firma_id is de brug
-- naar de centrale master data. Twee losse schakelaars, want ze staan los van
-- elkaar: een firma kan wel gevolgd worden op openstaande posten zonder dat er
-- vanuit Monday voor gefactureerd wordt.
CREATE TABLE IF NOT EXISTS boekhouding.firma (
    dossier_id          integer PRIMARY KEY,
    naam                text NOT NULL,
    kern_firma_id       uuid REFERENCES kern.firma(id) ON DELETE SET NULL,
    betaaltermijn_dagen smallint NOT NULL DEFAULT 7,
    wachtrekening       integer NOT NULL DEFAULT 599999,
    volgen              boolean NOT NULL DEFAULT true,
    factureren          boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS ix_boekhouding_firma_kern
    ON boekhouding.firma (kern_firma_id);

-- Post: spiegel van een openstaande leveranciers- of klantpost, of een regel op
-- de wachtrekening. Wordt bij elke verversing vervangen. `sleutel` is het
-- documentnummer zoals Octopus het teruggeeft: stabiel over verversingen heen,
-- en daarmee de haak waar een markering aan hangt.
CREATE TABLE IF NOT EXISTS boekhouding.post (
    id            bigserial PRIMARY KEY,
    dossier_id    integer NOT NULL REFERENCES boekhouding.firma(dossier_id) ON DELETE CASCADE,
    soort         text NOT NULL CHECK (soort IN ('leverancier', 'klant', 'wachtrekening')),
    sleutel       text NOT NULL,
    datum         date,
    verval        date,
    commentaar    text,
    bedrag        numeric(14,2) NOT NULL DEFAULT 0,
    debet         numeric(14,2) NOT NULL DEFAULT 0,
    credit        numeric(14,2) NOT NULL DEFAULT 0,
    relatie_id    text,
    relatie_naam  text,
    relatie_soort text,
    opgehaald_op  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dossier_id, soort, sleutel)
);
CREATE INDEX IF NOT EXISTS ix_boekhouding_post_firma
    ON boekhouding.post (dossier_id, soort);

-- Markering: wat een mens aan een post hangt. Bewust een aparte tabel, want de
-- posten worden bij elke verversing weggegooid en dit mag nooit meeverdwijnen.
-- Dat ging in de lokale voorloper mis: alles stond in een enkel JSON-bestand.
CREATE TABLE IF NOT EXISTS boekhouding.markering (
    dossier_id     integer NOT NULL REFERENCES boekhouding.firma(dossier_id) ON DELETE CASCADE,
    soort          text NOT NULL,
    sleutel        text NOT NULL,
    opmerking      text NOT NULL DEFAULT '',
    actie_door     text NOT NULL DEFAULT '',
    uitgesloten    boolean NOT NULL DEFAULT false,
    gewijzigd_op   timestamptz NOT NULL DEFAULT now(),
    gewijzigd_door text NOT NULL DEFAULT '',
    PRIMARY KEY (dossier_id, soort, sleutel)
);

-- Factuur: het logboek van wat deze app in Octopus heeft aangemaakt. Geen
-- spiegel van Octopus (dat blijft de bron), maar het antwoord op de vraag
-- "wie heeft dit laten aanmaken en op basis waarvan". De unieke sleutel op
-- dagboek plus documentnummer maakt dubbel aanmaken onmogelijk, ook als twee
-- mensen tegelijk op de knop drukken.
CREATE TABLE IF NOT EXISTS boekhouding.factuur (
    id              bigserial PRIMARY KEY,
    dossier_id      integer NOT NULL REFERENCES boekhouding.firma(dossier_id),
    dagboek         text NOT NULL,
    documentnummer  integer NOT NULL,
    factuurnummer   text NOT NULL,
    referentie      text NOT NULL DEFAULT '',
    monday_board_id text NOT NULL DEFAULT '',
    monday_item_id  text NOT NULL DEFAULT '',
    projectnummer   text NOT NULL DEFAULT '',
    omschrijving    text NOT NULL DEFAULT '',
    percentage      smallint,
    meerwerk        boolean NOT NULL DEFAULT false,
    bedrag_excl     numeric(14,2),
    bedrag_incl     numeric(14,2),
    relatie_id      text NOT NULL DEFAULT '',
    klantnaam       text NOT NULL DEFAULT '',
    aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
    aangemaakt_door text NOT NULL,
    UNIQUE (dossier_id, dagboek, documentnummer)
);
-- Bewust nog geen partij_id naar kern.partij: die koppeling zou vandaag leeg
-- blijven en dan staat er een dode relatie in het schema en in de graaf. Zodra
-- we facturen aan partijen willen hangen is dat een eigen migratie, samen met
-- de kant in graaf.py.
CREATE INDEX IF NOT EXISTS ix_boekhouding_factuur_monday
    ON boekhouding.factuur (monday_item_id);

-- Verversing: wanneer de openstaand-tab voor het laatst data ophaalde, en of
-- dat lukte. Voedt de versheidsbalk, zodat niemand ongemerkt naar oude cijfers
-- kijkt. Octopus limiteert de rapporten op 24 aanroepen per dag per dossier,
-- dus verversen is een bewuste handeling en geen achtergrondlus.
CREATE TABLE IF NOT EXISTS boekhouding.verversing (
    dossier_id   integer PRIMARY KEY REFERENCES boekhouding.firma(dossier_id) ON DELETE CASCADE,
    gestart_op   timestamptz,
    klaar_op     timestamptz,
    ok           boolean,
    aantal       integer NOT NULL DEFAULT 0,
    fout         text NOT NULL DEFAULT '',
    door         text NOT NULL DEFAULT ''
);

-- De acht dossiers uit Joan's aanlevering. Betaaltermijn 15 dagen bij
-- H-Architects, 7 elders (afspraak uit de bestaande facturatiescripts).
-- Factureren staat aan voor de vier firma's met een Monday-koppeling.
INSERT INTO boekhouding.firma (dossier_id, naam, betaaltermijn_dagen, volgen, factureren) VALUES
    (114703, 'H-Architects',      15, true, true),
    (164873, 'Energie Efficient',  7, true, true),
    (164872, 'UNABO',              7, true, true),
    (130699, 'TKN-Buro',           7, true, true),
    (181481, 'Contrax',            7, true, false),
    (108893, 'Harmonie Bouw',      7, true, false)
ON CONFLICT (dossier_id) DO NOTHING;

-- Koppeling naar de centrale firma-laag via de codes uit migratie 059.
UPDATE boekhouding.firma b
   SET kern_firma_id = f.id
  FROM kern.firma f
 WHERE f.code = CASE b.dossier_id
                    WHEN 114703 THEN 'HARC'
                    WHEN 164873 THEN 'ENEF'
                    WHEN 164872 THEN 'UNAB'
                    WHEN 130699 THEN 'TKNB'
                    WHEN 181481 THEN 'CONT'
                    WHEN 108893 THEN 'HARM'
                END
   AND b.kern_firma_id IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'boekhouding_writer') THEN
        CREATE ROLE boekhouding_writer LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA boekhouding TO boekhouding_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA boekhouding TO boekhouding_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA boekhouding TO boekhouding_writer;
GRANT USAGE ON SCHEMA kern TO boekhouding_writer;
GRANT SELECT ON kern.firma, kern.partij TO boekhouding_writer;
GRANT USAGE ON SCHEMA boekhouding TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA boekhouding TO portal;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('openstaande_post', 'Openstaande post',
     'Een verkoop- of aankoopfactuur die in Octopus nog niet volledig is afgepunt. '
     'De app boekhouding.globaal.be spiegelt ze per firma; de spiegel is weggooibaar, '
     'de notities en actiehouders die eraan hangen niet.'),
    ('wachtrekening', 'Wachtrekening',
     'Grootboekrekening 599999, waar betalingen belanden die nog niet aan een klant of '
     'leverancier gekoppeld zijn. Leeg krijgen is het doel: elke regel hoort uiteindelijk '
     'ergens anders thuis.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
