-- 054 - weergavenaam zonder afdeling (wens Mehdi/Shaniel 2026-07-08):
-- Mehdi, Angela en Siyan heten op het medewerkers-dashboard letterlijk
-- alleen bij hun voornaam, zonder "(Afdeling)" erachter. Data-gedreven
-- vlag zodat de uitzondering beheerbaar blijft en niet in code leeft.

ALTER TABLE kern.persoon
    ADD COLUMN afdeling_in_naam boolean NOT NULL DEFAULT true;

UPDATE kern.persoon
   SET afdeling_in_naam = false
 WHERE in_dienst
   AND lower(btrim(voornaam)) IN ('mehdi', 'angela', 'siyan');
