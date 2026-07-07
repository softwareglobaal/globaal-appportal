-- 048 - correctie Shaniel 2026-07-06 op migratie 046: klanten zijn geen
-- keuzelijst-opties. Verbraeken & Co en Yannick Technics zijn klanten van
-- Contrax; hun nummers krijgen doel "Klantnummer [firmanaam]" en
-- gebruikt-voor "Contrax". De klant-opties vervallen uit de lijst.

DELETE FROM communicatie.lijst
 WHERE categorie = 'Gebruikt voor'
   AND waarde IN ('Verbraeken en Co', 'Yannick Technics');

UPDATE kern.definitie
   SET definitie = 'Waarvoor het nummer feitelijk gebruikt wordt, gekozen uit een vaste keuzelijst: Contrax, Tekenwerk, Energie-efficient, de sales-campagnes en Prive. Bij persoonlijke nummers is het doel de naam van de collega en gebruikt-voor Prive; bij klantnummers is het doel "Klantnummer [firmanaam]" en gebruikt-voor de firma van de groep die de klant bedient (bv. Contrax). Alleen invullen wanneer dat afwijkt van wie betaalt. Opties beheren kan in communicatie.lijst, categorie "Gebruikt voor".'
 WHERE sleutel = 'gebruikt_voor';
