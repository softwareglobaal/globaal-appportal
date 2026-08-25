-- 129: Een overgeslagen bevestiging mag opnieuw geprobeerd worden (Elevait)
-- Aanleiding: bevinding bij het nalezen van de HR-agent, 21-08-2026.
--
-- mailer.al_verstuurd() blokkeerde op ELKE rij in uitgaande_mail, ongeacht
-- de status. Daardoor was de noodrem ELEVAIT_MAIL_ACTIEF geen pauze maar een
-- blijvende uitsluiting: een kandidaat die beoordeeld werd terwijl de mail
-- uitstond kreeg een rij 'overgeslagen' en daarna nooit meer een
-- ontvangstbevestiging, ook niet nadat de mail weer aanging. Hetzelfde gold
-- voor een SMTP-storing en voor het dagplafond. De website belooft antwoord
-- binnen twee werkdagen; deze kandidaten vielen stil zonder dat iets dat
-- meldde, want de postkamer bewaakt de mailbox en zij kwamen via het
-- formulier binnen.
--
-- De oorzaak is dat een status twee dingen betekende: "krijgt dit bewust
-- niet" (de backfill van migratie 111) en "nu even niet gelukt". Vanaf nu:
--
--   verzonden     eindpunt, is de deur uit
--   concept       eindpunt, staat klaar voor een mens
--   uitgesloten   eindpunt, krijgt dit bericht bewust niet          (NIEUW)
--   mislukt       tijdelijk, de volgende ronde probeert opnieuw
--   overgeslagen  tijdelijk, de volgende ronde probeert opnieuw
--
-- Zolang het tijdelijk is blijft het bij een rij per kandidaat en soort, met
-- een pogingteller. Anders schrijft een agent die elke vijf minuten langskomt
-- een nieuwe regel per ronde, en dat maakt het tabblad onleesbaar; dezelfde
-- les als het herinneringsplafond van migratie 113.

ALTER TABLE elevait.uitgaande_mail DROP CONSTRAINT IF EXISTS uitgaande_mail_status_check;
ALTER TABLE elevait.uitgaande_mail ADD CONSTRAINT uitgaande_mail_status_check
    CHECK (status IN ('verzonden', 'mislukt', 'overgeslagen', 'concept', 'uitgesloten'));

ALTER TABLE elevait.uitgaande_mail
    ADD COLUMN IF NOT EXISTS poging integer NOT NULL DEFAULT 1;

-- De backfill van migratie 111: bewust geen post met terugwerkende kracht.
-- Dat was en blijft een eindpunt, maar hoort niet dezelfde naam te dragen
-- als een bevestiging die alleen nog niet gelukt is.
UPDATE elevait.uitgaande_mail
   SET status = 'uitgesloten'
 WHERE status = 'overgeslagen' AND door = 'migratie';

-- Een ontbrekend of onleesbaar adres verandert ook niet meer.
UPDATE elevait.uitgaande_mail
   SET status = 'uitgesloten'
 WHERE status = 'overgeslagen' AND reden LIKE 'Geen bruikbaar e-mailadres%';

-- Wat nu nog op 'overgeslagen' of 'mislukt' staat is de noodrem, het
-- dagplafond of een storing. Die kandidaten zijn vanaf deze migratie vanzelf
-- weer in behandeling: de eerstvolgende ronde van de HR-agent pakt ze op.

-- Hoogstens een lopende rij per kandidaat en soort, zodat een herhaalde
-- poging de bestaande regel bijwerkt. Eerst opruimen wat er uit het verleden
-- dubbel zou staan, anders kan de index niet worden aangelegd en breekt de
-- migratie halverwege.
DELETE FROM elevait.uitgaande_mail u
 WHERE u.status IN ('mislukt', 'overgeslagen')
   AND EXISTS (SELECT 1 FROM elevait.uitgaande_mail n
                WHERE n.kandidaat_id = u.kandidaat_id
                  AND n.soort = u.soort
                  AND n.status IN ('mislukt', 'overgeslagen')
                  AND (n.verzonden_op, n.id) > (u.verzonden_op, u.id));

CREATE UNIQUE INDEX IF NOT EXISTS ux_elevait_uitgaande_mail_lopend
    ON elevait.uitgaande_mail (kandidaat_id, soort)
    WHERE status IN ('mislukt', 'overgeslagen');

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('uitgesloten', 'Uitgesloten',
   'Een bericht dat deze kandidaat bewust niet krijgt, en later ook niet alsnog: hij solliciteerde voordat de agent bevestigingen stuurde, er staat geen bruikbaar e-mailadres in de sollicitatie, of het versturen is zo vaak mislukt dat de agent is gestopt. De reden staat erbij. Onderscheiden van overgeslagen, want dat is tijdelijk.'),
  ('lopende-post', 'Lopende post',
   'Een bericht dat nog moet uitgaan: overgeslagen omdat de uitgaande mail uitstond of het dagplafond bereikt was, of mislukt door een storing. De agent probeert het bij elke ronde opnieuw en telt de pogingen; er komt geen nieuwe regel bij, de bestaande wordt bijgewerkt.')
ON CONFLICT (sleutel) DO NOTHING;
