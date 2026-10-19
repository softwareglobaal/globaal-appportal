-- 193: events en bedrijven in de platform-inhoud van angela.sr.
-- De nieuwe site (live sinds 2026-10-19) heeft de pagina's Events en
-- Bedrijven. Hun inhoud hoort, net als verhalen en jobs, in
-- items.platform_inhoud zodat Angela ze via Claude (MCP op angela.sr/mcp)
-- kan toevoegen en bijwerken. De CHECK uit 135 liet alleen de oude soorten
-- toe; deze migratie voegt 'event' en 'bedrijf' toe.
--
-- Gevolg op de site: zolang er geen rijen van een soort zijn, toont de app
-- voor bedrijven de vier bedrijven uit de code (pp.BEDRIJVEN_PLATFORM) en
-- voor events een lege agenda. Zodra er een eerste bedrijf in de tabel staat,
-- toont de site alleen nog de bedrijven uit de tabel.
--
-- Idempotent: de constraint wordt eerst weggehaald als hij bestaat.

BEGIN;

ALTER TABLE items.platform_inhoud
    DROP CONSTRAINT IF EXISTS platform_inhoud_soort_check;

ALTER TABLE items.platform_inhoud
    ADD CONSTRAINT platform_inhoud_soort_check
    CHECK (soort IN ('verhaal','job','column','woord',
                     'spiegel_ook','sterk','zwak','band',
                     'event','bedrijf'));

COMMIT;
