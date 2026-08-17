-- 117: Status "teruggetrokken" voor kandidaten (Elevait)
-- Aanleiding: een kandidaat trok zijn sollicitatie zelf in. Daar was geen
-- woord voor: hij belandde op afgewezen of talentenpool, en beide zeggen iets
-- anders dan wat er gebeurde. Afgewezen legt de beslissing bij ons terwijl de
-- kandidaat zelf stopte; dat is niet alleen onnauwkeurig maar ook oneerlijk
-- naar iemand die netjes afzegde en later opnieuw kan solliciteren.
--
-- Teruggetrokken is net als afgewezen en talentenpool een eindpunt en geen
-- stap in de pijplijn nieuw -> gesprek -> aangenomen.
--
-- Er valt niets om te zetten: bestaande rijen houden hun status. Wie eerder
-- verkeerd is weggezet, verplaats je met de hand op zijn profiel.

BEGIN;

ALTER TABLE elevait.kandidaat DROP CONSTRAINT IF EXISTS kandidaat_status_check;

ALTER TABLE elevait.kandidaat
  ADD CONSTRAINT kandidaat_status_check
  CHECK (status IN ('nieuw', 'gesprek', 'afgewezen', 'aangenomen',
                    'talentenpool', 'teruggetrokken'));

COMMENT ON COLUMN elevait.kandidaat.status IS
  'Waar de kandidaat staat. Pijplijn: nieuw, gesprek, aangenomen. '
  'Eindpunten daarnaast: afgewezen (wij stopten), teruggetrokken (hij stopte), '
  'talentenpool (bewaard voor later, alleen met bewaar_toestemming).';

COMMIT;
