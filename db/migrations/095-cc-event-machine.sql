-- 095: machine erbij in de hook-meting
-- Aanleiding: vraag Shaniel 2026-07-29. Hij werkt op twee machines (laptop en
-- een i9-werkstation) en wilde zien wat er op welke draait. cc_event legde dat
-- niet vast, dus twee machines van dezelfde persoon zijn niet te scheiden;
-- cc_tijd (migratie 094) kent het veld al. Dit trekt de twee gelijk.
--
-- Leeg blijft toegestaan: een hook van voor deze wijziging stuurt niets mee en
-- mag daar niet op stuklopen.

ALTER TABLE ontwikkeling.cc_event
    ADD COLUMN IF NOT EXISTS machine text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS ix_ontw_cc_event_machine
    ON ontwikkeling.cc_event (machine, ts);
