-- 018 — finalisatie-status (Second Brain) + KBO-nummer op firma's.
--
-- Meeting 2026-07-02 (Mehdi):
-- 1. "Blauw = gefinaliseerd, rood = nog niet" — per knoop vastleggen dat de data
--    gecontroleerd/gefinaliseerd is, mét wie en wanneer ("rollen wijzigen;
--    historie telt"). Daarom append-only: elke (de)finalisatie is een nieuwe rij,
--    de recentste geldt; er wordt nooit gewist of overschreven.
--    `doel` gebruikt de knoopnotatie van de Second Brain (p:/f:/a:/l:/s:/n:/e:/m:),
--    net als organisatie.meeting_vermelding.
-- 2. KBO-koppeling als eerstvolgende databron: het ondernemingsnummer op
--    kern.firma; het Organisatie-dashboard linkt ermee naar KBO Public Search en
--    de NBB-jaarrekeningen (verrijking via API's kan er later bovenop).

ALTER TABLE kern.firma
    ADD COLUMN kbo_nummer text NOT NULL DEFAULT '';   -- formaat vrij; bv. 1008.337.269

CREATE TABLE organisatie.finalisatie (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doel          text NOT NULL,          -- knoopnotatie, bv. 'f:<uuid>' of 'n:<uuid>'
    gefinaliseerd boolean NOT NULL,       -- true = gefinaliseerd; false = teruggedraaid
    door          text NOT NULL,          -- Authentik-username (Mehdi/Angela/Sian/…)
    op            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_finalisatie_doel ON organisatie.finalisatie (doel, op DESC);

-- Rechten: lezen voor portal, alleen INSERT voor de writer (append-only afgedwongen).
GRANT SELECT ON organisatie.finalisatie TO portal;
GRANT SELECT, INSERT ON organisatie.finalisatie TO medewerker_writer;
