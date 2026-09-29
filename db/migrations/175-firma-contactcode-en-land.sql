-- 175: Twee codes per firma, en het land als ISO-code.
--
-- Aanleiding: Mehdi, 29-09-2026. Een firma heeft twee afkortingen:
--   de firmacode van vier letters (HARC), voor agenda, mappen en gesprekken;
--   de contactcode van twee letters (HA), voor de naamregel van een contact in
--   Google Contacts, die Xelion bij een oproep toont: K HA5609 UN3782 SCN Jan Peeters.
-- De contactcodes stonden tot nu alleen in de werkwijze van De Contactwacht. Nu staan
-- ze in kern.firma, naast de firmacode, zodat agenda en contacten een bron hebben. De
-- Contactwacht leest ze via mijnagents-runner/koppelingen/organisatie.py.
--
-- Tweede punt van dezelfde dag: het land van een firma stond door elkaar als
-- 'België', 'BE', 'Suriname', 'SR' en 'India'. Voortaan de ISO 3166-1-code van twee
-- letters (BE, SR, IN); de volle naam is alleen weergave in de organisatie-app.
-- Suriname is SR. Gemeten op 29-09-2026: buiten de organisatie-app leest niemand
-- kern.firma.land (het boekhouddashboard leest zijn eigen register, de wagenparkwacht
-- het land van een voertuig, communicatie het land van een telefoonnummer).
--
-- Beide vastgezet met een CHECK, zodat een latere wijziging ze niet ongemerkt breekt.
-- Een landnaam die hieronder niet omgezet wordt, laat de CHECK falen en de hele
-- migratie terugrollen: liever een luide fout dan een stil gat.

BEGIN;

ALTER TABLE kern.firma ADD COLUMN IF NOT EXISTS code_contact text;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'firma_code_contact_vorm') THEN
        ALTER TABLE kern.firma ADD CONSTRAINT firma_code_contact_vorm
            CHECK (code_contact IS NULL OR code_contact ~ '^[A-Z]{2}$');
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS firma_code_contact_uniek
    ON kern.firma (code_contact) WHERE code_contact IS NOT NULL;

-- De contactcodes uit de werkwijze van De Contactwacht (v0.1, 29-09-2026). Alleen een
-- firma met klanten of prospects heeft er een nodig; de andere blijven leeg tot iemand
-- er een geeft op organisatie.globaal.be.
UPDATE kern.firma f SET code_contact = v.cc
  FROM (VALUES ('HARC', 'HA'), ('UNAB', 'UN'), ('TKNB', 'TK'), ('ENEF', 'EE'),
               ('HARM', 'HB'), ('CONT', 'CX'), ('ELEV', 'EL')) AS v(code, cc)
 WHERE f.code = v.code AND f.code_contact IS NULL;

UPDATE kern.firma SET land = CASE
        WHEN lower(land) IN ('belgië', 'belgie', 'belgium', 'belgique', 'be') THEN 'BE'
        WHEN lower(land) IN ('suriname', 'su', 'sr') THEN 'SR'
        WHEN lower(land) IN ('india', 'in') THEN 'IN'
        WHEN lower(land) IN ('nederland', 'netherlands', 'nl') THEN 'NL'
        ELSE land END
 WHERE land !~ '^[A-Z]{2}$';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'firma_land_iso') THEN
        ALTER TABLE kern.firma ADD CONSTRAINT firma_land_iso CHECK (land ~ '^[A-Z]{2}$');
    END IF;
END $$;

-- De regel op de pagina Bron van de waarheid. Zoals in 172: Voorstel, zonder
-- beslisser; de migratie kiest niet wie beslist. Mehdi staat in BRON_BEHEER en kan
-- hem zelf op Besloten zetten.
INSERT INTO kern.bron_regel (sleutel, volgorde, gegeven, bron, wie_wijzigt, kopieen, hoe) VALUES
    ('firma', 40, 'Firma: naam, firmacode, contactcode, land',
     'Organisatie-dashboard (Firma''s)', 'Mehdi',
     'Agendawacht, De Contactwacht, naamregels in Google Contacts en Xelion',
     'De agents lezen kern.firma bij elke ronde; een naamregel in Google Contacts past zich niet vanzelf aan als een code verandert')
ON CONFLICT (sleutel) DO NOTHING;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('firmacode', 'Firmacode',
     'De afkorting van vier letters van een firma, bv. HARC, UNAB, TKNB. Staat in agenda-afspraken, mapnamen en gesprekken. Uniek per firma; beheerd op organisatie.globaal.be bij Firma''s.'),
    ('contactcode', 'Contactcode',
     'De afkorting van twee letters van een firma in de naamregel van een contact in Google Contacts, die Xelion bij een oproep toont, bv. HA, UN, TK. Aan het dossiernummer geplakt: HA5609 is dossier 5609 van H-Architects. Uniek per firma; alleen een firma met klanten of prospects heeft er een. De Contactwacht leest ze hier.'),
    ('landcode_firma', 'Land (firma)',
     'Het land van een firma als ISO-code van twee letters: BE België, NL Nederland, SR Suriname, IN India. De volle naam is alleen weergave. Niet te verwarren met het land van een telefoonnummer.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
