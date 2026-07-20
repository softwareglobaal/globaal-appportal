-- 076: persoonslagen - alle gegevens in kern, per laag afgeschermd.
--
-- Besluit Shaniel 2026-07-20 (meeting met Mehdi en Ishara): de persoon blijft
-- de gedeelde kern zodat elke discipline eraan kan koppelen ("Abby moet uit
-- de HR-map"), maar wie het profiel ziet, ziet niet alles. Salaris hoort in
-- het platform en is alleen voor HR en management.
--
-- Waarom aparte tabellen en niet extra kolommen op kern.persoon: die tabel is
-- leesbaar voor zes app-rollen (portal, communicatie, kosten, draaiboek,
-- vermogen, hr_app). Een salariskolom daar zou dus voor het
-- communicatie-dashboard leesbaar zijn. De laaggrens is hier een grant, geen
-- afspraak. Zie docs/PERSOONSLAGEN.md voor de volledige rolmatrix.

-- ---------------------------------------------------------------------------
-- Laag 0: publiek. Alleen de foto ontbrak nog.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kern.persoon_foto (
    persoon_id    uuid PRIMARY KEY REFERENCES kern.persoon(id) ON DELETE CASCADE,
    afbeelding    bytea NOT NULL,
    mimetype      text NOT NULL DEFAULT 'image/jpeg',
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);
COMMENT ON TABLE kern.persoon_foto IS
    'Officiele foto: het platform is de bron, Zoom en Monday volgen.';

-- ---------------------------------------------------------------------------
-- Laag 1: HR. Contract, rooster, verlof en verzuim.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kern.persoon_hr (
    persoon_id        uuid PRIMARY KEY REFERENCES kern.persoon(id) ON DELETE CASCADE,
    geboortedatum     date,
    prive_email       text NOT NULL DEFAULT '',
    prive_telefoon    text NOT NULL DEFAULT '',
    adres_id          uuid REFERENCES kern.adres(id) ON DELETE SET NULL,
    contract_type     text NOT NULL DEFAULT '',
    uren_per_week     numeric,
    -- Het rooster stond in een PowerShell-array en in hr.medewerker; kern
    -- wordt de ene plek. Het HR-dashboard leidt het hiervandaan af.
    werkdag_start     text NOT NULL DEFAULT '',
    werkdag_eind      text NOT NULL DEFAULT '',
    flexibel          boolean NOT NULL DEFAULT false,
    verlofrecht_dagen numeric,
    verlof_opgenomen  numeric,
    notitie           text NOT NULL DEFAULT '',
    bijgewerkt_op     timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door   text NOT NULL DEFAULT ''
);

-- Verzuim en verlof als losse regels, zodat een saldo herleidbaar is in plaats
-- van een getal dat iemand overschrijft.
CREATE TABLE IF NOT EXISTS kern.persoon_afwezigheid (
    id            bigserial PRIMARY KEY,
    persoon_id    uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE CASCADE,
    soort         text NOT NULL CHECK (soort IN ('verlof', 'ziekte', 'feestdag',
                                                 'onbetaald', 'overig')),
    van           date NOT NULL,
    tot           date NOT NULL,
    dagen         numeric,
    reden         text NOT NULL DEFAULT '',
    bron          text NOT NULL DEFAULT '',   -- handmatig, agenda, desktime
    aangemaakt_op timestamptz NOT NULL DEFAULT now(),
    aangemaakt_door text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_kern_afwezigheid_persoon
    ON kern.persoon_afwezigheid (persoon_id, van);

-- ---------------------------------------------------------------------------
-- Laag 2: beloning. De zwaarste laag.
-- ---------------------------------------------------------------------------
-- Historie per regel: een loonsverhoging voegt een rij toe, hij overschrijft
-- niets. De geldende beloning is de laatste rij met een ingangsdatum <= nu.
CREATE TABLE IF NOT EXISTS kern.persoon_beloning (
    id              bigserial PRIMARY KEY,
    persoon_id      uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE CASCADE,
    ingangsdatum    date NOT NULL,
    bruto           numeric,
    valuta          text NOT NULL DEFAULT 'EUR',
    ritme           text NOT NULL DEFAULT 'maand'
                    CHECK (ritme IN ('maand', 'jaar', 'uur', 'week')),
    dertiende_maand boolean NOT NULL DEFAULT false,
    toelagen        numeric,
    toelichting     text NOT NULL DEFAULT '',
    aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
    aangemaakt_door text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_kern_beloning_persoon
    ON kern.persoon_beloning (persoon_id, ingangsdatum DESC);
COMMENT ON TABLE kern.persoon_beloning IS
    'Beloningslaag. Alleen HR en management. Nooit in de graaf, nooit in een '
    'AI-laag, geen export. Elke inzage wordt gelogd in kern.persoon_inzage.';

-- Wie keek wanneer naar welke beloning. Append-only.
CREATE TABLE IF NOT EXISTS kern.persoon_inzage (
    id         bigserial PRIMARY KEY,
    persoon_id uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE CASCADE,
    laag       text NOT NULL,
    gebruiker  text NOT NULL DEFAULT '',
    op         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_kern_inzage_op ON kern.persoon_inzage (op DESC);

-- ---------------------------------------------------------------------------
-- Rechten: hier ligt de laaggrens.
-- ---------------------------------------------------------------------------
-- Laag 0 (foto) hoort bij de publieke kern: alle apps mogen hem tonen.
GRANT SELECT ON kern.persoon_foto TO portal, communicatie, kosten, draaiboek,
                                     vermogen, hr_app;

-- Laag 1 (HR): alleen het organisatie-dashboard en de HR-app.
GRANT SELECT ON kern.persoon_hr, kern.persoon_afwezigheid TO portal, hr_app;

-- Laag 2 (beloning): alleen het organisatie-dashboard, dat zelf op rol
-- controleert. Bewust GEEN hr_app: het DeskTime-dashboard heeft geen
-- salarisgegevens nodig.
GRANT SELECT ON kern.persoon_beloning TO portal;

-- Schrijven gaat via de smalle schrijfrol van de organisatie-app.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON kern.persoon_foto, kern.persoon_hr, kern.persoon_afwezigheid,
       kern.persoon_beloning TO medewerker_writer;
GRANT SELECT, INSERT ON kern.persoon_inzage TO portal, medewerker_writer;
GRANT USAGE ON SEQUENCE kern.persoon_afwezigheid_id_seq,
                        kern.persoon_beloning_id_seq,
                        kern.persoon_inzage_id_seq TO medewerker_writer;
GRANT USAGE ON SEQUENCE kern.persoon_inzage_id_seq TO portal;

-- Zekerheidshalve expliciet: de andere app-rollen krijgen niets op de
-- gevoelige lagen. (Ze hebben geen grant, dus dit is een vangnet tegen een
-- toekomstige brede GRANT ... ON ALL TABLES IN SCHEMA kern.)
REVOKE ALL ON kern.persoon_hr, kern.persoon_afwezigheid, kern.persoon_beloning
    FROM communicatie, kosten, draaiboek, vermogen;
REVOKE ALL ON kern.persoon_beloning FROM hr_app;
