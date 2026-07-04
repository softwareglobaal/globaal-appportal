-- 032 - stijlregel (2026-07-04): geen gedachtestreepjes (em dashes) en geen
-- emoji's in teksten die gebruikers zien. De eerder geseede teksten bevatten
-- er veel; deze migratie ruimt de bestaande data op. De regel zelf staat in
-- CLAUDE.md (vaste regel 10) en geldt voor alle nieuwe teksten. Idempotent.
-- Ook run-snapshots (draaiboek.run_stap kopieert naam/omschrijving) gaan mee,
-- zodat lopende runs dezelfde tekst tonen als het sjabloon.

UPDATE kern.definitie
   SET definitie = replace(replace(definitie, ' — ', ' - '), '—', '-')
 WHERE definitie LIKE '%—%';
UPDATE kern.definitie
   SET term = replace(replace(term, ' — ', ' - '), '—', '-')
 WHERE term LIKE '%—%';

UPDATE kern.data_domein
   SET omschrijving = replace(replace(omschrijving, ' — ', ' - '), '—', '-')
 WHERE omschrijving LIKE '%—%';

UPDATE draaiboek.stap
   SET naam         = replace(replace(naam, ' — ', ' - '), '—', '-'),
       omschrijving = replace(replace(omschrijving, ' — ', ' - '), '—', '-')
 WHERE naam LIKE '%—%' OR omschrijving LIKE '%—%';
UPDATE draaiboek.run_stap
   SET naam         = replace(replace(naam, ' — ', ' - '), '—', '-'),
       omschrijving = replace(replace(omschrijving, ' — ', ' - '), '—', '-'),
       fase_naam    = replace(replace(fase_naam, ' — ', ' - '), '—', '-')
 WHERE naam LIKE '%—%' OR omschrijving LIKE '%—%' OR fase_naam LIKE '%—%';
UPDATE draaiboek.fase
   SET naam = replace(replace(naam, ' — ', ' - '), '—', '-')
 WHERE naam LIKE '%—%';
