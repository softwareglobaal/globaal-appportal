-- 031 — tool→discipline-mapping (PLAN.md stap 2a; Unified Dashboard).
--
-- Elke tool hoort bij één van de 17 disciplines (migratie 030). De mapping
-- maakt dubbele software, ongebruikte licenties en gaten zichtbaar: een
-- discipline zonder tools is het ziekenhuis-model ("hier hebben we niets"),
-- een NULL is "nog niet gemapt" en blijft een signaal in de Second Brain.
-- De kosten-host-app kent deze kolom niet en blijft gewoon werken (nullable);
-- de weergave leeft in het Organisatie-dashboard (view = query, geen opslag).

ALTER TABLE kosten.software
    ADD COLUMN discipline_sleutel text REFERENCES kern.discipline(sleutel);

-- Evidente mappings alvast (afspraak stap 2b: bij twijfel NIET gokken — de
-- rest blijft NULL en wordt met het team kortgesloten via gate G2):
UPDATE kosten.software SET discipline_sleutel = 'operations_projectmanagement'
 WHERE discipline_sleutel IS NULL AND vendor ILIKE '%monday%';
UPDATE kosten.software SET discipline_sleutel = 'finance_accounting'
 WHERE discipline_sleutel IS NULL AND vendor ILIKE '%octopus%';
UPDATE kosten.software SET discipline_sleutel = 'sales_bizdev'
 WHERE discipline_sleutel IS NULL AND vendor ILIKE '%pipedrive%';
UPDATE kosten.software SET discipline_sleutel = 'hr_recruitment'
 WHERE discipline_sleutel IS NULL AND vendor ILIKE '%desktime%';
-- Communicatie-/systeem-infrastructuur → IT & systemen:
UPDATE kosten.software SET discipline_sleutel = 'it_systemen'
 WHERE discipline_sleutel IS NULL
   AND (vendor ILIKE '%microsoft%' OR vendor ILIKE '%zoom%'
        OR vendor ILIKE 'close call%');

-- Wie mag de mapping bijwerken: het Organisatie-dashboard (medewerker_writer),
-- alléén deze kolom — de rest van kosten.software blijft van de kosten-app.
GRANT USAGE ON SCHEMA kosten TO medewerker_writer;
GRANT SELECT ON kosten.software TO medewerker_writer;
GRANT UPDATE (discipline_sleutel) ON kosten.software TO medewerker_writer;
