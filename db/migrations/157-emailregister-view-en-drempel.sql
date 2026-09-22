-- 157: persoonlijke view voor het e-mailregister, en de opruimdrempel in het
-- woordenboek.
--
-- Aanleiding: kritiekronde 22-09-2026, punt 13. De telefonietab bewaart per
-- Authentik-gebruiker welke kolommen hij ziet en hoe er gesorteerd is
-- (view_instelling, migratie 013). Tab 2 deed dat niet: elke herlaad begon
-- opnieuw. Zelfde tabel, twee extra kolommen, zodat "view van Mehdi" op beide
-- tabbladen hetzelfde betekent en er geen tweede opslagplek ontstaat.
--
-- De drempel "op te ruimen = uitgezet en onder 1 MB" stond alleen in code.
-- Hij blijft in code (de query moet hem kennen), maar de betekenis en het
-- getal staan nu ook in het woordenboek, waar de tooltips en de kolomkoppen
-- vandaan komen. Wie de drempel wil veranderen, verandert hem op twee
-- plekken bewust, in plaats van hem op een plek te vergeten.

BEGIN;

ALTER TABLE communicatie.view_instelling
    ADD COLUMN email_kolommen  text NOT NULL DEFAULT '',
    ADD COLUMN email_sortering text NOT NULL DEFAULT '';

COMMENT ON COLUMN communicatie.view_instelling.email_kolommen IS
    'Zichtbare kolommen op tab E-mailadressen, komma-gescheiden sleutels; leeg = standaard.';
COMMENT ON COLUMN communicatie.view_instelling.email_sortering IS
    'Sortering op tab E-mailadressen als sleutel:asc of sleutel:desc; leeg = standaardvolgorde.';

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_opruimen', 'Op te ruimen',
     'Een e-mailadres dat bij de leverancier uitgezet is en minder dan 1 MB gebruikt. Het houdt alleen nog een naam bezet: geen post, geen archief, geen reden om het te bewaren. De grens van 1 MB is de ondergrens van een lege postbus bij one.com (een lege postbus meet 0,03 tot 0,3 MB). Wie de grens wil verleggen, past hem aan in deze definitie en in de query van het register.'),
    ('email_peildatum', 'Peildatum',
     'De datum waarop de postvakgegevens (opslag, status, spamfilter, doorsturen) bij de leverancier zijn opgehaald. Er is geen automatische verversing: one.com geeft geen laatste-login of laatste-maildatum, dus dagelijks ophalen voegt niets toe aan een opslagcijfer. Na 90 dagen waarschuwt het register dat de cijfers oud zijn.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
