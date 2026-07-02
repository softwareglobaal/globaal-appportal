-- 016 — schema `vermogen`: panden, verzekeringen, leningen & leasingen, syndicus.
--
-- Skelet voor het Vermogens-dashboard (meeting 2026-07-02; bank vraagt overzicht,
-- Mehdi levert de data). Alles gelinkt: eigenaars/verzekeringnemers → kern.firma,
-- verzekeringen en leningen → pand, pand → syndicus. Huurders/verzekeraars/banken
-- zijn nog tekst — worden links zodra de klant-/externe-partij-entiteit bestaat.
--
-- LET OP: vereist de rol `vermogen` (db/roles.sql) — maak die eerst aan:
--   docker compose exec postgresql psql -U authentik -d appportal
--   dan: CREATE ROLE vermogen LOGIN PASSWORD '<zelf gekozen>';  (niet via chat delen)

CREATE SCHEMA vermogen;

CREATE TABLE vermogen.syndicus (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam            text NOT NULL,
    telefoon        text NOT NULL DEFAULT '',
    email           text NOT NULL DEFAULT '',
    jaarvergadering text NOT NULL DEFAULT '',   -- bv. "elk jaar in maart"
    documenten      text NOT NULL DEFAULT '',   -- waar de documenten te vinden zijn
    omschrijving    text NOT NULL DEFAULT '',
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

CREATE TABLE vermogen.pand (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam               text NOT NULL,            -- roepnaam, bv. "Pontstraat 72"
    adres              text NOT NULL DEFAULT '',
    type               text NOT NULL DEFAULT '', -- Appartement/Huis/Kantoor/…
    eigenaar_firma_id  uuid REFERENCES kern.firma(id),
    aankoopbedrag      numeric(14,2),
    aankoopdatum       date,
    deel_van_gebouw    text NOT NULL DEFAULT '', -- leeg = zelfstandig pand
    syndicus_id        uuid REFERENCES vermogen.syndicus(id),
    huurder            text NOT NULL DEFAULT '', -- externe partij; later klant-link
    maandhuur          numeric(12,2),
    huurcontract_start date,
    huurcontract_einde date,
    omschrijving       text NOT NULL DEFAULT '',
    actief             boolean NOT NULL DEFAULT true,
    bijgewerkt_op      timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door    text NOT NULL DEFAULT ''
);
CREATE INDEX ix_pand_eigenaar ON vermogen.pand (eigenaar_firma_id);
CREATE INDEX ix_pand_syndicus ON vermogen.pand (syndicus_id);

CREATE TABLE vermogen.lening (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    soort           text NOT NULL DEFAULT 'Lening'
        CONSTRAINT ck_lening_soort CHECK (soort IN ('Lening', 'Leasing')),
    verstrekker     text NOT NULL DEFAULT '',    -- bank / leasingmaatschappij
    firma_id        uuid REFERENCES kern.firma(id),   -- wie de verplichting aanging
    pand_id         uuid REFERENCES vermogen.pand(id), -- leeg = niet aan een pand
    hoofdsom        numeric(14,2),
    rente_pct       numeric(6,3),
    maandaflossing  numeric(12,2),
    startdatum      date,
    einddatum       date,
    omschrijving    text NOT NULL DEFAULT '',
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);
CREATE INDEX ix_lening_firma ON vermogen.lening (firma_id);
CREATE INDEX ix_lening_pand  ON vermogen.lening (pand_id);

CREATE TABLE vermogen.verzekering (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    soort                text NOT NULL DEFAULT '',  -- Brand/BA/ABR/Auto/…
    verzekeraar          text NOT NULL DEFAULT '',
    polisnummer          text NOT NULL DEFAULT '',
    firma_id             uuid REFERENCES kern.firma(id),    -- verzekeringnemer
    pand_id              uuid REFERENCES vermogen.pand(id), -- leeg = niet pand-gebonden
    object               text NOT NULL DEFAULT '',  -- bv. nummerplaat (auto's zijn nog geen entiteit)
    startdatum           date,
    einddatum            date,
    opzegtermijn_maanden integer,
    jaarpremie           numeric(12,2),
    omschrijving         text NOT NULL DEFAULT '',
    actief               boolean NOT NULL DEFAULT true,
    bijgewerkt_op        timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door      text NOT NULL DEFAULT ''
);
CREATE INDEX ix_verzekering_firma ON vermogen.verzekering (firma_id);
CREATE INDEX ix_verzekering_pand  ON vermogen.verzekering (pand_id);

-- ---- Rechten ---------------------------------------------------------------
-- Rol `vermogen`: leest kern (dropdowns + woordenboek), schrijft eigen schema.
GRANT USAGE ON SCHEMA kern TO vermogen;
GRANT SELECT ON kern.firma, kern.persoon, kern.afdeling, kern.leverancier, kern.definitie TO vermogen;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kern GRANT SELECT ON TABLES TO vermogen;

GRANT USAGE ON SCHEMA vermogen TO vermogen;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA vermogen TO vermogen;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA vermogen
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vermogen;

-- Leesrol `portal` mag meekijken (Second Brain, briefing-signalen zoals
-- "verzekering vervalt < 90 dagen" — de graph kan hier later zó op aansluiten).
GRANT USAGE ON SCHEMA vermogen TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA vermogen TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA vermogen
    GRANT SELECT ON TABLES TO portal;
