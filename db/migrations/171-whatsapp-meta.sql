-- 171: WhatsApp-app van Twilio naar de Cloud API van Meta (besluit 24-09-2026).
--
-- Waarom: een partij minder, geen opslag per bericht bovenop Meta, en
-- coexistence: het nummer blijft werken in de WhatsApp Business-app op de gsm,
-- en wat daar verstuurd wordt komt als echo ook in de inbox.
--
-- Meta meldt een binnenkomend bericht met het phone_number_id van ons nummer,
-- niet met het nummer zelf; dat ID komt dus in het register. De bericht-ID
-- heet voortaan extern_id (bij Meta een wamid), want hij is niet meer van
-- Twilio. Migratie 170 draaide dezelfde dag en de tabellen zijn nog leeg.

ALTER TABLE whatsapp.nummer
    ADD COLUMN IF NOT EXISTS meta_phone_number_id text UNIQUE;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'whatsapp' AND table_name = 'bericht'
                  AND column_name = 'twilio_sid') THEN
        ALTER TABLE whatsapp.bericht RENAME COLUMN twilio_sid TO extern_id;
    END IF;
END $$;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('whatsapp.coexistence', 'coexistence',
     'Een WhatsApp-nummer dat tegelijk in de WhatsApp Business-app op een gsm '
     'en op de Cloud API van Meta werkt. Berichten die op de gsm verstuurd '
     'worden, komen als echo ook in de inbox.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
