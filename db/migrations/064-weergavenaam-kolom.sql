-- 064 - weergavenaam als handmatige kolom (beslissing Shaniel 2026-07-13).
--
-- De displaynaam wordt NIET meer opgebouwd uit voornaam + afdeling +
-- vlaggen: het is gewone, met de hand beheerde data. Het zijn 41 mensen;
-- een kolom die je gewoon invult klopt altijd, ook voor de gevallen die
-- geen formule kan maken (Joan met twee afdelingen, de H-prefix van de
-- afdelingshoofden, ooit een tweede Damian met [LG]/[LD]).
-- Alle apps lezen kern.persoon.weergavenaam; de oude opbouw blijft in de
-- code alleen als terugval zolang deze migratie nog niet gedraaid is.
-- De kolom afdeling_in_naam (054) wordt hiermee overbodig voor weergave;
-- opruimen kan later, eerst overal bewijsbaar op de kolom draaien.

ALTER TABLE kern.persoon ADD COLUMN weergavenaam text NOT NULL DEFAULT '';

-- Vertrekpunt volgens de oude formule, zodat ook wie niet in de
-- Zoom-lijst staat (of uit dienst is) nergens leeg verschijnt.
UPDATE kern.persoon SET weergavenaam =
    CASE WHEN afdeling_in_naam IS FALSE THEN voornaam
         ELSE voornaam || ' (' ||
              coalesce((SELECT a.naam FROM kern.afdeling a
                         WHERE a.id = afdeling_id), '') || ')' END
 WHERE weergavenaam = '';

-- De Zoom-lijst van 2026-07-13 als handmatige waarheid eroverheen.
UPDATE kern.persoon p SET weergavenaam = z.weergave
  FROM (VALUES
    ('Abi-Gail', 'Abi-Gail (Scanning)'), ('Alexander', 'Alexander (Scanning)'),
    ('Amrish', 'Amrish (Energy)'), ('Amy', 'Amy (Finance)'),
    ('Angela', 'Angela'), ('Aqib', 'Aqib (Engineering)'),
    ('Ashley', 'Ashley (Intern)'), ('Ashvand', 'Ashvand (H-Energy)'),
    ('Casedy', 'Casedy (Energy)'), ('Chesron', 'Chesron (Architecture)'),
    ('Chilton', 'Chilton (Architecture)'), ('Gul', 'Gul (Engineering)'),
    ('Isaiah', 'Isaiah (Energy)'), ('Ishara', 'Ishara (HR)'),
    ('Jean-Charles', 'Jean-Charles (Energy)'), ('Joan', 'Joan (Finance + Office)'),
    ('Joey', 'Joey (Sales)'), ('Kirtie', 'Kirtie (Intern)'),
    ('Marise', 'Marise (Energy)'), ('Matthew', 'Matthew (H-Engineering)'),
    ('Mehdi', 'Mehdi'), ('Mukesh', 'Mukesh (Energy)'),
    ('Natanael', 'Natanael (Rendering)'), ('NOVA', 'NOVA (Virtual Assistant Mehdi)'),
    ('Patricio', 'Patricio (Intern)'), ('Raisha', 'Raisha (Architecture)'),
    ('Riaaz', 'Riaaz (Intern)'), ('Rohit', 'Rohit (Intern)'),
    ('Shanaya', 'Shanaya (Intern)'), ('Shaniel', 'Shaniel (H-AI & ICT)'),
    ('Shelton', 'Shelton (Sales)'), ('Siyan', 'Siyan'),
    ('Stacy', 'Stacy (Energy)'), ('Sudjal', 'Sudjal (AI)'),
    ('Sufa', 'Sufa (Architecture)'), ('Ultischa', 'Ultischa (Construction)'),
    ('Xaviera', 'Xaviera (Office)'), ('Yasier', 'Yasier (Intern)'),
    ('Zjafhira', 'Zjafhira (Scanning)')
  ) AS z(voornaam, weergave)
 WHERE p.in_dienst AND lower(p.voornaam) = lower(z.voornaam);

-- Handmatig beheer: bewerken mag via de schrijf-engine (kolom-grant,
-- zelfde patroon als migratie 031).
GRANT UPDATE (weergavenaam) ON kern.persoon TO medewerker_writer;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('weergavenaam', 'Weergavenaam',
     'De naam waarmee een collega overal in het platform wordt getoond, exact gelijk aan de Zoom-naam. Handmatig beheerde kolom op kern.persoon - geen automatische opbouw uit voornaam of afdeling: een mens vult hem in en overal klopt het. Conventie: Voornaam (Afdeling); afdelingshoofden krijgen H- voor de afdeling; Mehdi, Angela en Siyan staan kaal.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
