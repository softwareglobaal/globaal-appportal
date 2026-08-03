-- 110: Postkamer-agent Elevait (brok B: bewaken en melden)
-- Aanleiding: ontwerp postkamer-agent, akkoord Shaniel 31-07-2026.
-- De site belooft een reactie binnen twee werkdagen; deze kolommen maken
-- die belofte bewaakbaar.
--
-- beantwoord: vastgesteld door in de map INBOX.Sent te zoeken naar een
-- antwoord in dezelfde conversatie (In-Reply-To en References). Telefonisch
-- afgehandelde post ziet de agent niet; daarvoor is de knop "afgehandeld".
-- zoom_gemeld_op: voorkomt dat dezelfde openstaande post elk uur opnieuw in
-- de teamchat verschijnt. Een kanaal dat te vaak piept wordt genegeerd.

ALTER TABLE elevait.bericht
    ADD COLUMN IF NOT EXISTS beantwoord     boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS beantwoord_op  timestamptz,
    ADD COLUMN IF NOT EXISTS zoom_gemeld_op timestamptz;

CREATE INDEX IF NOT EXISTS ix_elevait_bericht_open
    ON elevait.bericht (categorie, beantwoord, afgehandeld)
    WHERE NOT beantwoord AND NOT afgehandeld;

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('twee-werkdagen', 'Twee werkdagen',
   'De belofte op de website: een klantaanvraag of sollicitatie krijgt binnen twee werkdagen antwoord. De postkamer-agent bewaakt die belofte door in de map Verzonden te kijken of er in dezelfde conversatie een antwoord is uitgegaan. Telefonisch afgehandeld ziet hij niet; daarvoor zet een mens het bericht op afgehandeld.')
ON CONFLICT (sleutel) DO NOTHING;
