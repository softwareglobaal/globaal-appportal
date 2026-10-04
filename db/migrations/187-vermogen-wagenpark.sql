-- 187: het wagenpark als echte entiteit in schema vermogen, naar het model van Odoo Fleet.
--
-- Aanleiding: Mehdi, 05-10-2026: "kan je onze dashboard omzetten naar zoiets als Odoo Fleet en
-- upgraden, alles wat we te veel hebben neem over, alles wat we te weinig hebben neem van Odoo over;
-- een functionerende app op onze Authentik". Tot nu toe stond een wagen alleen als tekst in
-- vermogen.verzekering.object ("zolang auto's geen entiteit zijn") en in een JSON-register van De
-- Wagenparkwacht. Odoo Fleet zelf draaien kan niet op de VM (schijf 94 procent, 1,8 GB geheugen vrij);
-- Mehdi koos de eigen app in Vermogen.
--
-- Model (Odoo Fleet -> hier):
--   fleet.vehicle            -> vermogen.voertuig
--   fleet.vehicle.log.services -> vermogen.voertuig_dienst (onderhoud, herstelling, banden, keuring,
--                               schade, brandstof), met de factuur als Dropbox-pad
--   fleet.vehicle.odometer   -> vermogen.voertuig_kmstand
--   fleet.vehicle.assignation.log -> vermogen.voertuig_bestuurder
--   fleet.vehicle.log.contract -> de bestaande vermogen.verzekering en vermogen.lening, nu met
--                               voertuig_id: een contract staat op een plaats, niet twee keer
--   mail.activity / chatter  -> vermogen.voertuig_activiteit (taken, notities, signalen van de agent)
--
-- Eigenaarschap: rijen met bron 'manueel' zijn van een mens; De Wagenparkwacht (VM) schrijft alleen
-- rijen met een eigen sleutel en laat velden die een mens aanpaste (voertuig.handmatig) staan.

BEGIN;

CREATE TABLE vermogen.voertuig (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plaat               text NOT NULL UNIQUE,          -- huidige plaat, of een interne code (SUR-PAJERO)
    platen_oud          text NOT NULL DEFAULT '',      -- vorige platen, komma-gescheiden
    plaat_buitenland    text NOT NULL DEFAULT '',      -- bv. de Surinaamse plaat
    vin                 text NOT NULL DEFAULT '',
    merk                text NOT NULL DEFAULT '',
    model               text NOT NULL DEFAULT '',
    categorie           text NOT NULL DEFAULT '',      -- M1 personenwagen, N1 lichte vracht
    brandstof           text NOT NULL DEFAULT '',
    bouwjaar            integer,
    eerste_inschrijving date,
    firma_id            uuid REFERENCES kern.firma(id),
    land                text NOT NULL DEFAULT 'België',
    status              text NOT NULL DEFAULT 'in gebruik',  -- in gebruik, stilgelegd, besteld, verkocht, geschrapt, buiten gebruik
    bestuurder          text NOT NULL DEFAULT '',
    keuring_tot         date,
    tankinhoud_l        integer,
    aankoopdatum        date,
    aankoopbedrag       numeric(12,2),
    verkoopdatum        date,
    dropbox_map         text NOT NULL DEFAULT '',
    omschrijving        text NOT NULL DEFAULT '',
    extra               jsonb NOT NULL DEFAULT '{}'::jsonb,
    handmatig           text[] NOT NULL DEFAULT '{}',  -- velden die een mens aanpaste: de agent laat ze staan
    actief              boolean NOT NULL DEFAULT true,
    bijgewerkt_op       timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door     text NOT NULL DEFAULT ''
);

CREATE TABLE vermogen.voertuig_dienst (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    voertuig_id     uuid NOT NULL REFERENCES vermogen.voertuig(id),
    datum           date,
    soort           text NOT NULL DEFAULT 'onderhoud',   -- onderhoud, herstelling, banden, keuring, schade, brandstof, andere
    status          text NOT NULL DEFAULT 'uitgevoerd',  -- gepland, uitgevoerd, geannuleerd
    leverancier     text NOT NULL DEFAULT '',
    km              integer,
    bedrag          numeric(12,2),
    munt            text NOT NULL DEFAULT 'EUR',
    btw             text NOT NULL DEFAULT '',            -- excl of incl: hoe het bedrag op de bron stond
    factuurnummer   text NOT NULL DEFAULT '',
    factuur_pad     text NOT NULL DEFAULT '',            -- Dropbox-pad van de factuur
    werken          jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{onderdeel, omschrijving, bedrag}]
    omschrijving    text NOT NULL DEFAULT '',
    bron            text NOT NULL DEFAULT 'manueel',     -- manueel, factuur, boekhouding, post, agent
    sleutel         text UNIQUE,                          -- alleen voor rijen van de agent
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);
CREATE INDEX ix_voertuig_dienst_voertuig ON vermogen.voertuig_dienst (voertuig_id, datum DESC);

CREATE TABLE vermogen.voertuig_kmstand (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    voertuig_id     uuid NOT NULL REFERENCES vermogen.voertuig(id),
    datum           date NOT NULL,
    km              integer NOT NULL,
    bron            text NOT NULL DEFAULT 'manueel',     -- manueel, factuur, tankkaart, keuring, agent
    verdacht        boolean NOT NULL DEFAULT false,      -- past niet in de reeks; telt niet mee
    sleutel         text UNIQUE,
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);
CREATE INDEX ix_voertuig_kmstand_voertuig ON vermogen.voertuig_kmstand (voertuig_id, datum);

CREATE TABLE vermogen.voertuig_bestuurder (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    voertuig_id     uuid NOT NULL REFERENCES vermogen.voertuig(id),
    naam            text NOT NULL,
    persoon_id      uuid REFERENCES kern.persoon(id),
    van             date,
    tot             date,
    omschrijving    text NOT NULL DEFAULT '',
    bron            text NOT NULL DEFAULT 'manueel',
    sleutel         text UNIQUE,
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

CREATE TABLE vermogen.voertuig_activiteit (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    voertuig_id       uuid NOT NULL REFERENCES vermogen.voertuig(id),
    soort             text NOT NULL DEFAULT 'notitie',   -- taak, notitie, signaal
    titel             text NOT NULL,
    tekst             text NOT NULL DEFAULT '',
    vervaldatum       date,
    status            text NOT NULL DEFAULT 'open',      -- open, gedaan
    bron              text NOT NULL DEFAULT 'manueel',   -- manueel of agent
    sleutel           text UNIQUE,                        -- een signaal van de agent komt maar een keer
    aangemaakt_op     timestamptz NOT NULL DEFAULT now(),
    aangemaakt_door   text NOT NULL DEFAULT '',
    afgehandeld_op    timestamptz,
    afgehandeld_door  text NOT NULL DEFAULT '',
    actief            boolean NOT NULL DEFAULT true,
    bijgewerkt_op     timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door   text NOT NULL DEFAULT ''
);
CREATE INDEX ix_voertuig_activiteit_open ON vermogen.voertuig_activiteit (voertuig_id) WHERE status = 'open';

-- Contracten: de bestaande verzekeringen en leningen/leasings krijgen een wagen.
ALTER TABLE vermogen.verzekering ADD COLUMN voertuig_id uuid REFERENCES vermogen.voertuig(id);
ALTER TABLE vermogen.lening      ADD COLUMN voertuig_id uuid REFERENCES vermogen.voertuig(id);

-- Rechten zoals de rest van schema vermogen (016): de app schrijft, het portaal leest.
GRANT SELECT, INSERT, UPDATE, DELETE ON vermogen.voertuig, vermogen.voertuig_dienst, vermogen.voertuig_kmstand,
    vermogen.voertuig_bestuurder, vermogen.voertuig_activiteit TO vermogen;
GRANT SELECT ON vermogen.voertuig, vermogen.voertuig_dienst, vermogen.voertuig_kmstand,
    vermogen.voertuig_bestuurder, vermogen.voertuig_activiteit TO portal;

-- Audit zoals 023: wie wat wanneer wijzigde.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['vermogen.voertuig', 'vermogen.voertuig_dienst', 'vermogen.voertuig_kmstand',
                             'vermogen.voertuig_bestuurder', 'vermogen.voertuig_activiteit']
    LOOP
        EXECUTE format('CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON %s '
                       'FOR EACH ROW EXECUTE FUNCTION kern.audit_log()', t);
    END LOOP;
END $$;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('voertuig', 'Voertuig',
     'Een wagen van de groep, in België of in Suriname, met plaat, chassisnummer, firma, bestuurder en status (in gebruik, stilgelegd, besteld, verkocht, geschrapt, buiten gebruik). Verkochte en geschrapte wagens blijven bewaard voor de historiek. Bron: vermogen.voertuig, beheerd in Vermogen onder Wagenpark.'),
    ('voertuig_dienst', 'Dienst (wagen)',
     'Alles wat aan een wagen gebeurde of gepland is: onderhoud, herstelling, banden, keuring, schade of brandstof, met datum, garage, kilometerstand, bedrag, de uitgevoerde werken en de factuur. Een rij met bron manueel is van een mens; De Wagenparkwacht schrijft alleen rijen met een eigen sleutel.'),
    ('voertuig_kmstand', 'Kilometerstand',
     'Een gemeten stand van de teller op een datum, uit een factuur, een tankbeurt, een keuring of een manuele ingave. Een stand die niet in de stijgende reeks van de wagen past, staat als verdacht en telt niet mee in km per jaar en kost per km.'),
    ('voertuig_activiteit', 'Activiteit (wagen)',
     'Een taak, notitie of signaal op een wagen, zoals in Odoo: een termijn die nadert, iets dat nagekeken moet worden, of een notitie van een mens. De Wagenparkwacht zet een signaal maar een keer en sluit het zelf als het opgelost is.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
