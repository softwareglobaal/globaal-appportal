-- 125: account-register, wie is verantwoordelijk voor geautomatiseerd werk
-- Aanleiding: vraag Sufa 24-08-2026, issue #31. Van elke collega worden e-mail
-- en Dropbox aan Claude gekoppeld om werk te automatiseren. Handelt Claude
-- namens iemand, dan moet achteraf vast te stellen zijn van wie dat kwam, zodat
-- iedereen individueel verantwoordelijk blijft. Concreet: gaat er een verkeerde
-- mail uit, dan moet het afzenderadres naar precies een persoon leiden.
--
-- Twee tabellen, want het zijn twee verschillende dingen:
--   account          een identiteit die kan handelen. Hoort bij een persoon.
--   dropbox_ruimte   een gedeelde map. Hoort bij een AFDELING, niet bij een
--                    persoon: meerdere mensen werken erin, dus de ruimte kan
--                    nooit vertellen wie iets deed.
-- De herleidbaarheid loopt daarom via het account dat handelde. De ruimte legt
-- alleen vast bij welke afdeling hij hoort en wie hem beheert.
--
-- De sleutel is het e-mailadres, niet de Dropbox-login. Iedere collega heeft of
-- krijgt een uniek adres; de login is een schakel die naar de persoon leidt.
--
-- Waarom geldig_van/geldig_tot en geen vinkje 'actief': de vraag bij een fout is
-- wie eigenaar was OP DAT MOMENT, niet wie het nu is. Wisselt een adres in juni
-- van eigenaar en kijk je in september naar iets van maart, dan geeft een vinkje
-- het verkeerde antwoord en een periode het goede.
--
-- OPEN VRAAG VOOR DE REVIEWER: kern.persoon.email bestaat al (citext). Is dat
-- het officiele adres, dan hoort hier alleen wat DAAR niet staat: de extra
-- adressen, het Claude-account en de Dropbox-login, en blijft kern.persoon.email
-- de bron voor het primaire adres. Zoals het nu staat kan het primaire adres in
-- allebei voorkomen en dus uit elkaar lopen. Zeg maar wat je wil, dan pas ik het
-- aan voor het toegepast wordt.

CREATE TABLE IF NOT EXISTS organisatie.account (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- RESTRICT en geen CASCADE: een persoon weghalen mag niet stilletjes de
    -- herleidbaarheid weghalen. Offboarding zet in_dienst op false.
    persoon_id           uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    dienst               text NOT NULL
                         CHECK (dienst IN ('claude', 'email', 'dropbox')),
    -- citext, net als kern.persoon.email en communicatie.adres (migratie 002):
    -- adressen zijn hoofdletterongevoelig. Zonder dat zijn Naam@ en naam@ twee
    -- accounts en valt de uniciteitsregel hieronder om.
    adres                public.citext NOT NULL,
    -- Het adres dat als afzender geldt binnen die dienst.
    is_primair           boolean NOT NULL DEFAULT false,
    -- Of de koppeling met Claude echt gelegd is. Staat los van of het account
    -- bestaat: iemand kan een tweede adres hebben dat nog niet gekoppeld is.
    gekoppeld_aan_claude boolean NOT NULL DEFAULT false,
    gekoppeld_op         date,
    geldig_van           date NOT NULL DEFAULT current_date,
    geldig_tot           date,
    opmerking            text NOT NULL DEFAULT '',
    aangemaakt_op        timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_account_geldigheid
        CHECK (geldig_tot IS NULL OR geldig_tot >= geldig_van)
);

-- De dragende regel: een adres hoort binnen een dienst bij een persoon. Een
-- adres opzoeken moet precies een naam opleveren, anders is het register geen
-- bewijs maar een lijstje. Afgesloten regels (geldig_tot gevuld) doen niet mee,
-- zodat een adres dat van eigenaar wisselt gewoon overgezet kan worden.
CREATE UNIQUE INDEX IF NOT EXISTS ux_account_adres_actueel
    ON organisatie.account (dienst, adres)
    WHERE geldig_tot IS NULL;

-- STRENGERE VARIANT, bewust niet aangezet. Bovenstaande index bewaakt alleen het
-- heden; twee afgesloten regels met dezelfde dienst en adres mogen elkaar in de
-- tijd overlappen, wat bij handmatig terugwerkend invoeren fout kan gaan. Wil je
-- dat ook dichttimmeren, vervang de index dan door:
--
--   CREATE EXTENSION IF NOT EXISTS btree_gist;
--   ALTER TABLE organisatie.account ADD CONSTRAINT ex_account_adres_periode
--       EXCLUDE USING gist (
--           dienst WITH =,
--           (lower(adres::text)) WITH =,
--           daterange(geldig_van, geldig_tot, '[]') WITH &&
--       );
--
-- Kost wel een extensie die hier nog nergens gebruikt wordt, en citext moet naar
-- text omdat btree_gist citext niet ondersteunt. Vandaar dat ik de eenvoudige
-- variant lever en jij kiest.

-- Hoogstens een primair adres per persoon per dienst.
CREATE UNIQUE INDEX IF NOT EXISTS ux_account_primair
    ON organisatie.account (persoon_id, dienst)
    WHERE is_primair AND geldig_tot IS NULL;

CREATE INDEX IF NOT EXISTS ix_account_persoon
    ON organisatie.account (persoon_id, dienst);

CREATE TABLE IF NOT EXISTS organisatie.dropbox_ruimte (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam                 public.citext NOT NULL,
    afdeling_id          uuid NOT NULL REFERENCES kern.afdeling(id) ON DELETE RESTRICT,
    -- Wie aanspreekbaar is voor deze ruimte. Vervangt niet de herleidbaarheid
    -- van een handeling: die loopt via het account dat handelde.
    beheerder_id         uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    pad                  text NOT NULL DEFAULT '',
    gekoppeld_aan_claude boolean NOT NULL DEFAULT false,
    geldig_van           date NOT NULL DEFAULT current_date,
    geldig_tot           date,
    aangemaakt_op        timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_dropbox_ruimte_geldigheid
        CHECK (geldig_tot IS NULL OR geldig_tot >= geldig_van)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_dropbox_ruimte_naam
    ON organisatie.dropbox_ruimte (naam)
    WHERE geldig_tot IS NULL;

CREATE INDEX IF NOT EXISTS ix_dropbox_ruimte_afdeling
    ON organisatie.dropbox_ruimte (afdeling_id);

-- De unieke adressen worden nog uitgerold, dus niet iedereen heeft er al een.
-- Een index kan alleen het maximum afdwingen (hoogstens een primair adres), niet
-- het minimum. Deze view laat zien wie er nog geen heeft, zodat een gat in de
-- uitrol opvalt in plaats van weg te vallen. Wie hier in staat, kan niet
-- aansprakelijk gesteld worden voor geautomatiseerd werk.
CREATE OR REPLACE VIEW organisatie.account_zonder_primair_adres AS
SELECT p.id   AS persoon_id,
       p.voornaam,
       coalesce(a.naam, '') AS afdeling
FROM kern.persoon p
LEFT JOIN kern.afdeling a ON a.id = p.afdeling_id
WHERE p.in_dienst
  AND NOT EXISTS (
      SELECT 1
      FROM organisatie.account ac
      WHERE ac.persoon_id = p.id
        AND ac.dienst     = 'email'
        AND ac.is_primair
        AND ac.geldig_tot IS NULL
  );

-- Lezen: portal (de Namenlijst leest hiermee). Schrijven: de smalle schrijfrol
-- van de app. Geen DELETE: regels worden afgesloten met geldig_tot, niet
-- verwijderd, anders verdwijnt precies de historie waar dit register voor is.
GRANT SELECT ON organisatie.account,
                organisatie.dropbox_ruimte,
                organisatie.account_zonder_primair_adres TO portal;
GRANT SELECT, INSERT, UPDATE
    ON organisatie.account, organisatie.dropbox_ruimte TO medewerker_writer;
