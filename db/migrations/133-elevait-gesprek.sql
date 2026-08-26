-- 133: Gesprekken Elevait (Second Brain, fase 1: bron + herleidbaarheid)
-- Aanleiding: koersgesprek 25-08-2026. De gesprekken (Fathom) moeten niet
-- verloren gaan en Claude moet weten waar ze over gaan. Fase 1 legt de bron
-- vast en maakt elke afgeleide herleidbaar naar het gesprek waar hij uit komt.
--
-- De gesprekken zelf (samenvatting + transcript) zijn intern-strategisch en
-- bevatten persoonsgegevens van genoemde derden (klanten, leveranciers). Ze
-- worden daarom afgeschermd van de portal-rol (de bredere Second Brain-graaf);
-- 083 geeft portal via default privileges anders automatisch leesrecht. De vier
-- partners zien alles via de interne app (elevait_app). De AFGELEIDEN
-- (beslissingen, open eindjes) gaan wel de graaf in -- dat is de afspraak:
-- afgeleiden in de graaf, rauw materiaal afgeschermd.
--
-- Sprekers komen uit het transcript, niet uit de Fathom-genodigden: bij
-- impromptu meetings kent Fathom alleen de opnemer, terwijl de gesprekspartner
-- wel als spreker in het transcript staat.

CREATE TABLE IF NOT EXISTS elevait.gesprek (
    id                  bigserial PRIMARY KEY,
    fathom_recording_id bigint NOT NULL UNIQUE,   -- incrementele sync, geen dubbels
    titel               text NOT NULL DEFAULT '',
    opgenomen_op        timestamptz NOT NULL,
    opnemer             text NOT NULL DEFAULT '',
    opnemer_email       text NOT NULL DEFAULT '',
    sprekers            jsonb NOT NULL DEFAULT '[]'::jsonb,  -- uit het transcript
    samenvatting        text NOT NULL DEFAULT '',            -- Fathom-samenvatting (markdown)
    transcript          jsonb,                               -- rauw; NULL = niet bewaard
    deel_url            text NOT NULL DEFAULT '',            -- share_url
    bron_url            text NOT NULL DEFAULT '',            -- url
    verwerkt_op         timestamptz,                         -- NULL = nog niet gedestilleerd
    opgehaald_op        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_elevait_gesprek_datum
    ON elevait.gesprek (opgenomen_op DESC);
-- Snel de nog-te-destilleren gesprekken vinden.
CREATE INDEX IF NOT EXISTS ix_elevait_gesprek_onverwerkt
    ON elevait.gesprek (opgenomen_op) WHERE verwerkt_op IS NULL;

-- Herleidbaarheid: een beslissing of open eindje kan uit een gesprek komen.
-- Nullable en ON DELETE SET NULL: bestaande rijen hebben geen bron, en een
-- verwijderd gesprek laat de afgeleide bestaan (de beslissing gold echt).
ALTER TABLE elevait.beslissing
    ADD COLUMN IF NOT EXISTS gesprek_id bigint
        REFERENCES elevait.gesprek(id) ON DELETE SET NULL;
ALTER TABLE elevait.open_eindje
    ADD COLUMN IF NOT EXISTS gesprek_id bigint
        REFERENCES elevait.gesprek(id) ON DELETE SET NULL;

-- Beloningsgevoelig-patroon toegepast op strategische gesprekken: uit de graaf.
REVOKE SELECT ON elevait.gesprek FROM portal;

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('gesprek', 'Gesprek',
   'Een opgenomen overleg (via Fathom), bewaard als bron voor de Second Brain: titel, datum, sprekers (uit het transcript), de samenvatting en optioneel het transcript. De beslissingen en open eindjes die eruit gedestilleerd worden verwijzen terug naar het gesprek, zodat elke afgeleide herleidbaar is. Het gesprek zelf blijft intern (afgeschermd van de bredere graaf); de afgeleiden niet.')
ON CONFLICT (sleutel) DO NOTHING;
