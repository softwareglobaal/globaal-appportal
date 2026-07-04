-- 037 - term exact zoals afgesproken: "Verantwoordelijke voor het nummer"
-- (correctie op 036; de gebruiker wil de kolom letterlijk zo noemen).
-- Sleutel blijft verantwoordelijke_nummer (sleutels hernoemen we nooit).

UPDATE kern.definitie
   SET term = 'Verantwoordelijke voor het nummer',
       definitie = 'De ene persoon die aanspreekbaar en eigenaar is van het telefoonnummer (accountable, precies een). In de telefonie is dit altijd de 1e in de belvolgorde.'
 WHERE sleutel = 'verantwoordelijke_nummer';
