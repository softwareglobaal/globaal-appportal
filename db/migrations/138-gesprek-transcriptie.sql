-- 138: Transcripties van Xelion-gesprekken (Plaud).
--
-- Aanleiding: opdracht Shaniel 31-08-2026. De telefooncentrale bewaart van elk
-- opgenomen gesprek een mp3 (communicatie.xelion_communicatie.opname_status =
-- 'recorded'), maar niemand luistert die ooit terug. Plaud levert een
-- transcriptie-API die spraak omzet in tekst met sprekerherkenning. Deze tabel
-- is de landingsplaats: per gesprek precies een rij, met de tekst en de
-- segmenten (tijdstempels + sprekerlabels).
--
-- Bewust anders dan het archief (migratie 034): hier WEL DELETE. Een
-- gespreksarchief wis je niet, maar een transcriptie is de letterlijke inhoud
-- van wat mensen tegen elkaar zeiden. Dat moet je kunnen intrekken zonder aan
-- het archief te komen: verwijder de transcriptie, de oproep zelf blijft staan.
-- Verwijderen zet de rij niet terug op 'wachtend' maar weg; opnieuw laten
-- transcriberen is dan een bewuste handeling.
--
-- Privacy: wie de tekst mag lezen is een rechtenkwestie in de app, niet hier.
-- De app toont transcripties alleen aan de editors-groepen (EDITOR_GROUPS),
-- niet aan iedereen die het communicatie-dashboard mag openen.

CREATE TABLE IF NOT EXISTS communicatie.gesprek_transcript (
    oid            text PRIMARY KEY
                   REFERENCES communicatie.xelion_communicatie(oid) ON DELETE CASCADE,
    status         text NOT NULL DEFAULT 'wachtend'
                   CHECK (status IN ('wachtend', 'verstuurd', 'klaar', 'mislukt', 'overgeslagen')),
    plaud_id       text NOT NULL DEFAULT '',      -- transcription_id bij Plaud
    taal           text NOT NULL DEFAULT '',      -- door Plaud gedetecteerd (BCP-47)
    duur_sec       integer,                       -- lengte volgens Plaud (afrekengrondslag)
    sprekers       integer,                       -- aantal onderscheiden stemmen
    tekst          text NOT NULL DEFAULT '',      -- de volledige transcriptie
    segmenten      jsonb,                         -- [{start, eind, spreker, tekst}, ...]
    audio_bytes    integer,                       -- grootte van de mp3 uit Xelion
    pogingen       integer NOT NULL DEFAULT 0,
    fout           text NOT NULL DEFAULT '',
    aangemaakt_op  timestamptz NOT NULL DEFAULT now(),
    verstuurd_op   timestamptz,                   -- moment van indienen bij Plaud
    klaar_op       timestamptz,
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now()
);

-- De werkvoorraad van de poller: alles wat nog niet klaar is, oudste eerst.
CREATE INDEX IF NOT EXISTS ix_gesprek_transcript_werk
    ON communicatie.gesprek_transcript (status, aangemaakt_op)
    WHERE status IN ('wachtend', 'verstuurd');
CREATE INDEX IF NOT EXISTS ix_gesprek_transcript_klaar
    ON communicatie.gesprek_transcript (klaar_op DESC)
    WHERE status = 'klaar';
-- Zoeken in de tekst. Bewust 'simple' en niet 'dutch': de gesprekken lopen door
-- elkaar in Nederlands, Frans en Engels, dus een taalspecifieke stemmer zou het
-- ene deel helpen en het andere verminken.
CREATE INDEX IF NOT EXISTS ix_gesprek_transcript_tekst
    ON communicatie.gesprek_transcript
    USING gin (to_tsvector('simple', tekst));

-- Status van de transcriptie-poller, op dezelfde statusrij als de Xelion-poller.
ALTER TABLE communicatie.xelion_sync
    ADD COLUMN IF NOT EXISTS trans_laatste_run timestamptz,
    ADD COLUMN IF NOT EXISTS trans_fout        text;

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.gesprek_transcript TO communicatie;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
  ('gesprek_transcript', 'Transcriptie',
   'De uitgeschreven tekst van een opgenomen telefoongesprek, met tijdstempels en sprekerlabels. De opname komt uit de telefooncentrale (Xelion) en wordt door Plaud omgezet naar tekst. Een transcriptie bestaat alleen voor gesprekken die daadwerkelijk zijn opgenomen en lang genoeg duren; de tekst is zichtbaar voor de beheerders van het communicatie-dashboard, niet voor iedereen.')
ON CONFLICT (sleutel) DO NOTHING;
