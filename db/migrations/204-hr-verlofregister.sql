-- 204: het verlofregister op de server (hr.globaal.be/verlofregister).
--
-- Waarom: het register van HR stond alleen in haar browser en in haar eigen
-- .json. Een collega met dezelfde rechten die de pagina opende zag daardoor
-- een leeg scherm met alleen "Openen uit bestand" -- haar browser had die
-- gegevens immers niet. Het bestand rondsturen lost dat niet op: dan zijn er
-- twee kopieën die meteen uit elkaar lopen. Keuze HR (29-10-2026): het
-- register gaat naar de database, zoals Payrun.
--
-- De app (globaal-hr, app/verlofregister_db.py) maakt zijn tabellen bij het
-- eerste bezoek zelf aan, maar hr_app heeft geen CREATE op schema hr
-- ("permission denied for schema hr"; zelfde verhaal als migratie 181 voor de
-- servicedesk). Vandaar deze migratie. De tabeldefinities zijn letterlijk
-- verlofregister_db.SCHEMA uit globaal-hr; bestaan de tabellen, dan slaat de
-- app zijn eigen DDL over (zorg_voor_tabellen) en leest hij gewoon.
--
-- Eén document met een versienummer: wie opslaat stuurt de versie mee die hij
-- las, en is die opgehoogd dan wordt de opslag geweigerd in plaats van er
-- overheen te gaan. Elke opgeslagen versie blijft in verlofregister_versie
-- staan (de app houdt er 200); dit is een administratie waarin één verkeerd
-- getal een saldo scheeftrekt, en dan wil je terug kunnen naar gisteren.
--
-- Schema hr: namen, saldi en aantallen ziektedagen. Dezelfde afspraak als de
-- rest van hr -- de AI-lagen lezen deze tabellen niet, en het portaal krijgt
-- hier niets. Geen reden en geen diagnose bij ziekte; alleen een aantal.

CREATE TABLE IF NOT EXISTS hr.verlofregister_werkblad (
    id          text PRIMARY KEY DEFAULT 'werkblad',
    versie      bigint      NOT NULL DEFAULT 0,
    doc         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    gewijzigd   timestamptz NOT NULL DEFAULT now(),
    door        text        NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS hr.verlofregister_versie (
    versie      bigint      PRIMARY KEY,
    doc         jsonb       NOT NULL,
    gewijzigd   timestamptz NOT NULL DEFAULT now(),
    door        text        NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS verlofregister_versie_wanneer
    ON hr.verlofregister_versie (gewijzigd DESC);

-- De ene rij waar alles in staat. Leeg document = "nog geen register"; de
-- pagina biedt dan aan om te openen uit een bestand en het erop te zetten.
INSERT INTO hr.verlofregister_werkblad (id) VALUES ('werkblad')
    ON CONFLICT (id) DO NOTHING;

-- Rechten: de app verbindt als hr_app. DELETE is nodig omdat de app de
-- oudste versies opruimt zodra er meer dan 200 staan.
GRANT USAGE ON SCHEMA hr TO hr_app;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON hr.verlofregister_werkblad, hr.verlofregister_versie TO hr_app;
