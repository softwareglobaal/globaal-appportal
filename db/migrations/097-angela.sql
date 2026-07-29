-- 097: schema `angela` - werkdashboard voor het initiatief Angela (Suriname).
-- Vangbak voor alles rond het initiatief: notities, links, bestanden, taken en
-- beslissingen, elk gekoppeld aan een werkstroom. Herkomst blijft zichtbaar
-- (bron_soort/bron_ref), zodat een item terug te voeren is op het gesprek waar
-- het uit komt.
--
-- Lagen (ontwerp-prompt docs/prompt-dashboard-ontwerp.md):
--   entiteiten  = werkstroom, betrokkene, item, bijlage
--   relaties    = item.werkstroom_id, item.verantwoordelijke_id,
--                 betrokkene.persoon_id (naar kern), angela.verband (item-item)
--   views       = queries in de app, niets opgeslagen
--
-- Discipline: strategic planning, met marketing/communications (merk, social),
-- procurement (inkoop/veilingen) en legal/compliance (NGO, import) eronder.
-- Eigen LOGIN-rol angela_writer (wachtwoord via ALTER ROLE op de VM).

CREATE SCHEMA IF NOT EXISTS angela;

-- Werkstroom: de vaste indeling van het initiatief. Structuur, geen inhoud.
CREATE TABLE IF NOT EXISTS angela.werkstroom (
    id            smallserial PRIMARY KEY,
    sleutel       text NOT NULL UNIQUE,
    naam          text NOT NULL,
    omschrijving  text,
    volgorde      smallint NOT NULL DEFAULT 100,
    actief        boolean NOT NULL DEFAULT true
);

-- Betrokkene: de koppelbare personenlaag. persoon_id is de brug naar de
-- centrale master data; externe betrokkenen die (nog) niet in kern staan,
-- laten die kolom leeg. Namen worden hier niet bewerkt of afgekort.
CREATE TABLE IF NOT EXISTS angela.betrokkene (
    id          smallserial PRIMARY KEY,
    naam        text NOT NULL UNIQUE,
    rol         text,
    persoon_id  uuid REFERENCES kern.persoon(id) ON DELETE SET NULL,
    actief      boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS ix_angela_betrokkene_persoon
    ON angela.betrokkene (persoon_id);

-- Item: alles wat gedropt wordt. Eén tabel met een soort-kolom, omdat de
-- bedieningsvraag "gooi het ergens neer" is en de soorten dezelfde velden
-- delen. Taak-velden (verantwoordelijke, status, deadline) en het
-- beslissingsveld (besloten_op) blijven leeg bij de andere soorten.
CREATE TABLE IF NOT EXISTS angela.item (
    id                    bigserial PRIMARY KEY,
    soort                 text NOT NULL
                           CHECK (soort IN ('notitie','link','bestand','taak','beslissing')),
    titel                 text NOT NULL,
    tekst                 text,
    url                   text,
    werkstroom_id         smallint REFERENCES angela.werkstroom(id) ON DELETE SET NULL,
    verantwoordelijke_id  smallint REFERENCES angela.betrokkene(id) ON DELETE SET NULL,
    status                text NOT NULL DEFAULT 'open'
                           CHECK (status IN ('open','bezig','klaar','geparkeerd','vervallen')),
    deadline              date,
    besloten_op           date,
    -- Herkomst: 'plaud' met het opname-id, 'gesprek', 'handmatig', 'extern'.
    bron_soort            text,
    bron_ref              text,
    bron_titel            text,
    aangemaakt_door       text NOT NULL DEFAULT 'onbekend',
    aangemaakt_op         timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_angela_item_soort       ON angela.item (soort);
CREATE INDEX IF NOT EXISTS ix_angela_item_werkstroom  ON angela.item (werkstroom_id);
CREATE INDEX IF NOT EXISTS ix_angela_item_status      ON angela.item (status);
CREATE INDEX IF NOT EXISTS ix_angela_item_verantw     ON angela.item (verantwoordelijke_id);
CREATE INDEX IF NOT EXISTS ix_angela_item_aangemaakt  ON angela.item (aangemaakt_op DESC);

-- Bijlage: foto's en documenten staan als BESTAND op het datavolume
-- (ANGELA_UPLOAD_DIR); in de database alleen pad en metadata.
CREATE TABLE IF NOT EXISTS angela.bijlage (
    id             bigserial PRIMARY KEY,
    item_id        bigint NOT NULL REFERENCES angela.item(id) ON DELETE CASCADE,
    bestandsnaam   text NOT NULL,
    pad            text NOT NULL,
    mimetype       text,
    grootte_bytes  bigint,
    is_afbeelding  boolean NOT NULL DEFAULT false,
    geupload_door  text,
    geupload_op    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_angela_bijlage_item ON angela.bijlage (item_id);

-- Verband: item-item relatie als eigen record, zodat betekenis in de link
-- leeft (een beslissing volgt uit een notitie, een taak hoort bij een link).
CREATE TABLE IF NOT EXISTS angela.verband (
    id             bigserial PRIMARY KEY,
    van_item_id    bigint NOT NULL REFERENCES angela.item(id) ON DELETE CASCADE,
    naar_item_id   bigint NOT NULL REFERENCES angela.item(id) ON DELETE CASCADE,
    relatie        text NOT NULL DEFAULT 'hoort bij',
    aangemaakt_op  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_angela_verband_niet_zelf CHECK (van_item_id <> naar_item_id),
    CONSTRAINT uq_angela_verband UNIQUE (van_item_id, naar_item_id, relatie)
);
CREATE INDEX IF NOT EXISTS ix_angela_verband_naar ON angela.verband (naar_item_id);

-- ---------------------------------------------------------------------------
-- Structuurseeds: de werkstromen en de betrokkenen uit de startgesprekken.
-- ---------------------------------------------------------------------------
INSERT INTO angela.werkstroom (sleutel, naam, omschrijving, volgorde) VALUES
  ('merk',    'Merk en branding',
   'Logo en beeldmerk, silhouet en Surinaamse vlag, naamgebruik en positionering.', 10),
  ('website', 'Website en bio-pagina',
   'Pilot met de verkoopsectie eerst, daarna de bio-pagina. Hosting en opbouw.', 20),
  ('webshop', 'Webshop',
   'Shopify, productcategorieën, keuze van het thema, productfoto''s.', 30),
  ('inkoop',  'Inkoop en veilingen',
   'Opkoop bij veilingen van gesloten bedrijven, verkoop per pallet, brede goederen.', 40),
  ('fiscaal', 'Fiscaal en juridisch',
   'Import en belastingnummer, keuze tussen vennootschap, stichting of NGO.', 50),
  ('social',  'Social media en content',
   'Pagina in plaats van persoonlijk profiel, contentplanning gekoppeld aan producten.', 60),
  ('data',    'Data en netwerk',
   'Dataverzameling en registers, netwerk richting overheid en organisaties.', 70)
ON CONFLICT (sleutel) DO NOTHING;

INSERT INTO angela.betrokkene (naam, rol) VALUES
  ('Mehdi',   'initiatiefnemer'),
  ('Shaniel', 'uitvoering'),
  ('Angela',  'merk en netwerk'),
  ('Siam',    'foto en beeld')
ON CONFLICT (naam) DO NOTHING;

-- ---------------------------------------------------------------------------
-- App-rol: leest en schrijft eigen schema, leest kern. Wachtwoord via ALTER ROLE.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'angela_writer') THEN
        CREATE ROLE angela_writer LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA angela TO angela_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA angela TO angela_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA angela TO angela_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA angela
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO angela_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA angela
    GRANT USAGE, SELECT ON SEQUENCES TO angela_writer;

-- De betrokkenenlaag verwijst naar kern.persoon; alleen lezen daar.
GRANT USAGE ON SCHEMA kern TO angela_writer;
GRANT SELECT ON kern.persoon TO angela_writer;

-- Leesrol portal mag meekijken (consistent met andere spoke-schema's).
GRANT USAGE ON SCHEMA angela TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA angela TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA angela
    GRANT SELECT ON TABLES TO portal;
