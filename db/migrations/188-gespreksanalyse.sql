-- 188: gespreksanalyse op de Xelion-transcripten (communicatie).
--
-- Mehdi, 02-10-2026: per gesprek willen we weten of ze elkaar begrepen, of
-- de klant tevreden was, waar het probleem vandaan kwam, welke acties volgen
-- en bij welk project of welke deal het gesprek hoort. Eerst op een testset
-- van twee gesprekken per lijn, gemeten tegen een referentie die een mens
-- invult; pas daarna op alles.
--
--   analyse_testset     welke gesprekken in de test zitten en waarom
--   analyse_resultaat   wat het model per gesprek gaf, per promptversie en run
--   analyse_referentie  wat een mens die het gesprek kent invulde (blind)
--
-- De prompts zelf staan in git (globaal-communicatie, prompts/); elk resultaat
-- bewaart de versie en de hash van de prompt waarmee het gemaakt is.

CREATE TABLE IF NOT EXISTS communicatie.analyse_testset (
  oid         text PRIMARY KEY,
  lijn        text NOT NULL,
  collega     text NOT NULL DEFAULT '',
  met_deal    boolean NOT NULL DEFAULT false,
  reden       text NOT NULL DEFAULT '',
  gekozen_op  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS communicatie.analyse_resultaat (
  oid            text NOT NULL,
  prompt_versie  text NOT NULL,
  prompt_hash    text NOT NULL,
  model          text NOT NULL,
  run            integer NOT NULL DEFAULT 1,
  velden         jsonb NOT NULL,
  gemaakt_op     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (oid, prompt_versie, run)
);

CREATE TABLE IF NOT EXISTS communicatie.analyse_referentie (
  oid            text PRIMARY KEY,
  velden         jsonb NOT NULL,
  ingevuld_door  text NOT NULL DEFAULT '',
  ingevuld_op    timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.analyse_testset, communicatie.analyse_resultaat,
  communicatie.analyse_referentie TO communicatie;
