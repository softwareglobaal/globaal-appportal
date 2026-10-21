-- 196: personeelsadministratie, verlofdagen per jaar op het contract
-- (hr.globaal.be/personeel).
--
-- Waarom: HR (21-10-2026) wil alles één keer invullen in de
-- personeelsadministratie en dat de andere dashboards het overnemen. Het
-- verlofrecht hoort bij het contract; het verlofregister neemt het over als
-- jaarrecht. Eén kolom erbij, geen nieuwe rechten nodig: hr_app heeft al
-- SELECT, INSERT, UPDATE op personeel.pa_contract (migratie 179).
--
-- Tot deze migratie draait, laat de app het veld weg (personeel_db.ONTBREEKT
-- in globaal-hr); daarna verschijnt het na een herstart van app-hr vanzelf.

ALTER TABLE personeel.pa_contract ADD COLUMN IF NOT EXISTS verlofdagen numeric(6,2);
