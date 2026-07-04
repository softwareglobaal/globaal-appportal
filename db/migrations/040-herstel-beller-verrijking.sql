-- 040 - herstel: beller (gebruiker_oid) alsnog vullen.
--
-- De verrijkingscode die de beller wegschrijft stond eerder live dan
-- migratie 038, waardoor de verrijking een tijd crashte op de ontbrekende
-- kolom en het archief zonder bellers bleef. Twee reparaties, idempotent:
--   1. alles wat al een detail-record in ruw heeft: beller direct afleiden;
--   2. verrijkte records die daarna nog steeds geen beller hebben (ruw is
--      daar nog het kale lijst-record): terug de wachtrij in, zodat de
--      poller ze opnieuw ophaalt met de huidige, complete code.

UPDATE communicatie.xelion_communicatie
   SET gebruiker_oid = ruw->'userProfile'->>'oid'
 WHERE gebruiker_oid IS NULL
   AND ruw ? 'userProfile';

UPDATE communicatie.xelion_communicatie
   SET verrijkt_op = NULL
 WHERE gebruiker_oid IS NULL
   AND verrijkt_op IS NOT NULL;
