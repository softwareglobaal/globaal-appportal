-- 104: de verversstand hoort bij de spiegel, en die is in 103 leeggegooid.
--
-- Migratie 103 gooide boekhouding.post leeg zodat de sleutels opnieuw opgebouwd
-- worden, maar liet boekhouding.verversing staan. Gevolg: de pagina meldde
-- "Cijfers van 31/07/2026 om 10:00" terwijl er geen enkele post meer was.
-- Een tijdstempel hoort te verwijzen naar data die er ook echt is.
--
-- Meteen ook de vervuiling opruimen die de oude foutafhandeling maakte: die
-- zette klaar_op op nu bij een mislukte poging, waardoor niet-opgehaalde
-- cijfers vers leken.

UPDATE boekhouding.verversing v
   SET klaar_op = NULL, ok = NULL, aantal = 0, aantal_opgehaald = 0, fout = ''
 WHERE NOT EXISTS (
       SELECT 1 FROM boekhouding.post p WHERE p.dossier_id = v.dossier_id);
