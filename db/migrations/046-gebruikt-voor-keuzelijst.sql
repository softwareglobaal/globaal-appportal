-- 046 - "Gebruikt voor" wordt een beheerbare keuzelijst (correctie Shaniel
-- 2026-07-06 op de entiteit-koppelingen van migratie 045: geen aparte
-- afdeling/persoon-velden maar een beperkt aantal vaste opties, zodat
-- iedereen dezelfde woorden gebruikt en er geteld kan worden).
--
-- De opties komen letterlijk uit het meeting-transcript: Contrax (7:24),
-- Tekenwerk (9:53), Energie-efficient (3:56), de twee sales-campagnes
-- (9:53), de klanten Verbraeken en Co (11:18) en Yannick Technics (11:29),
-- en Cataline (12:44, persoon met prive-nummer). Uitbreiden = een rij in
-- communicatie.lijst, geen code.

INSERT INTO communicatie.lijst (categorie, waarde, sort_order) VALUES
    ('Gebruikt voor', 'Contrax', 10),
    ('Gebruikt voor', 'Tekenwerk', 20),
    ('Gebruikt voor', 'Energie-efficiënt', 30),
    ('Gebruikt voor', 'Sales-campagne Unabo', 40),
    ('Gebruikt voor', 'Sales Unabo inbound', 50),
    ('Gebruikt voor', 'Verbraeken en Co', 60),
    ('Gebruikt voor', 'Yannick Technics', 70),
    ('Gebruikt voor', 'Cataline', 80)
ON CONFLICT (categorie, waarde) DO NOTHING;

UPDATE kern.definitie
   SET definitie = 'Waarvoor het nummer feitelijk gebruikt wordt, gekozen uit een vaste keuzelijst (Contrax, Tekenwerk, Energie-efficient, sales-campagnes, klanten, personen). Alleen invullen wanneer dat afwijkt van wie betaalt: aan jezelf hoef je niets uit te leggen. Opties beheren kan in communicatie.lijst, categorie "Gebruikt voor".'
 WHERE sleutel = 'gebruikt_voor';
