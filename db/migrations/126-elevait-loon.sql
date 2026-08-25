-- 126: Loonvoorbereiding Elevait (HR-agent, urenverwerking)
-- Aanleiding: gesprek Shaniel 25-08-2026. De uren staan al in DeskTime
-- (schema hr), maar de verwerking naar een betaalbare loonlijst duurt te
-- lang, waardoor betalingen te laat komen. De HR-agent sluit de periode af
-- (16e vorige maand t/m 15e deze maand), zet per medewerker een concept-
-- loonregel klaar zodra de DeskTime-data vast is (7 dagen na de 15e), en
-- bewaakt de betaaldeadline (eind van de maand).
--
-- Loonregels (deterministisch, geen taalmodel):
--   - 8 werkuren per dag standaard; alles erboven is overwerk tegen HETZELFDE
--     uurtarief. Overwerk telt pas na autorisatie door een mens.
--   - Op een nationale feestdag krijgt de medewerker zijn rooster-uren
--     betaald, ook afwezig; elk gewerkt uur telt als een extra uur. Feestdag-
--     werk telt pas na autorisatie.
--
-- BEWUST AFGESCHERMD: bedragen zijn beloningsdata (VOOR-HR.md) en mogen niet
-- in de Second Brain-graaf. Migratie 083 geeft de portal-rol via default
-- privileges automatisch SELECT op elke nieuwe elevait-tabel; dat recht wordt
-- hieronder voor de loon-tabellen expliciet teruggenomen. De agent leest
-- schema hr uitsluitend READ-ONLY.

-- 1. Leesrecht op de uren- en verlofbron (schema hr), read-only.
GRANT USAGE ON SCHEMA hr TO elevait_app;
GRANT SELECT ON hr.dag, hr.medewerker, hr.handmatig,
                hr.verlof_dag, hr.verlof_regel, hr.verlof_medewerker,
                hr.verlof_feestdag TO elevait_app;

-- 2. De loonperiode: een rij per periode, met de status van de afhandeling.
CREATE TABLE IF NOT EXISTS elevait.loonperiode (
    id             bigserial PRIMARY KEY,
    jaar           int  NOT NULL,
    maand          int  NOT NULL,          -- maand waarin de periode eindigt (de 15e)
    start          date NOT NULL,
    eind           date NOT NULL,
    data_vast_op   date NOT NULL,          -- eind + herzieningsvenster (7 dagen)
    betaaldatum    date,                   -- eind van de maand; bewaakt de deadline
    status         text NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'concept', 'vastgesteld', 'uitbetaald')),
    vastgesteld_op   timestamptz,
    vastgesteld_door text NOT NULL DEFAULT '',
    aangemaakt_op  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (jaar, maand)
);

-- 3. De concept-loonregel per medewerker. desktime_id koppelt aan hr.dag;
--    de naam staat erbij zodat de lijst leesbaar is zonder join.
CREATE TABLE IF NOT EXISTS elevait.loonregel (
    id                 bigserial PRIMARY KEY,
    periode_id         bigint NOT NULL REFERENCES elevait.loonperiode(id) ON DELETE CASCADE,
    desktime_id        text NOT NULL,
    naam               text NOT NULL DEFAULT '',
    reguliere_uren     numeric(8,2) NOT NULL DEFAULT 0,
    overwerk_uren      numeric(8,2) NOT NULL DEFAULT 0,   -- geautoriseerd
    feestdag_werk_uren numeric(8,2) NOT NULL DEFAULT 0,   -- geautoriseerd
    doorbetaald_uren   numeric(8,2) NOT NULL DEFAULT 0,   -- verlof/ziekte + feestdag-basis
    bedrag             numeric(12,2),                     -- NULL = tarief ontbreekt nog
    valuta             text NOT NULL DEFAULT 'SRD',
    tarief_ontbreekt   boolean NOT NULL DEFAULT false,
    compleet           boolean NOT NULL DEFAULT false,    -- geen open autorisatie meer
    signalen           jsonb NOT NULL DEFAULT '[]'::jsonb,
    berekend_op        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (periode_id, desktime_id)
);
CREATE INDEX IF NOT EXISTS ix_elevait_loonregel_periode
    ON elevait.loonregel (periode_id);

-- 4. De autorisatie-kanttekeningen achter de twee knoppen. Eén rij per
--    kandidaat (overwerk-dag of feestdagwerk); alleen 'geautoriseerd' telt
--    mee in het loon. 'open' houdt de loonregel incompleet.
CREATE TABLE IF NOT EXISTS elevait.loon_autorisatie (
    id           bigserial PRIMARY KEY,
    periode_id   bigint NOT NULL REFERENCES elevait.loonperiode(id) ON DELETE CASCADE,
    desktime_id  text NOT NULL,
    datum        date NOT NULL,
    soort        text NOT NULL CHECK (soort IN ('overwerk', 'feestdag')),
    uren         numeric(8,2) NOT NULL DEFAULT 0,
    status       text NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open', 'geautoriseerd', 'geweigerd')),
    door         text NOT NULL DEFAULT '',
    besloten_op  timestamptz,
    aangemaakt_op timestamptz NOT NULL DEFAULT now(),
    UNIQUE (periode_id, desktime_id, datum, soort)
);
CREATE INDEX IF NOT EXISTS ix_elevait_loon_autorisatie_open
    ON elevait.loon_autorisatie (periode_id, status) WHERE status = 'open';

-- 4b. Uurtarief per medewerker (beloningsdata). Een nieuwe regel per
--     wijziging, nooit overschrijven, zodat de historie klopt: het geldende
--     tarief is de laatste met vanaf <= periode-einde. Zo werkt de
--     beloningslaag ook (VOOR-HR.md).
CREATE TABLE IF NOT EXISTS elevait.uurtarief (
    id           bigserial PRIMARY KEY,
    desktime_id  text NOT NULL,
    uurtarief    numeric(12,2) NOT NULL,
    valuta       text NOT NULL DEFAULT 'SRD' CHECK (valuta IN ('EUR','USD','SRD')),
    vanaf        date NOT NULL,
    door         text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_elevait_uurtarief_mw
    ON elevait.uurtarief (desktime_id, vanaf DESC);

-- 5. Beloningsdata afschermen van de graaf. 083 gaf portal default SELECT op
--    schema elevait; neem dat terug voor deze drie tabellen én zet de default
--    zo dat een latere loon-tabel het ook niet automatisch krijgt.
REVOKE SELECT ON elevait.loonperiode, elevait.loonregel,
                 elevait.loon_autorisatie, elevait.uurtarief FROM portal;

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('loonperiode', 'Loonperiode',
   'De periode waarover loon wordt berekend: van de 16e van de vorige maand tot en met de 15e van deze maand. De DeskTime-uren zijn pas vast 7 dagen na de 15e; daarom zet de HR-agent de concept-loonlijst rond de 22e klaar, ruim voor de uitbetaling eind van de maand.'),
  ('loonautorisatie', 'Loonautorisatie',
   'Overwerk (uren boven het dagrooster) en werk op een nationale feestdag worden uit DeskTime gedetecteerd maar tellen pas mee in het loon nadat een mens ze goedkeurt. Per geval twee knoppen: geautoriseerd of geweigerd. Zolang er nog een kanttekening openstaat, is de loonregel niet compleet.')
ON CONFLICT (sleutel) DO NOTHING;
