-- 084: HR-agent fase 1 (Elevait)
-- Aanleiding: ontwerp HR-agent, besluit Shaniel 2026-07-28. De agent toetst
-- sollicitaties aan opgeschreven criteria en vult een scorekaart; mensen
-- (akadmin, mehdi) leggen hun eigen oordeel vast op de interne
-- wervingspagina (intern.elevaitnv.com). Beoordeling en oordeel komen NIET
-- als knopen in de Second Brain-graaf (bewuste curatie: inhoud is
-- vertrouwelijk beoordelingsmateriaal; de kandidaat-knoop volstaat).
-- Rechten lopen mee via de default privileges van migratie 083.

-- Koppeling naar de bronmap op het elevait-data-volume (pad, geen inhoud)
ALTER TABLE elevait.kandidaat ADD COLUMN IF NOT EXISTS bron_map text NOT NULL DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_elevait_kandidaat_bron_map
    ON elevait.kandidaat (bron_map) WHERE bron_map <> '';

-- Scorekaart van de agent: advies zonder opgeteld eindcijfer
CREATE TABLE IF NOT EXISTS elevait.beoordeling (
    id            bigserial PRIMARY KEY,
    kandidaat_id  bigint NOT NULL REFERENCES elevait.kandidaat(id) ON DELETE CASCADE,
    samenvatting  text NOT NULL,
    advies        text NOT NULL
                  CHECK (advies IN ('gesprek aanbevolen', 'twijfel', 'past niet')),
    criteria      jsonb NOT NULL DEFAULT '[]'::jsonb,
    opvallend     jsonb NOT NULL DEFAULT '[]'::jsonb,
    vragen        jsonb NOT NULL DEFAULT '[]'::jsonb,
    concepten     jsonb NOT NULL DEFAULT '{}'::jsonb,
    model         text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_elevait_beoordeling_kandidaat
    ON elevait.beoordeling (kandidaat_id);

-- Menselijk oordeel, een rij per beoordelaar per kandidaat
CREATE TABLE IF NOT EXISTS elevait.oordeel (
    id            bigserial PRIMARY KEY,
    kandidaat_id  bigint NOT NULL REFERENCES elevait.kandidaat(id) ON DELETE CASCADE,
    beoordelaar   text NOT NULL,
    oordeel       text NOT NULL DEFAULT '',
    notitie       text NOT NULL DEFAULT '',
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kandidaat_id, beoordelaar)
);

-- Begrip in het Elevait-definitieboek
INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('scorekaart', 'Scorekaart',
   'De toetsing van een sollicitatie aan de opgeschreven criteria per vacature: per criterium aangetroffen, deels of niet aangetroffen, met vindplaats. Bewust zonder opgeteld eindcijfer; de agent adviseert, de mens beslist.')
ON CONFLICT (sleutel) DO NOTHING;
