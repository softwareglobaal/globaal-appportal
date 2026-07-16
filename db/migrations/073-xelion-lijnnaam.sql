-- 073: de Xelion-lijnnaam in de belvolgorde-spiegel (cross-check 2026-07-16).
-- De tenant-admin-pagina (bron van waarheid volgens Shaniel) benoemt elke
-- lijn ("UNABO Sales", "Light Projects - H-A"); de poller haalde die naam al
-- op maar bewaarde hem niet. Met de naam in de spiegel kan het register
-- structureel vergeleken worden met wat Xelion zelf zegt, in plaats van via
-- losse screenshots.

ALTER TABLE communicatie.xelion_belvolgorde
    ADD COLUMN IF NOT EXISTS xelion_lijnnaam text NOT NULL DEFAULT '';
