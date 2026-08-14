-- 115: Conceptpost van de HR-agent (Elevait)
-- Aanleiding: Shaniel vroeg om een conceptuitnodiging voor een kandidaat.
-- De agent schrijft die al bij de beoordeling; wat ontbrak was een plek waar
-- je hem opent en verstuurt. Nu zet hij het concept in de map Concepten van
-- de mailbox, met de huisstijl eronder, zodat je alleen nog datum en tijd
-- invult en op versturen drukt.
--
-- Een concept kan per definitie niet vanzelf de deur uit. De grens blijft dus
-- staan: uitnodigen en afwijzen is en blijft een menselijk besluit.

ALTER TABLE elevait.uitgaande_mail DROP CONSTRAINT IF EXISTS uitgaande_mail_status_check;
ALTER TABLE elevait.uitgaande_mail ADD CONSTRAINT uitgaande_mail_status_check
    CHECK (status IN ('verzonden', 'mislukt', 'overgeslagen', 'concept'));

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('conceptpost', 'Conceptpost',
   'Een brief die de HR-agent schrijft en in de map Concepten van de mailbox zet, met de huisstijl eronder en met invulvelden voor wat de agent niet mag bepalen, zoals datum en tijd. Een mens opent, vult aan en verstuurt. Zo blijft het besluit menselijk terwijl het schrijfwerk verdwijnt.')
ON CONFLICT (sleutel) DO NOTHING;
