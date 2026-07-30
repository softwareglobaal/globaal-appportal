-- 097: het organisatieregister schakelt om naar APQC PCF v7.4 als skelet,
-- ESCO als rollenbron en ISO 9001 als keurmerk. Dit is de uitvoering van het
-- STOP-besluit van 28-07 (eerst een bron kiezen, dan bouwen); de VN-
-- verankering van 088-091 vervalt daarmee als actieve laag.
--
-- Structuur v1.0 zoals aangeleverd in organisatie-dashboard.html en
-- rollen-bibliotheek.html (Mehdi, 29-07-2026): 4 groepen, 17 pijlers,
-- 57 subpijlers, 199 taken, 121 unieke rollen met 127 plaatsingen.
--
-- De VN-laag wordt niet weggegooid maar gearchiveerd als kern.*_vn, zodat
-- REGEL 3 van het wijzigingslogboek (niets verdwijnt) gerespecteerd blijft.
-- De zeventien sleutels van kern.discipline worden hergebruikt en hernoemd;
-- de FK van kosten.software krijgt ON UPDATE CASCADE zodat de tien gemapte
-- softwarerijen meeverhuizen. Vrijgekomen slots: supply_chain (gaat op in
-- Procurement & Logistics) wordt client_work, informatiebeveiliging_privacy
-- (gaat op in IT & Digital Security als subpijler) wordt partnerships_relaties;
-- beide hadden nul gekoppelde software.
--
-- Gedachtestreepjes uit de aangeleverde teksten zijn omgezet naar gewone
-- streepjes (huisstijlregel 10, geldt ook voor seeds).

BEGIN;

-- 1. De VN-laag archiveren -------------------------------------------------
ALTER TABLE kern.subdiscipline DROP CONSTRAINT IF EXISTS subdiscipline_discipline_sleutel_fkey;
ALTER TABLE kern.subdiscipline RENAME TO subdiscipline_vn;
ALTER TABLE kern.subelement    RENAME TO subelement_vn;
ALTER TABLE kern.functie       RENAME TO functie_vn;
ALTER INDEX kern.subdiscipline_pkey        RENAME TO subdiscipline_vn_pkey;
ALTER INDEX kern.subdiscipline_code_uniek  RENAME TO subdiscipline_vn_code_uniek;
ALTER INDEX kern.ix_subdiscipline_discipline RENAME TO ix_subdiscipline_vn_discipline;
ALTER INDEX kern.subelement_pkey           RENAME TO subelement_vn_pkey;
ALTER INDEX kern.functie_pkey              RENAME TO functie_vn_pkey;
COMMENT ON TABLE kern.subdiscipline_vn IS
  'Archief: subdisciplineregister v3.0 (VN-verankerd, migraties 079-088). Vervangen door het PCF-register in 097.';
COMMENT ON TABLE kern.subelement_vn IS
  'Archief: sub-elementen bij het VN-register (migratie 090).';
COMMENT ON TABLE kern.functie_vn IS
  'Archief: functies onder ISCO-08 bij het VN-register (migratie 091). kern.rol blijft de ISCO-referentietabel.';

-- 2. Pijlers: kolommen, sleutelrenames, herseed ---------------------------
ALTER TABLE kern.discipline ADD COLUMN IF NOT EXISTS groep text;
ALTER TABLE kern.discipline ADD COLUMN IF NOT EXISTS bron  text NOT NULL DEFAULT '';
ALTER TABLE kern.discipline ADD COLUMN IF NOT EXISTS kern  boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN kern.discipline.groep IS 'Groep A-D uit het register (leeslaag boven de pijlers).';
COMMENT ON COLUMN kern.discipline.bron IS 'Bronvermelding van de pijlerstructuur (PCF-categorie, ESCO, wetgeving).';
COMMENT ON COLUMN kern.discipline.kern IS 'Kernpijler: ons eigen vak, bewust zonder rollencatalogus.';

ALTER TABLE kosten.software DROP CONSTRAINT software_discipline_sleutel_fkey;
ALTER TABLE kosten.software ADD CONSTRAINT software_discipline_sleutel_fkey
    FOREIGN KEY (discipline_sleutel) REFERENCES kern.discipline (sleutel) ON UPDATE CASCADE;

-- Volgorde eerst wegzetten: de kolom heeft een unieke constraint.
UPDATE kern.discipline SET volgorde = volgorde + 100;
UPDATE kern.discipline SET sleutel = 'partnerships_relaties' WHERE sleutel = 'informatiebeveiliging_privacy';
UPDATE kern.discipline SET sleutel = 'client_work' WHERE sleutel = 'supply_chain';
UPDATE kern.discipline SET sleutel = 'projecten_programma' WHERE sleutel = 'operations_projectmanagement';
UPDATE kern.discipline SET sleutel = 'innovatie_diensten' WHERE sleutel = 'research_development';
UPDATE kern.discipline SET sleutel = 'inkoop_logistiek' WHERE sleutel = 'procurement_vendormanagement';
UPDATE kern.discipline SET sleutel = 'hr_welzijn' WHERE sleutel = 'hr_recruitment';
UPDATE kern.discipline SET sleutel = 'it_security' WHERE sleutel = 'it_systemen';
UPDATE kern.discipline SET sleutel = 'data_kennis' WHERE sleutel = 'data_analytics';
UPDATE kern.discipline SET sleutel = 'office_facilities' WHERE sleutel = 'facilities_administratie';
UPDATE kern.discipline SET sleutel = 'strategie_duurzaamheid' WHERE sleutel = 'strategische_planning';
UPDATE kern.discipline SET sleutel = 'risk_continuiteit' WHERE sleutel = 'risk_management';

UPDATE kern.discipline SET code = 'A1', naam_en = 'Sales & Business Development', naam = 'Verkoop en business development', groep = 'A',
       bron = 'structuur: register v2 (bevroren) · APQC PCF v7.4 - cat. 3 · ESCO · wet van 17 juni 2016', kern = false, volgorde = 1, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'sales_bizdev';
UPDATE kern.discipline SET code = 'A2', naam_en = 'Marketing & Communications', naam = 'Marketing en communicatie', groep = 'A',
       bron = 'APQC PCF v7.4 - cat. 3, 12, 7 · ESCO · Verordening (EU) 2016/679', kern = false, volgorde = 2, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'marketing_communicatie';
UPDATE kern.discipline SET code = 'A3', naam_en = 'Customer Service & Aftercare', naam = 'Klantenservice en nazorg', groep = 'A',
       bron = 'APQC PCF v7.4 - cat. 6 · ESCO', kern = false, volgorde = 3, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'customer_service';
UPDATE kern.discipline SET code = 'A4', naam_en = 'Partnerships & External Relations', naam = 'Partners en externe relaties', groep = 'A',
       bron = 'APQC PCF v7.4 - cat. 12, 5', kern = false, volgorde = 4, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'partnerships_relaties';
UPDATE kern.discipline SET code = 'B1', naam_en = 'Client Work - Service Lines', naam = 'Klantwerk: onze dienstenlijnen', groep = 'B',
       bron = 'APQC PCF v7.4 - cat. 5 (zie kamer 5.0) · wetten 20/2/1939 & 26/6/1963 · gewestelijke EPB-regelgeving · oud BW 1792/2270', kern = true, volgorde = 5, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'client_work';
UPDATE kern.discipline SET code = 'B2', naam_en = 'Projects, Programme & Change', naam = 'Projecten, programma en verandering', groep = 'B',
       bron = 'APQC PCF v7.4 - cat. 13 · ESCO · Andersen, Grude & Haug - GDPM', kern = false, volgorde = 6, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'projecten_programma';
UPDATE kern.discipline SET code = 'B3', naam_en = 'Quality Management', naam = 'Kwaliteitsmanagement', groep = 'B',
       bron = 'APQC PCF v7.4 - cat. 13, 5, 11 · ESCO · EN ISO 9001:2015', kern = false, volgorde = 7, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'quality_assurance';
UPDATE kern.discipline SET code = 'B4', naam_en = 'Innovation & New Services', naam = 'Innovatie en nieuwe diensten', groep = 'B',
       bron = 'APQC PCF v7.4 - cat. 2 · ESCO', kern = false, volgorde = 8, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'innovatie_diensten';
UPDATE kern.discipline SET code = 'B5', naam_en = 'Procurement & Logistics', naam = 'Inkoop en logistiek', groep = 'B',
       bron = 'APQC PCF v7.4 - cat. 4 · ESCO', kern = false, volgorde = 9, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'inkoop_logistiek';
UPDATE kern.discipline SET code = 'C1', naam_en = 'HR & Well-being', naam = 'HR en welzijn', groep = 'C',
       bron = 'APQC PCF v7.4 - cat. 7, 13, 9 · ESCO · welzijnswet van 4 augustus 1996', kern = false, volgorde = 10, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'hr_welzijn';
UPDATE kern.discipline SET code = 'C2', naam_en = 'Finance & Accounting', naam = 'Financien en boekhouding', groep = 'C',
       bron = 'APQC PCF v7.4 - cat. 9 · ESCO · richtlijn 2013/34/EU', kern = false, volgorde = 11, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'finance_accounting';
UPDATE kern.discipline SET code = 'C3', naam_en = 'IT & Digital Security', naam = 'IT en digitale beveiliging', groep = 'C',
       bron = 'APQC PCF v7.4 - cat. 8 · ESCO · GDPR · NIS2 · AI-verordening', kern = false, volgorde = 12, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'it_security';
UPDATE kern.discipline SET code = 'C4', naam_en = 'Data, Analytics & Knowledge', naam = 'Data, analyse en kennis', groep = 'C',
       bron = 'APQC PCF v7.4 - cat. 8, 13 · ESCO · bewust vollediger: hier is de kennis vandaag het kleinst', kern = false, volgorde = 13, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'data_kennis';
UPDATE kern.discipline SET code = 'C5', naam_en = 'Office & Facilities', naam = 'Kantoor en facilities', groep = 'C',
       bron = 'APQC PCF v7.4 - cat. 10 · ESCO', kern = false, volgorde = 14, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'office_facilities';
UPDATE kern.discipline SET code = 'D1', naam_en = 'Strategy & Sustainability', naam = 'Strategie en duurzaamheid', groep = 'D',
       bron = 'APQC PCF v7.4 - cat. 1, 13 · ESCO · Ged. Verordening (EU) 2023/2772', kern = false, volgorde = 15, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'strategie_duurzaamheid';
UPDATE kern.discipline SET code = 'D2', naam_en = 'Legal & Compliance', naam = 'Juridisch en compliance', groep = 'D',
       bron = 'APQC PCF v7.4 - cat. 12, 11 · ESCO · WVV · wet van 28 november 2022', kern = false, volgorde = 16, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'legal_compliance';
UPDATE kern.discipline SET code = 'D3', naam_en = 'Risk & Continuity', naam = 'Risico en continuiteit', groep = 'D',
       bron = 'APQC PCF v7.4 - cat. 11, 8 · ESCO · achtergrond: EN ISO 31000 (bijlage deel 6)', kern = false, volgorde = 17, bijgewerkt_door = 'migratie 097'
   WHERE sleutel = 'risk_continuiteit';

-- 2b. Woordenboek: dezelfde sleutels, nieuwe termen en definities ---------
UPDATE kern.definitie SET sleutel = 'partnerships_relaties' WHERE sleutel = 'informatiebeveiliging_privacy';
UPDATE kern.definitie SET sleutel = 'client_work' WHERE sleutel = 'supply_chain';
UPDATE kern.definitie SET sleutel = 'projecten_programma' WHERE sleutel = 'operations_projectmanagement';
UPDATE kern.definitie SET sleutel = 'innovatie_diensten' WHERE sleutel = 'research_development';
UPDATE kern.definitie SET sleutel = 'inkoop_logistiek' WHERE sleutel = 'procurement_vendormanagement';
UPDATE kern.definitie SET sleutel = 'hr_welzijn' WHERE sleutel = 'hr_recruitment';
UPDATE kern.definitie SET sleutel = 'it_security' WHERE sleutel = 'it_systemen';
UPDATE kern.definitie SET sleutel = 'data_kennis' WHERE sleutel = 'data_analytics';
UPDATE kern.definitie SET sleutel = 'office_facilities' WHERE sleutel = 'facilities_administratie';
UPDATE kern.definitie SET sleutel = 'strategie_duurzaamheid' WHERE sleutel = 'strategische_planning';
UPDATE kern.definitie SET sleutel = 'risk_continuiteit' WHERE sleutel = 'risk_management';
INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('sales_bizdev', 'Verkoop en business development', 'Nieuwe dossiers binnenhalen en klantrelaties laten groeien: van prospectie en offerte tot account en tender.'),
('marketing_communicatie', 'Marketing en communicatie', 'Zichtbaarheid en boodschap: markt- en klantinzicht, merk, website, sociale media, pers en interne communicatie.'),
('customer_service', 'Klantenservice en nazorg', 'Vragen, klachten en tevredenheid tijdens en na het dossier, met een vaste route en antwoordtermijnen.'),
('partnerships_relaties', 'Partners en externe relaties', 'Relaties buiten de klantketen: Orde en federaties, overheden, bank, en het netwerk van partners en onderaannemers.'),
('client_work', 'Klantwerk: onze dienstenlijnen', 'Ons eigen vak: dossiers besturen, capaciteit en erkenningen, en de uitvoering van opstart tot oplevering en archief.'),
('projecten_programma', 'Projecten, programma en verandering', 'Dossiers en interne projecten plannen en bijsturen volgens GDPM, met portfolio-overzicht en verankering van nieuwe werkwijzen.'),
('quality_assurance', 'Kwaliteitsmanagement', 'Het kwaliteitssysteem: beleid en doelen, checklists, vier-ogen-vrijgave, interne audit, directiebeoordeling en de verbeterlus.'),
('innovatie_diensten', 'Innovatie en nieuwe diensten', 'Ideeen voor nieuwe diensten en tools verzamelen, beoordelen, uitwerken en lanceren.'),
('inkoop_logistiek', 'Inkoop en logistiek', 'Aankopen van software, apparatuur en onderaanneming, plus de beoordeling en opvolging van vaste leveranciers.'),
('hr_welzijn', 'HR en welzijn', 'Instroom, ontwikkeling en erkenningen van het team, verloning en personeelsadministratie, welzijn en preventie.'),
('finance_accounting', 'Financien en boekhouding', 'Facturatie en inning, boekhouding en btw, budget en marge, betalingen en cashplanning.'),
('it_security', 'IT en digitale beveiliging', 'Werkplekken en systemen, applicaties en koppelingen, en de beveiliging en privacy in de praktijk.'),
('data_kennis', 'Data, analyse en kennis', 'Datakwaliteit en naamconventies, cockpits en rapportering, en de kennisbank die kennis in het bureau houdt.'),
('office_facilities', 'Kantoor en facilities', 'Onthaal en kantoorwerking, plus pand, meetapparatuur en wagenpark.'),
('strategie_duurzaamheid', 'Strategie en duurzaamheid', 'Koers en jaarplan, het verdienmodel, en duurzaamheid in het bureau en in het advies.'),
('legal_compliance', 'Juridisch en compliance', 'Contracten en registers, vennootschapszaken en governance, en de naleving van deontologie en GDPR.'),
('risk_continuiteit', 'Risico en continuiteit', 'Het risicoregister, de verzekeringen, en een plan B dat getest is.')
ON CONFLICT (sleutel) DO UPDATE SET term = excluded.term,
    definitie = excluded.definitie, bijgewerkt_op = now();

-- Nieuwe termen uit het register zelf, zodat de Woordenboek-tab en de hovers
-- dezelfde taal spreken als de Disciplines-tab.
INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('subpijler', 'Subpijler', 'De onderverdeling van een pijler: waar het werk gebeurt. Draagt haar PCF-nummer en de ISO 9001-clausules die op haar landen.'),
('taak_subelement', 'Taak (sub-element)', 'Een taak die het register onder een subpijler opsomt. Samen beschrijven ze wat er in die subpijler gebeurt.'),
('register_rol', 'Rol in het register', 'Een beroep of pet die in een of meer subpijlers woont. Elke rol staat een keer in de rollenbibliotheek, met haar eigen uitleg.'),
('register_status', 'Status van een rol', 'MUST: moet vandaag belegd zijn, een pet of externe partij telt mee. OPT: optioneel. TOETS: ESCO-ontdekking, nog te beoordelen en te schrappen.'),
('esco_beroep', 'ESCO-beroep', 'Een rol die als beroep gedefinieerd is in ESCO, de Europese classificatie van beroepen. Draagt het E-merk in het register.'),
('agent_kandidaat', 'Agent-kandidaat', 'Rol die geheel of gedeeltelijk door een agent gedaan kan worden. Een kandidatuur, geen beslissing.')
ON CONFLICT (sleutel) DO UPDATE SET term = excluded.term,
    definitie = excluded.definitie, bijgewerkt_op = now();

-- 3. Nieuwe lagen ---------------------------------------------------------
-- Statuslijst als eigen tabel: de drie waarden hebben elk hun uitleg nodig
-- in de legenda en in het woordenboek.
CREATE TABLE kern.functie_status (
    code     text    NOT NULL PRIMARY KEY,
    naam     text    NOT NULL,
    uitleg   text    NOT NULL,
    volgorde integer NOT NULL
);
COMMENT ON TABLE kern.functie_status IS
  'De drie statussen van een rol in het register (migratie 097).';
INSERT INTO kern.functie_status (code, naam, uitleg, volgorde) VALUES
('MUST',  'must',  'Moet vandaag belegd zijn: een pet, een collega of een externe partij.', 1),
('OPT',   'opt',   'Optioneel: nuttig, niet noodzakelijk.', 2),
('TOETS', 'toets', 'ESCO-ontdekking: beoordelen en schrappen wat niet van toepassing is.', 3);

CREATE TABLE kern.subdiscipline (
    code               text    NOT NULL PRIMARY KEY,
    discipline_sleutel text    NOT NULL REFERENCES kern.discipline (sleutel) ON UPDATE CASCADE,
    naam               text    NOT NULL,
    definitie          text    NOT NULL DEFAULT '',
    pcf_code           text    NOT NULL DEFAULT '',
    iso_clausules      text    NOT NULL DEFAULT '',
    volgorde           integer NOT NULL
);
CREATE INDEX ix_subdiscipline_discipline ON kern.subdiscipline (discipline_sleutel, volgorde);
COMMENT ON TABLE kern.subdiscipline IS
  'Subpijlers van het organisatieregister v1.0, geindexeerd op APQC PCF v7.4 met de ISO 9001-clausules erbij (migratie 097).';
COMMENT ON COLUMN kern.subdiscipline.pcf_code IS 'Nummer(s) uit APQC PCF v7.4, het skelet van de structuur.';
COMMENT ON COLUMN kern.subdiscipline.iso_clausules IS 'ISO 9001:2015-clausules die op deze subpijler landen; leeg = geen.';

CREATE TABLE kern.subelement (
    subdiscipline_code text    NOT NULL REFERENCES kern.subdiscipline (code) ON DELETE CASCADE,
    volgorde           integer NOT NULL,
    naam               text    NOT NULL,
    PRIMARY KEY (subdiscipline_code, volgorde)
);
COMMENT ON TABLE kern.subelement IS
  'Taken per subpijler: de sub-elementen zoals het register ze opsomt (migratie 097).';

CREATE TABLE kern.functie (
    code            text    NOT NULL PRIMARY KEY,
    titel           text    NOT NULL UNIQUE,
    definitie       text    NOT NULL,
    status          text    NOT NULL REFERENCES kern.functie_status (code),
    agent_kandidaat boolean NOT NULL DEFAULT false,
    esco            boolean NOT NULL DEFAULT false,
    volgorde        integer NOT NULL
);
COMMENT ON TABLE kern.functie IS
  'Rollenbibliotheek: elke rol een keer, met status, agent-kandidatuur en de ESCO-vlag (migratie 097).';
COMMENT ON COLUMN kern.functie.status IS 'MUST = moet vandaag belegd zijn, OPT = optioneel, TOETS = ESCO-ontdekking, beoordelen en schrappen.';
COMMENT ON COLUMN kern.functie.agent_kandidaat IS 'Sterretje in het register: kandidaat om (deels) door een agent gedaan te worden.';
COMMENT ON COLUMN kern.functie.esco IS 'Beroep gedefinieerd in ESCO. Voorkeurslabel en URI zijn nog niet geverifieerd.';

CREATE TABLE kern.subdiscipline_functie (
    subdiscipline_code text    NOT NULL REFERENCES kern.subdiscipline (code) ON DELETE CASCADE,
    functie_code       text    NOT NULL REFERENCES kern.functie (code) ON DELETE CASCADE,
    volgorde           integer NOT NULL,
    PRIMARY KEY (subdiscipline_code, functie_code)
);
CREATE INDEX ix_subdiscipline_functie_functie ON kern.subdiscipline_functie (functie_code);
COMMENT ON TABLE kern.subdiscipline_functie IS
  'Waar een rol woont: veel-op-veel tussen subpijler en rol (migratie 097). Een rol kan in meer dan een subpijler wonen.';

CREATE TABLE kern.register_wijziging (
    volgorde integer NOT NULL PRIMARY KEY,
    soort    text    NOT NULL CHECK (soort IN ('regel', 'entry')),
    kop      text    NOT NULL,
    datum    date,
    tekst    text    NOT NULL
);
COMMENT ON TABLE kern.register_wijziging IS
  'Wijzigingslogboek van het register: de bevriezingsregels en elke wijziging met datum en reden (migratie 097).';

-- 4. Inhoud ---------------------------------------------------------------
INSERT INTO kern.subdiscipline (code, discipline_sleutel, naam, definitie, pcf_code, iso_clausules, volgorde) VALUES
('A1.1', 'sales_bizdev', 'Sales strategy & planning', 'Doelen, doelgroepen, territoria en prijzen bepalen: waar halen we volgend jaar onze dossiers, en tegen welke voorwaarden?', '3.4', '', 1),
('A1.2', 'sales_bizdev', 'Lead generation & prospecting', 'Actief nieuwe dossiers aantrekken: prospectie, leads kwalificeren en doelklanten gericht benaderen.', '3.5', '', 2),
('A1.3', 'sales_bizdev', 'Quotes, bids & tenders', 'Offertes en aanbestedingen opmaken, opvolgen en winnen. ⚖ Wet overheidsopdrachten bij publieke tenders.', '3.5.3', '8.2', 3),
('A1.4', 'sales_bizdev', 'Account management', 'Bestaande klanten beheren en laten groeien: portefeuille, retentie, verlenging en meerwerk.', '3.5', '', 4),
('A1.5', 'sales_bizdev', 'Sales operations & enablement', 'De motor achter de verkoop: CRM en pipeline, het offerteproces, training en rapportering.', '3.4 · 3.5', '', 5),
('A1.6', 'sales_bizdev', 'Business development', 'Groei buiten de gebaande paden: nieuwe markten, nieuwe proposities en strategische allianties.', '3.4 · 2.2 · 12.2', '', 6),
('A2.1', 'marketing_communicatie', 'Market & client insight', 'Begrijpen wie onze klanten zijn en wat beweegt in de markt: regularisatiegolven, premies, nieuwe verplichtingen.', '3.1', '', 1),
('A2.2', 'marketing_communicatie', 'Brand & marketing plan', 'Positionering, huisstijl en het jaarplan: waar zijn we zichtbaar, met welke boodschap en welk budget?', '3.2', '', 2),
('A2.3', 'marketing_communicatie', 'Content & online presence', 'Website, referentieprojecten, social media en nieuwsbrief actueel houden. ⚖ GDPR/ePrivacy bij direct marketing.', '3.3', '', 3),
('A2.4', 'marketing_communicatie', 'PR & internal communication', 'Pers en externe communicatie, plus het interne nieuws naar het team - ISO vraagt bewuste interne communicatie.', '12.5 · 7.8', '7.4', 4),
('A3.1', 'customer_service', 'Client contact & questions', 'Eén duidelijk kanaal voor vragen tijdens en na het dossier, met afspraken over wie wanneer antwoordt.', '6.2', '', 1),
('A3.2', 'customer_service', 'Complaints & resolution', 'Klachten registreren, oplossen en er structureel uit leren - voor ISO zijn klachten input voor corrigerende acties.', '6.2', '10.2', 2),
('A3.3', 'customer_service', 'Satisfaction & reviews', 'Tevredenheid meten na oplevering; reviews en referenties verzamelen. ISO vraagt expliciet klanttevredenheidsmeting.', '6.5', '9.1.2', 3),
('A4.1', 'partnerships_relaties', 'Sector & government relations', 'Orde, beroepsfederaties, gemeentebesturen en administraties: relaties die dossiers vlotter maken.', '12.2', '', 1),
('A4.2', 'partnerships_relaties', 'Financier relations', 'De bank en eventuele investeerders; kredietlijnen en waarborgen voor het bureau.', '12.1', '', 2),
('A4.3', 'partnerships_relaties', 'Partner network', 'Een vast netwerk van onderaannemers, collega-bureaus en kennispartners onderhouden.', '5.2.2', '', 3),
('B1.1', 'client_work', 'Service governance & standards', 'Hoe we dossiers besturen: werkwijzen per dienstenlijn, kwaliteitsbewaking en de erkenningen als harde randvoorwaarde. ⚖ Architectenwet & Orde, BA-verzekering. Voor ISO: de scope en de procesbeschrijving van het QMS.', '5.1', '4.3 · 4.4 · 8.1', 1),
('B1.2', 'client_work', 'Capacity & people planning', 'Wie-kan-wat: vaardigheden én erkenningen per gewest, planning van team en draftingpool, onderaanneming.', '5.2', '7.1 · 7.2', 2),
('B1.3', 'client_work', 'Service delivery: start → execute → close', 'Elk dossier: opstarten (nummer, monday, map) → uitvoeren (scan, ontwerp, studies, staving, vergunning, werf) → afronden (attesten, archief ≥ 10 jaar, werkles naar kennisbank). ⚖ EPB-aangifteplicht · tienjarige aansprakelijkheid · GDPR.', '5.3', '8.2 · 8.3 · 8.5 · 8.6', 3),
('B2.1', 'projecten_programma', 'Project management - GDPM', 'Onze methodiek: mijlpalenplan (het wát vóór het hóé) en een verantwoordelijkheidsschema per dossier. Bron: Andersen, Grude & Haug.', '13.2', '8.1', 1),
('B2.2', 'projecten_programma', 'Portfolio overview', 'Alle lopende dossiers en interne projecten in één overzicht: prioriteit, capaciteit en knelpunten.', '13.2', '', 2),
('B2.3', 'projecten_programma', 'Change & adoption', 'Nieuwe werkwijzen - zoals dit register of ISO - laten landen in het team: uitleg, oefening, verankering.', '13.4', '6.3', 3),
('B3.1', 'quality_assurance', 'Quality policy & objectives', 'Het kwaliteitsbeleid op één A4 en meetbare kwaliteitsdoelen per jaar - het hart van elk ISO-systeem, ondertekend door de directie.', '13.3', '5.2 · 6.2', 1),
('B3.2', 'quality_assurance', 'Quality system & checklists', 'Vaste controlepunten per dossiertype (bv. de stavingsstukkenlijst EPB), sjablonen en gedocumenteerde informatie - ISO-taal voor het datafundament.', '13.3', '4.3 · 4.4 · 7.5', 2),
('B3.3', 'quality_assurance', 'File review & release', 'Vier-ogen-controle vóór indiening of aangifte: niets vertrekt ongecheckt; afwijkende output wordt tegengehouden en geregistreerd.', '13.3 · 5.3', '8.6 · 8.7', 3),
('B3.4', 'quality_assurance', 'Internal audit', 'Zelf periodiek controleren of we doen wat we afspraken - verplicht voor ISO. Klein maar vast programma; auditor is onafhankelijk van het geauditeerde werk.', '13.3 · 11.2', '9.2', 4),
('B3.5', 'quality_assurance', 'Management review', 'Vast ritme waarin de directie het systeem beoordeelt: cijfers, klachten, audits, doelen - met een kort verslag als bewijs.', '13.6', '9.3', 5),
('B3.6', 'quality_assurance', 'Improvement loop', 'Fouten en werklessen omzetten in aangepaste checklists en sjablonen; ISO-taal: corrigerende acties en continue verbetering.', '13.6', '10.2 · 10.3', 6),
('B4.1', 'innovatie_diensten', 'Idea funnel', 'Ideeën voor nieuwe diensten of tools verzamelen, beoordelen en kiezen wat we uitproberen.', '2.2', '', 1),
('B4.2', 'innovatie_diensten', 'Service development', 'Een nieuwe dienst - bv. een extra attestering - uitwerken, testen bij enkele klanten en lanceren. ISO ziet dit als ontwerp & ontwikkeling.', '2.3', '8.3', 2),
('B5.1', 'inkoop_logistiek', 'Purchasing', 'Software, meetapparatuur, bureaumateriaal en onderaanneming aankopen tegen goede voorwaarden.', '4.2', '', 1),
('B5.2', 'inkoop_logistiek', 'Vendor management', 'Vaste leveranciers en onderaannemers beoordelen en de afspraken bewaken - ISO eist beheersing van extern geleverde processen.', '4.2 · 5.2.2', '8.4', 2),
('C1.1', 'hr_welzijn', 'Recruitment & onboarding', 'Vacatures, selectie en een goede start voor nieuwe collega''s - inclusief toegang, tools en meter/peter.', '7.2 · 7.3', '', 1),
('C1.2', 'hr_welzijn', 'Development & accreditations', 'Opleiding en permanente vorming (Orde), en de erkenningen van het team actueel houden - ISO-taal: competentie aantonen.', '7.3', '7.2', 2),
('C1.3', 'hr_welzijn', 'Pay & administration', 'Verloning en personeelsadministratie; de verwerking loopt via het sociaal secretariaat.', '7.5 · 9.5', '', 3),
('C1.4', 'hr_welzijn', 'Well-being & prevention', 'Welzijn en preventie op het werk. ⚖ Welzijnswet: risicoanalyses en een aangeduide preventieadviseur.', '13.8', '', 4),
('C2.1', 'finance_accounting', 'Invoicing & collection', 'Facturen per dossier(fase) uitsturen en betalingen opvolgen - de zuurstof van het bureau.', '9.2', '', 1),
('C2.2', 'finance_accounting', 'Bookkeeping & reporting', 'Boekhouding, btw en jaarrekening. ⚖ BE GAAP / richtlijn 2013/34/EU.', '9.3', '', 2),
('C2.3', 'finance_accounting', 'Budget & margin control', 'Budget, kostprijs en marge per dossiertype bewaken: verdienen we aan wat we doen?', '9.1', '', 3),
('C2.4', 'finance_accounting', 'Payments & cash', 'Leveranciersfacturen, onkosten en de cashplanning.', '9.6 · 9.7', '', 4),
('C3.1', 'it_security', 'Workplace & systems', 'Laptops, licenties, netwerk en de helpdeskvragen van het team.', '8.7', '', 1),
('C3.2', 'it_security', 'Applications & integrations', 'monday, Drive en het boekhoudpakket - en de koppelingen ertussen (het loodgieterswerk van het datafundament).', '8.5 · 8.6', '', 2),
('C3.3', 'it_security', 'Security & privacy in practice', 'Back-ups, toegangsbeheer, MFA en de datalekprocedure. ⚖ GDPR; NIS2 indien in scope; AI-verordening bij AI-gebruik.', '8.3', '', 3),
('C4.1', 'data_kennis', 'Data quality & stewardship', 'Het dossiernummer als sleutel, propere monday-data en de tien gouden regels van het datafundament bewaken - ISO-taal: beheersing van gedocumenteerde informatie.', '8.4', '7.5', 1),
('C4.2', 'data_kennis', 'Dashboards & reporting', 'Cockpits per dienstenlijn: pipeline, doorlooptijd, marge - de cijfers waarop we sturen. ISO vraagt monitoring en meting van de processen.', '13.7', '9.1', 2),
('C4.3', 'data_kennis', 'Knowledge base - second brain', 'Werklessen, sjablonen en de pijlerpagina''s: kennis die in het bureau blijft in plaats van in hoofden.', '13.5', '7.5', 3),
('C5.1', 'office_facilities', 'Office & reception', 'Het kantoor draaiende houden: onthaal, benodigdheden, klein onderhoud.', '10.3', '', 1),
('C5.2', 'office_facilities', 'Premises & equipment', 'Eigen pand, meetapparatuur en wagenpark - van aankoop tot afvoer. Klantprojecten horen hier níét: die wonen in 5.0. ISO eist bewijsbare kalibratie van meetapparatuur.', '10.1-10.4', '7.1.5', 2),
('D1.1', 'strategie_duurzaamheid', 'Vision & yearly plan', 'Koers en jaarplan: waar willen we staan, en wat pakken we dít jaar aan? Voor ISO: context, belanghebbenden en leiderschap.', '1.1-1.3', '4.1 · 4.2 · 5.1', 1),
('D1.2', 'strategie_duurzaamheid', 'Business model', 'Waar verdienen we aan - en klopt de prijs- en dienstenmix nog met de markt?', '1.4', '', 2),
('D1.3', 'strategie_duurzaamheid', 'Sustainability', 'Duurzaamheid van het bureau én in ons advies. ⚖ CSRD/ESRS enkel indien ooit in scope.', '13.9', '', 3),
('D2.1', 'legal_compliance', 'Contracts', 'Ereloonovereenkomsten, onderaanneming en NDA''s: sjablonen plus een register met vervaldagen.', '12.4', '', 1),
('D2.2', 'legal_compliance', 'Company & governance', 'WVV-verplichtingen, statuten en bestuursverslagen netjes op orde.', '12.3 · 12.4', '', 2),
('D2.3', 'legal_compliance', 'Compliance', 'Naleving bewaken: deontologie van de Orde, GDPR-afspraken, klokkenluidersregeling. ⚖ Klokkenluiderswet vanaf 50 wn.', '11.2', '', 3),
('D3.1', 'risk_continuiteit', 'Risk register', 'De grootste bedrijfsrisico''s benoemen, wegen en van een eigenaar voorzien - kort en levend, geen boekwerk. ISO-taal: risico''s en kansen.', '11.1', '6.1', 1),
('D3.2', 'risk_continuiteit', 'Insurance', 'BA-beroepsaansprakelijkheid (⚖ wettelijk verplicht), ABR en de andere polissen beheren.', '11.1', '', 2),
('D3.3', 'risk_continuiteit', 'Business continuity', 'Wat als de server, een sleutelcollega of het pand uitvalt: plan B klaar en getest.', '11.4', '', 3);

INSERT INTO kern.subelement (subdiscipline_code, volgorde, naam) VALUES
('A1.1', 1, 'marktsegmentatie & targeting'),
('A1.1', 2, 'verkoopdoelstellingen & quota'),
('A1.1', 3, 'territoriumindeling'),
('A1.1', 4, 'sales forecasting'),
('A1.1', 5, 'prijszetting ↔ marketing & financiën'),
('A1.2', 1, 'inbound/outbound prospectie'),
('A1.2', 2, 'leadkwalificatie (MQL/SQL)'),
('A1.2', 3, 'account-based selling'),
('A1.2', 4, 'offertes & tenders ↔ quotes-subpijler'),
('A1.3', 1, 'offertes opmaken & opvolgen'),
('A1.3', 2, 'RFP/RFQ-respons'),
('A1.3', 3, 'bid/no-bid-beslissing'),
('A1.3', 4, 'raamovereenkomsten'),
('A1.3', 5, 'win/verlies-analyse'),
('A1.4', 1, 'klantportefeuillebeheer'),
('A1.4', 2, 'key-accountmanagement'),
('A1.4', 3, 'retentie & contractverlenging'),
('A1.4', 4, 'upselling & cross-selling'),
('A1.4', 5, 'klanttevredenheid ↔ customer service'),
('A1.5', 1, 'CRM- & pipelinebeheer'),
('A1.5', 2, 'offerteproces (CPQ)'),
('A1.5', 3, 'salestraining & coaching'),
('A1.5', 4, 'commissiestructuren'),
('A1.5', 5, 'salesrapportering ↔ data'),
('A1.6', 1, 'nieuwe markten & segmenten'),
('A1.6', 2, 'nieuwe proposities ↔ innovation'),
('A1.6', 3, 'strategische deals & allianties ↔ partnerships'),
('A1.6', 4, 'kanaalontwikkeling'),
('A2.1', 1, 'marktonderzoek'),
('A2.1', 2, 'klantinzichten & doelgroepen'),
('A2.1', 3, 'concurrentie-analyse'),
('A2.1', 4, 'trends & regelgeving volgen'),
('A2.2', 1, 'positionering & waardepropositie'),
('A2.2', 2, 'huisstijl & merkbewaking'),
('A2.2', 3, 'jaarplan & budget'),
('A2.3', 1, 'website & SEO'),
('A2.3', 2, 'referentieprojecten & cases'),
('A2.3', 3, 'social media & nieuwsbrief'),
('A2.3', 4, 'beeldmateriaal'),
('A2.4', 1, 'persrelaties'),
('A2.4', 2, 'externe communicatie'),
('A2.4', 3, 'interne nieuwsbrief & teamcommunicatie'),
('A3.1', 1, 'kanaalafspraken (mail/telefoon)'),
('A3.1', 2, 'vraagregistratie & routering'),
('A3.1', 3, 'antwoordtermijnen'),
('A3.2', 1, 'klachtenregistratie'),
('A3.2', 2, 'oplossing & goodwill'),
('A3.2', 3, 'oorzaakanalyse ↔ kwaliteit'),
('A3.3', 1, 'tevredenheidsmeting na oplevering'),
('A3.3', 2, 'reviews & referenties'),
('A3.3', 3, 'verbeterpunten terugkoppelen'),
('A4.1', 1, 'Orde & beroepsfederaties'),
('A4.1', 2, 'contacten gemeenten & administraties'),
('A4.1', 3, 'sectorevents & netwerken'),
('A4.2', 1, 'bankrelatie & kredietlijnen'),
('A4.2', 2, 'waarborgen'),
('A4.2', 3, 'investeerderscontacten'),
('A4.3', 1, 'onderaannemers & collega-bureaus'),
('A4.3', 2, 'kennispartners'),
('A4.3', 3, 'samenwerkingsafspraken & evaluatie'),
('B1.1', 1, 'werkwijzen per dienstenlijn'),
('B1.1', 2, 'kwaliteits- & voortgangsbewaking'),
('B1.1', 3, 'erkenningenbeheer per gewest'),
('B1.1', 4, 'klantfeedback na oplevering'),
('B1.2', 1, 'wie-kan-wat-matrix (skills & erkenningen)'),
('B1.2', 2, 'teamplanning & draftingpool'),
('B1.2', 3, 'pipeline vs. capaciteit'),
('B1.2', 4, 'onderaanneming inschakelen'),
('B1.3', 1, 'dossieropening: nummer'),
('B1.3', 2, 'monday-item'),
('B1.3', 3, 'sjabloonmap'),
('B1.3', 4, 'opmeting & scan'),
('B1.3', 5, 'ontwerp & studies'),
('B1.3', 6, 'drafting'),
('B1.3', 7, 'staving & vergunning'),
('B1.3', 8, 'werfopvolging'),
('B1.3', 9, 'attesten & archief'),
('B1.3', 10, 'werkles naar kennisbank'),
('B2.1', 1, 'mijlpalenplan'),
('B2.1', 2, 'verantwoordelijkheidsschema'),
('B2.1', 3, 'voortgang & bijsturing'),
('B2.1', 4, 'projectafsluiting'),
('B2.2', 1, 'overzicht dossiers & projecten'),
('B2.2', 2, 'prioritering'),
('B2.2', 3, 'capaciteitsknelpunten'),
('B2.3', 1, 'impactanalyse'),
('B2.3', 2, 'uitleg & training'),
('B2.3', 3, 'verankering & nazorg'),
('B3.1', 1, 'kwaliteitsbeleid opstellen'),
('B3.1', 2, 'meetbare doelstellingen per jaar'),
('B3.1', 3, 'jaarlijkse herziening'),
('B3.2', 1, 'checklists per dossiertype'),
('B3.2', 2, 'sjablonenbeheer'),
('B3.2', 3, 'documentstandaarden & versiebeheer'),
('B3.3', 1, 'vier-ogen-controle'),
('B3.3', 2, 'vrijgave vóór indiening'),
('B3.3', 3, 'bevroren pdf zoals ingediend'),
('B3.3', 4, 'afwijkingen registreren'),
('B3.4', 1, 'jaarlijkse auditplanning'),
('B3.4', 2, 'audits uitvoeren & verslag'),
('B3.4', 3, 'opvolging van vaststellingen'),
('B3.5', 1, 'vaste agenda & ritme (bv. 2×/jaar)'),
('B3.5', 2, 'input verzamelen: KPI''s, klachten, audits'),
('B3.5', 3, 'besluiten & verslag'),
('B3.6', 1, 'afwijkingen & werklessen registreren'),
('B3.6', 2, 'oorzaakanalyse'),
('B3.6', 3, 'checklists & sjablonen bijwerken'),
('B4.1', 1, 'ideeën verzamelen'),
('B4.1', 2, 'beoordelen & kiezen'),
('B4.1', 3, 'klein experiment opzetten'),
('B4.2', 1, 'dienst uitwerken & prijszetting'),
('B4.2', 2, 'testen bij klanten'),
('B4.2', 3, 'lancering ↔ marketing'),
('B5.1', 1, 'behoefte & offertes vergelijken'),
('B5.1', 2, 'bestellen & ontvangst'),
('B5.1', 3, 'factuurmatching ↔ financiën'),
('B5.2', 1, 'leveranciersbeoordeling'),
('B5.2', 2, 'afspraken & prijsherzieningen'),
('B5.2', 3, 'vaste-leverancierslijst'),
('C1.1', 1, 'vacature & selectie'),
('C1.1', 2, 'contract & opstart'),
('C1.1', 3, 'onboarding-checklist & meter/peter'),
('C1.2', 1, 'opleidingsplan'),
('C1.2', 2, 'permanente vorming Orde'),
('C1.2', 3, 'erkenningen actueel houden'),
('C1.2', 4, 'competentieregister'),
('C1.3', 1, 'verloning & voordelen'),
('C1.3', 2, 'tijdregistratie & verlof'),
('C1.3', 3, 'dossier bij sociaal secretariaat'),
('C1.4', 1, 'risicoanalyses'),
('C1.4', 2, 'preventiemaatregelen & EHBO'),
('C1.4', 3, 'psychosociaal welzijn'),
('C1.4', 4, 'jaaractieplan'),
('C2.1', 1, 'facturatie per dossierfase'),
('C2.1', 2, 'betalingsopvolging'),
('C2.1', 3, 'aanmaningen & incasso'),
('C2.2', 1, 'boekingen & btw'),
('C2.2', 2, 'maand- & jaarafsluiting'),
('C2.2', 3, 'jaarrekening'),
('C2.3', 1, 'jaarbudget'),
('C2.3', 2, 'kostprijs & marge per dossiertype'),
('C2.3', 3, 'afwijkingsanalyse'),
('C2.4', 1, 'leveranciersfacturen & onkosten'),
('C2.4', 2, 'betalingen'),
('C2.4', 3, 'cashplanning'),
('C3.1', 1, 'hardware & licenties'),
('C3.1', 2, 'accounts & toegang'),
('C3.1', 3, 'helpdesk'),
('C3.2', 1, 'monday- & Drive-beheer'),
('C3.2', 2, 'koppelingen & automatisaties'),
('C3.2', 3, 'instellingen & versiebeheer'),
('C3.3', 1, 'back-ups & herstel testen'),
('C3.3', 2, 'MFA & toegangsbeheer'),
('C3.3', 3, 'datalekprocedure'),
('C3.3', 4, 'awareness'),
('C4.1', 1, 'dossiernummer & naamconventies bewaken'),
('C4.1', 2, 'monday-datakwaliteit'),
('C4.1', 3, 'tien gouden regels'),
('C4.1', 4, 'toegangsafspraken'),
('C4.2', 1, 'KPI-definities'),
('C4.2', 2, 'cockpits per dienstenlijn'),
('C4.2', 3, 'periodieke rapportering'),
('C4.3', 1, 'werklessen vastleggen'),
('C4.3', 2, 'sjablonen & pijlerpagina''s'),
('C4.3', 3, 'vindbaarheid & onderhoud'),
('C5.1', 1, 'onthaal & post'),
('C5.1', 2, 'benodigdheden'),
('C5.1', 3, 'klein onderhoud'),
('C5.2', 1, 'pand & verzekering pand'),
('C5.2', 2, 'meetapparatuur & kalibratiebewijzen ↔ kwaliteit'),
('C5.2', 3, 'wagenpark'),
('D1.1', 1, 'visie & doelen'),
('D1.1', 2, 'context & belanghebbenden'),
('D1.1', 3, 'jaarplan & initiatieven'),
('D1.1', 4, 'opvolgritme'),
('D1.2', 1, 'diensten- & prijsmix'),
('D1.2', 2, 'verdienmodel per lijn'),
('D1.2', 3, 'make-or-buy'),
('D1.3', 1, 'duurzaamheid bureau (energie, mobiliteit)'),
('D1.3', 2, 'duurzaam advies naar klanten'),
('D1.3', 3, 'rapportering indien vereist'),
('D2.1', 1, 'ereloonovereenkomsten & sjablonen'),
('D2.1', 2, 'onderaanneming & NDA''s'),
('D2.1', 3, 'contractregister & vervaldagen'),
('D2.2', 1, 'statuten & WVV-verplichtingen'),
('D2.2', 2, 'verslagen & neerleggingen'),
('D2.2', 3, 'volmachten'),
('D2.3', 1, 'deontologie Orde'),
('D2.3', 2, 'GDPR-afspraken & register'),
('D2.3', 3, 'klokkenluidersregeling (≥ 50 wn.)'),
('D3.1', 1, 'risico''s benoemen & wegen'),
('D3.1', 2, 'eigenaars & maatregelen'),
('D3.1', 3, 'jaarlijkse review'),
('D3.2', 1, 'BA-polis & ABR'),
('D3.2', 2, 'aangiftes & schadedossiers'),
('D3.2', 3, 'dekking jaarlijks toetsen'),
('D3.3', 1, 'back-up & uitwijk ↔ IT'),
('D3.3', 2, 'sleutelpersonen & vervanging'),
('D3.3', 3, 'noodscenario''s testen');

INSERT INTO kern.functie (code, titel, definitie, status, agent_kandidaat, esco, volgorde) VALUES
('F001', 'Sales lead', 'Bepaalt doelgroepen, prijzen en targets; de commerciële koers - vaak de zaakvoerder (pet).', 'OPT', false, false, 1),
('F002', 'Sales manager', 'Leidt de verkoop: strategie, targets en opvolging van het commerciële werk.', 'TOETS', false, true, 2),
('F003', 'Business developer', 'Zoekt groeikansen en nieuwe klanten; werkt offertes en deals uit en volgt ze op.', 'MUST', true, true, 3),
('F004', 'Bid manager', 'Coördineert grote aanbestedingsdossiers: planning, stukken, indiening (bureau-pet, geen ESCO-beroep).', 'OPT', false, false, 4),
('F005', 'Sales support assistant', 'Ondersteunt de verkoop administratief: offertes, orders en klantgegevens.', 'TOETS', true, true, 5),
('F006', 'Account owner', 'Vast aanspreekpunt per klant; houdt relatie en pipeline in monday actueel (pet).', 'MUST', false, false, 6),
('F007', 'Sales account manager', 'Beheert een portefeuille klanten en bouwt de relatie planmatig uit.', 'TOETS', false, true, 7),
('F008', 'Commercial sales representative', 'Verkoopt diensten actief aan bedrijven: prospecteert, presenteert en onderhandelt.', 'TOETS', false, true, 8),
('F009', 'Sales processor', 'Verwerkt verkooporders en offertes administratief correct en tijdig.', 'TOETS', true, true, 9),
('F010', 'CRM-beheerder', 'Houdt klantdata proper in monday en segmenteert voor gerichte opvolging (pet).', 'OPT', true, false, 10),
('F011', 'Market research analyst', 'Onderzoekt markt en klanten en vertaalt data naar bruikbare inzichten.', 'TOETS', true, true, 11),
('F012', 'Marketing coordinator', 'Voert het marketingjaarplan uit en bewaakt de huisstijl (pet).', 'MUST', true, false, 12),
('F013', 'Marketing manager', 'Leidt marketing: strategie, budget, campagnes en resultaten.', 'TOETS', false, true, 13),
('F014', 'External agency', 'Extern bureau voor campagnes, design en drukwerk (leverancier).', 'OPT', false, false, 14),
('F015', 'Content maker', 'Schrijft cases en onderhoudt website en social media; kan freelance.', 'OPT', true, false, 15),
('F016', 'Web content manager', 'Beheert inhoud en structuur van de website planmatig.', 'TOETS', true, true, 16),
('F017', 'Social media manager', 'Plant en beheert de sociale-mediakanalen en de interactie erop.', 'TOETS', true, true, 17),
('F018', 'Communication manager', 'Stuurt interne en externe communicatie en bewaakt de boodschap.', 'TOETS', false, true, 18),
('F019', 'Public relations officer', 'Verzorgt persrelaties en het publieke imago van het bureau.', 'TOETS', false, true, 19),
('F020', 'Service contact', 'Eerste aanspreekpunt voor klantvragen; registreert en routeert (pet).', 'MUST', true, false, 20),
('F021', 'Customer service representative', 'Beantwoordt klantvragen en lost problemen op via mail en telefoon.', 'TOETS', true, true, 21),
('F022', 'Complaint owner', 'Behandelt klachten en koppelt oorzaken terug naar de verbeterlus (pet).', 'MUST', false, false, 22),
('F023', 'Client relations manager', 'Bewaakt de klantrelatie en tevredenheid bij lopende dossiers.', 'TOETS', false, true, 23),
('F024', 'Feedback coördinator', 'Stuurt tevredenheidsmetingen uit en bundelt reviews (pet).', 'OPT', true, false, 24),
('F025', 'Customer experience manager', 'Ontwerpt en verbetert de totale klantbeleving over alle contactpunten.', 'TOETS', false, true, 25),
('F026', 'Relations lead', 'Onderhoudt Orde-, federatie- en overheidscontacten - vaak de zaakvoerder.', 'OPT', false, false, 26),
('F027', 'Finance contact', 'Beheert bankrelatie, kredietlijnen en waarborgen (directie-pet).', 'MUST', false, false, 27),
('F028', 'Partner coordinator', 'Onderhoudt het netwerk van onderaannemers en collega-bureaus (pet).', 'OPT', false, false, 28),
('F029', 'Project manager', 'Plant, organiseert en stuurt projecten: scope, tijd, budget en team - bij ons via GDPM.', 'MUST', false, true, 29),
('F030', 'PMO / planner', 'Bewaakt portfolio-overzicht, capaciteit en prioriteiten over alle dossiers (pet).', 'OPT', true, false, 30),
('F031', 'Change facilitator', 'Begeleidt nieuwe werkwijzen tot ze verankerd zijn in het team (pet).', 'OPT', false, false, 31),
('F032', 'Quality coordinator', 'Houdt het kwaliteitssysteem levend: beleid, checklists en afwijkingen (pet; geen exact ESCO-beroep - zie quality services manager).', 'MUST', true, false, 32),
('F033', 'Quality services manager', 'Beheert kwaliteit in een dienstenorganisatie: normen, audits en verbetering - het ESCO-beroep dat het dichtst bij ons past.', 'TOETS', false, true, 33),
('F034', 'Industrial quality manager', 'Kwaliteitsmanager uit de industrie; bruikbare ESCO-proxy voor QMS-beheer.', 'TOETS', false, true, 34),
('F035', 'Reviewer (vier ogen)', 'Controle-rol per dossier: tweede paar ogen dat vrijgeeft vóór indiening (geen beroep, wisselt per dossier).', 'MUST', false, false, 35),
('F036', 'Internal auditor', 'Voert interne audits uit, onafhankelijk van het eigen werk; kruiselings tussen collega''s of extern (ISO-functie, geen exact ESCO-beroep).', 'MUST', false, false, 36),
('F037', 'Managing director', 'Eindverantwoordelijke leiding: zet koers, zit de directiebeoordeling voor en beslist over middelen.', 'MUST', false, true, 37),
('F038', 'Quality engineer', 'Ontwerpt kwaliteitscontroles en analyseert afwijkingen - eerder industrieel profiel.', 'TOETS', false, true, 38),
('F039', 'Innovation lead', 'Verzamelt en filtert ideeën; kiest de experimenten (pet).', 'OPT', false, false, 39),
('F040', 'Product manager', 'Beheert een dienst of product door zijn levenscyclus: van behoefte tot lancering.', 'TOETS', false, true, 40),
('F041', 'Service owner', 'Werkt een nieuwe dienst uit en test ze bij klanten (pet).', 'OPT', false, false, 41),
('F042', 'Research and development manager', 'Leidt onderzoek en ontwikkeling van nieuwe diensten en methodes.', 'TOETS', false, true, 42),
('F043', 'Purchasing officer', 'Vraagt offertes op, bestelt en matcht facturen (pet).', 'MUST', true, false, 43),
('F044', 'Purchaser', 'Koopt goederen en diensten aan tegen de beste voorwaarden.', 'TOETS', true, true, 44),
('F045', 'Purchasing manager', 'Leidt het aankoopbeleid en de leveranciersstrategie.', 'TOETS', false, true, 45),
('F046', 'Vendor owner', 'Beoordeelt vaste leveranciers en bewaakt de afspraken (pet - ISO 8.4).', 'MUST', false, false, 46),
('F047', 'Supply chain manager', 'Plant en stuurt de volledige leverketen - bij ons beperkt relevant door de kleine goederenstroom.', 'TOETS', false, true, 47),
('F048', 'HR officer', 'Regelt werving, contracten, administratie en houdt opleidingen en erkenningen bij (pet; ESCO: human resources officer).', 'MUST', true, true, 48),
('F049', 'Recruitment consultant', 'Zoekt en screent actief kandidaten voor openstaande functies; kan extern.', 'TOETS', true, true, 49),
('F050', 'Human resources assistant', 'Ondersteunt HR administratief: dossiers, verlof, documenten.', 'TOETS', true, true, 50),
('F051', 'Human resources manager', 'Leidt het volledige personeelsbeleid: instroom, ontwikkeling, retentie - bij groei.', 'TOETS', false, true, 51),
('F052', 'Corporate trainer', 'Geeft interne opleidingen en ontwikkelt de vaardigheden van het team.', 'TOETS', false, true, 52),
('F053', 'Corporate training manager', 'Plant en beheert het opleidingsbeleid en -budget.', 'TOETS', false, true, 53),
('F054', 'Payroll (sociaal secretariaat)', 'Externe partner die lonen en sociale documenten verwerkt.', 'MUST', false, false, 54),
('F055', 'Payroll clerk', 'Verwerkt lonen, premies en aangiftes correct en tijdig - bij ons grotendeels uitbesteed.', 'TOETS', true, true, 55),
('F056', 'Compensation and benefits manager', 'Ontwerpt verloningspakketten en extralegale voordelen.', 'TOETS', false, true, 56),
('F057', 'Prevention advisor', 'Wettelijke functie uit de welzijnswet: risicoanalyses en preventie; bij < 20 wn. mag de werkgever dit zelf zijn.', 'MUST', false, false, 57),
('F058', 'Vertrouwenspersoon', 'Aanspreekpunt psychosociaal welzijn; opleiding vereist (aanbevolen, niet verplicht).', 'OPT', false, false, 58),
('F059', 'Health and safety officer', 'Bewaakt veiligheid en gezondheid op de werkplek; ondersteunt het preventiebeleid.', 'TOETS', false, true, 59),
('F060', 'Invoicing officer', 'Factureert per dossierfase en volgt betalingen op (pet).', 'MUST', true, false, 60),
('F061', 'Accounting assistant', 'Ondersteunt de boekhouding: invoer, facturen, afstemmingen.', 'TOETS', true, true, 61),
('F062', 'Accountant', 'Voert boekhouding, btw en jaarrekening; kan een extern kantoor zijn.', 'MUST', true, true, 62),
('F063', 'Bookkeeper', 'Registreert de dagelijkse boekingen en houdt de administratie bij.', 'TOETS', true, true, 63),
('F064', 'Financial auditor', 'Controleert financiële cijfers en processen onafhankelijk.', 'TOETS', false, true, 64),
('F065', 'Tax advisor', 'Adviseert over btw, vennootschapsbelasting en fiscale optimalisatie.', 'TOETS', false, true, 65),
('F066', 'Financial controller', 'Bewaakt budget, kostprijs en marge; rapporteert aan de directie.', 'OPT', true, true, 66),
('F067', 'Cost analyst', 'Analyseert kosten en rendement per dossiertype.', 'TOETS', false, true, 67),
('F068', 'Financial manager', 'Leidt de volledige financiële functie en planning - bij groei.', 'TOETS', false, true, 68),
('F069', 'Payments owner', 'Keurt betalingen goed en bewaakt de cashplanning (directie-pet).', 'MUST', false, false, 69),
('F070', 'Corporate treasurer', 'Beheert cash, financiering en bankrelaties professioneel.', 'TOETS', false, true, 70),
('F071', 'ICT system administrator', 'Beheert servers, accounts en toestellen; houdt de systemen draaiend - kan extern/managed.', 'MUST', true, true, 71),
('F072', 'ICT help desk agent', 'Eerste hulp bij IT-vragen en incidenten van het team.', 'TOETS', true, true, 72),
('F073', 'ICT network engineer', 'Ontwerpt en onderhoudt netwerk en verbindingen.', 'TOETS', false, true, 73),
('F074', 'Application manager', 'Beheert de inrichting van monday/Drive en de koppelingen ertussen (pet).', 'OPT', true, false, 74),
('F075', 'ICT application configurator', 'Stelt softwarepakketten in op maat van de organisatie.', 'TOETS', true, true, 75),
('F076', 'Software developer', 'Bouwt en onderhoudt software en automatisaties.', 'TOETS', true, true, 76),
('F077', 'ICT service manager', 'Stuurt IT-diensten en -leveranciers; bewaakt afspraken en kwaliteit.', 'TOETS', false, true, 77),
('F078', 'Security officer', 'Bewaakt back-ups, MFA en de datalekprocedure (pet, kan samen met sysadmin).', 'MUST', false, false, 78),
('F079', 'Privacy contact (GDPR)', 'Intern aanspreekpunt gegevensbescherming; formele DPO enkel indien wettelijk vereist (pet).', 'MUST', false, false, 79),
('F080', 'ICT security manager', 'Plant en beheert de informatiebeveiliging en de maatregelen.', 'TOETS', false, true, 80),
('F081', 'ICT security administrator', 'Voert beveiligingsinstellingen en toegangsbeheer uit in de praktijk.', 'TOETS', true, true, 81),
('F082', 'Chief ICT security officer', 'Eindverantwoordelijke informatiebeveiliging (CISO) - pas bij groei of NIS2-scope.', 'TOETS', false, true, 82),
('F083', 'Data protection officer', 'Onafhankelijk toezicht op GDPR-naleving; wettelijk enkel verplicht in specifieke gevallen.', 'TOETS', false, true, 83),
('F084', 'Data steward', 'Bewaakt naamgeving, dossiernummers en datakwaliteit in monday & Drive (pet; geen ESCO-beroep).', 'MUST', true, false, 84),
('F085', 'Data quality specialist', 'Meet en verbetert de kwaliteit van data structureel.', 'TOETS', true, true, 85),
('F086', 'Database administrator', 'Beheert databanken: toegang, back-ups, prestaties.', 'TOETS', true, true, 86),
('F087', 'Database developer', 'Bouwt en optimaliseert databankstructuren.', 'TOETS', true, true, 87),
('F088', 'Chief data officer', 'Eindverantwoordelijke datastrategie en -governance - in onze visie de latere eigenaar van de AI-cockpit.', 'TOETS', false, true, 88),
('F089', 'Data analyst', 'Onderzoekt concrete vragen in de data: doorlooptijden, marges, knelpunten.', 'OPT', true, true, 89),
('F090', 'Data scientist', 'Bouwt modellen en voorspellingen - pas zinvol bij veel data; nu nog niet.', 'OPT', true, true, 90),
('F091', 'Business analyst', 'Vertaalt bedrijfsvragen naar analyses en verbetervoorstellen.', 'TOETS', true, true, 91),
('F092', 'ICT business analyst', 'Vertaalt bedrijfsnoden naar IT-oplossingen en vereisten.', 'TOETS', true, true, 92),
('F093', 'Statistician', 'Past statistiek toe op data; academischer profiel dan een data-analist.', 'TOETS', false, true, 93),
('F094', 'Knowledge manager', 'Houdt kennisbank en sjablonen actueel en vindbaar (pet).', 'MUST', false, false, 94),
('F095', 'Information manager', 'Beheert informatiestromen, -systemen en hun toegankelijkheid.', 'TOETS', false, true, 95),
('F096', 'AI / automation specialist', 'Zet AI-assistenten en automatisaties op bovenop propere data - de latere agentlaag (geen ESCO-beroep).', 'OPT', true, false, 96),
('F097', 'Office manager', 'Houdt kantoor, onthaal en bestellingen draaiende (pet).', 'MUST', true, true, 97),
('F098', 'Receptionist', 'Onthaalt bezoekers en beheert telefonie en post.', 'TOETS', true, true, 98),
('F099', 'Administrative assistant', 'Algemene administratieve ondersteuning van het team.', 'TOETS', true, true, 99),
('F100', 'Management assistant', 'Ondersteunt de directie: agenda, verslagen, opvolging.', 'TOETS', false, true, 100),
('F101', 'Equipment owner', 'Beheert meetapparatuur en kalibratiebewijzen (pet - ISO 7.1.5).', 'MUST', false, false, 101),
('F102', 'Facilities manager', 'Beheert gebouwen, diensten en faciliteiten professioneel - bij groei of eigen pand.', 'TOETS', false, true, 102),
('F103', 'Fleet manager', 'Beheert het wagenpark: contracten, onderhoud, kosten.', 'TOETS', false, true, 103),
('F104', 'Business consultant', 'Adviseert over strategie, organisatie en verbetering - extern in te schakelen.', 'TOETS', false, true, 104),
('F105', 'Business manager', 'Stuurt bedrijfsvoering en verdienmodel operationeel aan.', 'TOETS', false, true, 105),
('F106', 'Sustainability lead', 'Trekt duurzaamheid in bureau en advies (pet).', 'OPT', false, false, 106),
('F107', 'Sustainability manager', 'Ontwikkelt en implementeert het duurzaamheidsbeleid.', 'TOETS', false, true, 107),
('F108', 'Corporate social responsibility manager', 'Beheert maatschappelijk verantwoord ondernemen en de rapportering erover.', 'TOETS', false, true, 108),
('F109', 'Contract administrator', 'Beheert sjablonen en het contractregister met vervaldagen (pet).', 'MUST', true, false, 109),
('F110', 'Contract manager', 'Beheert contracten door hun levenscyclus: opmaak, naleving, vernieuwing.', 'TOETS', false, true, 110),
('F111', 'Legal assistant', 'Ondersteunt juridisch werk: documenten, registers, opvolging.', 'TOETS', true, true, 111),
('F112', 'External counsel', 'Advocaat of notaris op afroep voor vennootschapszaken (extern).', 'MUST', false, false, 112),
('F113', 'Lawyer', 'Juridisch adviseur en vertegenwoordiger bij geschillen.', 'TOETS', false, true, 113),
('F114', 'Corporate lawyer', 'Gespecialiseerd in vennootschapsrecht en ondernemingszaken.', 'TOETS', false, true, 114),
('F115', 'Compliance owner', 'Bewaakt deontologie, GDPR-afspraken en de meldingsregeling (pet; ''compliance officer'' bestaat niet als exact ESCO-beroep).', 'OPT', false, false, 115),
('F116', 'Risk owner', 'Houdt het risicoregister levend (directie-pet).', 'MUST', false, false, 116),
('F117', 'Financial risk manager', 'Identificeert en beheert financiële risico''s.', 'TOETS', false, true, 117),
('F118', 'Insurance administrator', 'Beheert polissen, aangiftes en de jaarlijkse toetsing (pet).', 'MUST', true, false, 118),
('F119', 'Insurance broker', 'Onafhankelijke tussenpersoon voor verzekeringen (extern).', 'TOETS', false, true, 119),
('F120', 'Insurance claims handler', 'Behandelt schadedossiers en aangiftes.', 'TOETS', true, true, 120),
('F121', 'Continuity owner', 'Houdt plan B actueel en test het jaarlijks (pet, samen met IT).', 'OPT', false, false, 121);

INSERT INTO kern.subdiscipline_functie (subdiscipline_code, functie_code, volgorde) VALUES
('A1.1', 'F001', 1),
('A1.1', 'F002', 2),
('A1.2', 'F008', 1),
('A1.3', 'F003', 1),
('A1.3', 'F004', 2),
('A1.4', 'F006', 1),
('A1.4', 'F007', 2),
('A1.5', 'F010', 1),
('A1.5', 'F005', 2),
('A1.5', 'F009', 3),
('A1.6', 'F003', 1),
('A2.1', 'F011', 1),
('A2.2', 'F012', 1),
('A2.2', 'F013', 2),
('A2.2', 'F014', 3),
('A2.3', 'F015', 1),
('A2.3', 'F016', 2),
('A2.3', 'F017', 3),
('A2.4', 'F018', 1),
('A2.4', 'F019', 2),
('A3.1', 'F020', 1),
('A3.1', 'F021', 2),
('A3.2', 'F022', 1),
('A3.2', 'F023', 2),
('A3.3', 'F024', 1),
('A3.3', 'F025', 2),
('A4.1', 'F026', 1),
('A4.2', 'F027', 1),
('A4.3', 'F028', 1),
('B2.1', 'F029', 1),
('B2.2', 'F030', 1),
('B2.3', 'F031', 1),
('B3.1', 'F032', 1),
('B3.1', 'F033', 2),
('B3.2', 'F032', 1),
('B3.2', 'F034', 2),
('B3.3', 'F035', 1),
('B3.4', 'F036', 1),
('B3.5', 'F037', 1),
('B3.6', 'F032', 1),
('B3.6', 'F038', 2),
('B4.1', 'F039', 1),
('B4.1', 'F040', 2),
('B4.2', 'F041', 1),
('B4.2', 'F042', 2),
('B5.1', 'F043', 1),
('B5.1', 'F044', 2),
('B5.1', 'F045', 3),
('B5.2', 'F046', 1),
('B5.2', 'F047', 2),
('C1.1', 'F048', 1),
('C1.1', 'F049', 2),
('C1.1', 'F050', 3),
('C1.1', 'F051', 4),
('C1.2', 'F048', 1),
('C1.2', 'F052', 2),
('C1.2', 'F053', 3),
('C1.3', 'F054', 1),
('C1.3', 'F055', 2),
('C1.3', 'F056', 3),
('C1.4', 'F057', 1),
('C1.4', 'F058', 2),
('C1.4', 'F059', 3),
('C2.1', 'F060', 1),
('C2.1', 'F061', 2),
('C2.2', 'F062', 1),
('C2.2', 'F063', 2),
('C2.2', 'F064', 3),
('C2.2', 'F065', 4),
('C2.3', 'F066', 1),
('C2.3', 'F067', 2),
('C2.3', 'F068', 3),
('C2.4', 'F069', 1),
('C2.4', 'F070', 2),
('C3.1', 'F071', 1),
('C3.1', 'F072', 2),
('C3.1', 'F073', 3),
('C3.2', 'F074', 1),
('C3.2', 'F075', 2),
('C3.2', 'F076', 3),
('C3.2', 'F077', 4),
('C3.3', 'F078', 1),
('C3.3', 'F079', 2),
('C3.3', 'F080', 3),
('C3.3', 'F081', 4),
('C3.3', 'F082', 5),
('C3.3', 'F083', 6),
('C4.1', 'F084', 1),
('C4.1', 'F085', 2),
('C4.1', 'F086', 3),
('C4.1', 'F087', 4),
('C4.1', 'F088', 5),
('C4.2', 'F089', 1),
('C4.2', 'F090', 2),
('C4.2', 'F091', 3),
('C4.2', 'F092', 4),
('C4.2', 'F093', 5),
('C4.3', 'F094', 1),
('C4.3', 'F095', 2),
('C4.3', 'F096', 3),
('C5.1', 'F097', 1),
('C5.1', 'F098', 2),
('C5.1', 'F099', 3),
('C5.1', 'F100', 4),
('C5.2', 'F101', 1),
('C5.2', 'F102', 2),
('C5.2', 'F103', 3),
('D1.1', 'F037', 1),
('D1.1', 'F104', 2),
('D1.2', 'F105', 1),
('D1.3', 'F106', 1),
('D1.3', 'F107', 2),
('D1.3', 'F108', 3),
('D2.1', 'F109', 1),
('D2.1', 'F110', 2),
('D2.1', 'F111', 3),
('D2.2', 'F112', 1),
('D2.2', 'F113', 2),
('D2.2', 'F114', 3),
('D2.3', 'F115', 1),
('D2.3', 'F083', 2),
('D3.1', 'F116', 1),
('D3.1', 'F117', 2),
('D3.2', 'F118', 1),
('D3.2', 'F119', 2),
('D3.2', 'F120', 3),
('D3.3', 'F121', 1);

INSERT INTO kern.register_wijziging (volgorde, soort, kop, datum, tekst) VALUES
(1, 'regel', 'REGEL 1', NULL, 'De structuur (pijlers & subpijlers) is bevroren. Wijzigen kan alleen additief: toevoegen mag, verwijderen of samenvoegen niet.'),
(2, 'regel', 'REGEL 2', NULL, 'Elke wijziging - ook een toevoeging - krijgt hier een datum, een inhoud en een reden.'),
(3, 'regel', 'REGEL 3', NULL, 'Niets verdwijnt of wijzigt zonder expliciet akkoord van Mehdi. Geen stilzwijgende herstructurering, nooit.'),
(4, 'entry', '29-07-2026', '2026-07-29', 'Sales & Business Development hersteld naar de volledige registerstructuur v2: de 5 oorspronkelijke subpijlers (strategy & planning · lead generation & prospecting · account management · sales operations & enablement · business development) mét al hun taken, verbatim. De toevoeging "Quotes, bids & tenders" blijft behouden als ISO 8.2-anker en tenderluik. Kruisverwijzingen (↔) vertaald van oude pijlernummers naar deurnamen. Rollen herverdeeld; niets verwijderd.'),
(5, 'entry', '29-07-2026', '2026-07-29', 'Alsnog geregistreerd: bij de omschakeling naar de Engelse/PCF-versie werden subpijlers over de hele lijn versmald zonder wijzigingstabel - een procesfout. De volledige delta t.o.v. register v2 wordt ter goedkeuring voorgelegd vóór verder herstel.'),
(6, 'entry', '30-07-2026', '2026-07-30', 'Structuur v1.0 in de database gezet: 17 pijlers, 57 subpijlers, 199 taken en 121 rollen uit de twee aangeleverde bestanden. Het VN-register (102 subdisciplines, 209 sub-elementen, 108 ISCO-functies) is gearchiveerd als kern.subdiscipline_vn, kern.subelement_vn en kern.functie_vn; niets is verwijderd. Samenvoegingen tegenover het VN-register, met akkoord van Mehdi: Informatiebeveiliging en privacy wordt een subpijler van IT & Digital Security, Supply chain en logistiek gaat op in Procurement & Logistics, en Operations wordt gesplitst in Client Work (kern) en Projects, Programme & Change. Nieuw: Partnerships & External Relations. De pijlercodes D1-D17 zijn vervangen door groepscodes A1-D3.');

COMMIT;
