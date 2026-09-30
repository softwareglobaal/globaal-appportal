-- 178: het WhatsApp-nummer van de agents (+32 460 23 30 42, "UNABO Assistant").
--
-- Waarom: Mehdi wil de meldingen van De Bode op zijn prive-WhatsApp, niet op
-- Telegram (30-09-2026), en een eigen agentennummer in plaats van het
-- UNABO-nummer. Het nummer staat sinds 30-09-2026 live op de Cloud API in
-- WABA Unabo (phone number ID 1363238613534658).
--
-- De WhatsApp-app bewaart binnenkomende berichten alleen voor nummers in dit
-- register; De Bode leest daaruit het 24-uursvenster en Mehdi's antwoorden.
-- Maar dit is Mehdi's eigen draad met zijn agents, geen klantgesprek: Office
-- hoort het niet in de gedeelde inbox te zien. Daarom een vlag in_inbox; de
-- app toont alleen gesprekken van nummers met in_inbox = true.

ALTER TABLE whatsapp.nummer
    ADD COLUMN IF NOT EXISTS in_inbox boolean NOT NULL DEFAULT true;

INSERT INTO whatsapp.nummer (nummer, firma_code, status, meta_phone_number_id, agent_aan, in_inbox,
                             gebruikt_door, opmerking, bijgewerkt_door)
VALUES ('+32460233042', 'UNAB', 'api', '1363238613534658', false, false,
        'De Bode (agents van Mehdi)',
        'Twilio-nummer, weergavenaam UNABO Assistant. Alleen voor meldingen van de agents aan Mehdi; '
        'niet zichtbaar in de inbox. Belt ook: vastzit- en alarmoproepen (TWILIO_VAN_VAST).',
        'migratie 178')
ON CONFLICT (nummer) DO UPDATE
   SET meta_phone_number_id = EXCLUDED.meta_phone_number_id,
       status = EXCLUDED.status, agent_aan = false, in_inbox = false,
       gebruikt_door = EXCLUDED.gebruikt_door, opmerking = EXCLUDED.opmerking,
       bijgewerkt_door = EXCLUDED.bijgewerkt_door, bijgewerkt_op = now();

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('whatsapp.agentennummer', 'agentennummer',
     'Het WhatsApp-nummer waarmee de agents Mehdi berichten sturen (UNABO Assistant, '
     '+32 460 23 30 42). Staat in het nummerregister van de WhatsApp-app, maar niet in '
     'de gedeelde inbox.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
