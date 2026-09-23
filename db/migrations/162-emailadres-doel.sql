-- 162: Doel op het e-mailadres. Waarvoor dient dit adres.
--
-- Aanleiding: vergadering 22-09-2026. Mehdi over info@elevaitservices.com:
-- "ik kan die vraag binnen een week terugvragen, het is niet dat ik kan
-- onthouden. Dus dan zou dat eigenlijk de doel moeten ook er voorbij staan."
-- Het register zei tot nu toe wie verantwoordelijk is en wat het kost, maar
-- niet waarvoor een adres bestaat. Dat is precies wat je een week later kwijt
-- bent.
--
-- Hergebruik, geen nieuw begrip: `doel` bestaat al voor telefoonnummers, met
-- dezelfde betekenis en dezelfde beheerde keuzelijst (communicatie.lijst,
-- categorie "Doel"). Een nummer en een adres die allebei voor Finance zijn,
-- horen hetzelfde woord te krijgen; dat is het punt dat Mehdi in dezelfde
-- vergadering maakte over een centrale bron in plaats van vijf dashboards.
--
-- Wel een verschil in invoer. Bij nummers is doel een vrij tekstveld met
-- meerdere waarden achter puntkomma's, en dat is uit de hand gelopen: 58
-- verschillende waarden op 94 nummers, waaronder namen van collega's en
-- "Enstaco (oud)/Ashvand". Op 502 adressen zou dat driehonderd waarden geven
-- en dan filtert niemand er meer op. Bij e-mail is doel daarom een keuze uit
-- de lijst, een waarde per adres. Wie het specifieker wil, schrijft het in
-- Omschrijving; dat veld bestaat al.

BEGIN;

ALTER TABLE communicatie.emailadres
    ADD COLUMN IF NOT EXISTS doel text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS ix_emailadres_doel ON communicatie.emailadres (doel);

-- Vier waarden erbij in de gedeelde lijst. Ze komen uit wat er feitelijk in
-- het register staat, niet uit een bedacht model:
--   Persoonlijk      - het naampostvak van een collega, veruit de grootste
--                      groep en bij nummers opgelost door de naam in het doel
--                      te zetten. Dat is juist de wildgroei die we hier niet
--                      willen: wie het is staat in Verantwoordelijke.
--   IT en systemen   - admin@, no-reply@, scanning@, monitoring@: adressen
--                      waar geen mens achter zit maar een koppeling.
--   Opbouw           - iets dat nog gebouwd wordt, Mehdi's eigen woord voor
--                      de Elevait-demo in de vergadering.
--   Archief          - bestaat alleen nog om oude post te kunnen terugvinden.
--                      Niet hetzelfde als Behouden: dat is een oordeel, dit
--                      is waarvoor het adres dient.
-- Telefonie ziet deze vier er ook bij staan en zal ze zelden kiezen; dat is
-- een kleinere prijs dan twee woordenlijsten die uit elkaar groeien.
INSERT INTO communicatie.lijst (categorie, waarde, sort_order) VALUES
    ('Doel', 'Persoonlijk',    10),
    ('Doel', 'IT en systemen', 11),
    ('Doel', 'Opbouw',         12),
    ('Doel', 'Archief',        13)
ON CONFLICT (categorie, waarde) DO NOTHING;

-- Definitie verruimd naar nummers en adressen, zoals migratie 158 dat deed
-- met status en behouden.
UPDATE kern.definitie
   SET definitie = 'Waarvoor een telefoonnummer of een e-mailadres dient, als '
       || 'uniek en telbaar begrip op categorie-niveau, gekozen uit de beheerde '
       || 'lijst (communicatie.lijst, categorie "Doel"): Algemeen, Sales, '
       || 'Finance, HR, B2B, Klantencommunicatie, Standaardprojecten, Spoofing, '
       || 'Cold calling, Persoonlijk, IT en systemen, Opbouw of Archief. Het '
       || 'doel mag nooit herhalen wat platform, firma, verantwoordelijke of '
       || 'gebruikt-voor al zegt: het beschrijft in mensentaal waarvoor iets '
       || 'bestaat, zodat je dat een week later niet opnieuw hoeft te vragen '
       || '(regel meeting 2026-07-08, uitgebreid naar e-mail 2026-09-22). Bij '
       || 'telefoonnummers mogen er meerdere doelen achter puntkomma''s staan '
       || 'en zijn twee patroon-vormen toegestaan: de naam van de collega bij '
       || 'een prive-nummer en "Klantnummer [firmanaam]" bij een klantnummer. '
       || 'Bij e-mailadressen is het een waarde uit de lijst en niets anders: '
       || 'op vijfhonderd adressen wordt vrije tekst binnen een maand '
       || 'onbruikbaar. Wie het specifieker wil zeggen, gebruikt Omschrijving. '
       || 'Niet "functie", dat woord is voor personen.'
 WHERE sleutel = 'doel';

-- Eerste vulling, alleen waar de regel een feit is en geen gok. Droogtest op
-- de 502 adressen gaf 88 treffers: 20 Persoonlijk, 18 Algemeen, 15 Finance,
-- 14 Sales, 13 IT en systemen, 8 HR. De overige 414 blijven bewust leeg.
--
-- Twee regels, allebei een exacte vergelijking:
--   1. het deel voor de apenstaart is exact een rolwoord (boekhouding, sales,
--      hr, info, admin, ...). Geen "bevat", geen patroon: bij "bevat" wordt
--      ap.zidiconstruct Finance en dat klopt niet.
--   2. het deel voor de apenstaart is exact de naam van iemand in kern.persoon
--      (voornaam, voornaam.achternaam, v.achternaam of voornaamachternaam).
--      Een opzoeking in het personenregister, geen naamherkenning.
-- Wat hier niet in zit is met opzet weggelaten. De ~130 ex-collega's van
-- h-architects.be staan niet in kern.persoon, dus hun naampostvakken vallen
-- buiten regel 2; ai.*, ass-arch-light1 en archief_andrew zijn huisconventies
-- die je moet kennen om te kunnen duiden. Dat is werk voor een mens met de
-- bulkbalk, niet voor een regel die er meestal naast zit. In de vergadering
-- van 22-09-2026 zei Shaniel al over de firma-indeling: "ik heb de firma
-- sortering wel via de AI gedaan, dus het gaat waarschijnlijk niet accuraat
-- zijn". Die fout herhalen we hier niet.
WITH rol AS (
    SELECT e.id,
           CASE
             WHEN split_part(e.adres::text, '@', 1) IN
                  ('boekhouding','facturatie','invoice','invoices','ap','finance',
                   'accounting','betalingen','crediteuren','debiteuren')
               THEN 'Finance'
             WHEN split_part(e.adres::text, '@', 1) IN
                  ('sales','offerte','offertes','verkoop','b2b','quote','quotes',
                   'online-shop','shop')
               THEN 'Sales'
             WHEN split_part(e.adres::text, '@', 1) IN
                  ('hr','sollicitaties','sollicitatie','jobs','vacature','vacatures',
                   'recruitment','personeel')
               THEN 'HR'
             WHEN split_part(e.adres::text, '@', 1) IN
                  ('info','office','contact','algemeen','general','mail','post','hello')
               THEN 'Algemeen'
             WHEN split_part(e.adres::text, '@', 1) IN
                  ('admin','administrator','no-reply','noreply','webmaster','postmaster',
                   'hostmaster','abuse','scanning','scan','software','it','ict','support',
                   'helpdesk','backup','monitoring','alerts','notificaties')
               THEN 'IT en systemen'
             WHEN EXISTS (
                    SELECT 1 FROM kern.persoon p
                     WHERE p.voornaam <> ''
                       AND lower(split_part(e.adres::text, '@', 1)) IN (
                             lower(p.voornaam),
                             lower(p.voornaam || '.' || p.achternaam),
                             lower(left(p.voornaam, 1) || '.' || p.achternaam),
                             lower(p.voornaam || p.achternaam)))
               THEN 'Persoonlijk'
             ELSE NULL
           END AS doel
      FROM communicatie.emailadres e
     WHERE e.doel = ''
)
UPDATE communicatie.emailadres e
   SET doel = rol.doel,
       bijgewerkt_door = 'migratie-162',
       bijgewerkt_op = now()
  FROM rol
 WHERE rol.id = e.id AND rol.doel IS NOT NULL;

COMMIT;
