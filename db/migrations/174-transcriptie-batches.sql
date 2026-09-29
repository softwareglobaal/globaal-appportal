-- 174: Transcriptie in goedgekeurde batches, en het ruwe transcript naast de
-- door de correctie-agent verbeterde versie.
--
-- Aanleiding (Shaniel, 29-09-2026): de proefset is goedgekeurd door het
-- management; de 920 opgenomen gesprekken sinds 16-06-2026 gaan door Scribe
-- v2 met de correctie-agent erachter, in batches van 50. Een volgende batch
-- start pas na een kwaliteitscontrole van de vorige.
--
-- transcriptie_batch
--   Elke rij ontgrendelt een batch: tot en met dit aantal uitgeschreven
--   gesprekken buiten de proefset mag de werker gaan. Wie goedkeurde en
--   waarom staat erbij. Batch 1 is de goedkeuring van de proefset zelf, in de
--   plaats van een meting tegen de referentie. Het proefslot in de app leest
--   deze tabel; zonder rij voor de productievariant blijft het slot dicht.
--
-- gesprek_transcript: ruw_tekst en ruw_segmenten
--   Wat Scribe hoorde, onaangeroerd. tekst en segmenten worden na de
--   correctie-agent de verbeterde versie; agent_status volgt dat
--   ('' = niet van toepassing, wachtend, klaar, fout).

BEGIN;

CREATE TABLE IF NOT EXISTS communicatie.transcriptie_batch (
    nr               integer PRIMARY KEY,
    tot_en_met       integer NOT NULL CHECK (tot_en_met > 0),
    variant          text NOT NULL,
    goedgekeurd_door text NOT NULL,
    reden            text NOT NULL DEFAULT '',
    goedgekeurd_op   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE communicatie.gesprek_transcript
    ADD COLUMN IF NOT EXISTS ruw_tekst     text,
    ADD COLUMN IF NOT EXISTS ruw_segmenten jsonb,
    ADD COLUMN IF NOT EXISTS agent_status  text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS agent_fout    text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS agent_op      timestamptz;

CREATE INDEX IF NOT EXISTS ix_gesprek_transcript_agent_wachtend
    ON communicatie.gesprek_transcript (agent_status)
    WHERE agent_status = 'wachtend';

GRANT SELECT, INSERT ON communicatie.transcriptie_batch TO communicatie;

COMMIT;
