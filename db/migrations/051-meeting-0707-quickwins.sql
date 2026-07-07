-- 051 - meeting Mehdi/Joan 2026-07-07: quick wins.
--
-- 1. xelion_uitgesloten: spoofing- en doorschakelnummers komen op het
--    Xelion-platform voor (als afzender-CLI) maar er wordt nooit op
--    opgenomen of mee uitgebeld; ze horen niet als Xelion-nummer te tellen.
--    Mehdi's sleutel-analogie: een sleutel hebben is niet met de auto rijden.
-- 2. abonnement_type: naast de kostprijs ook het abonnementstype van de
--    factuur (bv. Business Mobile Smart).
-- 3. Status kent voortaan ook "Vervallen": definitief weg bij de provider,
--    niet te heractiveren (Niet-actief = kan nog geactiveerd worden).
--    De waarde-lijst leeft in de apps; geen DB-constraint.

ALTER TABLE communicatie.nummer
    ADD COLUMN xelion_uitgesloten boolean NOT NULL DEFAULT false,
    ADD COLUMN abonnement_type text NOT NULL DEFAULT '';

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('abonnement_type', 'Abonnementstype',
     'Het type abonnement zoals het op de factuur van de leverancier staat, bv. Business Mobile Smart. Naast de kostprijs de tweede helft van het contractbeeld.'),
    ('xelion_uitgesloten', 'Telt niet als Xelion',
     'Het nummer komt op het Xelion-platform voor (bv. als afzender bij spoofing of als doorschakelnummer) maar er wordt nooit op opgenomen of mee uitgebeld. Het telt daarom niet mee als Xelion-nummer in statistieken en belvolgorde. De sleutel-analogie van Mehdi: een sleutel hebben is niet met de auto rijden.'),
    ('status_vervallen', 'Vervallen',
     'Het nummer is definitief weg bij de provider en kan niet meer geheractiveerd worden. Niet-actief betekent daarentegen: kan nog geactiveerd worden.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
