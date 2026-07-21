-- 077: agent-events - zichtbaarheid van het agent-team (wens Shaniel
-- 2026-07-21, na de geslaagde pilot van fase 1).
--
-- De vier rollen (architect, bouwer, reviewer, verifier) melden hun start,
-- klaar en fout via het token-endpoint van het organisatie-dashboard; de
-- Ontwikkeling-tab toont daarmee per rol de status. Eerlijkheid vooraf: de
-- agents zijn oproepkrachten, geen 24/7-diensten. "Rust" is hun normale
-- toestand; de weergave doet niet alsof er een wachtende dienst draait.

CREATE TABLE IF NOT EXISTS ontwikkeling.agent_event (
    id        bigserial PRIMARY KEY,
    rol       text NOT NULL,
    event     text NOT NULL CHECK (event IN ('start', 'klaar', 'fout')),
    taak      text NOT NULL DEFAULT '',
    repo      text NOT NULL DEFAULT '',
    gebruiker text NOT NULL DEFAULT '',   -- wie de agent-groep aanstuurde
    tokens    bigint,                     -- verbruik van de taak (alleen bij klaar/fout bekend)
    ts        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ontw_agent_event ON ontwikkeling.agent_event (rol, ts DESC);

GRANT SELECT ON ontwikkeling.agent_event TO portal;
GRANT INSERT ON ontwikkeling.agent_event TO medewerker_writer;
GRANT USAGE ON SEQUENCE ontwikkeling.agent_event_id_seq TO medewerker_writer;
