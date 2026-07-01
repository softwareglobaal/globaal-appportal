-- 002 — Communicatie-dashboard: schema `communicatie` + centrale lijst `kern.leverancier`.
--
-- Het Communicatie-dashboard (communicatie.globaal.be) vervangt op termijn de
-- vrije-tekst-velden van het telefoonregister door échte verwijzingen naar de
-- centrale lijsten. Terminologie volgt DEFINITIEBOEK.md:
--   doel (niet "functie"), leverancier (niet "provider"), verantwoordelijke (één),
--   gebruikers (multi), factuur-/doorfactuur-firma. "Toegewezen aan" (vrije tekst)
--   verdwijnt: vervangen door verantwoordelijke + gebruikers + afdeling.
--
-- Vereist: rol `communicatie` bestaat (db/roles.sql) vóór het draaien.

-- Centrale leverancierslijst (gedeeld begrip: telefonie nu, software later).
-- Beheer (toevoegen/hernoemen/uitzetten) ligt bij de communicatie-app; verwijderen
-- kan niet — uitzetten gaat via `actief` (zacht, zoals firma/afdeling/persoon).
CREATE TABLE kern.leverancier (
    id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam   text NOT NULL UNIQUE,
    actief boolean NOT NULL DEFAULT true
);

CREATE SCHEMA communicatie;

CREATE TABLE communicatie.nummer (
    id                           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    telefoonnummer               text NOT NULL DEFAULT '',
    genormaliseerd               text NOT NULL DEFAULT '',   -- cijfers, voor dubbelcheck
    status                       varchar(20) NOT NULL DEFAULT 'Actief'
        CONSTRAINT ck_nummer_status CHECK (status IN ('Actief', 'Niet-actief', 'Onbekend')),
    doel                         text NOT NULL DEFAULT '',   -- waarvoor het nummer dient
    land                         text NOT NULL DEFAULT '',
    platform                     text NOT NULL DEFAULT '',
    type                         text NOT NULL DEFAULT '',
    omschrijving                 text NOT NULL DEFAULT '',
    aandacht                     text NOT NULL DEFAULT '',   -- leeg = geen markering
    leverancier_id               uuid REFERENCES kern.leverancier(id),
    factuur_firma_id             uuid REFERENCES kern.firma(id),      -- wie de factuur betaalt
    doorfactuur_firma_id         uuid REFERENCES kern.firma(id),      -- aan wie doorgerekend
    afdeling_id                  uuid REFERENCES kern.afdeling(id),
    verantwoordelijke_persoon_id uuid REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    aangemaakt_op                timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op                timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door              text NOT NULL DEFAULT ''
);
-- Bewust GEEN unique op genormaliseerd: de bestaande data bevat duplicaten; de app
-- blokkeert nieuwe duplicaten en markeert bestaande (net als het telefoonregister).
CREATE INDEX ix_nummer_genormaliseerd     ON communicatie.nummer (genormaliseerd);
CREATE INDEX ix_nummer_leverancier        ON communicatie.nummer (leverancier_id);
CREATE INDEX ix_nummer_factuur_firma      ON communicatie.nummer (factuur_firma_id);
CREATE INDEX ix_nummer_verantwoordelijke  ON communicatie.nummer (verantwoordelijke_persoon_id);

-- Gebruikers van een nummer (multi) — wie erop werkt/opneemt.
CREATE TABLE communicatie.nummer_gebruiker (
    nummer_id  uuid NOT NULL REFERENCES communicatie.nummer(id) ON DELETE CASCADE,
    persoon_id uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    PRIMARY KEY (nummer_id, persoon_id)
);

-- Afgeschermde inloggegevens (PIN/PUK/kaartnummer), 1-op-1 bij een nummer.
CREATE TABLE communicatie.geheim (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nummer_id     uuid NOT NULL UNIQUE REFERENCES communicatie.nummer(id) ON DELETE CASCADE,
    kaartnummer   text NOT NULL DEFAULT '',
    pin1          text NOT NULL DEFAULT '',
    puk1          text NOT NULL DEFAULT '',
    pin2          text NOT NULL DEFAULT '',
    puk2          text NOT NULL DEFAULT '',
    notitie       text NOT NULL DEFAULT '',
    bijgewerkt_op timestamptz NOT NULL DEFAULT now()
);

-- Tab 2: e-mailadressen. Adres zonder verantwoordelijke = zichtbaar "open".
CREATE TABLE communicatie.emailadres (
    id                           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    adres                        public.citext NOT NULL UNIQUE,
    firma_id                     uuid REFERENCES kern.firma(id),
    verantwoordelijke_persoon_id uuid REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    omschrijving                 text NOT NULL DEFAULT '',
    actief                       boolean NOT NULL DEFAULT true,
    aangemaakt_op                timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op                timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door              text NOT NULL DEFAULT ''
);
CREATE INDEX ix_emailadres_firma ON communicatie.emailadres (firma_id);

-- App-eigen keuzewaarden (Land/Platform/Type — géén centrale begrippen).
CREATE TABLE communicatie.lijst (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    categorie  text NOT NULL,
    waarde     text NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    UNIQUE (categorie, waarde)
);

-- ---- Rechten ---------------------------------------------------------------
-- Rol `communicatie`: leest kern (dropdowns), schrijft enkel het eigen schema,
-- plus beheer van de leverancierslijst (INSERT/UPDATE, geen DELETE — zacht uitzetten).
GRANT USAGE ON SCHEMA kern TO communicatie;
GRANT SELECT ON kern.persoon, kern.afdeling, kern.firma, kern.leverancier TO communicatie;
GRANT INSERT, UPDATE ON kern.leverancier TO communicatie;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kern GRANT SELECT ON TABLES TO communicatie;

GRANT USAGE ON SCHEMA communicatie TO communicatie;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA communicatie TO communicatie;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA communicatie
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO communicatie;

-- Leesrol `portal` mag meekijken (360°-profiel, latere dashboards).
GRANT USAGE ON SCHEMA communicatie TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA communicatie TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA communicatie
    GRANT SELECT ON TABLES TO portal;
