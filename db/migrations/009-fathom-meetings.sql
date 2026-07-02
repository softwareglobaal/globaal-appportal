-- 009 — Fathom-meetings in de Second Brain (levende data, geen handwerk).
--
-- De Second Brain synct incrementeel meetings + transcripts + actiepunten uit de
-- Fathom-API (FATHOM_API_KEYS in .env; meerdere opnemers mogelijk). Meetings worden
-- knopen in de graph (laatste 30 dagen), gelinkt aan personen; transcripts en open
-- actiepunten voeden de AI-chat en de dagbriefing ("niets wordt vergeten").

CREATE TABLE organisatie.meeting (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fathom_recording_id  bigint NOT NULL UNIQUE,   -- dedup over meerdere keys heen
    titel                text NOT NULL DEFAULT '',
    share_url            text NOT NULL DEFAULT '',
    opgenomen_door       text NOT NULL DEFAULT '',
    gestart_op           timestamptz,
    geeindigd_op         timestamptz,
    taal                 text NOT NULL DEFAULT '',
    transcript           text NOT NULL DEFAULT '',  -- "Spreker: tekst" per regel
    binnengehaald_op     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_meeting_gestart ON organisatie.meeting (gestart_op);

CREATE TABLE organisatie.meeting_deelnemer (
    meeting_id uuid NOT NULL REFERENCES organisatie.meeting(id) ON DELETE CASCADE,
    persoon_id uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    PRIMARY KEY (meeting_id, persoon_id)
);

CREATE TABLE organisatie.meeting_actiepunt (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id  uuid NOT NULL REFERENCES organisatie.meeting(id) ON DELETE CASCADE,
    tekst       text NOT NULL,
    afgehandeld boolean NOT NULL DEFAULT false
);

-- Sync-cursor per API-key (sha256-prefix als label; de key zelf wordt nooit opgeslagen).
CREATE TABLE organisatie.fathom_cursor (
    sleutel      text PRIMARY KEY,
    laatste_sync timestamptz NOT NULL
);

-- Lezen: gedekt door de default privileges van migratie 007 (portal).
GRANT SELECT, INSERT, UPDATE ON organisatie.meeting TO medewerker_writer;
GRANT SELECT, INSERT, DELETE ON organisatie.meeting_deelnemer TO medewerker_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON organisatie.meeting_actiepunt TO medewerker_writer;
GRANT SELECT, INSERT, UPDATE ON organisatie.fathom_cursor TO medewerker_writer;
