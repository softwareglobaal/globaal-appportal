-- 087: Engelse namen voor de disciplines en subdisciplines, en het register
-- terugbrengen tot uitsluitend EU-bronnen.
--
-- Waarom Engels als extra kolom en niet in plaats van `naam`: de Nederlandse
-- naam wordt ook gebruikt op de discipline-kaart, in de graaf en in de
-- kosten-mapping. Een extra kolom laat de Disciplines-tab Engels tonen zonder
-- die plekken stilzwijgend mee te veranderen, en is omkeerbaar.
--
-- De Engelse namen volgen waar mogelijk de terminologie van de EU-bron zelf
-- (ESRS, EN ISO 9001/31000/56002, e-CF PLAN-BUILD-RUN-ENABLE-MANAGE,
-- Richtlijn 2014/24/EU, NIS2 art. 21(2), Eurostat CBF), zodat de subdiscipline
-- letterlijk terug te vinden is in haar bron.
--
-- Bronopschoning: niet-EU-bronnen zijn verwijderd. Weg gaan ISCO-08 (ILO/VN),
-- EFQM en EMC (private organisaties), IEC 31010 (internationaal) en het
-- Europees Octrooiverdrag (EOV: eigen verdrag, geen EU-instrument). Blijven wel
-- staan: EU-wetgeving, ESRS, Eurostat CBF, ESCO, EQF, GreenComp, EBA-richtsnoeren
-- en de EN-normen (CEN is de Europese normalisatie-instelling onder Verordening
-- (EU) nr. 1025/2012, dus een EN-norm is een Europese bron).
--
-- Waar het schrappen van de niet-EU-bron niets overlaat, gaat de subdiscipline
-- naar status C (ontwerpkeuze, geen EU-bron op dit niveau). Dat is bewust:
-- liever eerlijk C dan een EU-bron erbij verzinnen die het onderwerp niet
-- benoemt. Dat raakt vijf subdisciplines: D2.2, D3.3, D3.5, D7.6 en D10.9.
-- Een echte EU-vervanger is er wel voor D12.10: ESRS G1-1 heet voluit
-- "Business conduct policies and corporate culture" en benoemt cultuur dus
-- expliciet; die gaat daarmee van B naar A.

-- Terugdraaien: DROP COLUMN naam_en op beide tabellen, en de twaalf bronnen
-- terugzetten naar hun waarde van voor deze migratie:
--   D1.1   'ISCO-08 1212; ESCO human resources manager'          B
--   D2.2   'ISCO-08 122'                                         B
--   D3.3   'EMC International Marketing Competencies'            B
--   D3.4   'EMC; AVG art. 6 en 7; Richtlijn 2002/58/EG'          B
--   D3.5   'ISCO-08 1222'                                        A
--   D6.7   'Verordening (EU) 2017/1001; Europees Octrooiverdrag' B
--   D7.6   'EFQM Stakeholder Perceptions'                        B
--   D10.9  'EFQM Model, RADAR-logica'                            B
--   D11.4  'EN ISO 31000 par. 6.4.3; IEC 31010'                  A
--   D12.1  'EFQM Direction; ESRS 2 SBM-1'                        A
--   D12.10 'EFQM Direction'                                      B
--   D15.10 'Verordening (EU) 2017/1001; Europees Octrooiverdrag' A

BEGIN;

ALTER TABLE kern.discipline    ADD COLUMN IF NOT EXISTS naam_en text;
ALTER TABLE kern.subdiscipline ADD COLUMN IF NOT EXISTS naam_en text;

COMMENT ON COLUMN kern.discipline.naam_en    IS 'Engelse naam; getoond op de Disciplines-tab. Nederlands blijft in naam.';
COMMENT ON COLUMN kern.subdiscipline.naam_en IS 'Engelse naam; getoond op de Disciplines-tab. Nederlands blijft in naam.';

-- ---------------------------------------------------------------- disciplines
UPDATE kern.discipline d SET naam_en = v.naam_en
  FROM (VALUES
    ('D1',  'HR and people'),
    ('D2',  'Sales and business development'),
    ('D3',  'Marketing and communications'),
    ('D4',  'Finance and accounting'),
    ('D5',  'Operations and process management'),
    ('D6',  'Legal and compliance'),
    ('D7',  'Customer service and support'),
    ('D8',  'IT and information systems'),
    ('D9',  'Procurement and supplier management'),
    ('D10', 'Quality management'),
    ('D11', 'Risk management and internal control'),
    ('D12', 'Strategy, governance and sustainability'),
    ('D13', 'Data and analytics'),
    ('D14', 'Facilities and administration'),
    ('D15', 'R&D and innovation management'),
    ('D16', 'Supply chain and logistics'),
    ('D17', 'Information security and privacy')
  ) AS v(code, naam_en)
 WHERE d.code = v.code;

-- ------------------------------------------------------------- subdisciplines
UPDATE kern.subdiscipline s SET naam_en = v.naam_en
  FROM (VALUES
    -- D1 volgt ESRS S1
    ('D1.1',  'Recruitment and selection'),
    ('D1.2',  'Remuneration and working conditions'),
    ('D1.3',  'Social protection'),
    ('D1.4',  'Training and skills development'),
    ('D1.5',  'Health and safety at work'),
    ('D1.6',  'Social dialogue and collective bargaining'),
    ('D1.7',  'Diversity, equality and inclusion'),
    ('D1.8',  'Work-life balance'),
    ('D1.9',  'Channels to raise concerns, complaints and remedy'),
    ('D1.10', 'Workforce administration and data'),
    -- D2
    ('D2.1',  'Sales agency and channel sales'),
    ('D2.2',  'Market development and acquisition'),
    ('D2.3',  'Quotation and tender management'),
    ('D2.4',  'Account management and customer relations'),
    ('D2.5',  'Pricing and commercial terms'),
    ('D2.6',  'Sales administration and customer data management'),
    -- D3 volgt Eurostat CBF 2.4.1
    ('D3.1',  'Advertising and media representation'),
    ('D3.2',  'Market research and public opinion polling'),
    ('D3.3',  'Brand and product positioning'),
    ('D3.4',  'Digital marketing and consent management'),
    ('D3.5',  'Corporate communications and public relations'),
    ('D3.6',  'Internal communications'),
    ('D3.7',  'Public affairs and lobbying'),
    -- D4 volgt Richtlijn 2013/34/EU
    ('D4.1',  'Bookkeeping and general ledger'),
    ('D4.2',  'Annual accounts and financial reporting'),
    ('D4.3',  'Management report'),
    ('D4.4',  'Statutory audit and auditor relations'),
    ('D4.5',  'Treasury and liquidity management'),
    ('D4.6',  'Accounts receivable and accounts payable'),
    ('D4.7',  'Taxation'),
    ('D4.8',  'Management accounting and costing'),
    ('D4.9',  'Budgeting and financial planning'),
    -- D5 volgt EN ISO 9001 hoofdstuk 8
    ('D5.1',  'Operational planning and control'),
    ('D5.2',  'Requirements for products and services'),
    ('D5.3',  'Design and development'),
    ('D5.4',  'Control of externally provided processes'),
    ('D5.5',  'Production and service provision'),
    ('D5.6',  'Release of products and services'),
    ('D5.7',  'Control of nonconforming outputs'),
    ('D5.8',  'Project and programme management'),
    ('D5.9',  'Capacity and resource planning'),
    -- D6 volgt ESRS G1 en Eurostat CBF 2.1.2
    ('D6.1',  'Contract management'),
    ('D6.2',  'Company law and corporate housekeeping'),
    ('D6.3',  'Compliance function'),
    ('D6.4',  'Code of conduct and business ethics'),
    ('D6.5',  'Anti-corruption and anti-bribery'),
    ('D6.6',  'Whistleblowing and reporting channels'),
    ('D6.7',  'Intellectual property, legal'),
    ('D6.8',  'Disputes and litigation'),
    ('D6.9',  'Legal assessment of data protection'),
    -- D7 volgt het consumentenacquis
    ('D7.1',  'Customer contact and helpdesk'),
    ('D7.2',  'Complaint handling and alternative dispute resolution'),
    ('D7.3',  'Warranty and conformity'),
    ('D7.4',  'Information and right of withdrawal'),
    ('D7.5',  'Technical support and after-sales service'),
    ('D7.6',  'Customer satisfaction measurement'),
    ('D7.7',  'Knowledge base and self-service'),
    -- D8 volgt EN 16234-1 (e-CF), de gebiednamen zijn al Engels
    ('D8.1',  'PLAN - Envision, design and decide'),
    ('D8.2',  'BUILD - Develop and implement'),
    ('D8.3',  'RUN - Deliver, support and maintain'),
    ('D8.4',  'ENABLE - Create the preconditions'),
    ('D8.5',  'MANAGE - Steer and control'),
    -- D9 volgt Richtlijn 2014/24/EU
    ('D9.1',  'Needs assessment and preliminary market consultation'),
    ('D9.2',  'Specification and technical requirements'),
    ('D9.3',  'Choice of procedure'),
    ('D9.4',  'Exclusion and selection criteria'),
    ('D9.5',  'Award and award criteria'),
    ('D9.6',  'Procurement techniques and instruments'),
    ('D9.7',  'Contract performance and modification'),
    ('D9.8',  'Subcontracting'),
    ('D9.9',  'Supplier relationships and payment practices'),
    ('D9.10', 'Sustainable and ethical procurement'),
    -- D10 volgt EN ISO 9001 hoofdstukken 4 tot 10
    ('D10.1', 'Context of the organisation'),
    ('D10.2', 'Leadership and quality policy'),
    ('D10.3', 'Planning: risks, opportunities and objectives'),
    ('D10.4', 'Support: resources, competence and documented information'),
    ('D10.5', 'Monitoring, measurement and analysis'),
    ('D10.6', 'Internal audit'),
    ('D10.7', 'Management review'),
    ('D10.8', 'Nonconformity, correction and improvement'),
    ('D10.9', 'Excellence assessment'),
    -- D11 volgt EN ISO 31000 hoofdstuk 6
    ('D11.1',  'Communication and consultation'),
    ('D11.2',  'Scope, context and criteria'),
    ('D11.3',  'Risk identification'),
    ('D11.4',  'Risk analysis'),
    ('D11.5',  'Risk evaluation'),
    ('D11.6',  'Risk treatment'),
    ('D11.7',  'Monitoring and review'),
    ('D11.8',  'Recording and reporting'),
    ('D11.9',  'Internal control'),
    ('D11.10', 'Internal audit'),
    ('D11.11', 'Business continuity and crisis management'),
    -- D12 volgt ESRS 2
    ('D12.1',  'Mission, vision and strategy setting'),
    ('D12.2',  'Administrative body: composition, role and oversight'),
    ('D12.3',  'Information provided to the administrative body'),
    ('D12.4',  'Due diligence process'),
    ('D12.5',  'Internal control over reporting'),
    ('D12.6',  'Stakeholders: interests and views'),
    ('D12.7',  'Materiality assessment'),
    ('D12.8',  'Sustainability strategy'),
    ('D12.9',  'Sustainability reporting'),
    ('D12.10', 'Corporate culture and leadership'),
    ('D12.11', 'Corporate development, acquisitions and partnerships'),
    -- D13 volgt de AI Act, de Data Act en de AVG
    ('D13.1',  'Data governance and ownership'),
    ('D13.2',  'Data quality'),
    ('D13.3',  'Records of processing activities'),
    ('D13.4',  'Data architecture and interoperability'),
    ('D13.5',  'Data availability and sharing'),
    ('D13.6',  'AI governance and AI literacy'),
    ('D13.7',  'Business intelligence and reporting'),
    ('D13.8',  'Data science and modelling'),
    -- D14 volgt EN 15221-4
    ('D14.1',  'Space and workplace'),
    ('D14.2',  'Maintenance and technical installations'),
    ('D14.3',  'Cleaning'),
    ('D14.4',  'Grounds and outdoor areas'),
    ('D14.5',  'Physical safety and security'),
    ('D14.6',  'Hospitality and catering'),
    ('D14.7',  'ICT workplace support'),
    ('D14.8',  'Internal logistics and document management'),
    ('D14.9',  'Office administration and business support'),
    ('D14.10', 'Tactical facility management coordination'),
    -- D15 volgt EN ISO 56002 par. 8.3
    ('D15.1',  'Innovation policy and strategy'),
    ('D15.2',  'Identify opportunities'),
    ('D15.3',  'Create concepts'),
    ('D15.4',  'Validate concepts'),
    ('D15.5',  'Develop solutions'),
    ('D15.6',  'Deploy solutions'),
    ('D15.7',  'Research'),
    ('D15.8',  'Engineering and related technical services'),
    ('D15.9',  'Value management and functional specification'),
    ('D15.10', 'Intellectual property portfolio'),
    ('D15.11', 'Innovation partnerships and funding'),
    -- D16 volgt Eurostat CBF 2.5
    ('D16.1',  'Transport'),
    ('D16.2',  'Warehousing and storage'),
    ('D16.3',  'Packaging'),
    ('D16.4',  'Customs and trade formalities'),
    ('D16.5',  'Supply chain due diligence'),
    ('D16.6',  'Returns and waste management'),
    ('D16.7',  'Demand and supply chain planning'),
    ('D16.8',  'Inventory management'),
    -- D17 volgt NIS2 art. 21(2)(a) tot en met (j), plus de AVG
    ('D17.1',  'Risk analysis and information security policy'),
    ('D17.2',  'Incident handling'),
    ('D17.3',  'Business continuity and backup'),
    ('D17.4',  'Supply chain security'),
    ('D17.5',  'Secure acquisition, development and maintenance'),
    ('D17.6',  'Assessment of effectiveness'),
    ('D17.7',  'Cyber hygiene and training'),
    ('D17.8',  'Cryptography and encryption'),
    ('D17.9',  'Human resources security, access control and asset management'),
    ('D17.10', 'Multi-factor authentication and secured communications'),
    ('D17.11', 'Data protection: officer, security and impact assessment'),
    ('D17.12', 'Personal data breach notification')
  ) AS v(code, naam_en)
 WHERE s.code = v.code;

-- ------------------------------------------------- uitsluitend EU-bronnen
UPDATE kern.subdiscipline s SET bron = v.bron, status = v.status
  FROM (VALUES
    -- ISCO-08 (ILO/VN) weg; ESCO is wel een EU-bron en blijft staan
    ('D1.1',  'ESCO human resources manager',                                'B'),
    -- ISCO-08 was de enige bron: geen EU-bron benoemt marktontwikkeling
    ('D2.2',  'geen EU-bron op dit niveau',                                  'C'),
    -- EMC is een private federatie, geen EU-instelling
    ('D3.3',  'geen EU-bron op dit niveau',                                  'C'),
    ('D3.4',  'AVG art. 6 en 7; Richtlijn 2002/58/EG',                       'B'),
    -- Eurostat CBF 2.4.1 noemt reclame en marktonderzoek, maar geen PR
    ('D3.5',  'geen EU-bron op dit niveau',                                  'C'),
    -- Europees Octrooiverdrag is geen EU-instrument; het Uniemerk wel
    ('D6.7',  'Verordening (EU) 2017/1001',                                  'B'),
    -- EFQM is privaat; ESRS S4 gaat over duurzaamheidsimpact, niet over
    -- tevredenheidsmeting, dus dat zou de bron oprekken
    ('D7.6',  'geen EU-bron op dit niveau',                                  'C'),
    ('D10.9', 'geen EU-bron op dit niveau',                                  'C'),
    -- IEC 31010 is internationaal; EN ISO 31000 is de Europese norm
    ('D11.4', 'EN ISO 31000 par. 6.4.3',                                     'A'),
    ('D12.1', 'ESRS 2 SBM-1',                                                'A'),
    -- ESRS G1-1 heet voluit "Business conduct policies and corporate culture"
    ('D12.10', 'ESRS G1-1',                                                  'A'),
    ('D15.10', 'Verordening (EU) 2017/1001',                                 'A')
  ) AS v(code, bron, status)
 WHERE s.code = v.code;

COMMIT;
