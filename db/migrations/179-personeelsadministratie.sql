-- 179: personeelsadministratie (hr.globaal.be/personeel, domein 4.1).
--
-- Waarom: HR vervangt de Excel-personeelschecklijst door een pagina op het
-- platform (globaal-hr, app/personeel_*.py). 4.1 is de eigenaar van de
-- persoon: hier wordt een medewerker aangemaakt, gewijzigd en uit dienst
-- gezet; andere dashboards lezen het register dat de app wegschrijft.
--
-- De app kon deze tabellen niet zelf aanmaken: hr_app heeft geen CREATE op
-- schema hr of op de database (30-09-2026 gezien op de VM). Vandaar deze
-- migratie. De tabeldefinities zijn letterlijk personeel_db.SCHEMA uit
-- globaal-hr; wijzigt daar een veld, dan hoort er een nieuwe migratie bij.
--
-- Eigen schema, niet hr: de migraties die het portaal leesrecht geven op
-- alles in hr (075, 113) mogen deze tabellen met adres, bankrekening en
-- ID-nummer niet raken. Het portaal krijgt hier niets. De AI-lagen lezen
-- dit schema niet (zelfde afspraak als hr en loon). Geen salaris: dat
-- blijft in loon.
--
-- Niets wordt verwijderd: hr_app krijgt geen DELETE of TRUNCATE, en op het
-- mutatielogboek alleen SELECT en INSERT. Daarbovenop weigert een trigger
-- elke UPDATE, DELETE en TRUNCATE op het logboek, ook voor de eigenaar.

CREATE SCHEMA IF NOT EXISTS personeel;

CREATE TABLE IF NOT EXISTS personeel.pa_instelling (
  sleutel  text PRIMARY KEY,
  waarde   jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS personeel.pa_rooster (
  code           text PRIMARY KEY,
  omschrijving   text,
  werktijden     text,
  pauze_minuten  int,
  werkdagen      text,
  actief         boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS personeel.pa_persoon (
  personeelsnummer text PRIMARY KEY CHECK (personeelsnummer ~ '^[0-9]{5}$'),
  achternaam text,
  voornaam text,
  roepnaam text,
  geslacht text,
  geboortedatum date,
  id_nummer text,
  adres text,
  woonplaats text,
  district text,
  telefoon text,
  email text,
  noodcontact text,
  bank text,
  valuta text,
  rekeningnummer text,
  entiteit text,
  afdelingscode text,
  locatie text,
  functie text,
  leidinggevende text,
  status text,
  in_dienst date,
  uit_dienst date,
  reden_uit_dienst text,
  uitdienst_verwerkt boolean NOT NULL DEFAULT false,
  contractvorm text,
  uren_per_week numeric(6,2),
  rooster text,
  werktijden text,
  pauze_minuten int,
  werktijden_zaterdag text,
  flexibel boolean NOT NULL DEFAULT false,
  proeftijd_tot date,
  opleiding text,
  verzekering text,
  verzekering_van date,
  verzekering_tot date,
  dossierpad text,
  opmerking text,
  aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
  gewijzigd_op    timestamptz NOT NULL DEFAULT now(),
  gewijzigd_door  text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS personeel.pa_contract (
  id serial PRIMARY KEY,
  personeelsnummer text NOT NULL REFERENCES personeel.pa_persoon(personeelsnummer),
  volgnummer int,
  soort text,
  van date,
  tot date,
  proeftijd_tot date,
  entiteit text,
  functie text,
  afdelingscode text,
  locatie text,
  uren_per_week numeric(6,2),
  rooster text,
  werktijden text,
  pauze_minuten int,
  opzegtermijn text,
  getekend boolean NOT NULL DEFAULT false,
  getekend_op date,
  bestand text,
  opmerking text,
  beeindigd_op date,
  reden_beeindiging text,
  aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
  aangemaakt_door text NOT NULL DEFAULT '',
  UNIQUE (personeelsnummer, volgnummer)
);

CREATE TABLE IF NOT EXISTS personeel.pa_overeenkomst (
  id serial PRIMARY KEY,
  personeelsnummer text NOT NULL REFERENCES personeel.pa_persoon(personeelsnummer),
  soort text,
  omschrijving text,
  contract_volgnummer int,
  datum date,
  geldig_tot date,
  getekend boolean NOT NULL DEFAULT false,
  getekend_op date,
  bestand text,
  beeindigd_op date,
  aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
  aangemaakt_door text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS personeel.pa_dossier (
  personeelsnummer text NOT NULL REFERENCES personeel.pa_persoon(personeelsnummer),
  item          text NOT NULL,
  aanwezig      boolean NOT NULL DEFAULT false,
  opmerking     text,
  gewijzigd_op  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (personeelsnummer, item)
);

CREATE TABLE IF NOT EXISTS personeel.pa_gesprek (
  id serial PRIMARY KEY,
  personeelsnummer text NOT NULL REFERENCES personeel.pa_persoon(personeelsnummer),
  soort text,
  gepland date,
  gehouden date,
  status text,
  met text,
  notitie text,
  aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
  aangemaakt_door text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS personeel.pa_waarschuwing (
  id serial PRIMARY KEY,
  personeelsnummer text NOT NULL REFERENCES personeel.pa_persoon(personeelsnummer),
  datum date,
  soort text,
  omschrijving text,
  geldig_tot date,
  status text,
  aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
  aangemaakt_door text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS personeel.pa_mutatie (
  id                bigserial PRIMARY KEY,
  tijdstip          timestamptz NOT NULL DEFAULT now(),
  personeelsnummer  text,
  onderdeel         text NOT NULL,
  veld              text NOT NULL,
  oud               text,
  nieuw             text,
  toelichting       text,
  door              text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS pa_mutatie_pn ON personeel.pa_mutatie (personeelsnummer, tijdstip);

-- Het logboek wordt nooit gewist en nooit bewerkt.
CREATE OR REPLACE FUNCTION personeel.pa_mutatie_alleen_toevoegen() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Het mutatielogboek wordt nooit gewijzigd of gewist';
END $$;
DROP TRIGGER IF EXISTS pa_mutatie_vast ON personeel.pa_mutatie;
CREATE TRIGGER pa_mutatie_vast BEFORE UPDATE OR DELETE ON personeel.pa_mutatie
  FOR EACH ROW EXECUTE FUNCTION personeel.pa_mutatie_alleen_toevoegen();
DROP TRIGGER IF EXISTS pa_mutatie_vast_truncate ON personeel.pa_mutatie;
CREATE TRIGGER pa_mutatie_vast_truncate BEFORE TRUNCATE ON personeel.pa_mutatie
  FOR EACH STATEMENT EXECUTE FUNCTION personeel.pa_mutatie_alleen_toevoegen();


-- Rechten: de app verbindt als hr_app. Lezen, toevoegen en wijzigen; nooit
-- verwijderen. Het logboek alleen lezen en aanvullen.
GRANT USAGE ON SCHEMA personeel TO hr_app;
GRANT SELECT, INSERT, UPDATE ON
    personeel.pa_instelling, personeel.pa_rooster, personeel.pa_persoon,
    personeel.pa_contract, personeel.pa_overeenkomst, personeel.pa_dossier,
    personeel.pa_gesprek, personeel.pa_waarschuwing
    TO hr_app;
GRANT SELECT, INSERT ON personeel.pa_mutatie TO hr_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA personeel TO hr_app;
