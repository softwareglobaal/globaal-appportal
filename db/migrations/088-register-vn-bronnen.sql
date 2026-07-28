-- 088: Register v3.0, VN-verankerd. Vervangt de EU-bronnen (087) door bronnen
-- uit het VN-systeem, en laat subdisciplines zonder VN-bron vervallen
-- (afspraak Shaniel 28-07: "wat geen bron heeft, geldt niet voor ons").
--
-- Afbakening VN-systeem: VN-organen en -verdragen (Algemene Vergadering,
-- UNCITRAL, UNCAC/UNODC, UNGP's, UNGCP, UNCTAD, UNECE, UNEP, UNDRR, UNSD) en
-- gespecialiseerde organisaties (ILO, UNESCO, WIPO, UNIDO, ITU). NIET tot het
-- VN-systeem behoren: ISO/IEC en CEN (onafhankelijke normalisatie), EU-recht,
-- EFQM, EMC, OECD, WCO en WTO. Daarmee vervalt de grond onder de op EN ISO
-- 9001/31000/56002 en e-CF gebouwde delen (D5, D8, D10, D11, D15-proces).
--
-- Ruggengraat: de Classification of Business Functions (Statistical Papers
-- Series F No. 125), op 4 maart 2022 door de VN-Statistiekcommissie bekrachtigd
-- als internationale statistische classificatie. Codes hier zijn de
-- VN-handboekcodes (die wijken af van de oude Eurostat-GVC-codes!):
--   1 productie; 2.1.1 management (financieel, hoofdkantoor, HR);
--   2.1.2 administratie en backoffice (juridisch, boekhouding, audit, kantoor);
--   2.2.1 engineering; 2.2.2 R&D; 2.3.1 ICT-diensten; 2.3.2 software;
--   2.4.1 marketing en after-sales (reclame, marktonderzoek, callcenters);
--   2.4.2 verkoop (handelsagenten); 2.5.1 transport; 2.5.2 opslag en verpakking;
--   2.6.1 facility management (schoonmaak, groen, catering); 2.6.2 onderhoud;
--   2.6.3 overige diensten (o.a. beveiliging).
--
-- Terugdraaien: de EU-bronnen staan in 087, de oorspronkelijke waarden in 079.
-- Kolom vervallen droppen en bron/status terugzetten volstaat.

BEGIN;

ALTER TABLE kern.subdiscipline ADD COLUMN IF NOT EXISTS vervallen boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN kern.subdiscipline.vervallen IS
  'Geen VN-bron op dit niveau: telt niet mee in het register (v3.0, 2026-07-28).';

-- ---------------------------------------------------------------- VN-bronnen
UPDATE kern.subdiscipline s SET bron = v.bron, status = v.status, vervallen = false
  FROM (VALUES
    -- D1 volgt de ILO-verdragen (ILO is een gespecialiseerde VN-organisatie)
    ('D1.1',  'ILO C181; ILO-beginselen voor eerlijke werving',              'A'),
    ('D1.2',  'ILO C95; ILO C131',                                          'A'),
    ('D1.3',  'ILO C102',                                                   'A'),
    ('D1.4',  'ILO C142',                                                   'A'),
    ('D1.5',  'ILO C155; ILO C187',                                         'A'),
    ('D1.6',  'ILO C87; ILO C98',                                           'A'),
    ('D1.7',  'ILO C100; ILO C111',                                         'A'),
    ('D1.8',  'ILO C156; ILO C183',                                         'A'),
    ('D1.9',  'ILO C190; UNGP 29',                                          'A'),
    ('D1.10', 'ILO C160; UN CBF 2.1.1',                                     'B'),
    -- D2
    ('D2.1',  'UN CBF 2.4.2 (activities of sales agents)',                  'A'),
    ('D2.2',  'ISCO-08 122',                                                'B'),
    ('D2.3',  'UNCITRAL modelwet aanbesteding 2011 (inschrijverszijde)',    'B'),
    ('D2.5',  'CISG art. 14 en 53-59',                                      'B'),
    ('D2.6',  'UNCITRAL modelwet elektronische handel; GA-res. 45/95',      'B'),
    -- D3
    ('D3.1',  'UN CBF 2.4.1 (advertising and media representation)',        'A'),
    ('D3.2',  'UN CBF 2.4.1 (market research and public opinion polling)',  'A'),
    ('D3.3',  'ISCO-08 1221',                                               'B'),
    ('D3.4',  'UNGCP (GA-res. 70/186), elektronische handel; GA-res. 45/95', 'B'),
    ('D3.5',  'ISCO-08 1222',                                               'A'),
    -- D4
    ('D4.1',  'UN CBF 2.1.2 (bookkeeping, accounting and auditing)',        'A'),
    ('D4.2',  'UNCTAD-ISAR SMEGA',                                          'A'),
    ('D4.3',  'UNCTAD-ISAR richtsnoeren governance-verslaggeving',          'B'),
    ('D4.4',  'UN CBF 2.1.2 (auditing)',                                    'A'),
    ('D4.5',  'UN CBF 2.1.1 (financial services)',                          'B'),
    ('D4.6',  'UNCTAD-ISAR SMEGA; CISG art. 53-59',                         'B'),
    ('D4.7',  'UN-modelverdrag dubbele belasting (2021); UN Practical Manual on Transfer Pricing', 'A'),
    -- D5: alleen wat de VN-classificatie zelf draagt
    ('D5.1',  'ISCO-08 132',                                                'B'),
    ('D5.4',  'UN CBF-handboek F.125, sourcing-raamwerk',                   'B'),
    ('D5.5',  'UN CBF 1 en 2 (kernfunctie: productie en dienstverlening)',  'A'),
    -- D6
    ('D6.1',  'UN CBF 2.1.2 (legal tasks); CISG',                           'A'),
    ('D6.2',  'UNCITRAL wetgevingsgids besloten ondernemingsvormen (2021)', 'B'),
    ('D6.3',  'UNCAC art. 12(2)(b)',                                        'A'),
    ('D6.4',  'UNCAC art. 12(2)(b); UN Global Compact beginsel 10',         'A'),
    ('D6.5',  'UNCAC art. 12 en 21',                                        'A'),
    ('D6.6',  'UNCAC art. 33',                                              'A'),
    ('D6.7',  'WIPO: Verdrag van Parijs, Madrid en PCT',                    'A'),
    ('D6.8',  'UNCITRAL modelwet arbitrage; Verdrag van Singapore inzake mediation', 'A'),
    ('D6.9',  'GA-res. 45/95',                                              'B'),
    -- D7 volgt de UN Guidelines for Consumer Protection
    ('D7.1',  'UN CBF 2.4.1 (call centres)',                                'A'),
    ('D7.2',  'UNGCP (GA-res. 70/186), geschillenbeslechting en verhaal',   'A'),
    ('D7.3',  'UNGCP (GA-res. 70/186), kwaliteit en veiligheid',            'B'),
    ('D7.4',  'UNGCP (GA-res. 70/186), consumenteninformatie',              'B'),
    ('D7.5',  'UN CBF 2.4.1 (after-sales services)',                        'A'),
    -- D9 volgt de UNCITRAL-modelwet aanbesteding 2011
    ('D9.2',  'UNCITRAL modelwet aanbesteding art. 10',                     'A'),
    ('D9.3',  'UNCITRAL modelwet aanbesteding hoofdstuk II',                'A'),
    ('D9.4',  'UNCITRAL modelwet aanbesteding art. 9',                      'A'),
    ('D9.5',  'UNCITRAL modelwet aanbesteding art. 11 en 20',               'A'),
    ('D9.6',  'UNCITRAL modelwet aanbesteding hoofdstuk VII (raamovereenkomsten)', 'A'),
    ('D9.7',  'CISG art. 53-60',                                            'B'),
    ('D9.9',  'CISG art. 53-59; UNGP 13(b)',                                'B'),
    ('D9.10', 'UNGP 17-21; UNEP-richtsnoeren duurzaam inkopen',             'B'),
    -- D11: wat UNCAC en Sendai dragen
    ('D11.9',  'UNCAC art. 12(2)(f)',                                       'A'),
    ('D11.10', 'UNCAC art. 12(2)(f)',                                       'A'),
    ('D11.11', 'Sendai-raamwerk 2015-2030 (GA-res. 69/283)',                'B'),
    -- D12
    ('D12.1',  'ISCO-08 1120',                                              'B'),
    ('D12.2',  'UNCTAD-ISAR richtsnoeren governance-verslaggeving',         'A'),
    ('D12.3',  'UNCTAD-ISAR richtsnoeren governance-verslaggeving',         'B'),
    ('D12.4',  'UNGP 17-21',                                                'A'),
    ('D12.5',  'UNCTAD-ISAR richtsnoeren governance-verslaggeving',         'B'),
    ('D12.6',  'UNGP 18',                                                   'B'),
    ('D12.7',  'UNCTAD-ISAR GCI',                                           'B'),
    ('D12.8',  'Agenda 2030 (GA-res. 70/1); UN Global Compact',             'A'),
    ('D12.9',  'UNCTAD-ISAR GCI',                                           'A'),
    -- D13
    ('D13.1',  'UNESCO-aanbeveling AI-ethiek (2021), datagovernance',       'B'),
    ('D13.2',  'GA-res. 45/95, beginsel juistheid',                         'B'),
    ('D13.3',  'GA-res. 45/95',                                             'B'),
    ('D13.6',  'UNESCO-aanbeveling AI-ethiek (2021); GA-res. 78/265',       'A'),
    -- D14 volgt UN CBF 2.6
    ('D14.1',  'UN CBF 2.6.1',                                              'B'),
    ('D14.2',  'UN CBF 2.6.2 (maintenance and repair services)',            'A'),
    ('D14.3',  'UN CBF 2.6.1 (cleaning services)',                          'A'),
    ('D14.4',  'UN CBF 2.6.1 (landscape services)',                         'A'),
    ('D14.5',  'UN CBF 2.6.3 (security)',                                   'A'),
    ('D14.6',  'UN CBF 2.6.1 (food and beverage services)',                 'A'),
    ('D14.7',  'UN CBF 2.3.1 (grensvlak met D8)',                           'B'),
    ('D14.8',  'UN CBF 2.5.1 (postal services); UN CBF 2.1.2',              'B'),
    ('D14.9',  'UN CBF 2.1.2 (office administration and business support)', 'A'),
    ('D14.10', 'UN CBF 2.6.1 (facility management)',                        'B'),
    -- D15
    ('D15.1',  'UNESCO-aanbeveling wetenschap (2017)',                      'B'),
    ('D15.7',  'UN CBF 2.2.2 (research and development)',                   'A'),
    ('D15.8',  'UN CBF 2.2.1 (engineering and related technical services)', 'A'),
    ('D15.10', 'WIPO: PCT, Madrid, Verdrag van Parijs',                     'A'),
    ('D15.11', 'UNESCO-aanbeveling wetenschap (2017), samenwerking en financiering', 'B'),
    -- D16
    ('D16.1',  'UN CBF 2.5.1 (transport and logistics)',                    'A'),
    ('D16.2',  'UN CBF 2.5.2 (warehousing and storage)',                    'A'),
    ('D16.3',  'UN CBF 2.5.2 (packaging)',                                  'A'),
    ('D16.4',  'UNECE TIR-verdrag (1975); UN/CEFACT-aanbevelingen',         'B'),
    ('D16.5',  'UNGP 17-21',                                                'A'),
    ('D16.6',  'Verdrag van Bazel (UNEP)',                                  'B'),
    -- D17 volgt GA-res. 57/239 (negen elementen van cyberveiligheidscultuur)
    ('D17.1',  'GA-res. 57/239: risk assessment en security management',    'A'),
    ('D17.2',  'GA-res. 57/239: response',                                  'A'),
    ('D17.3',  'GA-res. 57/239; Sendai-raamwerk',                           'B'),
    ('D17.5',  'GA-res. 57/239: security design and implementation',        'A'),
    ('D17.6',  'GA-res. 57/239: reassessment',                              'A'),
    ('D17.7',  'GA-res. 57/239: awareness',                                 'A'),
    ('D17.8',  'GA-res. 57/239 (afleidbaar)',                               'B'),
    ('D17.9',  'GA-res. 57/239: security management (afleidbaar)',          'B'),
    ('D17.10', 'GA-res. 57/239 (afleidbaar)',                               'B'),
    ('D17.11', 'GA-res. 45/95, beveiligingsbeginsel',                       'B')
  ) AS v(code, bron, status)
 WHERE s.code = v.code;

-- ------------------------------------------------ vervallen: geen VN-bron
UPDATE kern.subdiscipline SET vervallen = true,
       bron = 'geen VN-bron op dit niveau', status = 'C'
 WHERE code IN (
    'D2.4',
    'D3.6', 'D3.7',
    'D4.8', 'D4.9',
    'D5.2', 'D5.3', 'D5.6', 'D5.7', 'D5.8', 'D5.9',
    'D7.6', 'D7.7',
    'D8.1', 'D8.2', 'D8.3', 'D8.4', 'D8.5',
    'D9.1', 'D9.8',
    'D10.1', 'D10.2', 'D10.3', 'D10.4', 'D10.5', 'D10.6', 'D10.7', 'D10.8', 'D10.9',
    'D11.1', 'D11.2', 'D11.3', 'D11.4', 'D11.5', 'D11.6', 'D11.7', 'D11.8',
    'D12.10', 'D12.11',
    'D13.4', 'D13.5', 'D13.7', 'D13.8',
    'D15.2', 'D15.3', 'D15.4', 'D15.5', 'D15.6', 'D15.9',
    'D16.7', 'D16.8',
    'D17.4', 'D17.12');

-- --------------------------- nieuw: de onderverdeling die de VN-bron zelf geeft
-- D8: e-CF (CEN) vervalt; UN CBF 2.3 verdeelt het ICT-domein in twee groepen.
INSERT INTO kern.subdiscipline (code, discipline_sleutel, naam, naam_en, definitie, bron, status, relevantie, volgorde)
SELECT 'D8.6', d.sleutel, 'Softwareontwikkeling', 'Software programming',
       'Programmeren en aanverwante taken voor software die de organisatie bouwt of aanpast.',
       'UN CBF 2.3.2 (software programming)', 'A', 'K', 6
  FROM kern.discipline d WHERE d.code = 'D8'
   AND NOT EXISTS (SELECT 1 FROM kern.subdiscipline WHERE code = 'D8.6');

INSERT INTO kern.subdiscipline (code, discipline_sleutel, naam, naam_en, definitie, bron, status, relevantie, volgorde)
SELECT 'D8.7', d.sleutel, 'ICT-diensten en -beheer', 'ICT services other than software programming',
       'Levering en beheer van ICT-diensten: consultancy, telecommunicatie, dataverwerking en hosting, installatie en onderhoud van systemen.',
       'UN CBF 2.3.1 (ICT services other than software programming)', 'A', 'K', 7
  FROM kern.discipline d WHERE d.code = 'D8'
   AND NOT EXISTS (SELECT 1 FROM kern.subdiscipline WHERE code = 'D8.7');

-- D10: EN ISO 9001 vervalt; UNIDO (VN-organisatie) draagt de kwaliteitsinfrastructuur.
INSERT INTO kern.subdiscipline (code, discipline_sleutel, naam, naam_en, definitie, bron, status, relevantie, volgorde)
SELECT 'D10.10', d.sleutel, 'Kwaliteitsinfrastructuur en conformiteitsbeoordeling',
       'Quality infrastructure and conformity assessment',
       'Gebruik van normen, metrologie, keuring en certificering om de kwaliteit van producten en diensten aan te tonen.',
       'UNIDO Quality Infrastructure-kader', 'B', 'S', 10
  FROM kern.discipline d WHERE d.code = 'D10'
   AND NOT EXISTS (SELECT 1 FROM kern.subdiscipline WHERE code = 'D10.10');

COMMIT;
