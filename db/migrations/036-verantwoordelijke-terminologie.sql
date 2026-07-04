-- 036 - terminologie: "verantwoordelijke" generiek, nummer-variant apart
-- (TODO-punt Mehdi, meeting 2026-07-03; verzoek 2026-07-04).
--
-- Woordenboek-principe: een term betekent overal hetzelfde. De oude definitie
-- van "verantwoordelijke" was telefoonlijn-specifiek ("altijd de 1e in de
-- belvolgorde") terwijl de term ook op e-mailadressen, panden en domeinen
-- gebruikt wordt. Daarom: de algemene term wordt generiek, en de telefonie-
-- kolom krijgt een eigen sleutel met de belvolgorde-uitleg. De kolomsleutel
-- in opgeslagen views blijft ongewijzigd (die hernoemen we nooit); alleen de
-- weergave leest voortaan de nieuwe term.

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('verantwoordelijke_nummer', 'Verantwoordelijke voor nummer',
     'De ene persoon die aanspreekbaar en eigenaar is van dit telefoonnummer (accountable, precies een). In de telefonie is dit altijd de 1e in de belvolgorde.')
ON CONFLICT (sleutel) DO NOTHING;

UPDATE kern.definitie
   SET definitie = 'De ene persoon die aanspreekbaar en eigenaar is van een resource (accountable) - precies een, zodat niets eigenaarloos blijft. Wat de verantwoordelijkheid concreet inhoudt verschilt per resource: zie bv. "Verantwoordelijke voor nummer".'
 WHERE sleutel = 'verantwoordelijke';
