-- 086: geschiktheid per rol in de HR-agent-beoordeling (Elevait)
-- Aanleiding: verzoek Shaniel 2026-07-28. Een open sollicitant werd alleen
-- aan de mindset-criteria getoetst, zonder brug naar de openstaande rollen.
-- De beoordeling krijgt een rollen-blok: per rol een indicatie (goed
-- passend, mogelijk passend, niet passend) met onderbouwing, geen cijfers.
-- Rechten lopen mee via de default privileges van migratie 083; geen
-- graaf-wijziging nodig (beoordeling staat bewust buiten de graaf).

ALTER TABLE elevait.beoordeling
    ADD COLUMN IF NOT EXISTS rollen jsonb NOT NULL DEFAULT '[]'::jsonb;
