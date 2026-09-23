-- 166: Vervaldatum als veld op het e-maildomein, niet als zin in een opmerking.
--
-- Aanleiding 23-09-2026, Shaniel over de kostenregel van unabo.be: vrije tekst
-- in een gele doos, "het lijkt alsof het gewoon random is geplaatst". Klopt:
-- migratie 159 zette de analyse van dat moment als proza in
-- email_domein.opmerking (11 van de 17 domeinen, tot 506 tekens), en de app
-- toonde die als waarschuwing. Twee gevolgen:
--   - op unabo.be stond "post 30,1 GB van 50 GB" in de regel en "verbruik
--     35,4 van 50 GB" in de doos: twee getallen voor wat hetzelfde lijkt;
--   - de enige echte waarschuwing, qoppa.be vervalt op 29-09-2026, bestond
--     alleen als zin in zo'n doos, en was dus niet te tellen, te filteren of
--     rood te kleuren.
--
-- De regel wordt nu vaste velden in een vaste volgorde. Wat een feit is, krijgt
-- een kolom; de opmerking blijft bestaan maar gaat achter een notitie-teken.
-- one.com levert beide datums: renewalDate (verlengt, leeg als het domein
-- niet verlengt) en expirationDate (vervalt).

BEGIN;

ALTER TABLE communicatie.email_domein
    ADD COLUMN IF NOT EXISTS vervaldatum date;

-- Vastgesteld 22-09-2026 in het one.com-paneel: het enige domein met een lege
-- renewalDate en een expirationDate.
UPDATE communicatie.email_domein
   SET vervaldatum = DATE '2026-09-29',
       bijgewerkt_door = 'migratie-166',
       bijgewerkt_op = now()
 WHERE domein = 'qoppa.be' AND verlengdatum IS NULL;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_pakket_verbruik', 'Verbruik',
     'Hoeveel ruimte het hele hostingpakket van een e-maildomein gebruikt: post plus webhosting en bestanden, tegenover het quotum van het pakket. Het quotum geldt voor dat geheel, daarom staat in de kostenregel dit ene getal. Hoeveel daarvan post is, staat in de uitleg bij het getal.'),
    ('email_vervaldatum', 'Vervaldatum',
     'De datum waarop een e-maildomein afloopt omdat het niet automatisch verlengt. Na die datum stopt de post op alle adressen van het domein. Staat er een vervaldatum en geen verlengdatum, dan moet iemand bewust kiezen: verlengen, of de post veiligstellen en doorstuuradressen omleggen voordat het domein vervalt.'),
    ('email_domein_notitie', 'Notitie',
     'Een vrije opmerking bij een e-maildomein: een besluit, een achtergrond, iets dat niet in een vast veld past. Staat achter het notitie-teken in de kostenregel en niet als waarschuwing: wat een feit is (pakket, verbruik, jaarbedrag, verlengt, vervalt) heeft een eigen veld.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
