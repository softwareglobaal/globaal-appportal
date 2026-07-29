-- 092: Financien Elevait (finance-agent fase 1)
-- Aanleiding: ontwerp finance-agent, besluiten Shaniel 2026-07-28. Register
-- van ALLE uitgaven van Elevait: terugkerend (abonnement), eenmalig (uitgave)
-- en LLM-verbruik per agent per dag (llm_verbruik, gevoed door de agents
-- zelf). Bedragen zijn alleen zichtbaar op de interne pagina
-- (intern.elevaitnv.com); uitgave en llm_verbruik komen bewust NIET in de
-- Second Brain-graaf, abonnementen wel maar zonder bedrag (de graaf is
-- breder zichtbaar). Rechten lopen mee via de default privileges van 083.

CREATE TABLE IF NOT EXISTS elevait.abonnement (
    id            bigserial PRIMARY KEY,
    leverancier   text NOT NULL,
    omschrijving  text NOT NULL DEFAULT '',
    bedrag        numeric(12,2),  -- NULL = PM, bedrag nog niet vastgesteld
    valuta        text NOT NULL DEFAULT 'EUR'
                  CHECK (valuta IN ('EUR', 'USD', 'SRD')),
    periode       text NOT NULL DEFAULT 'maand'
                  CHECK (periode IN ('maand', 'jaar')),
    verlengdatum  date,
    categorie     text NOT NULL DEFAULT 'overig'
                  CHECK (categorie IN ('infrastructuur', 'software', 'llm',
                                       'marketing', 'juridisch', 'overig')),
    actief        boolean NOT NULL DEFAULT true,
    bron          text NOT NULL DEFAULT 'mens',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS elevait.uitgave (
    id            bigserial PRIMARY KEY,
    datum         date NOT NULL,
    leverancier   text NOT NULL,
    omschrijving  text NOT NULL DEFAULT '',
    bedrag        numeric(12,2) NOT NULL,
    valuta        text NOT NULL DEFAULT 'EUR'
                  CHECK (valuta IN ('EUR', 'USD', 'SRD')),
    categorie     text NOT NULL DEFAULT 'overig'
                  CHECK (categorie IN ('hardware', 'diensten', 'marketing',
                                       'juridisch', 'overig')),
    bron          text NOT NULL DEFAULT 'mens',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_elevait_uitgave_datum ON elevait.uitgave (datum);

-- Een rij per dag per agent per model; de agents tellen er zelf bij op
CREATE TABLE IF NOT EXISTS elevait.llm_verbruik (
    id          bigserial PRIMARY KEY,
    dag         date NOT NULL,
    agent       text NOT NULL,
    model       text NOT NULL,
    aanroepen   integer NOT NULL DEFAULT 0,
    tokens_in   bigint NOT NULL DEFAULT 0,
    tokens_uit  bigint NOT NULL DEFAULT 0,
    kosten_usd  numeric(12,4) NOT NULL DEFAULT 0,
    UNIQUE (dag, agent, model)
);

-- Startregistraties (besluiten 2026-07-28); bedrag NULL = PM
INSERT INTO elevait.abonnement (leverancier, omschrijving, valuta, periode, categorie)
SELECT 'one.com', 'Domein en e-mail elevaitnv.com', 'EUR', 'jaar', 'infrastructuur'
WHERE NOT EXISTS (SELECT 1 FROM elevait.abonnement WHERE leverancier = 'one.com');

INSERT INTO elevait.abonnement (leverancier, omschrijving, valuta, periode, categorie)
SELECT 'Globaal', 'Interne verrekening gedeelde infrastructuur (VM en mail-infra)', 'EUR', 'maand', 'infrastructuur'
WHERE NOT EXISTS (SELECT 1 FROM elevait.abonnement WHERE leverancier = 'Globaal');

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('kostensprong', 'Kostensprong',
   'Signaal van de finance-agent: het dagverbruik van een agent wijkt sterk af van zijn eigen gemiddelde over de voorgaande dagen, het klassieke teken van een agent in een lus. Verschijnt op het Kosten-tabblad en gaat als e-mail naar het vaste interne adres.')
ON CONFLICT (sleutel) DO NOTHING;
