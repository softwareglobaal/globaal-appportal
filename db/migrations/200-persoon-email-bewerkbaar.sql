-- 200: Het e-mailadres van een persoon bewerkbaar op organisatie.globaal.be.
--
-- Aanleiding: Mehdi, 30-10-2026 (Zoom): per persoon een e-mailadres, dat ook het Zoom-adres is, en daarnaast het
-- agenda-adres (migratie 185). De kolom email bestond al (citext, uniek) maar was bij 1 van de 30 mensen in dienst
-- ingevuld en kon nergens gewijzigd worden: de app had er geen schrijfrecht op.
-- Geen nieuwe kolom en geen nieuwe relatie, dus niets voor de Second Brain.

BEGIN;

GRANT UPDATE (email) ON kern.persoon TO medewerker_writer;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('persoon_email', 'E-mail (Zoom)',
     'Het werkadres van een persoon, dat ook zijn Zoom-adres is. Staat op zijn profiel en in de medewerkerslijst op organisatie.globaal.be. Niet hetzelfde als het agenda-adres: dat is het adres waarmee iemand zijn agenda leest. Sinds 30-10-2026 (Mehdi).')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
