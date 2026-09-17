-- 152: Levensteken van de lokale transcriptiewerker.
--
-- Besluit Shaniel 17-09-2026: de opnames worden niet door een dienst in de VS
-- uitgeschreven maar door Whisper op een eigen Linux-pc. Die pc heeft geen
-- publiek adres en haalt zijn werk zelf op bij het communicatie-dashboard
-- (/werker, buiten de forward-auth om, met een eigen token).
--
-- Omdat er dan niets meer is dat vanaf onze kant zichtbaar maakt of de pc nog
-- leeft, meldt hij zich elke ronde. Twee kolommen op dezelfde statusrij als de
-- andere pollers, zodat de tab kan tonen wanneer er voor het laatst gewerkt is.
-- Geen eigen tabel: dit is een stand, geen geschiedenis.

ALTER TABLE communicatie.xelion_sync
    ADD COLUMN IF NOT EXISTS werker_laatste_run timestamptz,
    ADD COLUMN IF NOT EXISTS werker_melding     text;
