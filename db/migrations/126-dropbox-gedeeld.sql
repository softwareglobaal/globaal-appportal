-- 126: Dropbox is gedeeld per afdeling, niet persoonlijk
-- Aanleiding: antwoorden Sufa 24-08-2026 op de open vragen bij 125 (#31, #32).
--
-- 125 ging ervan uit dat elke collega een eigen Dropbox-login heeft, naast zijn
-- e-mailadres. Dat klopt niet: het e-mailadres is persoonlijk en uniek, maar
-- Dropbox loopt via een handvol GEDEELDE accounts, een per afdeling. Meerdere
-- collega's werken in hetzelfde account.
--
-- Dat verschil is niet cosmetisch. De unieke index op organisatie.account eist
-- dat een adres binnen een dienst bij een persoon hoort, want daar hangt de
-- herleidbaarheid aan. Een gedeeld Dropbox-account invoeren als 'dienst =
-- dropbox' zou bij de tweede collega afketsen op die index, en terecht: dat
-- adres wijst nu eenmaal niet naar een persoon.
--
-- Daarom:
--   1. 'dropbox' verdwijnt als dienst uit organisatie.account. Wat daar staat
--      moet naar een persoon wijzen, en een gedeeld account doet dat niet.
--   2. organisatie.dropbox_ruimte krijgt het adres van het gedeelde account
--      erbij, want dat is wat in logs en koppelingen opduikt.
--   3. organisatie.dropbox_toegang legt vast wie in welke ruimte werkt.
--
-- Wat dit wel en niet oplevert: gebeurt er iets in een gedeelde ruimte, dan
-- zegt dit register eerlijk WIE ER TOEGANG HADDEN, niet wie het deed. Dat is
-- een kring, geen naam. Voor overzicht is dat genoeg; wil je bij Dropbox
-- dezelfde herleidbaarheid als bij e-mail, dan zijn eigen logins de enige weg.
-- De beheerder van de ruimte blijft de aanspreekbare persoon.
--
-- LET OP bij toepassen: stap 1 gaat ervan uit dat er nog geen regels met
-- dienst = 'dropbox' in organisatie.account staan. 125 is net toegepast, dus de
-- tabel hoort leeg te zijn. Faalt de migratie hierop, dan staan er toch al
-- regels: zet die dan eerst om naar dropbox_ruimte en draai opnieuw.

-- 1. Dienst 'dropbox' eruit. Zelfde patroon als 124 gebruikte voor namen_kolom.
ALTER TABLE organisatie.account DROP CONSTRAINT IF EXISTS account_dienst_check;

ALTER TABLE organisatie.account ADD CONSTRAINT account_dienst_check
    CHECK (dienst IN ('claude', 'email'));

-- 2. Het adres van het gedeelde account. Leeg toegestaan zolang een ruimte nog
--    geen eigen login heeft, bijvoorbeeld een map binnen een ander account.
ALTER TABLE organisatie.dropbox_ruimte
    ADD COLUMN IF NOT EXISTS adres public.citext NOT NULL DEFAULT ''::public.citext;

-- Een gedeeld account hoort bij een ruimte. Lege adressen doen niet mee, anders
-- kan er maar een ruimte zonder login bestaan.
CREATE UNIQUE INDEX IF NOT EXISTS ux_dropbox_ruimte_adres
    ON organisatie.dropbox_ruimte (adres)
    WHERE geldig_tot IS NULL AND adres <> ''::public.citext;

-- 3. Wie werkt in welke gedeelde ruimte. Met een periode, om dezelfde reden als
--    bij account: de vraag achteraf is wie er toegang had OP DAT MOMENT.
CREATE TABLE IF NOT EXISTS organisatie.dropbox_toegang (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ruimte_id     uuid NOT NULL REFERENCES organisatie.dropbox_ruimte(id) ON DELETE RESTRICT,
    persoon_id    uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    geldig_van    date NOT NULL DEFAULT current_date,
    geldig_tot    date,
    opmerking     text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_dropbox_toegang_geldigheid
        CHECK (geldig_tot IS NULL OR geldig_tot >= geldig_van)
);

-- Iemand staat hoogstens een keer actief in dezelfde ruimte. Toegang die is
-- ingetrokken en later opnieuw gegeven wordt een tweede regel, geen wijziging
-- van de oude, zodat de historie klopt.
CREATE UNIQUE INDEX IF NOT EXISTS ux_dropbox_toegang_actueel
    ON organisatie.dropbox_toegang (ruimte_id, persoon_id)
    WHERE geldig_tot IS NULL;

CREATE INDEX IF NOT EXISTS ix_dropbox_toegang_persoon
    ON organisatie.dropbox_toegang (persoon_id);

-- Overzicht voor de Namenlijst: per persoon de ruimtes waar hij nu in werkt.
-- Scheelt de app een join van drie tabellen en houdt de periodelogica op een
-- plek in plaats van in elke query die dit nodig heeft.
CREATE OR REPLACE VIEW organisatie.dropbox_toegang_actueel AS
SELECT t.persoon_id,
       r.id      AS ruimte_id,
       r.naam    AS ruimte,
       r.adres   AS ruimte_adres,
       r.afdeling_id,
       r.beheerder_id,
       (r.beheerder_id = t.persoon_id) AS is_beheerder,
       r.gekoppeld_aan_claude
FROM organisatie.dropbox_toegang t
JOIN organisatie.dropbox_ruimte r ON r.id = t.ruimte_id
WHERE t.geldig_tot IS NULL
  AND r.geldig_tot IS NULL;

GRANT SELECT ON organisatie.dropbox_toegang,
                organisatie.dropbox_toegang_actueel TO portal;
GRANT SELECT, INSERT, UPDATE ON organisatie.dropbox_toegang TO medewerker_writer;
