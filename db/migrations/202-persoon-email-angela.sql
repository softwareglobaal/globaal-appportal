-- 202: Het e-mailadres van Angela (Shaniel, 30-10-2026).
--
-- Bleef buiten migratie 201 omdat Zoom sollicitaties@medianselections.com toont, wat op een functie-adres lijkt. Het
-- juiste adres is angela@globaal.be. Het adres in Zoom zelf is hiermee niet gewijzigd. Een bestaand adres wordt nooit
-- overschreven, en de regel moet precies een persoon in dienst raken, anders faalt de migratie.

BEGIN;

UPDATE kern.persoon SET email = 'angela@globaal.be'
 WHERE voornaam = 'Angela' AND in_dienst AND email IS NULL;

DO $$
BEGIN
    IF (SELECT count(*) FROM kern.persoon WHERE voornaam = 'Angela' AND in_dienst AND email = 'angela@globaal.be') <> 1 THEN
        RAISE EXCEPTION 'angela@globaal.be hoort bij precies een persoon in dienst (Angela)';
    END IF;
END $$;

COMMIT;
