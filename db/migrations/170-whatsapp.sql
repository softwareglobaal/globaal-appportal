-- 170: schema `whatsapp` - gedeelde WhatsApp-inbox per firma met een agent die
-- antwoorden voorstelt (whatsapp.globaal.be, repo globaal-whatsapp).
--
-- Waarom (meeting 23-09-2026): klanten van UNABO hebben Mehdi's eigen nummer,
-- dus alle opvolging komt bij hem terecht. UNABO krijgt een eigen WhatsApp-
-- nummer via de officiele Business API (Twilio), Office behandelt de berichten
-- samen in een app, en een agent schrijft bij elk bericht een voorstel. Een
-- mens verstuurt; de agent nooit (afspraak 24-09-2026).
--
-- Lagen:
--   entiteiten = nummer, gesprek, bericht, voorstel
--   relaties   = gesprek -> nummer, bericht -> gesprek, voorstel -> gesprek
--   views      = queries in de app
--
-- Bewust geen FK naar kern.firma: de firma staat als code (UNAB, HARC ...)
-- zoals in kern.firma.code, en is hier alleen de sleutel naar het kennisbestand
-- en het Pipedrive-token. Alle FK's blijven binnen dit schema; net als bij
-- migratie 118 zou een knoop in de graaf niets verbinden dat er nog niet staat.
--
-- Privacy: dit schema bewaart berichttekst van klanten. Dat is de functie van
-- een inbox, maar het betekent ook: alleen de groepen whatsapp, manager en
-- admin lezen mee, en de portal-rol krijgt bewust GEEN leesrecht op bericht
-- en voorstel (wel op nummer, het register).
--
-- Eigen LOGIN-rol whatsapp_writer (wachtwoord via ALTER ROLE op de VM).

CREATE SCHEMA IF NOT EXISTS whatsapp;

-- Het register dat Mehdi vroeg: welk nummer, op welke gsm, op welke computer,
-- in welke browser, wie het gebruikt. `status` zegt hoe het nummer werkelijk
-- aan WhatsApp hangt: alleen in de app, in de Twilio-sandbox, of live via de API.
CREATE TABLE IF NOT EXISTS whatsapp.nummer (
    id              serial PRIMARY KEY,
    nummer          text NOT NULL UNIQUE,          -- E.164, bv. +32472...
    firma_code      text NOT NULL DEFAULT 'UNAB',
    status          text NOT NULL DEFAULT 'app'
                    CHECK (status IN ('app', 'sandbox', 'api', 'uit')),
    gsm             text NOT NULL DEFAULT '',
    computer        text NOT NULL DEFAULT '',
    browser         text NOT NULL DEFAULT '',
    gebruikt_door   text NOT NULL DEFAULT '',
    email           text NOT NULL DEFAULT '',
    opmerking       text NOT NULL DEFAULT '',
    agent_aan       boolean NOT NULL DEFAULT true,
    bijgewerkt_door text NOT NULL DEFAULT '',
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now()
);

-- Een gesprek = een klantnummer op een van onze nummers. `laatste_binnen`
-- bepaalt het 24-uursvenster van WhatsApp: daarbuiten mag alleen een
-- goedgekeurd sjabloon. `behandeld_door` is de claim, zodat twee collega's
-- niet tegelijk antwoorden (verloopt in de app na 15 minuten).
CREATE TABLE IF NOT EXISTS whatsapp.gesprek (
    id              bigserial PRIMARY KEY,
    nummer_id       integer NOT NULL REFERENCES whatsapp.nummer(id) ON DELETE CASCADE,
    contact         text NOT NULL,
    profielnaam     text NOT NULL DEFAULT '',
    pipedrive       jsonb,
    pipedrive_op    timestamptz,
    laatste_binnen  timestamptz,
    laatste_bericht timestamptz,
    ongelezen       integer NOT NULL DEFAULT 0,
    behandeld_door  text NOT NULL DEFAULT '',
    behandeld_sinds timestamptz,
    gesloten        boolean NOT NULL DEFAULT false,
    UNIQUE (nummer_id, contact)
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_gesprek_laatste
    ON whatsapp.gesprek (laatste_bericht DESC);

CREATE TABLE IF NOT EXISTS whatsapp.voorstel (
    id               bigserial PRIMARY KEY,
    gesprek_id       bigint NOT NULL REFERENCES whatsapp.gesprek(id) ON DELETE CASCADE,
    na_bericht_id    bigint,
    tekst            text NOT NULL DEFAULT '',
    escaleren        boolean NOT NULL DEFAULT false,
    reden            text NOT NULL DEFAULT '',
    na_te_kijken     jsonb NOT NULL DEFAULT '[]',
    model            text NOT NULL DEFAULT '',
    invoer_tokens    integer,
    uitvoer_tokens   integer,
    fout             text NOT NULL DEFAULT '',
    gevraagd_door    text NOT NULL DEFAULT '',
    -- open -> ongewijzigd | aangepast | verworpen | niet gebruikt | vervangen
    status           text NOT NULL DEFAULT 'open',
    gelijkenis       numeric(4,3),                -- 1 = letterlijk verstuurd
    gemaakt_op       timestamptz NOT NULL DEFAULT now(),
    afgehandeld_door text NOT NULL DEFAULT '',
    afgehandeld_op   timestamptz
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_voorstel_gesprek
    ON whatsapp.voorstel (gesprek_id, status);

CREATE TABLE IF NOT EXISTS whatsapp.bericht (
    id             bigserial PRIMARY KEY,
    gesprek_id     bigint NOT NULL REFERENCES whatsapp.gesprek(id) ON DELETE CASCADE,
    richting       text NOT NULL CHECK (richting IN ('in', 'uit')),
    tekst          text NOT NULL DEFAULT '',
    media          jsonb NOT NULL DEFAULT '[]',
    twilio_sid     text UNIQUE,
    status         text NOT NULL DEFAULT '',
    fout           text NOT NULL DEFAULT '',
    verzonden_door text NOT NULL DEFAULT '',
    voorstel_id    bigint REFERENCES whatsapp.voorstel(id) ON DELETE SET NULL,
    tijd           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_bericht_gesprek
    ON whatsapp.bericht (gesprek_id, tijd);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'whatsapp_writer') THEN
        CREATE ROLE whatsapp_writer LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA whatsapp TO whatsapp_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA whatsapp TO whatsapp_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA whatsapp TO whatsapp_writer;
GRANT USAGE ON SCHEMA whatsapp TO portal;
GRANT SELECT ON whatsapp.nummer TO portal;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('whatsapp.voorstel', 'antwoordvoorstel',
     'Een door de agent geschreven WhatsApp-antwoord dat een collega leest, '
     'aanpast en zelf verstuurt. De agent verstuurt nooit zelf.'),
    ('whatsapp.venster', '24-uursvenster',
     'WhatsApp laat een bedrijf alleen vrij antwoorden binnen 24 uur na het '
     'laatste bericht van de klant. Daarna mag alleen een door Meta '
     'goedgekeurd sjabloon.'),
    ('whatsapp.nummerregister', 'WhatsApp-nummerregister',
     'Per WhatsApp-nummer van de groep: firma, op welke gsm en computer het '
     'staat, in welke browser of app, wie het gebruikt en hoe het aan WhatsApp '
     'hangt (app, sandbox of API).')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
