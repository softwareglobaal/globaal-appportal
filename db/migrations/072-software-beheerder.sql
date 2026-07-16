-- 072: softwarekaart traceerbaar maken (besluit Shaniel 2026-07-16).
-- De beheerder was vrije tekst (kolom admin); wordt een echte koppeling naar
-- kern.persoon zodat de naam klikbaar is en op het persoonsprofiel en in de
-- graaf verschijnt. Het einde/verlengt-op-veld was vrije tekst; wordt een
-- datum. Beide velden waren overal leeg (gemeten 2026-07-16), dus er valt
-- niets te migreren; de oude admin-kolom blijft staan als archief maar
-- verdwijnt uit het formulier.

ALTER TABLE kosten.software
    ADD COLUMN IF NOT EXISTS beheerder_persoon_id uuid
        REFERENCES kern.persoon(id) ON DELETE SET NULL;

ALTER TABLE kosten.software
    ALTER COLUMN end_date TYPE date USING nullif(end_date, '')::date;
