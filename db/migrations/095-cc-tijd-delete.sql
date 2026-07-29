-- 095: de ingest van gemeten Claude Code-tijd mag ook opruimen
-- Migratie 094 gaf SELECT, INSERT en UPDATE, maar een hermeting moet een dag
-- volledig kunnen vervangen: valt een applicatie bij een hermeting weg (te
-- breed trefwoord rechtgezet), dan moet die regel echt verdwijnen in plaats
-- van te blijven staan en door te tellen.

GRANT DELETE ON ontwikkeling.cc_tijd TO medewerker_writer;
