-- 185: Het agenda-adres van een persoon.
--
-- Aanleiding: Mehdi, 03-10-2026: "ik wil eigenlijk in de toekomst een systeem vinden waarbij je iemand kunt
-- toevoegen ... Die agenda wordt dan gezien door Catalin ... Zodat het gewoon op hun agenda verschijnt in de
-- toekomst. Dan hoef ik niet handmatig mails te ontvangen ... Dat zijn allemaal Gmail-adressen."
--
-- email_agenda is het adres waarmee iemand zijn agenda leest (meestal een Gmail-adres). De Agendawacht zet die
-- persoon als gast op de afspraken waar hij bij hoort (zijn naam in de titel, of een afspraak van de firma waar hij
-- partner is), zonder mail (sendUpdates=none): de afspraak verschijnt in zijn agenda. Iemand toevoegen is dit veld
-- invullen op organisatie.globaal.be bij de persoon. Het werkadres (email) en het privé-adres in de HR-laag blijven
-- wat ze waren; dit veld is alleen voor de agenda.
-- Catalin (Harmoniebouw) krijgt harmoniebouw@gmail.com, door Mehdi bevestigd op 03-10-2026. Andere adressen
-- worden pas ingevuld na Mehdi's bevestiging: een verkeerd adres deelt zijn agenda met een vreemde.

BEGIN;

ALTER TABLE kern.persoon ADD COLUMN IF NOT EXISTS email_agenda text;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'persoon_email_agenda_vorm') THEN
        ALTER TABLE kern.persoon ADD CONSTRAINT persoon_email_agenda_vorm
            CHECK (email_agenda IS NULL OR email_agenda ~ '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$');
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS persoon_email_agenda_uniek
    ON kern.persoon (email_agenda) WHERE email_agenda IS NOT NULL;

-- het dashboard (organisatie.globaal.be) mag het veld bijwerken, zoals naam en dienstverband (migratie 153)
GRANT UPDATE (email_agenda) ON kern.persoon TO medewerker_writer;

UPDATE kern.persoon p SET email_agenda = 'harmoniebouw@gmail.com'
  FROM kern.firma f
 WHERE f.id = p.werkgever_firma_id AND f.code = 'HARM' AND p.voornaam = 'Catalin' AND p.email_agenda IS NULL;

DO $$
BEGIN
    IF (SELECT count(*) FROM kern.persoon WHERE email_agenda = 'harmoniebouw@gmail.com') <> 1 THEN
        RAISE EXCEPTION 'harmoniebouw@gmail.com hoort bij precies een persoon (Catalin, Harmoniebouw)';
    END IF;
END $$;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('agenda_adres', 'Agenda-adres',
     'Het adres waarmee iemand zijn agenda leest, meestal een Gmail-adres. De Agendawacht zet die persoon als gast op de afspraken waar hij bij hoort, zonder mail: de afspraak verschijnt in zijn agenda. Iemand toevoegen is dit veld invullen bij de persoon. Sinds 03-10-2026 (Mehdi).')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
