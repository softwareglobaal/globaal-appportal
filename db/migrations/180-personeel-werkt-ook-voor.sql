-- 180: personeelsadministratie, "werkt ook voor" (hr.globaal.be/personeel).
--
-- Waarom: in het organisatie-dashboard werken mensen voor meer dan een firma
-- (kern.persoon_dienstfirma, "diensten voor"). HR wil dat in de eigen
-- personeelsadministratie zien en bijhouden.
--
-- 1. hr_app mag kern.persoon_dienstfirma lezen (zoals al persoon, firma,
--    afdeling en persoon_hr, migraties 075 en 076). Alleen lezen.
-- 2. Een eigen tabel personeel.pa_dienstfirma: voor welke entiteiten iemand
--    naast de werkgever werkt. Een koppeling wordt uitgezet (actief = false),
--    nooit verwijderd; hr_app krijgt dus geen DELETE. Wijzigingen staan in
--    personeel.pa_mutatie. De tabeldefinitie is letterlijk
--    personeel_db.SCHEMA_180 uit globaal-hr.

GRANT SELECT ON kern.persoon_dienstfirma TO hr_app;

CREATE TABLE IF NOT EXISTS personeel.pa_dienstfirma (
  personeelsnummer text NOT NULL REFERENCES personeel.pa_persoon(personeelsnummer),
  entiteit      text NOT NULL,
  actief        boolean NOT NULL DEFAULT true,
  gewijzigd_op  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (personeelsnummer, entiteit)
);

GRANT SELECT, INSERT, UPDATE ON personeel.pa_dienstfirma TO hr_app;
