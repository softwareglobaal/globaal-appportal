-- 010 — het vangnet: AI-extractie uit meeting-transcripts.
--
-- Elke gesyncte meeting krijgt één AI-extractieronde: samenvatting, actiepunten
-- (met een VOORGESTELDE eigenaar — de mens bevestigt via de Taken-pagina),
-- beslissingen (aparte categorie: "we nemen iemand aan" ≠ "HR maakt het profiel")
-- en vermeldingen (welke bestaande knopen inhoudelijk besproken zijn → de
-- "besproken"-relaties in de Second Brain).

ALTER TABLE organisatie.meeting
    ADD COLUMN samenvatting text NOT NULL DEFAULT '',
    ADD COLUMN geextraheerd boolean NOT NULL DEFAULT false;

ALTER TABLE organisatie.meeting_actiepunt
    ADD COLUMN bron text NOT NULL DEFAULT 'fathom',          -- 'fathom' | 'ai'
    ADD COLUMN voorgesteld_aan_persoon_id uuid REFERENCES kern.persoon(id),
    ADD COLUMN toegewezen_aan_persoon_id  uuid REFERENCES kern.persoon(id);
    -- workflow: AI vult voorgesteld_aan; een mens zet toegewezen_aan (= bevestigd).

CREATE TABLE organisatie.meeting_beslissing (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id uuid NOT NULL REFERENCES organisatie.meeting(id) ON DELETE CASCADE,
    tekst      text NOT NULL
);

-- Inhoudelijk besproken knopen, in graph-notatie ('p:', 'f:', 's:', ...).
CREATE TABLE organisatie.meeting_vermelding (
    meeting_id uuid NOT NULL REFERENCES organisatie.meeting(id) ON DELETE CASCADE,
    doel       text NOT NULL,
    PRIMARY KEY (meeting_id, doel)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON organisatie.meeting_beslissing TO medewerker_writer;
GRANT SELECT, INSERT, DELETE ON organisatie.meeting_vermelding TO medewerker_writer;
