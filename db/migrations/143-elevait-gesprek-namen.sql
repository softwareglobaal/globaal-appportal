-- 143: Fathom-accountnamen naar personen.
-- Mehdi neemt op met het account "Afspraken" (zoomafspraken@gmail.com); Fathom
-- zet die accountnaam als opnemer en als spreker. Shaniel verschijnt als
-- "Shaniel Work". Vanaf nu vertaalt fathom.py dit bij het ophalen; dit zet
-- de bestaande rijen recht. Vrije tekst in beslissingen en open eindjes
-- blijft staan: "Afspraken" is daar ook gewoon het Nederlandse woord.

UPDATE elevait.gesprek SET opnemer = 'Mehdi'   WHERE opnemer = 'Afspraken';
UPDATE elevait.gesprek SET opnemer = 'Shaniel' WHERE opnemer = 'Shaniel Work';

-- Sprekerslijst: vertalen en ontdubbelen, volgorde van eerste voorkomen behouden.
UPDATE elevait.gesprek g
   SET sprekers = (
       SELECT coalesce(jsonb_agg(naam ORDER BY eerste), '[]'::jsonb)
         FROM (
           SELECT naam, min(volgnr) AS eerste
             FROM (
               SELECT CASE s
                        WHEN 'Afspraken' THEN 'Mehdi'
                        WHEN 'Shaniel Work' THEN 'Shaniel'
                        WHEN 'Shaniel (H-AI & ICT)' THEN 'Shaniel'
                        ELSE s END AS naam,
                      volgnr
                 FROM jsonb_array_elements_text(g.sprekers) WITH ORDINALITY AS t(s, volgnr)
             ) x
            GROUP BY naam
         ) y
   )
 WHERE g.sprekers ?| array['Afspraken', 'Shaniel Work', 'Shaniel (H-AI & ICT)'];

UPDATE elevait.open_eindje SET wie = 'Mehdi'   WHERE wie = 'Afspraken';
UPDATE elevait.open_eindje SET wie = 'Shaniel' WHERE wie = 'Shaniel Work';
