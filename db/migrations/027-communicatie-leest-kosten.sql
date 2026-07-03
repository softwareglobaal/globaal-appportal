-- 027 — leverancier/platform-detailpagina's (meeting 2026-07-03): het
-- Communicatie-dashboard toont bij een leverancier ook de kosten-kant
-- (software-abonnementen + werkelijke maandbedragen, gelinkt via migratie 012).
-- Daarvoor: alleen-lezen op de kosten-tabellen voor de communicatie-rol.

GRANT USAGE ON SCHEMA kosten TO communicatie;
GRANT SELECT ON kosten.software, kosten.charge_actual, kosten.firma TO communicatie;
