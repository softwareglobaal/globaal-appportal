-- 047 - correctie Shaniel 2026-07-06 op migratie 046: personen zijn geen
-- keuzelijst-opties. Bij persoonlijke nummers blijft het doel de naam van de
-- collega en wordt gebruikt-voor gewoon "Privé". De optie Cataline vervalt.

INSERT INTO communicatie.lijst (categorie, waarde, sort_order) VALUES
    ('Gebruikt voor', 'Privé', 80)
ON CONFLICT (categorie, waarde) DO NOTHING;

DELETE FROM communicatie.lijst
 WHERE categorie = 'Gebruikt voor' AND waarde = 'Cataline';

UPDATE kern.definitie
   SET definitie = 'Waarvoor het nummer feitelijk gebruikt wordt, gekozen uit een vaste keuzelijst: Contrax, Tekenwerk, Energie-efficient, de sales-campagnes, klanten (Verbraeken en Co, Yannick Technics) en Prive voor persoonlijke nummers (het doel is dan de naam van de collega). Alleen invullen wanneer dat afwijkt van wie betaalt: aan jezelf hoef je niets uit te leggen. Opties beheren kan in communicatie.lijst, categorie "Gebruikt voor".'
 WHERE sleutel = 'gebruikt_voor';
