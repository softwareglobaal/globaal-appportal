-- 199: trainingen en opleidingen in de platform-inhoud van angela.sr.
-- De site krijgt de pagina Leren (angela.sr/leren) met eigen aanbod en dat
-- van opleiders in Suriname. Net als events en bedrijven (193) hoort die
-- inhoud in items.platform_inhoud, zodat Angela hem via Claude (MCP op
-- angela.sr/mcp) kan toevoegen en bijwerken. Deze migratie voegt de soort
-- 'opleiding' toe aan de CHECK.
--
-- Gevolg op de site: zolang er geen rijen zijn, staat Leren leeg met een
-- oproep om aanbod te plaatsen.
--
-- Idempotent: de constraint wordt eerst weggehaald als hij bestaat.

BEGIN;

ALTER TABLE items.platform_inhoud
    DROP CONSTRAINT IF EXISTS platform_inhoud_soort_check;

ALTER TABLE items.platform_inhoud
    ADD CONSTRAINT platform_inhoud_soort_check
    CHECK (soort IN ('verhaal','job','column','woord',
                     'spiegel_ook','sterk','zwak','band',
                     'event','bedrijf','opleiding'));

COMMIT;
