-- 186: Agenda-adressen van vier collega's.
--
-- Mehdi, 03-10-2026: "ik kan ja zeggen tegen alle punten die jij hebt genoemd". De adressen komen uit zijn
-- eigen agenda: elk stond al tientallen keren als gast op zijn interne afspraken (Matthew 26, Siyan 24, Angela 55,
-- Shaniel 3). De Agendawacht zet deze collega's voortaan zonder mail als gast op de afspraken waar ze bij horen
-- (migratie 185). Elke regel moet precies een persoon in dienst raken, anders faalt de migratie.

BEGIN;

UPDATE kern.persoon p SET email_agenda = v.adres
  FROM (VALUES ('Matthew', 'Blijd', 'matthewblijd10@gmail.com'),
               ('Siyan', 'Tong Sang', 'siyanhdswerk@gmail.com'),
               ('Angela', 'Soekhradj', 'soekhradjangelahb@gmail.com'),
               ('Shaniel', 'Badrie', 'shanielbadriesb@gmail.com')) AS v(voornaam, achternaam, adres)
 WHERE p.voornaam = v.voornaam AND p.achternaam = v.achternaam AND p.in_dienst AND p.email_agenda IS NULL;

DO $$
BEGIN
    IF (SELECT count(*) FROM kern.persoon WHERE email_agenda IN ('matthewblijd10@gmail.com', 'siyanhdswerk@gmail.com',
                                                                  'soekhradjangelahb@gmail.com', 'shanielbadriesb@gmail.com')) <> 4 THEN
        RAISE EXCEPTION 'de vier agenda-adressen horen bij precies vier personen (Matthew, Siyan, Angela, Shaniel)';
    END IF;
END $$;

COMMIT;
