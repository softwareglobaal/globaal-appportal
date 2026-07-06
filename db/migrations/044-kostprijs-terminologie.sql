-- 044 - meeting Mehdi 2026-07-06: kostprijs-terminologie + prijs-metadata.
--
-- 1. "Vaste prijs" wordt "Kostprijs": "vast" is fout, elke prijs kan
--    veranderen. Sleutel blijft vaste_prijs (sleutels hernoemen we nooit).
-- 2. "Interne doorfacturatie naar" wordt "Kosten aanrekenen aan": er wordt
--    niets echt gefactureerd. Sleutel blijft doorfactureren_naar.
-- 3. Prijs-metadata op het nummer: prijstype (maandbedrag of per minuut) en
--    de peildatum van de laatste factuur. Ouder dan 2 maanden geeft een
--    waarschuwing in het register ("dan is er iets mis"). Kosten komen van
--    facturen, niet uit de Xelion-API (die heeft ze niet, bewezen 044-1).

UPDATE kern.definitie
   SET term = 'Kostprijs',
       definitie = 'De kostprijs van het abonnement in euro exclusief BTW, overgenomen van de laatste factuur van de leverancier. Niet "vast": elke prijs kan veranderen. Maandbedrag of tarief per minuut: zie het prijstype. Leeg = onbekend. Kortingen en acties staan alleen op de factuur; de factuur blijft de bron.'
 WHERE sleutel = 'vaste_prijs';

UPDATE kern.definitie
   SET term = 'Kosten aanrekenen aan',
       definitie = 'De firma van de groep aan wie de kosten intern worden aangerekend; kan verschillen van wie de leveranciersfactuur ontvangt en betaalt. Leeg wanneer de betalende firma de kosten zelf draagt: aan jezelf reken je niets aan. Verving "Interne doorfacturatie naar" (meeting 2026-07-06): er wordt niets echt gefactureerd.'
 WHERE sleutel = 'doorfactureren_naar';

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('prijs_type', 'Prijstype',
     'Of de kostprijs een maandbedrag is of een tarief per minuut. Bepaalt hoe het bedrag gelezen en opgeteld wordt: alleen maandbedragen tellen mee in maandtotalen.'),
    ('prijs_peildatum', 'Prijs bijgewerkt op',
     'De datum van de laatste factuur waarvan de kostprijs is overgenomen. Ouder dan 2 maanden betekent controleren: mogelijk is er een factuur gemist of is er iets veranderd.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

ALTER TABLE communicatie.nummer
    ADD COLUMN prijs_type text NOT NULL DEFAULT '',
    ADD COLUMN prijs_peildatum date;
