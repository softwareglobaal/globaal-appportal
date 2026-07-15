-- 066 - signalen-agent (archetype 2): tabellen voor de detectoren en de
-- AI-duiding.
--
-- Ontwerp (besluit Shaniel 2026-07-15, AI-agent-brainstorm): twee lagen,
-- conform het gangbare patroon bij monitoring-agents (regels detecteren,
-- het model licht toe en prioriteert):
--   Laag 1: detectoren draaien elk uur als gewone SQL in de organisatie-app
--           (kost niets) en schrijven bevindingen hier. De vingerafdruk
--           voorkomt dubbels: bestaat het signaal al, dan schuift alleen
--           laatste_keer op; verdwijnt de oorzaak, dan sluit het signaal
--           vanzelf (opgelost_op).
--   Laag 2: een AI-duiding per dag (Claude, zelfde sleutel als de
--           dagbriefing), plus een extra duiding zodra er een nieuw
--           signaal met ernst 'hoog' bijkomt. Zo blijven de kosten op
--           enkele euro's per maand.

CREATE TABLE organisatie.signaal (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code          text NOT NULL,
    vingerafdruk  text NOT NULL UNIQUE,
    ernst         text NOT NULL CHECK (ernst IN ('hoog', 'middel', 'laag')),
    titel         text NOT NULL,
    detail        jsonb NOT NULL DEFAULT '{}'::jsonb,
    eerste_keer   timestamptz NOT NULL DEFAULT now(),
    laatste_keer  timestamptz NOT NULL DEFAULT now(),
    opgelost_op   timestamptz
);
CREATE INDEX ix_signaal_open ON organisatie.signaal (code) WHERE opgelost_op IS NULL;

CREATE TABLE organisatie.signaal_duiding (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    aangemaakt_op  timestamptz NOT NULL DEFAULT now(),
    aanleiding     text NOT NULL DEFAULT 'dagelijks',
    tekst          text NOT NULL,
    signalen       jsonb NOT NULL DEFAULT '[]'::jsonb
);

-- Lezen voor de dashboards, schrijven alleen voor de agent in de
-- organisatie-app. Geen DELETE: opgeloste signalen en oude duidingen
-- blijven als historie staan.
GRANT SELECT ON organisatie.signaal, organisatie.signaal_duiding TO portal;
GRANT SELECT, INSERT, UPDATE ON organisatie.signaal TO medewerker_writer;
GRANT SELECT, INSERT ON organisatie.signaal_duiding TO medewerker_writer;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('signalen_agent', 'Signalen-agent',
     'De automatische bewaking van de bedrijfsdata: detectoren (vaste regels, elk uur) zoeken afwijkingen zoals een haperende Octopus-sync, een dossier zonder boekingen of een ongewoon grote boeking, en de AI vat de open signalen een keer per dag samen met een prioriteit en een eerstvolgende actie. Een signaal sluit vanzelf zodra de oorzaak weg is.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
