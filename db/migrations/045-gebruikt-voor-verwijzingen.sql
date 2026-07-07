-- 045 - gebruikt-voor als echte verwijzing + redundantie-opschoning
-- (meeting Mehdi 2026-07-06).
--
-- 1. Gebruikt-voor kan ook een afdeling (TKN = tekenwerk) of persoon
--    (Cataline) zijn; die entiteiten bestaan al in kern. Klant en campagne
--    blijven vrije tekst tot de klantendatabase er is.
-- 2. Redundantie weg (het "Shaniel is de voornaam van Shaniel"-argument):
--    gebruikt-voor gelijk aan de betaler zegt niets, en kosten aanrekenen
--    aan jezelf bestaat niet.

ALTER TABLE communicatie.nummer
    ADD COLUMN gebruikt_voor_afdeling_id uuid
        REFERENCES kern.afdeling(id) ON DELETE SET NULL,
    ADD COLUMN gebruikt_voor_persoon_id uuid
        REFERENCES kern.persoon(id) ON DELETE SET NULL;

UPDATE communicatie.nummer
   SET gebruikt_voor_firma_id = NULL
 WHERE gebruikt_voor_firma_id = factuur_firma_id;

UPDATE communicatie.nummer
   SET doorfactuur_firma_id = NULL
 WHERE doorfactuur_firma_id = factuur_firma_id;

UPDATE kern.definitie
   SET definitie = 'Wie of wat de resource feitelijk gebruikt: een firma, afdeling, persoon, of (vrije tekst, later de klantendatabase) een klant, dossier of campagne. Alleen invullen wanneer dat afwijkt van wie betaalt: aan jezelf hoef je niets uit te leggen (meeting 2026-07-06).'
 WHERE sleutel = 'gebruikt_voor';
