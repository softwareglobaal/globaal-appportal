-- 079: subdisciplineregister v2.0 (27-07-2026) onder de 17 bedrijfsdisciplines.
--
-- Bron: het EU-verankerde register van Shaniel. Elke subdiscipline draagt zijn
-- herkomst mee: bron (EU-tekst of norm), status A/B/C (A = EU-bron benoemt het
-- expliciet, B = afleidbaar, C = ontwerpkeuze zonder EU-bron) en relevantie
-- K/S (kern of situatie-afhankelijk). Zo is in het dashboard zichtbaar wat
-- verankerd is en wat een keuze van onszelf is.
--
-- De 17 pijlers stonden al in kern.discipline in exact de D1-D16-volgorde. Twee
-- wijzigingen: de namen volgen nu het register, en slot 17 wisselt van
-- "Partnerships & vendor relations" (0 gekoppelde software, gaat op in D9
-- Inkoop) naar D17 Informatiebeveiliging en privacy.

ALTER TABLE kern.discipline ADD COLUMN IF NOT EXISTS code text;

UPDATE kern.discipline SET code = v.code, naam = v.naam FROM (VALUES
 ('hr_recruitment','D1','HR en mensen'),
 ('sales_bizdev','D2','Sales en business development'),
 ('marketing_communicatie','D3','Marketing en communicatie'),
 ('finance_accounting','D4','Finance en accounting'),
 ('operations_projectmanagement','D5','Operations en procesmanagement'),
 ('legal_compliance','D6','Legal en compliance'),
 ('customer_service','D7','Klantenservice en support'),
 ('it_systemen','D8','IT en informatiesystemen'),
 ('procurement_vendormanagement','D9','Inkoop en leveranciersmanagement'),
 ('quality_assurance','D10','Kwaliteitsmanagement'),
 ('risk_management','D11','Risicomanagement en internal control'),
 ('strategische_planning','D12','Strategie, governance en duurzaamheid'),
 ('data_analytics','D13','Data en analytics'),
 ('facilities_administratie','D14','Facilities en administratie'),
 ('research_development','D15','R&D en innovatiemanagement'),
 ('supply_chain','D16','Supply chain en logistiek')
) AS v(sleutel, code, naam) WHERE kern.discipline.sleutel = v.sleutel;

-- Slot 17: Partnerships eruit (geen software gekoppeld), Security erin.
DELETE FROM kern.discipline WHERE sleutel = 'partnerships_vendorrelaties';
INSERT INTO kern.discipline (sleutel, naam, volgorde, code, bijgewerkt_door)
VALUES ('informatiebeveiliging_privacy','Informatiebeveiliging en privacy',17,'D17','migratie 079')
ON CONFLICT (sleutel) DO UPDATE SET naam = EXCLUDED.naam, code = EXCLUDED.code;

CREATE TABLE IF NOT EXISTS kern.subdiscipline (
    code               text PRIMARY KEY,              -- D1.1
    discipline_sleutel text NOT NULL REFERENCES kern.discipline(sleutel) ON DELETE CASCADE,
    naam               text NOT NULL,
    definitie          text NOT NULL DEFAULT '',
    bron               text NOT NULL DEFAULT '',
    status             text NOT NULL CHECK (status IN ('A','B','C')),
    relevantie         text NOT NULL CHECK (relevantie IN ('K','S')),
    volgorde           integer NOT NULL,
    bijgewerkt_op      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_subdiscipline_discipline
    ON kern.subdiscipline (discipline_sleutel, volgorde);

INSERT INTO kern.subdiscipline (code, discipline_sleutel, naam, definitie, bron, status, relevantie, volgorde) VALUES
-- D1 HR en mensen
('D1.1','hr_recruitment','Werving en selectie','Aantrekken, beoordelen en aannemen van nieuwe medewerkers.','ISCO-08 1212; ESCO human resources manager','B','K',1),
('D1.2','hr_recruitment','Beloning en arbeidsvoorwaarden','Vaststellen van lonen, toeslagen en contractvoorwaarden.','ESRS S1-10; S1-16','A','K',2),
('D1.3','hr_recruitment','Sociale bescherming','Regelingen bij ziekte, werkloosheid, arbeidsongeschiktheid en pensioen.','ESRS S1-11','A','K',3),
('D1.4','hr_recruitment','Opleiding en competentieontwikkeling','Ontwikkelen van vaardigheden en loopbaanbegeleiding.','ESRS S1-13; EQF','A','K',4),
('D1.5','hr_recruitment','Welzijn en veiligheid op het werk','Risicobeoordeling, preventie en bescherming van gezondheid en veiligheid.','Richtlijn 89/391/EEG art. 6 en 9; ESRS S1-14','A','K',5),
('D1.6','hr_recruitment','Sociale dialoog en collectief overleg','Overleg met werknemersvertegenwoordiging en cao-toepassing.','ESRS S1-8','A','K',6),
('D1.7','hr_recruitment','Diversiteit, gelijkheid en inclusie','Samenstelling van het personeelsbestand en gelijke behandeling.','ESRS S1-9; S1-12','A','S',7),
('D1.8','hr_recruitment','Werk-privebalans','Regelingen rond verlof, flexibiliteit en werkdruk.','ESRS S1-15','A','S',8),
('D1.9','hr_recruitment','Meldkanalen, klachten en herstel','Kanalen om zorgen te uiten en negatieve gevolgen te herstellen.','ESRS S1-3; S1-17','A','K',9),
('D1.10','hr_recruitment','Personeelsadministratie en workforce data','Registratie van dienstverbanden, uren en personeelskengetallen.','ESRS S1-6 en S1-7','B','K',10),
-- D2 Sales
('D2.1','sales_bizdev','Handelsagentschap en kanaalverkoop','Verkoop via agenten, wederverkopers of partners.','Eurostat CBF 2.4.2 Sales','A','S',1),
('D2.2','sales_bizdev','Marktontwikkeling en acquisitie','Openen van nieuwe markten, segmenten en klantrelaties.','ISCO-08 122','B','K',2),
('D2.3','sales_bizdev','Offerte- en inschrijvingsbeheer','Opstellen en indienen van offertes en aanbestedingsdossiers.','Spiegelzijde Richtlijn 2014/24/EU art. 56-58','B','K',3),
('D2.4','sales_bizdev','Accountbeheer en klantrelaties','Onderhouden en uitbouwen van bestaande klantrelaties.','geen EU-bron op dit niveau','C','K',4),
('D2.5','sales_bizdev','Prijszetting en commerciele voorwaarden','Bepalen van tarieven, kortingen en betalingsvoorwaarden.','Richtlijn 2011/7/EU','B','K',5),
('D2.6','sales_bizdev','Verkoopadministratie en klantgegevensbeheer','Vastleggen van leads, pijplijn en klantgegevens.','AVG art. 6','B','K',6),
-- D3 Marketing
('D3.1','marketing_communicatie','Reclame en mediavertegenwoordiging','Ontwikkelen en plaatsen van commerciele boodschappen.','Eurostat CBF 2.4.1','A','K',1),
('D3.2','marketing_communicatie','Markt- en opinieonderzoek','Verzamelen van inzicht in markt, klant en perceptie.','Eurostat CBF 2.4.1','A','K',2),
('D3.3','marketing_communicatie','Merk- en productpositionering','Bepalen van merkbelofte, positionering en propositie.','EMC International Marketing Competencies','B','K',3),
('D3.4','marketing_communicatie','Digitale marketing en toestemmingsbeheer','Online kanalen, e-mail en advertenties, inclusief toestemming.','EMC; AVG art. 6 en 7; Richtlijn 2002/58/EG','B','K',4),
('D3.5','marketing_communicatie','Corporate communicatie en public relations','Externe woordvoering, persrelaties en reputatie.','ISCO-08 1222','A','K',5),
('D3.6','marketing_communicatie','Interne communicatie','Informatievoorziening aan de eigen organisatie.','geen EU-bron op dit niveau','C','K',6),
('D3.7','marketing_communicatie','Public affairs en belangenbehartiging','Contacten met overheid, sector en belangenorganisaties.','ESRS G1-5','A','S',7),
-- D4 Finance
('D4.1','finance_accounting','Boekhouding en grootboek','Vastleggen van financiele transacties.','Eurostat CBF 2.1.2','A','K',1),
('D4.2','finance_accounting','Jaarrekening en financiele verslaggeving','Opstellen van balans, resultatenrekening en toelichting.','Richtlijn 2013/34/EU art. 4-18','A','K',2),
('D4.3','finance_accounting','Bestuursverslag','Verslag over de gang van zaken en vooruitzichten.','Richtlijn 2013/34/EU art. 19','A','S',3),
('D4.4','finance_accounting','Wettelijke controle en accountantsrelatie','Voorbereiding en begeleiding van de externe controle.','Richtlijn 2006/43/EG; Eurostat CBF 2.1.2','A','S',4),
('D4.5','finance_accounting','Treasury en liquiditeitsbeheer','Beheer van kaspositie, financiering en bankrelaties.','Eurostat CBF 2.1.1','B','K',5),
('D4.6','finance_accounting','Debiteuren- en crediteurenbeheer','Facturatie, inning en betaling, inclusief betaaltermijnen.','Richtlijn 2011/7/EU art. 3-4; ESRS G1-6','A','K',6),
('D4.7','finance_accounting','Fiscaliteit','Aangifte en beheer van belastingen en heffingen.','Richtlijn 2006/112/EG','B','K',7),
('D4.8','finance_accounting','Management accounting en kostprijsbepaling','Interne kostentoerekening en marge-analyse.','geen EU-bron op dit niveau','C','K',8),
('D4.9','finance_accounting','Budgettering en financiele planning','Opstellen en bewaken van begroting en prognose.','geen EU-bron op dit niveau','C','K',9),
-- D5 Operations
('D5.1','operations_projectmanagement','Operationele planning en beheersing','Plannen, uitvoeren en beheersen van de processen die het aanbod voortbrengen.','EN ISO 9001 par. 8.1','A','K',1),
('D5.2','operations_projectmanagement','Bepaling van eisen aan product en dienst','Vaststellen en beoordelen van wat de klant en de regelgeving vragen.','EN ISO 9001 par. 8.2','A','K',2),
('D5.3','operations_projectmanagement','Ontwerp en ontwikkeling','Van eisen naar een uitvoerbaar ontwerp, inclusief verificatie en validatie.','EN ISO 9001 par. 8.3','A','K',3),
('D5.4','operations_projectmanagement','Beheersing van uitbestede processen','Sturen op processen, producten en diensten van derden binnen de eigen levering.','EN ISO 9001 par. 8.4','A','K',4),
('D5.5','operations_projectmanagement','Uitvoering en dienstverlening','De feitelijke productie of dienstverlening, inclusief identificatie en traceerbaarheid.','EN ISO 9001 par. 8.5','A','K',5),
('D5.6','operations_projectmanagement','Vrijgave en oplevering','Toetsen en vrijgeven van het resultaat aan de klant.','EN ISO 9001 par. 8.6','A','K',6),
('D5.7','operations_projectmanagement','Beheersing van afwijkende output','Identificeren en afhandelen van werk dat niet aan de eisen voldoet.','EN ISO 9001 par. 8.7','A','K',7),
('D5.8','operations_projectmanagement','Project- en programmamanagement','Organiseren van tijdelijk werk met een afgebakend doel.','ESCO project manager (geen EU-functieclassificatie)','C','K',8),
('D5.9','operations_projectmanagement','Capaciteits- en inzetplanning','Verdelen van mensen en middelen over het werk.','geen EU-bron op dit niveau','C','K',9),
-- D6 Legal
('D6.1','legal_compliance','Contractbeheer','Opstellen, beoordelen en bewaken van contracten.','Eurostat CBF 2.1.2','A','K',1),
('D6.2','legal_compliance','Vennootschapsrecht en bedrijfsjuridische zaken','Rechtsvorm, statuten, aandeelhouders en bestuursbesluiten.','Eurostat CBF 2.1.2; Richtlijn (EU) 2017/1132','A','K',2),
('D6.3','legal_compliance','Compliancefunctie','Bewaken van naleving van wet- en regelgeving en intern beleid.','EBA/GL/2021/05','A','K',3),
('D6.4','legal_compliance','Gedragscode en bedrijfsethiek','Vastleggen en uitdragen van integriteitsnormen.','ESRS G1-1','A','K',4),
('D6.5','legal_compliance','Anti-corruptie en omkopingspreventie','Voorkomen, opsporen en aanpakken van corruptie.','ESRS G1-3','A','K',5),
('D6.6','legal_compliance','Klokkenluidersregeling en meldkanalen','Interne meldkanalen en bescherming van melders.','Richtlijn (EU) 2019/1937 art. 8-9 en 19-21','A','K',6),
('D6.7','legal_compliance','Intellectuele eigendom, juridisch','Bescherming en handhaving van merken, modellen en octrooien.','Verordening (EU) 2017/1001; Europees Octrooiverdrag','B','S',7),
('D6.8','legal_compliance','Geschillen en procesvoering','Behandelen van conflicten, claims en gerechtelijke procedures.','geen EU-bron op dit niveau','C','S',8),
('D6.9','legal_compliance','Juridische duiding van gegevensbescherming','Beoordelen van verwerkingsgrondslag, verwerkersovereenkomsten en rechten.','AVG art. 6, 28 en 12-22 (grensvlak met D17)','B','K',9),
-- D7 Klantenservice
('D7.1','customer_service','Klantcontact en helpdesk','Eerstelijns beantwoording van vragen en verzoeken.','Eurostat CBF 2.4.1','A','K',1),
('D7.2','customer_service','Klachtenbehandeling en buitengerechtelijke beslechting','Registreren, oplossen en escaleren van klachten.','Richtlijn 2013/11/EU art. 5','A','K',2),
('D7.3','customer_service','Garantie en conformiteit','Afhandelen van gebreken en niet-conforme levering.','Richtlijn (EU) 2019/771 art. 5-14; Richtlijn (EU) 2019/770','A','S',3),
('D7.4','customer_service','Informatie- en herroepingsplichten','Verstrekken van wettelijke voorinformatie en herroepingsrecht.','Richtlijn 2011/83/EU art. 5-6 en 9-16','A','S',4),
('D7.5','customer_service','Technische ondersteuning en nazorg','Ondersteuning na oplevering, inclusief onderhoud en updates.','Eurostat CBF 2.4.1','A','K',5),
('D7.6','customer_service','Klanttevredenheidsmeting','Meten en analyseren van klantperceptie.','EFQM Stakeholder Perceptions','B','K',6),
('D7.7','customer_service','Kennisbank en selfservice','Documentatie waarmee klanten zichzelf kunnen helpen.','geen EU-bron op dit niveau','C','S',7),
-- D8 IT
('D8.1','it_systemen','PLAN - Bedenken, ontwerpen, beslissen','Afstemming van informatievoorziening op de bedrijfsstrategie, architectuur en technologiekeuze.','EN 16234-1 Dimensie 1, gebied A','A','K',1),
('D8.2','it_systemen','BUILD - Ontwikkelen en implementeren','Bouwen, integreren, testen en in gebruik nemen van oplossingen.','EN 16234-1 Dimensie 1, gebied B','A','K',2),
('D8.3','it_systemen','RUN - Leveren, ondersteunen, onderhouden','Draaiend houden van diensten, gebruikersondersteuning en probleembeheer.','EN 16234-1 Dimensie 1, gebied C','A','K',3),
('D8.4','it_systemen','ENABLE - Randvoorwaarden scheppen','Inkoop, verkoopondersteuning, contract- en leveranciersbeheer voor IT, informatiebeveiligingsstrategie.','EN 16234-1 Dimensie 1, gebied D','A','K',4),
('D8.5','it_systemen','MANAGE - Sturen en beheersen','Portfolio-, project-, risico- en kwaliteitsbeheer binnen de IT-functie.','EN 16234-1 Dimensie 1, gebied E','A','K',5),
-- D9 Inkoop
('D9.1','procurement_vendormanagement','Behoeftebepaling en marktverkenning','Vaststellen wat nodig is en verkennen wat de markt biedt.','Richtlijn 2014/24/EU art. 40','A','K',1),
('D9.2','procurement_vendormanagement','Specificatie en bestek','Vertalen van de behoefte naar technische eisen en keurmerken.','Richtlijn 2014/24/EU art. 42-44','A','K',2),
('D9.3','procurement_vendormanagement','Procedurekeuze','Kiezen van de wijze waarop de markt wordt benaderd.','Richtlijn 2014/24/EU art. 26-32','A','K',3),
('D9.4','procurement_vendormanagement','Uitsluiting en geschiktheidstoetsing','Beoordelen of een leverancier mag en kan leveren.','Richtlijn 2014/24/EU art. 57-58','A','K',4),
('D9.5','procurement_vendormanagement','Gunning en gunningscriteria','Beoordelen van aanbiedingen en toewijzen van de opdracht.','Richtlijn 2014/24/EU art. 67 en 69','A','K',5),
('D9.6','procurement_vendormanagement','Inkooptechnieken en -instrumenten','Raamovereenkomsten, dynamische aankoopsystemen, gezamenlijke inkoop.','Richtlijn 2014/24/EU art. 33-39','A','S',6),
('D9.7','procurement_vendormanagement','Contractuitvoering en wijziging','Bewaken van naleving en beheersen van wijzigingen tijdens de looptijd.','Richtlijn 2014/24/EU art. 70, 72 en 73','A','K',7),
('D9.8','procurement_vendormanagement','Onderaanneming','Toestaan, toetsen en bewaken van uitbesteding door de leverancier.','Richtlijn 2014/24/EU art. 71','A','S',8),
('D9.9','procurement_vendormanagement','Leveranciersrelaties en betalingspraktijken','Onderhouden van de relatie en nakomen van betaaltermijnen.','ESRS G1-2; G1-6','A','K',9),
('D9.10','procurement_vendormanagement','Duurzaam en ethisch inkopen','Meewegen van milieu-, sociale en mensenrechtenaspecten.','Richtlijn 2014/24/EU art. 18(2); Richtlijn (EU) 2024/1760 art. 5-8','A','K',10),
-- D10 Kwaliteit
('D10.1','quality_assurance','Context van de organisatie','Bepalen van interne en externe factoren, belanghebbenden en toepassingsgebied.','EN ISO 9001 par. 4','A','K',1),
('D10.2','quality_assurance','Leiderschap en kwaliteitsbeleid','Verantwoordelijkheid van de directie, beleid, rollen en bevoegdheden.','EN ISO 9001 par. 5','A','K',2),
('D10.3','quality_assurance','Planning: risicos, kansen en doelstellingen','Bepalen van kwaliteitsdoelen en het omgaan met risicos en kansen.','EN ISO 9001 par. 6','A','K',3),
('D10.4','quality_assurance','Ondersteuning: middelen, competentie en documentatie','Beschikbaar stellen van mensen, kennis, infrastructuur en gedocumenteerde informatie.','EN ISO 9001 par. 7','A','K',4),
('D10.5','quality_assurance','Monitoring, meting en analyse','Volgen en beoordelen van prestaties en klanttevredenheid.','EN ISO 9001 par. 9.1','A','K',5),
('D10.6','quality_assurance','Interne audit','Systematisch toetsen of het systeem werkt zoals bedoeld.','EN ISO 9001 par. 9.2','A','K',6),
('D10.7','quality_assurance','Directiebeoordeling','Periodieke beoordeling van het systeem door de leiding.','EN ISO 9001 par. 9.3','A','K',7),
('D10.8','quality_assurance','Afwijkingen, correctie en verbetering','Aanpakken van afwijkingen en doorvoeren van structurele verbetering.','EN ISO 9001 par. 10','A','K',8),
('D10.9','quality_assurance','Excellence-assessment','Zelfevaluatie tegen een breder prestatiemodel.','EFQM Model, RADAR-logica','B','S',9),
-- D11 Risico
('D11.1','risk_management','Communicatie en consultatie','Betrekken van belanghebbenden gedurende het gehele risicoproces.','EN ISO 31000 par. 6.2','A','K',1),
('D11.2','risk_management','Toepassingsgebied, context en criteria','Afbakenen waarover het gaat en wanneer een risico aanvaardbaar is.','EN ISO 31000 par. 6.3','A','K',2),
('D11.3','risk_management','Risico-identificatie','Opsporen en beschrijven van risicos.','EN ISO 31000 par. 6.4.2','A','K',3),
('D11.4','risk_management','Risicoanalyse','Bepalen van waarschijnlijkheid, gevolg en samenhang.','EN ISO 31000 par. 6.4.3; IEC 31010','A','K',4),
('D11.5','risk_management','Risico-evaluatie','Afwegen van analyse-uitkomsten tegen de criteria.','EN ISO 31000 par. 6.4.4','A','K',5),
('D11.6','risk_management','Risicobehandeling','Kiezen en uitvoeren van maatregelen.','EN ISO 31000 par. 6.5','A','K',6),
('D11.7','risk_management','Monitoring en beoordeling','Volgen of maatregelen werken en of het risicobeeld verandert.','EN ISO 31000 par. 6.6','A','K',7),
('D11.8','risk_management','Registratie en rapportage','Vastleggen en communiceren van het risicoproces en de uitkomsten.','EN ISO 31000 par. 6.7','A','K',8),
('D11.9','risk_management','Internal control','Beheersmaatregelen in de eerste en tweede lijn.','EBA/GL/2021/05','A','K',9),
('D11.10','risk_management','Internal audit','Onafhankelijke toetsing vanuit de derde lijn.','EBA/GL/2021/05','A','S',10),
('D11.11','risk_management','Bedrijfscontinuiteit en crisisbeheer','Voorbereiding op en beheersing van ernstige verstoringen.','Richtlijn (EU) 2022/2555 art. 21(2)(c)','A','S',11),
-- D12 Strategie
('D12.1','strategische_planning','Missie, visie en strategiebepaling','Vastleggen waar de organisatie voor staat en heen gaat.','EFQM Direction; ESRS 2 SBM-1','A','K',1),
('D12.2','strategische_planning','Bestuursorgaan: samenstelling, rol en toezicht','Inrichting en werking van het bestuur en het toezicht daarop.','ESRS 2 GOV-1; EBA/GL/2021/05','A','K',2),
('D12.3','strategische_planning','Informatievoorziening aan het bestuur','Wat het bestuur wanneer moet weten om te kunnen sturen.','ESRS 2 GOV-2','A','K',3),
('D12.4','strategische_planning','Due diligence-proces','Systematisch identificeren en aanpakken van nadelige gevolgen.','ESRS 2 GOV-4; Richtlijn (EU) 2024/1760 art. 5','A','S',4),
('D12.5','strategische_planning','Interne controle over rapportage','Beheersing van de betrouwbaarheid van de verslaggeving.','ESRS 2 GOV-5','A','K',5),
('D12.6','strategische_planning','Belanghebbenden: belangen en standpunten','Vaststellen wie belang heeft en wat zij verwachten.','ESRS 2 SBM-2','A','K',6),
('D12.7','strategische_planning','Materialiteitsbepaling','Bepalen welke onderwerpen er werkelijk toe doen.','ESRS 2 IRO-1; SBM-3','A','K',7),
('D12.8','strategische_planning','Duurzaamheidsstrategie','Vertalen van duurzaamheidsambities naar beleid en doelen.','ESRS 1 en 2; GreenComp','A','S',8),
('D12.9','strategische_planning','Duurzaamheidsrapportage','Opstellen van de duurzaamheidsverklaring.','Gedelegeerde Verordening (EU) 2023/2772','A','S',9),
('D12.10','strategische_planning','Organisatiecultuur en leiderschap','Vormgeven van gedrag, waarden en leiderschapsstijl.','EFQM Direction','B','K',10),
('D12.11','strategische_planning','Bedrijfsontwikkeling, overname en samenwerking','Structurele wijzigingen in de ondernemingsvorm of het portfolio.','geen EU-bron op dit niveau','C','S',11),
-- D13 Data
('D13.1','data_analytics','Datagovernance en eigenaarschap','Wie beslist over welke gegevens, en onder welke voorwaarden.','Verordening (EU) 2022/868 (Data Governance Act)','B','K',1),
('D13.2','data_analytics','Datakwaliteit','Zorgen dat gegevens relevant, representatief en volledig zijn.','Verordening (EU) 2024/1689 (AI Act) art. 10','A','K',2),
('D13.3','data_analytics','Verwerkingsregister','Bijhouden welke persoonsgegevens waarvoor worden verwerkt.','AVG art. 30','A','K',3),
('D13.4','data_analytics','Data-architectuur en interoperabiliteit','Structureren van gegevens zodat systemen kunnen samenwerken.','Verordening (EU) 2023/2854 (Data Act) art. 33','B','K',4),
('D13.5','data_analytics','Databeschikbaarheid en -deling','Toegang tot en uitwisseling van gegevens met derden.','Verordening (EU) 2023/2854 art. 3-5','A','S',5),
('D13.6','data_analytics','AI-governance en AI-geletterdheid','Beheersen van de inzet van AI-systemen en bekwaamheid van gebruikers.','Verordening (EU) 2024/1689 art. 4 en 9','A','K',6),
('D13.7','data_analytics','Business intelligence en rapportage','Ontsluiten van gegevens voor sturing en verantwoording.','geen EU-bron op dit niveau','C','K',7),
('D13.8','data_analytics','Data science en modellering','Analyseren en modelleren van gegevens voor voorspelling of inzicht.','ESCO skills pillar','C','S',8),
-- D14 Facilities
('D14.1','facilities_administratie','Ruimte en werkplek','Huisvesting, indeling en toewijzing van werkplekken.','EN 15221-4 productgroep 1000','A','K',1),
('D14.2','facilities_administratie','Onderhoud en technische installaties','In stand houden van gebouw en installaties.','EN 15221-4 (1000); Eurostat CBF 2.6.2','A','K',2),
('D14.3','facilities_administratie','Reiniging','Schoonmaak van gebouw, ruimten en installaties.','EN 15221-4 (1000); Eurostat CBF 2.6.1','A','K',3),
('D14.4','facilities_administratie','Buitenruimte en terrein','Beheer van terrein, groen en toegangswegen.','EN 15221-4 (1000); Eurostat CBF 2.6.1','A','S',4),
('D14.5','facilities_administratie','Fysieke veiligheid en beveiliging','Toegangscontrole, bewaking en fysieke bescherming.','EN 15221-4 productgroep 2000','A','K',5),
('D14.6','facilities_administratie','Horeca en catering','Voorzieningen voor eten en drinken.','EN 15221-4 (2000); Eurostat CBF 2.6.1','A','S',6),
('D14.7','facilities_administratie','Werkplekondersteuning ICT','Faciliteren van de digitale werkplek als voorziening.','EN 15221-4 (2000); grensvlak met D8','A','S',7),
('D14.8','facilities_administratie','Interne logistiek en documentbeheer','Post, archief, reprografie en interne verplaatsingen.','EN 15221-4 (2000)','A','K',8),
('D14.9','facilities_administratie','Kantooradministratie en business support','Algemene ondersteunende administratie.','Eurostat CBF 2.1.2','A','K',9),
('D14.10','facilities_administratie','Tactische FM-regie','Coordinatie tussen vraag en aanbod van facilitaire diensten.','EN 15221-4 (tactische integratie)','A','K',10),
-- D15 R&D
('D15.1','research_development','Innovatiebeleid en -strategie','Richting, ambitie en middelen voor innovatie.','EN ISO 56002 par. 5','A','K',1),
('D15.2','research_development','Identificeren van kansen','Signaleren van behoeften, problemen en mogelijkheden.','EN ISO 56002 par. 8.3.2','A','K',2),
('D15.3','research_development','Conceptcreatie','Omzetten van kansen naar concrete concepten.','EN ISO 56002 par. 8.3.3','A','K',3),
('D15.4','research_development','Conceptvalidatie','Toetsen van aannames en haalbaarheid.','EN ISO 56002 par. 8.3.4','A','K',4),
('D15.5','research_development','Oplossingsontwikkeling','Uitwerken van het concept tot een bruikbare oplossing.','EN ISO 56002 par. 8.3.5','A','K',5),
('D15.6','research_development','Implementatie en uitrol','In gebruik nemen en verspreiden van de oplossing.','EN ISO 56002 par. 8.3.6','A','K',6),
('D15.7','research_development','Onderzoek','Fundamenteel en toegepast onderzoek.','Eurostat CBF 2.2.2','A','S',7),
('D15.8','research_development','Engineering en technische diensten','Architectonische en technische uitwerking en analyse.','Eurostat CBF 2.2.1','A','K',8),
('D15.9','research_development','Value management en functionele specificatie','Uitdrukken van de behoefte in functies en waarde.','EN 12973; EN 1325; EN 16271','A','S',9),
('D15.10','research_development','Intellectuele-eigendomsportefeuille','Opbouwen en beheren van merken, modellen en octrooien.','Verordening (EU) 2017/1001; Europees Octrooiverdrag','A','S',10),
('D15.11','research_development','Innovatiepartnerschappen en subsidies','Samenwerking en externe financiering van innovatie.','Richtlijn 2014/24/EU art. 31; Verordening (EU) 2021/695','A','S',11),
-- D16 Supply chain
('D16.1','supply_chain','Transport en vervoer','Verplaatsen van goederen of personen over weg, water, spoor of lucht.','Eurostat CBF 2.5.1','A','S',1),
('D16.2','supply_chain','Opslag en magazijnbeheer','Bewaren en beheren van voorraad en materiaal.','Eurostat CBF 2.5.2','A','S',2),
('D16.3','supply_chain','Verpakking','Beschermen en gereedmaken van goederen voor verzending.','Eurostat CBF 2.5.2; Verordening (EU) 2025/40 (PPWR)','A','S',3),
('D16.4','supply_chain','Douane en handelsformaliteiten','Aangifte, classificatie en oorsprong bij grensoverschrijding.','Verordening (EU) nr. 952/2013','A','S',4),
('D16.5','supply_chain','Ketendue diligence','Identificeren en aanpakken van nadelige gevolgen in de keten.','Richtlijn (EU) 2024/1760 art. 5-11','A','S',5),
('D16.6','supply_chain','Retourstromen en afvalbeheer','Terugname, hergebruik en verwerking van materiaal.','Richtlijn 2008/98/EG art. 4','A','S',6),
('D16.7','supply_chain','Vraag- en ketenplanning','Afstemmen van verwachte vraag op beschikbaarheid.','geen EU-bron op dit niveau','C','S',7),
('D16.8','supply_chain','Voorraadbeheer','Bepalen en bewaken van voorraadniveaus.','geen EU-bron op dit niveau','C','S',8),
-- D17 Informatiebeveiliging en privacy
('D17.1','informatiebeveiliging_privacy','Risicoanalyse en informatiebeveiligingsbeleid','Systematisch bepalen van beveiligingsrisicos en het bijbehorende beleid.','Richtlijn (EU) 2022/2555 art. 21(2)(a)','A','K',1),
('D17.2','informatiebeveiliging_privacy','Incidentbehandeling','Voorkomen, detecteren, analyseren en herstellen van incidenten.','Art. 21(2)(b); meldplicht art. 23','A','K',2),
('D17.3','informatiebeveiliging_privacy','Bedrijfscontinuiteit en back-up','Back-upbeheer, uitwijk en crisisbeheer.','Art. 21(2)(c)','A','K',3),
('D17.4','informatiebeveiliging_privacy','Beveiliging van de toeleveringsketen','Beveiligingsaspecten in relaties met directe leveranciers.','Art. 21(2)(d); art. 22','A','K',4),
('D17.5','informatiebeveiliging_privacy','Veilige verwerving, ontwikkeling en onderhoud','Beveiliging in aanschaf, ontwikkeling en kwetsbaarhedenbeheer.','Art. 21(2)(e)','A','K',5),
('D17.6','informatiebeveiliging_privacy','Beoordeling van doeltreffendheid','Toetsen of de beveiligingsmaatregelen werken.','Art. 21(2)(f)','A','K',6),
('D17.7','informatiebeveiliging_privacy','Cyberhygiene en opleiding','Basispraktijken en training, inclusief voor het bestuur.','Art. 21(2)(g); art. 20(2)','A','K',7),
('D17.8','informatiebeveiliging_privacy','Cryptografie en encryptie','Beleid voor versleuteling en sleutelbeheer.','Art. 21(2)(h)','A','K',8),
('D17.9','informatiebeveiliging_privacy','Personeelsbeveiliging, toegangsbeheer en assetbeheer','Wie toegang heeft tot wat, en welke middelen er zijn.','Art. 21(2)(i)','A','K',9),
('D17.10','informatiebeveiliging_privacy','Multifactorauthenticatie en beveiligde communicatie','Sterke authenticatie en beveiligde communicatiekanalen.','Art. 21(2)(j)','A','K',10),
('D17.11','informatiebeveiliging_privacy','Gegevensbescherming: functionaris, beveiliging en effectbeoordeling','Aanstellen van een DPO, beveiliging van verwerking en DPIAs.','AVG art. 32, 35 en 37-39','A','K',11),
('D17.12','informatiebeveiliging_privacy','Datalekmelding','Melden van inbreuken aan toezichthouder en betrokkenen.','AVG art. 33-34','A','K',12)
ON CONFLICT (code) DO UPDATE SET
    discipline_sleutel = EXCLUDED.discipline_sleutel, naam = EXCLUDED.naam,
    definitie = EXCLUDED.definitie, bron = EXCLUDED.bron, status = EXCLUDED.status,
    relevantie = EXCLUDED.relevantie, volgorde = EXCLUDED.volgorde,
    bijgewerkt_op = now();

GRANT SELECT ON kern.subdiscipline TO portal, medewerker_writer, hr_app;
