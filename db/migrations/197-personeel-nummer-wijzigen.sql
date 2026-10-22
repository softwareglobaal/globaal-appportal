-- 197: personeelsadministratie, een personeelsnummer kunnen rechtzetten
-- (hr.globaal.be/personeel).
--
-- Waarom: HR (22-10-2026) wil dat iemand overal hetzelfde personeelsnummer
-- heeft, met de personeelsadministratie als bron. Daar staan ook foute
-- nummers in (bijvoorbeeld 00000 uit een import), en die moeten recht te
-- zetten zijn zonder dat contracten, dossier en gesprekken los raken.
--
-- Alle verwijzingen naar personeel.pa_persoon(personeelsnummer) krijgen ON
-- UPDATE CASCADE: wijzigt het nummer, dan gaan de onderliggende rijen mee. Er
-- wordt niets verwijderd (ON DELETE blijft zoals het was: weigeren). Het
-- logboek personeel.pa_mutatie heeft geen verwijzing en blijft onaantastbaar;
-- de app schrijft daar "personeelsnummer gewijzigd van X naar Y" bij.
-- Geen nieuwe rechten: hr_app heeft al UPDATE op de tabellen (migratie 179).

DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.conrelid::regclass AS tabel, c.conname, a.attname AS kolom
      FROM pg_constraint c
      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
     WHERE c.contype = 'f'
       AND c.confrelid = 'personeel.pa_persoon'::regclass
       AND c.confupdtype <> 'c'
  LOOP
    EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tabel, r.conname);
    EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY (%I)'
                   ' REFERENCES personeel.pa_persoon(personeelsnummer) ON UPDATE CASCADE',
                   r.tabel, r.conname, r.kolom);
  END LOOP;
END $$;
