-- 181: HR service desk & middelen (hr.globaal.be/servicedesk).
--
-- Waarom: HR vervangt de QuickView-Excel (werktijden, lockers, sleutels) en
-- de bruikleenlijst door een pagina op het platform (globaal-hr,
-- app/servicedesk_*.py). De app maakt zijn tabellen bij het eerste bezoek
-- zelf aan, maar hr_app heeft geen CREATE op schema hr ("permission denied
-- for schema hr", 01-10-2026). Vandaar deze migratie. De tabeldefinities
-- zijn letterlijk servicedesk_db.SCHEMA uit globaal-hr; bestaan de tabellen,
-- dan slaat de app zijn eigen DDL over en zet hij alleen de lege lijsten neer.
--
-- Een nieuwe kolom in de pagina is geen migratie: de waarden staan als jsonb
-- in hr.sd_rij. Alleen een wijziging aan deze tabellen zelf hoort hier.
--
-- Schema hr: namen en werktijden, dus dezelfde afspraak als de rest van hr:
-- de AI-lagen lezen deze tabellen niet. Het portaal krijgt hier niets.
-- hr_app mag wel verwijderen: een regel of lijst weghalen kan in de pagina
-- (anders dan in de personeelsadministratie).

CREATE TABLE IF NOT EXISTS hr.sd_lijst (
  id              serial PRIMARY KEY,
  titel           text NOT NULL,
  icoon           text NOT NULL DEFAULT '',
  omschrijving    text NOT NULL DEFAULT '',
  kolommen        jsonb NOT NULL DEFAULT '[]'::jsonb,
  instelling      jsonb NOT NULL DEFAULT '{}'::jsonb,
  volgorde        int  NOT NULL DEFAULT 0,
  gewijzigd_door  text NOT NULL DEFAULT '',
  gewijzigd_op    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hr.sd_rij (
  id              serial PRIMARY KEY,
  lijst_id        int NOT NULL REFERENCES hr.sd_lijst(id) ON DELETE CASCADE,
  data            jsonb NOT NULL DEFAULT '{}'::jsonb,
  gearchiveerd    boolean NOT NULL DEFAULT false,
  volgorde        int NOT NULL DEFAULT 0,
  aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
  gewijzigd_door  text NOT NULL DEFAULT '',
  gewijzigd_op    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sd_rij_lijst ON hr.sd_rij (lijst_id, volgorde, id);

CREATE TABLE IF NOT EXISTS hr.sd_log (
  id       serial PRIMARY KEY,
  wanneer  timestamptz NOT NULL DEFAULT now(),
  door     text NOT NULL DEFAULT '',
  wat      text NOT NULL
);

-- Rechten: de app verbindt als hr_app.
GRANT USAGE ON SCHEMA hr TO hr_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON hr.sd_lijst, hr.sd_rij, hr.sd_log TO hr_app;
GRANT USAGE, SELECT ON SEQUENCE hr.sd_lijst_id_seq, hr.sd_rij_id_seq, hr.sd_log_id_seq TO hr_app;
