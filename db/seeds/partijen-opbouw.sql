-- Partijen opbouwen uit de Octopus-import (migratie 058). Idempotent:
-- na elke herimport van de exports opnieuw draaien.
--   docker compose exec -T postgresql psql -U authentik -d appportal \
--     < db/seeds/partijen-opbouw.sql

BEGIN;

-- 1. Partijen op BTW-nummer (de langste naam wint als weergavenaam)
INSERT INTO kern.partij (naam, btw_nummer)
SELECT DISTINCT ON (btw_nummer) naam, btw_nummer
  FROM kosten.octopus_relatie
 WHERE btw_nummer <> ''
 ORDER BY btw_nummer, length(naam) DESC, naam
ON CONFLICT (btw_nummer) WHERE btw_nummer <> '' DO NOTHING;

UPDATE kosten.octopus_relatie o
   SET partij_id = p.id
  FROM kern.partij p
 WHERE o.partij_id IS NULL AND o.btw_nummer <> ''
   AND p.btw_nummer = o.btw_nummer;

-- 2. Partijen zonder BTW: exact gelijke naam groepeert (aanname 2026-07-08)
INSERT INTO kern.partij (naam, btw_nummer)
SELECT DISTINCT ON (lower(btrim(naam))) naam, ''
  FROM kosten.octopus_relatie
 WHERE btw_nummer = '' AND partij_id IS NULL
 ORDER BY lower(btrim(naam)), length(naam) DESC, naam
ON CONFLICT (lower(btrim(naam))) WHERE btw_nummer = '' DO NOTHING;

UPDATE kosten.octopus_relatie o
   SET partij_id = p.id
  FROM kern.partij p
 WHERE o.partij_id IS NULL AND o.btw_nummer = ''
   AND p.btw_nummer = ''
   AND lower(btrim(p.naam)) = lower(btrim(o.naam));

-- 3. Eigenschappen van de partij afleiden uit de onderliggende vlakken
UPDATE kern.partij p SET is_intern = true
 WHERE NOT p.is_intern
   AND EXISTS (SELECT 1 FROM kosten.octopus_relatie o
                WHERE o.partij_id = p.id AND o.is_intern);

UPDATE kern.partij p
   SET leverancier_id = (SELECT o.leverancier_id FROM kosten.octopus_relatie o
                          WHERE o.partij_id = p.id AND o.leverancier_id IS NOT NULL
                          LIMIT 1)
 WHERE p.leverancier_id IS NULL;

-- Interne partijen eenduidig aan de eigen firma koppelen (naam-bevat-match,
-- alleen wanneer er precies een kandidaat is: nooit gokken)
UPDATE kern.partij p
   SET kern_firma_id = f.id
  FROM kern.firma f
 WHERE p.is_intern AND p.kern_firma_id IS NULL
   AND length(f.naam) >= 4
   AND lower(p.naam) LIKE '%' || lower(f.naam) || '%'
   AND (SELECT count(*) FROM kern.firma f2
         WHERE length(f2.naam) >= 4
           AND lower(p.naam) LIKE '%' || lower(f2.naam) || '%') = 1;

COMMIT;

-- Controle
SELECT count(*) AS partijen,
       count(*) FILTER (WHERE btw_nummer <> '') AS met_btw,
       count(*) FILTER (WHERE is_intern) AS intern,
       count(*) FILTER (WHERE kern_firma_id IS NOT NULL) AS aan_firma_gekoppeld,
       count(*) FILTER (WHERE leverancier_id IS NOT NULL) AS aan_leverancier_gekoppeld
  FROM kern.partij;
SELECT count(*) AS vlakken_zonder_partij
  FROM kosten.octopus_relatie WHERE partij_id IS NULL;
SELECT p.volgnr, p.naam, count(o.id) AS vlakken,
       string_agg(o.firma_code || ' #' || o.octopus_id, ', ' ORDER BY o.firma_code) AS boekhoudingen
  FROM kern.partij p JOIN kosten.octopus_relatie o ON o.partij_id = p.id
 GROUP BY p.id HAVING count(o.id) >= 4
 ORDER BY count(o.id) DESC LIMIT 10;
