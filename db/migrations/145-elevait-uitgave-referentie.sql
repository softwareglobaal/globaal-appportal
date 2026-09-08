-- 145: Uitgaven die de finance-agent uit admin@elevaitnv.com boekt, krijgen
-- een referentie (receipt- of factuurnummer) zodat dezelfde mail nooit twee
-- keer een uitgave wordt. De vijf handmatig geboekte regels van 8 september
-- krijgen hun referentie alsnog, anders zou de agent ze opnieuw boeken.

ALTER TABLE elevait.uitgave ADD COLUMN IF NOT EXISTS referentie text;
CREATE UNIQUE INDEX IF NOT EXISTS ux_elevait_uitgave_referentie
    ON elevait.uitgave (leverancier, referentie) WHERE referentie IS NOT NULL;

UPDATE elevait.uitgave SET referentie = '2443-9436' WHERE leverancier = 'Anthropic' AND omschrijving LIKE '%2443-9436%' AND referentie IS NULL;
UPDATE elevait.uitgave SET referentie = '2912-9621' WHERE leverancier = 'Anthropic' AND omschrijving LIKE '%2912-9621%' AND referentie IS NULL;
UPDATE elevait.uitgave SET referentie = '1689-9447' WHERE leverancier = 'Runpod' AND omschrijving LIKE '%1689-9447%' AND referentie IS NULL;
UPDATE elevait.uitgave SET referentie = '1547-6576' WHERE leverancier = 'Runpod' AND omschrijving LIKE '%1547-6576%' AND referentie IS NULL;
UPDATE elevait.uitgave SET referentie = '1632-0631' WHERE leverancier = 'Runpod' AND omschrijving LIKE '%1632-0631%' AND referentie IS NULL;
UPDATE elevait.uitgave SET referentie = 'order-2026-07-08' WHERE leverancier = 'one.com' AND datum = DATE '2026-07-08' AND referentie IS NULL;

-- Het abonnement kent zijn leverancier; de agent zet de verlengdatum op
-- basis van de periode in de receipt. Geen extra kolom nodig.
