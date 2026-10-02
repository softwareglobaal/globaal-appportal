-- 183: De agendacode van een firma heeft twee letters.
--
-- Aanleiding: Mehdi, 02-10-2026: "Ik wil de afkortingen van de bedrijven allemaal met twee letters
-- hebben. Dus niet meer met vier letters en dan twee letters voor de agenda." Goedgekeurd dezelfde
-- dag ('goedgekeurd. pas ook aan in het dashboard dat geen discussie geeft'), uitgewerkt in
-- 'Agendawacht - onderzoek en herstelvoorstel v1.1' p. 9-11.
--
-- Drie codes per firma, elk met één betekenis:
--   code_agenda  (nieuw, twee letters) staat in de titel van een afspraak: [HA-KB], [UB-PO].
--   code_contact (twee letters, migratie 175) staat in de naamregel van een contact: HA5609, UN3782.
--                Ongewijzigd: de contacten in Google Contacts en Xelion dragen die code al.
--   code         (vier letters, HARC) blijft de interne sleutel voor boekhouding, mappen en
--                koppelingen; die lezen hem al (boekhouddashboard, kosten, wagenpark, contactwacht).
--                Niet meer in de agenda.
-- UnaBo heeft daardoor UB in de agenda en UN in de contacten; dat is bewust (v1.1 p. 9).
-- Geen firma verandert van naam, land, actiefstatus of id.

BEGIN;

ALTER TABLE kern.firma ADD COLUMN IF NOT EXISTS code_agenda text;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'firma_code_agenda_vorm') THEN
        ALTER TABLE kern.firma ADD CONSTRAINT firma_code_agenda_vorm
            CHECK (code_agenda IS NULL OR code_agenda ~ '^[A-Z]{2}$');
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS firma_code_agenda_uniek
    ON kern.firma (code_agenda) WHERE code_agenda IS NOT NULL;

UPDATE kern.firma f SET code_agenda = v.ca
  FROM (VALUES ('HARC', 'HA'), ('UNAB', 'UB'), ('TKNB', 'TK'), ('ENEF', 'EE'), ('ELEV', 'EL'),
               ('HINV', 'HI'), ('HARM', 'HB'), ('CONT', 'CX'), ('MELO', 'ME'), ('HDSI', 'DI'),
               ('HDSS', 'DS'), ('BFUT', 'BF'), ('CORE', 'CB'), ('ENST', 'ES'), ('MEDI', 'MS'),
               ('ORVA', 'OR'), ('QOPP', 'QP'), ('ZIDI', 'ZC')) AS v(code, ca)
 WHERE f.code = v.code AND f.code_agenda IS NULL;

-- Een firma zonder agendacode zou een vierletterige titel uitlokken: luid falen.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM kern.firma WHERE code_agenda IS NULL) THEN
        RAISE EXCEPTION 'firma zonder agendacode: %',
            (SELECT string_agg(code, ', ') FROM kern.firma WHERE code_agenda IS NULL);
    END IF;
END $$;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('agendacode', 'Agendacode',
     'De afkorting van twee letters van een firma in de titel van een afspraak, bv. [HA-KB] WB 2145, [UB-PO], [TK-KO]. Uniek per firma; beheerd op organisatie.globaal.be bij Firma''s. Sinds 02-10-2026 (Mehdi); daarvoor stond de interne code van vier letters in de titel.'),
    ('firmacode', 'Interne code',
     'De afkorting van vier letters van een firma, bv. HARC, UNAB, TKNB. Interne sleutel voor boekhouding, mappen en koppelingen. Staat sinds 02-10-2026 niet meer in de agenda: daar staat de agendacode van twee letters.'),
    ('contactcode', 'Contactcode',
     'De afkorting van twee letters van een firma in de naamregel van een contact in Google Contacts, die Xelion bij een oproep toont, bv. HA, UN, TK. Aan het dossiernummer geplakt: HA5609 is dossier 5609 van H-Architects. Niet te verwarren met de agendacode: UnaBo is UB in de agenda en UN in de contacten.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

UPDATE kern.bron_regel
   SET gegeven = 'Firma: naam, agendacode (twee letters), contactcode (twee letters), interne code (vier letters), land'
 WHERE sleutel = 'firma';

COMMIT;
