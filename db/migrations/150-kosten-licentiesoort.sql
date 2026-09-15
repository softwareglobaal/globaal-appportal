-- 150: Kosten Software - labels per softwarekaart (vraag Mehdi 2026-09-15).
-- Het dashboard heet voortaan "Kosten Software" en elke kaart krijgt drie
-- zichtbare labels: hoe er betaald wordt, door welke firma, en wat voor
-- soort licentie het is. Seats konden alleen aan een persoon hangen; sommige
-- licenties zijn per afdeling, dus een seat kan nu ook aan een afdeling hangen.
--
-- Betaalwijze: de kolom payment_method bestond al met standaard 'VISA', maar
-- alle kaarten in de afschriften zijn KBC-Mastercards (het "VISA"-kanaal in de
-- oude generator). De bestaande waarde wordt daarom Mastercard; overschrijving
-- en domiciliëring komen erbij voor leveranciers die per factuur betaald worden.

ALTER TABLE kosten.software
    ADD COLUMN IF NOT EXISTS licentie_soort text
        CHECK (licentie_soort IN ('persoon', 'afdeling', 'firma', 'gedeeld'));
COMMENT ON COLUMN kosten.software.licentie_soort IS
    'persoon = seat per medewerker; afdeling = licentie voor een afdeling; firma = een licentie voor de hele vennootschap; gedeeld = een login die meerdere mensen delen.';

ALTER TABLE kosten.software ALTER COLUMN payment_method SET DEFAULT 'Mastercard';
UPDATE kosten.software SET payment_method = 'Mastercard' WHERE payment_method = 'VISA';
COMMENT ON COLUMN kosten.software.payment_method IS
    'Mastercard (KBC-kaart van de firma), Overschrijving, Domiciliëring of Onbekend.';

ALTER TABLE kosten.seat
    ADD COLUMN IF NOT EXISTS afdeling_id uuid
        REFERENCES kern.afdeling(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS seat_afdeling_idx ON kosten.seat (afdeling_id);
COMMENT ON COLUMN kosten.seat.afdeling_id IS
    'Seat die aan een afdeling hangt in plaats van aan een persoon (licentie_soort = afdeling).';

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('licentie_soort', 'Licentiesoort',
     'Hoe een softwarelicentie toegewezen is: per persoon (elke medewerker een eigen seat), per afdeling (een licentie voor een afdeling), per firma (een licentie voor de hele vennootschap) of gedeeld (een login die meerdere mensen delen). Bepaalt of seats aan personen of aan afdelingen gekoppeld worden in Kosten Software.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
