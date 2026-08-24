-- 127: ook Claude is gedeeld per afdeling, persoonlijk blijft alleen e-mail
-- Aanleiding: verduidelijking Sufa 24-08-2026 bij #31 en #32, na 126.
--
-- 126 haalde 'dropbox' uit organisatie.account omdat Dropbox per afdeling
-- gedeeld wordt. Voor Claude geldt precies hetzelfde: collega's hebben geen
-- eigen Claude-account, ook dat is er een per afdeling. In 126 staat 'claude'
-- nog als persoonlijke dienst, en dat loopt op dezelfde manier stuk zodra de
-- tweede collega van een afdeling ingevoerd wordt: de unieke index op
-- organisatie.account eist dat een adres binnen een dienst bij EEN persoon
-- hoort, want daar hangt de herleidbaarheid aan.
--
-- Het enige dat uniek is per collega is het e-mailadres. Dat is dus de sleutel,
-- en de rest is gedeeld gereedschap.
--
-- Wat de structuur wordt:
--   organisatie.account          alleen nog dienst 'email'. Persoonlijk, uniek,
--                                en daarmee de sleutel voor verantwoordelijkheid.
--   organisatie.gedeeld_account  de gedeelde accounts, Claude EN Dropbox, met
--                                een afdeling en een beheerder.
--   organisatie.gedeeld_toegang  wie in welk gedeeld account werkt.
--
-- Claude en Dropbox in een tabel en niet in twee: het is hetzelfde soort ding,
-- een account dat een afdeling deelt. Twee tabellen met dezelfde vorm lopen na
-- verloop van tijd uit elkaar. Vandaar dat dropbox_ruimte en dropbox_toegang
-- uit 125 en 126 hierin opgaan.
--
-- Wat dit oplevert, eerlijk gezegd: gaat er een verkeerde mail uit, dan staat er
-- een naam op, want de afzender is persoonlijk. Wie hem via het gedeelde
-- Claude-account in gang zette is daarmee niet vastgelegd; dat blijft de kring
-- uit gedeeld_toegang. Voor de vraag wie hierop aanspreekbaar is, is de
-- mailboxeigenaar het antwoord, en dat was de vraag.
--
-- LET OP bij toepassen: dit verwijdert organisatie.dropbox_ruimte (125) en
-- organisatie.dropbox_toegang (126). Die tabellen zijn een of twee migraties oud
-- en er kan nog geen data in zitten, want er is nog geen scherm om ze te vullen.
-- Staat er toch iets in, zet dat dan eerst over naar gedeeld_account en
-- gedeeld_toegang, en draai daarna pas.

-- 1. account houdt alleen nog persoonlijke identiteiten over.
ALTER TABLE organisatie.account DROP CONSTRAINT IF EXISTS account_dienst_check;

ALTER TABLE organisatie.account ADD CONSTRAINT account_dienst_check
    CHECK (dienst IN ('email'));

-- 2. Het oude, te smalle model eruit. De view eerst, die hangt aan de tabellen.
DROP VIEW  IF EXISTS organisatie.dropbox_toegang_actueel;
DROP TABLE IF EXISTS organisatie.dropbox_toegang;
DROP TABLE IF EXISTS organisatie.dropbox_ruimte;

-- 3. De gedeelde accounts.
CREATE TABLE IF NOT EXISTS organisatie.gedeeld_account (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dienst        text NOT NULL CHECK (dienst IN ('claude', 'dropbox')),
    -- Het adres of de login waarmee het account bekend staat. Dit is wat in
    -- koppelingen en logs opduikt. Leeg mag, voor een ruimte zonder eigen login.
    adres         public.citext NOT NULL DEFAULT ''::public.citext,
    -- Herkenbare naam, bijvoorbeeld de afdeling of de ruimte.
    naam          public.citext NOT NULL,
    afdeling_id   uuid NOT NULL REFERENCES kern.afdeling(id) ON DELETE RESTRICT,
    -- Wie aanspreekbaar is voor dit gedeelde account. Vervangt de kring niet,
    -- maar geeft wel een naam om bij te beginnen.
    beheerder_id  uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    -- Alleen zinvol bij dienst 'dropbox': het gedeelde Claude-account waaraan
    -- deze ruimte hangt. Zo staat vast welke afdeling met welke data werkt.
    gekoppeld_aan uuid REFERENCES organisatie.gedeeld_account(id) ON DELETE RESTRICT,
    pad           text NOT NULL DEFAULT '',
    geldig_van    date NOT NULL DEFAULT current_date,
    geldig_tot    date,
    opmerking     text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_gedeeld_account_geldigheid
        CHECK (geldig_tot IS NULL OR geldig_tot >= geldig_van)
);

-- Een adres hoort binnen een dienst bij een gedeeld account. Lege adressen doen
-- niet mee, anders kan er maar een account zonder login bestaan.
CREATE UNIQUE INDEX IF NOT EXISTS ux_gedeeld_account_adres
    ON organisatie.gedeeld_account (dienst, adres)
    WHERE geldig_tot IS NULL AND adres <> ''::public.citext;

CREATE UNIQUE INDEX IF NOT EXISTS ux_gedeeld_account_naam
    ON organisatie.gedeeld_account (dienst, naam)
    WHERE geldig_tot IS NULL;

CREATE INDEX IF NOT EXISTS ix_gedeeld_account_afdeling
    ON organisatie.gedeeld_account (afdeling_id, dienst);

-- 4. Wie werkt in welk gedeeld account. Met een periode, om dezelfde reden als
--    bij account: de vraag achteraf is wie er toegang had OP DAT MOMENT.
CREATE TABLE IF NOT EXISTS organisatie.gedeeld_toegang (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gedeeld_account_id uuid NOT NULL
                       REFERENCES organisatie.gedeeld_account(id) ON DELETE RESTRICT,
    persoon_id         uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    geldig_van         date NOT NULL DEFAULT current_date,
    geldig_tot         date,
    opmerking          text NOT NULL DEFAULT '',
    aangemaakt_op      timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_gedeeld_toegang_geldigheid
        CHECK (geldig_tot IS NULL OR geldig_tot >= geldig_van)
);

-- Iemand staat hoogstens een keer actief in hetzelfde account. Toegang die is
-- ingetrokken en later opnieuw gegeven wordt een tweede regel, geen wijziging
-- van de oude, zodat de historie klopt.
CREATE UNIQUE INDEX IF NOT EXISTS ux_gedeeld_toegang_actueel
    ON organisatie.gedeeld_toegang (gedeeld_account_id, persoon_id)
    WHERE geldig_tot IS NULL;

CREATE INDEX IF NOT EXISTS ix_gedeeld_toegang_persoon
    ON organisatie.gedeeld_toegang (persoon_id);

-- 5. Overzicht voor de Namenlijst: per persoon de gedeelde accounts waar hij nu
--    in werkt. Scheelt de app een join van drie tabellen en houdt de
--    periodelogica op een plek in plaats van in elke query die dit nodig heeft.
CREATE OR REPLACE VIEW organisatie.gedeeld_toegang_actueel AS
SELECT t.persoon_id,
       g.id     AS gedeeld_account_id,
       g.dienst,
       g.naam,
       g.adres,
       g.afdeling_id,
       g.beheerder_id,
       (g.beheerder_id = t.persoon_id) AS is_beheerder
FROM organisatie.gedeeld_toegang t
JOIN organisatie.gedeeld_account g ON g.id = t.gedeeld_account_id
WHERE t.geldig_tot IS NULL
  AND g.geldig_tot IS NULL;

GRANT SELECT ON organisatie.gedeeld_account,
                organisatie.gedeeld_toegang,
                organisatie.gedeeld_toegang_actueel TO portal;
GRANT SELECT, INSERT, UPDATE
    ON organisatie.gedeeld_account, organisatie.gedeeld_toegang TO medewerker_writer;
