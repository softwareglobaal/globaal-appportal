-- 113: verloftabellen van het HR-dashboard (schema hr, alles verlof_*)
-- Aanleiding: de app maakt dit schema sinds commit c6ece67 zelf aan bij het eerste
-- bezoek aan /verlof. Dat werkt, maar zet de tabellen buiten de migratiereeks: bouw
-- je de database opnieuw op uit db/migrations, dan ontbreken ze tot iemand toevallig
-- die pagina opent. Deze migratie is letterlijk dezelfde DDL als in app/verlof_db.py,
-- met CREATE ... IF NOT EXISTS, dus draaien is veilig ongeacht wat er al staat.
--
-- Blijft de app het ook zelf doen? Ja, en dat mag: het is idempotent en het vangt de
-- situatie op waarin het dashboard eerder draait dan de migratie.

CREATE SCHEMA IF NOT EXISTS hr;

CREATE TABLE IF NOT EXISTS hr.verlof_profiel (
  naam                    text PRIMARY KEY,
  omschrijving            text NOT NULL DEFAULT '',
  verlofrecht_per_jaar    numeric NOT NULL DEFAULT 0,
  opbouwmethode           text NOT NULL DEFAULT 'maandelijks_pro_rata',
  proeftijd_maanden       int  NOT NULL DEFAULT 0,
  kwartaalbonus           text NOT NULL DEFAULT 'ja',
  bonusdagen_per_kwartaal numeric NOT NULL DEFAULT 1,
  recht_op_bouwverlof     text NOT NULL DEFAULT 'nee',
  overdracht_positief     text NOT NULL DEFAULT 'ja',
  max_overdracht          numeric,
  overdracht_negatief     text NOT NULL DEFAULT 'ja',
  volgorde                int  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hr.verlof_regel (
  code                  text PRIMARY KEY,
  aliassen              text NOT NULL DEFAULT '',
  omschrijving          text NOT NULL DEFAULT '',
  eenheid               text NOT NULL DEFAULT 'dagen',
  afwezigheid_standaard numeric NOT NULL DEFAULT 1,
  van_saldo_af          text NOT NULL DEFAULT 'ja',
  dekking_werkgever     numeric NOT NULL DEFAULT 0,
  telt_als_ziekte       text NOT NULL DEFAULT 'nee',
  breekt_bonus          text NOT NULL DEFAULT 'nee',
  telt_als_afwezig      text NOT NULL DEFAULT 'ja',
  alleen_handmatig      text NOT NULL DEFAULT 'nee',
  actief                text NOT NULL DEFAULT 'ja',
  volgorde              int  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hr.verlof_periode (
  jaar              int  NOT NULL,
  nummer            int,
  naam              text NOT NULL,
  start             date NOT NULL,
  eind              date NOT NULL,
  kwartaal          int,
  soort             text NOT NULL DEFAULT 'periode',
  opbouw_maandfactor numeric,
  PRIMARY KEY (jaar, naam, soort)
);

CREATE TABLE IF NOT EXISTS hr.verlof_feestdag (
  datum        date PRIMARY KEY,
  omschrijving text NOT NULL DEFAULT '',
  land         text NOT NULL DEFAULT 'Suriname'
);

CREATE TABLE IF NOT EXISTS hr.verlof_medewerker (
  id                text PRIMARY KEY,
  voornaam          text NOT NULL,
  achternaam        text NOT NULL DEFAULT '',
  aliassen          text NOT NULL DEFAULT '',
  persnr_oud        text NOT NULL DEFAULT '',
  afdeling          text NOT NULL DEFAULT '',
  functie           text NOT NULL DEFAULT '',
  datum_indienst    date,
  datum_uitdienst   date,
  contracttype      text REFERENCES hr.verlof_profiel(naam),
  uren_per_week     numeric NOT NULL DEFAULT 40,
  dagen_per_week    numeric NOT NULL DEFAULT 5,
  uren_per_dag      numeric NOT NULL DEFAULT 8,
  proeftijd_maanden int,
  actief            boolean NOT NULL DEFAULT true,
  aangemaakt        timestamptz NOT NULL DEFAULT now(),
  gewijzigd_door    text NOT NULL DEFAULT ''
);

-- Overdracht uit het vorige jaar, per persoon per jaar. Wordt bij de
-- jaarafsluiting gevuld en is met de hand te corrigeren.
CREATE TABLE IF NOT EXISTS hr.verlof_overdracht (
  medewerker_id text NOT NULL REFERENCES hr.verlof_medewerker(id),
  jaar          int  NOT NULL,
  dagen         numeric NOT NULL DEFAULT 0,
  PRIMARY KEY (medewerker_id, jaar)
);

-- De canonieke tabel: een rij per persoon per dag. Volledig herschreven bij
-- elke synchronisatie, behalve de rijen met bron 'handmatig'.
CREATE TABLE IF NOT EXISTS hr.verlof_dag (
  id            bigserial PRIMARY KEY,
  medewerker_id text NOT NULL REFERENCES hr.verlof_medewerker(id),
  datum         date NOT NULL,
  code          text NOT NULL,
  periode       int,
  kwartaal      int,
  dagwaarde     numeric NOT NULL DEFAULT 0,
  uren          numeric NOT NULL DEFAULT 0,
  saldo_dagen   numeric NOT NULL DEFAULT 0,
  ziekte_dagen  numeric NOT NULL DEFAULT 0,
  breekt_bonus  boolean NOT NULL DEFAULT false,
  uren_plus     numeric NOT NULL DEFAULT 0,
  uren_min      numeric NOT NULL DEFAULT 0,
  bron          text NOT NULL DEFAULT 'kalender',
  reden         text NOT NULL DEFAULT '',
  ingevoerd_door text NOT NULL DEFAULT '',
  ingevoerd_op  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS verlof_dag_mw_datum ON hr.verlof_dag (medewerker_id, datum);

-- Zuivere saldobijstellingen. Geen afwezigheid, dus nooit in de
-- bezettingsanalyse. Het script schrijft hier nooit.
CREATE TABLE IF NOT EXISTS hr.verlof_correctie (
  id            bigserial PRIMARY KEY,
  datum         date NOT NULL,
  medewerker_id text NOT NULL REFERENCES hr.verlof_medewerker(id),
  dagen         numeric NOT NULL,
  reden         text NOT NULL DEFAULT '',
  beslist_door  text NOT NULL DEFAULT '',
  ingevoerd_op  timestamptz NOT NULL DEFAULT now()
);

-- Afgesloten jaren, overgenomen zoals ze berekend zijn. Nooit herrekend.
CREATE TABLE IF NOT EXISTS hr.verlof_historiek (
  medewerker_id text NOT NULL REFERENCES hr.verlof_medewerker(id),
  jaar          int  NOT NULL,
  recht         numeric,
  bonus         numeric,
  opgenomen     numeric,
  ziekte        numeric,
  saldo         numeric,
  formule_klopt boolean,
  PRIMARY KEY (medewerker_id, jaar)
);

-- Wat niet geplaatst kon worden bij de laatste synchronisatie.
CREATE TABLE IF NOT EXISTS hr.verlof_niet_herkend (
  id       bigserial PRIMARY KEY,
  titel    text NOT NULL DEFAULT '',
  datum    date,
  naam     text NOT NULL DEFAULT '',
  code     text NOT NULL DEFAULT '',
  reden    text NOT NULL DEFAULT '',
  gezien   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hr.verlof_log (
  id        bigserial PRIMARY KEY,
  tijdstip  timestamptz NOT NULL DEFAULT now(),
  gebruiker text NOT NULL DEFAULT '',
  actie     text NOT NULL DEFAULT '',
  details   text NOT NULL DEFAULT ''
);

-- Vorige stand van de kwartaalbonus, om een omslag te kunnen melden.
CREATE TABLE IF NOT EXISTS hr.verlof_bonus_stand (
  medewerker_id text NOT NULL REFERENCES hr.verlof_medewerker(id),
  jaar          int  NOT NULL,
  dagen         numeric NOT NULL DEFAULT 0,
  PRIMARY KEY (medewerker_id, jaar)
);

-- Rechten: de app verbindt als hr_app, het portaal leest mee (zelfde patroon als 075).
GRANT USAGE ON SCHEMA hr TO hr_app, portal;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA hr TO hr_app;
GRANT SELECT ON ALL TABLES IN SCHEMA hr TO portal;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA hr TO hr_app;
