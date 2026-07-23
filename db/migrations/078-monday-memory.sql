-- 078: memory voor het Monday-zandbak-dashboard (wens Shaniel/Mehdi 2026-07-23).
-- Drie soorten geheugen in een eigen schema, plus een experimentenlog:
--   A beslissing   - besluiten over het ideale Monday-bord
--   B sessie       - wat AI of mens per sessie deed (context over sessies heen)
--   C definitie    - het definitieboek: een woord, een betekenis
-- Bewust in de gedeelde Postgres zodat het portaal en Graphify er bij kunnen.

CREATE SCHEMA IF NOT EXISTS monday;

CREATE TABLE IF NOT EXISTS monday.beslissing (
    id         bigserial PRIMARY KEY,
    titel      text NOT NULL,
    inhoud     text NOT NULL DEFAULT '',
    status     text NOT NULL DEFAULT 'open' CHECK (status IN ('open','vast','herzien')),
    auteur     text NOT NULL DEFAULT '',
    aangemaakt timestamptz NOT NULL DEFAULT now(),
    bijgewerkt timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS monday.definitie (
    term       text PRIMARY KEY,
    betekenis  text NOT NULL,
    context    text NOT NULL DEFAULT '',   -- waar het geldt (bord, kolom, afdeling)
    bijgewerkt timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS monday.sessie (
    id          bigserial PRIMARY KEY,
    actor       text NOT NULL DEFAULT '',   -- wie/wat: ai of een persoon
    soort       text NOT NULL DEFAULT '',   -- experiment, analyse, opbouw
    samenvatting text NOT NULL DEFAULT '',
    ts          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS monday.experiment (
    id        bigserial PRIMARY KEY,
    titel     text NOT NULL,
    hypothese text NOT NULL DEFAULT '',
    uitkomst  text NOT NULL DEFAULT '',
    status    text NOT NULL DEFAULT 'lopend' CHECK (status IN ('lopend','geslaagd','mislukt')),
    ts        timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monday_app') THEN
        CREATE ROLE monday_app LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA monday TO monday_app, portal;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA monday TO monday_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA monday TO monday_app;
GRANT SELECT ON ALL TABLES IN SCHEMA monday TO portal;
