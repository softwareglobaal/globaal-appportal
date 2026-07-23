-- 079: schema `items` — verkoop-etalage tweedehands ICT met AI-taxatie.
-- Beheer-tegel (items.globaal.be, forward-auth) schrijft; publieke verkoop-app
-- (poort 8770) leest. Foto's staan als BESTANDEN op de bind-mount ./items-data
-- (/data/fotos in de container); in de DB enkel het pad + metadata.
-- Eigen LOGIN-rol items_writer (wachtwoord via ALTER ROLE op de VM).

CREATE SCHEMA IF NOT EXISTS items;

CREATE TABLE IF NOT EXISTS items.products (
    id                      bigserial PRIMARY KEY,
    sku                     text,
    status                  text NOT NULL DEFAULT 'concept'
                             CHECK (status IN ('concept','onderzoek','te_controleren',
                                               'live','gereserveerd','verkocht','gearchiveerd')),
    merk                    text,
    model                   text,
    serienummer             text,
    ean                     text,
    categorie               text,
    conditie                text,
    conditie_notities       text,
    titel                   text,
    omschrijving            text,
    specs                   jsonb NOT NULL DEFAULT '{}'::jsonb,
    prijs_voorstel_cents    integer,
    prijs_min_cents         integer,
    prijs_max_cents         integer,
    prijs_definitief_cents  integer,
    munt                    text NOT NULL DEFAULT 'EUR',
    goedgekeurd_door        text,
    goedgekeurd_op          timestamptz,
    gepubliceerd_op         timestamptz,
    aangemaakt_op           timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_items_products_status ON items.products (status);

CREATE TABLE IF NOT EXISTS items.product_images (
    id          bigserial PRIMARY KEY,
    product_id  bigint NOT NULL REFERENCES items.products(id) ON DELETE CASCADE,
    bestand     text NOT NULL,           -- relatief pad onder /data/fotos
    is_primair  boolean NOT NULL DEFAULT false,
    volgorde    integer NOT NULL DEFAULT 0,
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_items_images_product ON items.product_images (product_id);

CREATE TABLE IF NOT EXISTS items.valuations (
    id                  bigserial PRIMARY KEY,
    product_id          bigint NOT NULL REFERENCES items.products(id) ON DELETE CASCADE,
    model_gebruikt      text,
    prijs_voorstel_cents integer,
    prijs_min_cents     integer,
    prijs_max_cents     integer,
    munt                text NOT NULL DEFAULT 'EUR',
    vertrouwen          text,
    redenering          text,
    ruwe_respons        jsonb,
    input_tokens        integer NOT NULL DEFAULT 0,
    output_tokens       integer NOT NULL DEFAULT 0,
    cache_read_tokens   integer NOT NULL DEFAULT 0,
    cache_write_tokens  integer NOT NULL DEFAULT 0,
    web_searches        integer NOT NULL DEFAULT 0,
    kosten_usd          double precision NOT NULL DEFAULT 0,
    aangemaakt_op       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_items_valuations_product ON items.valuations (product_id);

CREATE TABLE IF NOT EXISTS items.valuation_sources (
    id            bigserial PRIMARY KEY,
    valuation_id  bigint NOT NULL REFERENCES items.valuations(id) ON DELETE CASCADE,
    bron          text,
    url           text,
    titel         text,
    prijs_cents   integer,
    conditie      text,
    type          text
);
CREATE INDEX IF NOT EXISTS ix_items_sources_val ON items.valuation_sources (valuation_id);

-- App-rol: leest en schrijft eigen schema. Wachtwoord later via ALTER ROLE op de VM.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'items_writer') THEN
        CREATE ROLE items_writer LOGIN;
    END IF;
END $$;

-- Tabellen worden door de authentik-superuser aangemaakt -> default privileges op die rol.
GRANT USAGE ON SCHEMA items TO items_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA items TO items_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA items TO items_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA items
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO items_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA items
    GRANT USAGE, SELECT ON SEQUENCES TO items_writer;

-- Leesrol portal mag meekijken (consistent met andere spoke-schema's).
GRANT USAGE ON SCHEMA items TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA items TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA items
    GRANT SELECT ON TABLES TO portal;
