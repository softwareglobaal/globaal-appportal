-- 091: specifieke functietitels per subdiscipline, ter vervanging van de kale
-- ISCO-koppeling uit 089. Aanleiding (Shaniel 28-07): door rechtstreeks aan
-- ISCO-groepen te koppelen kwam dezelfde generieke groep telkens terug
-- (negen keer "Database and Network Professionals n.e.c." in D17). ISCO-08 is
-- van 2008 en te grof als functietitel.
--
-- Model: een eigen, logisch opgebouwde functietitel met een eigen korte
-- Nederlandse beschrijving, geclassificeerd onder een ISCO-08 unit group
-- (kern.rol blijft de ISCO-referentietabel met officiele definities en
-- paginanummers). Zo blijven titels specifiek en verschillend, terwijl de
-- kapstok en de link naar de officiele beschrijving ISCO blijven.
-- kern.subdiscipline_rol (de een-op-een-koppeling) vervalt.

BEGIN;

CREATE TABLE IF NOT EXISTS kern.functie (
    subdiscipline_code text    NOT NULL REFERENCES kern.subdiscipline (code),
    volgorde           integer NOT NULL,
    titel              text    NOT NULL,
    definitie          text    NOT NULL,
    isco_code          text    REFERENCES kern.rol (code),
    PRIMARY KEY (subdiscipline_code, volgorde)
);
COMMENT ON TABLE kern.functie IS
  'Jobs-laag: eigen functietitels per subdiscipline, geclassificeerd onder ISCO-08 (migratie 091).';

DROP TABLE IF EXISTS kern.subdiscipline_rol;

INSERT INTO kern.functie (subdiscipline_code, volgorde, titel, definitie, isco_code) VALUES
('D1.1',  1, 'Recruiter', 'Werft, beoordeelt en begeleidt kandidaten tot en met de aanwerving.', '2423'),
('D1.2',  1, 'Compensation and benefits specialist', 'Bepaalt en onderhoudt loonhuis, voordelen en arbeidsvoorwaarden.', '2423'),
('D1.3',  1, 'Benefits administrator', 'Beheert aansluitingen en dossiers voor sociale zekerheid en verzekeringen.', '4416'),
('D1.4',  1, 'Learning and development specialist', 'Bepaalt opleidingsbehoeften en organiseert opleiding en ontwikkeling.', '2424'),
('D1.5',  1, 'Prevention advisor', 'Beoordeelt arbeidsrisico''s en adviseert over preventie en bescherming.', '2263'),
('D1.5',  2, 'Safety coordinator', 'Voert inspecties uit en volgt veiligheidsmaatregelen op.', '3257'),
('D1.6',  1, 'Labour relations specialist', 'Voert het sociaal overleg en beheert cao- en overlegdossiers.', '2423'),
('D1.7',  1, 'Diversity and inclusion officer', 'Bewaakt gelijke behandeling en een divers personeelsbeleid.', '2423'),
('D1.8',  1, 'Wellbeing and leave coordinator', 'Regelt verlofstelsels, flexibiliteit en welzijnsinitiatieven.', '2423'),
('D1.9',  1, 'Confidential counsellor', 'Eerste aanspreekpunt voor meldingen; begeleidt klacht en herstel.', '2423'),
('D1.10', 1, 'HR administrator', 'Houdt personeelsdossiers, uren en mutaties bij.', '4416'),
('D2.1',  1, 'Sales representative', 'Verkoopt aan klanten en onderhoudt het klantcontact.', '3322'),
('D2.1',  2, 'Channel manager', 'Bouwt en beheert verkoop via agenten en partners.', '1221'),
('D2.2',  1, 'Business developer', 'Opent nieuwe markten, segmenten en klantrelaties.', '1221'),
('D2.3',  1, 'Tender specialist', 'Stelt offertes en aanbestedingsdossiers op en dient ze in.', '3339'),
('D2.5',  1, 'Pricing specialist', 'Bepaalt tarieven, kortingen en commerciele voorwaarden.', '1221'),
('D2.6',  1, 'Sales administrator', 'Verwerkt orders en houdt klant- en verkoopgegevens bij.', '4110'),
('D3.1',  1, 'Advertising specialist', 'Ontwikkelt en plaatst reclame en kiest media.', '2431'),
('D3.2',  1, 'Market researcher', 'Onderzoekt markt, klant en perceptie en rapporteert inzichten.', '2431'),
('D3.3',  1, 'Brand manager', 'Bewaakt merkbelofte, positionering en huisstijl.', '2431'),
('D3.4',  1, 'Digital marketeer', 'Beheert online kanalen, campagnes en toestemmingen.', '2431'),
('D3.5',  1, 'PR and communications officer', 'Verzorgt woordvoering, pers en externe communicatie.', '2432'),
('D4.1',  1, 'Bookkeeper', 'Voert de dagelijkse boekhouding en het grootboek.', '4311'),
('D4.2',  1, 'Financial accountant', 'Stelt de jaarrekening en financiele verslagen op.', '2411'),
('D4.3',  1, 'Reporting specialist', 'Verzorgt het bestuursverslag en de toelichtingen.', '2411'),
('D4.4',  1, 'Audit coordinator', 'Bereidt de externe controle voor en begeleidt de auditor.', '2411'),
('D4.5',  1, 'Treasurer', 'Beheert kaspositie, financiering en bankrelaties.', '1211'),
('D4.6',  1, 'Accounts receivable and payable officer', 'Factureert, int en betaalt en bewaakt termijnen.', '3313'),
('D4.7',  1, 'Tax specialist', 'Verzorgt aangiften en fiscale posities.', '2411'),
('D5.1',  1, 'Operations planner', 'Plant capaciteit, mensen en middelen voor de uitvoering.', '1321'),
('D5.4',  1, 'Outsourcing coordinator', 'Stuurt uitbestede processen en externe leveranciers aan.', '1219'),
('D5.5',  1, 'Operations manager', 'Leidt de dagelijkse productie en dienstverlening.', '1321'),
('D6.1',  1, 'Contract manager', 'Stelt contracten op, beoordeelt ze en bewaakt de looptijd.', '2619'),
('D6.2',  1, 'Corporate counsel', 'Behandelt vennootschapsrecht en bedrijfsjuridische zaken.', '2611'),
('D6.3',  1, 'Compliance officer', 'Bewaakt naleving van wet, regels en intern beleid.', '2619'),
('D6.4',  1, 'Ethics officer', 'Beheert de gedragscode en behandelt integriteitsvragen.', '2619'),
('D6.5',  1, 'Anti-corruption officer', 'Voorkomt en onderzoekt omkoping en belangenconflicten.', '2619'),
('D6.6',  1, 'Whistleblowing case handler', 'Beheert het meldkanaal en beschermt melders.', '2619'),
('D6.7',  1, 'IP counsel', 'Beschermt merken, modellen en octrooien juridisch.', '2619'),
('D6.8',  1, 'Litigation counsel', 'Behandelt geschillen, claims en procedures.', '2611'),
('D6.9',  1, 'Privacy counsel', 'Beoordeelt verwerkingen en adviseert over gegevensbescherming.', '2619'),
('D7.1',  1, 'Helpdesk agent', 'Beantwoordt vragen en meldingen in de eerste lijn.', '4222'),
('D7.2',  1, 'Complaints coordinator', 'Registreert, behandelt en escaleert klachten.', '4229'),
('D7.3',  1, 'Warranty handler', 'Handelt garantie- en conformiteitsdossiers af.', '4229'),
('D7.4',  1, 'Customer information officer', 'Verstrekt wettelijke en praktische klantinformatie.', '4225'),
('D7.5',  1, 'Support technician', 'Biedt technische ondersteuning en nazorg na levering.', '3512'),
('D8.6',  1, 'Software developer', 'Ontwerpt en bouwt software en integraties.', '2512'),
('D8.6',  2, 'Application programmer', 'Programmeert en test applicaties naar specificatie.', '2514'),
('D8.7',  1, 'ICT service manager', 'Stuurt de ICT-dienstverlening en prioriteiten.', '1330'),
('D8.7',  2, 'System administrator', 'Beheert servers, netwerk en werkplekken.', '2522'),
('D9.2',  1, 'Technical buyer', 'Vertaalt behoeften naar specificaties en vraagt aanbiedingen op.', '3323'),
('D9.3',  1, 'Procurement procedure lead', 'Kiest de inkoopmethode en bewaakt het verloop.', '1324'),
('D9.4',  1, 'Supplier qualification officer', 'Toetst geschiktheid en betrouwbaarheid van leveranciers.', '3323'),
('D9.5',  1, 'Bid evaluator', 'Beoordeelt aanbiedingen tegen de criteria.', '1324'),
('D9.6',  1, 'Framework agreement manager', 'Beheert raamovereenkomsten en mini-competities.', '1324'),
('D9.7',  1, 'Contract performance officer', 'Bewaakt levering, wijzigingen en naleving.', '3323'),
('D9.9',  1, 'Supplier relations manager', 'Onderhoudt leveranciersrelaties en betalingsafspraken.', '1324'),
('D9.10', 1, 'Sustainable procurement officer', 'Weegt duurzaamheid en zorgplicht mee in de inkoop.', '1324'),
('D10.10', 1, 'Quality inspector', 'Keurt producten en diensten tegen de eisen.', '3119'),
('D10.10', 2, 'Certification coordinator', 'Begeleidt certificatie- en keuringstrajecten.', '3119'),
('D11.9',  1, 'Internal control officer', 'Ontwerpt en bewaakt interne beheersmaatregelen.', '2421'),
('D11.10', 1, 'Internal auditor', 'Toetst onafhankelijk of de beheersing werkt.', '2411'),
('D11.11', 1, 'Business continuity coordinator', 'Bereidt de organisatie voor op ernstige verstoringen.', '2421'),
('D12.1',  1, 'Strategy officer', 'Werkt strategie uit en bewaakt de uitvoering.', '1120'),
('D12.2',  1, 'Company secretary', 'Ondersteunt bestuur en toezicht en bewaakt de governance.', '2619'),
('D12.3',  1, 'Board reporting officer', 'Verzorgt de informatievoorziening aan het bestuur.', '1213'),
('D12.4',  1, 'Due diligence officer', 'Voert het zorgvuldigheidsproces uit en volgt het op.', '2619'),
('D12.5',  1, 'Reporting control officer', 'Bewaakt de betrouwbaarheid van de verslaggeving.', '2411'),
('D12.6',  1, 'Stakeholder relations officer', 'Organiseert overleg met belanghebbenden.', '2432'),
('D12.7',  1, 'Materiality analyst', 'Bepaalt welke onderwerpen wezenlijk zijn.', '2421'),
('D12.8',  1, 'Sustainability manager', 'Vertaalt duurzaamheidsambities naar beleid en doelen.', '2133'),
('D12.9',  1, 'Sustainability reporting analyst', 'Stelt de duurzaamheidsrapportage op.', '2411'),
('D13.1',  1, 'Data governance officer', 'Belegt eigenaarschap en regels voor gegevens.', '1330'),
('D13.2',  1, 'Data quality steward', 'Bewaakt juistheid en volledigheid van gegevens.', '2521'),
('D13.3',  1, 'Data register administrator', 'Houdt het register van verwerkingen bij.', '2521'),
('D13.6',  1, 'AI governance officer', 'Beheert de verantwoorde inzet van AI-systemen.', '2421'),
('D14.1',  1, 'Workplace coordinator', 'Beheert ruimte, werkplekken en huurzaken.', '1219'),
('D14.2',  1, 'Maintenance technician', 'Onderhoudt gebouw en installaties en herstelt defecten.', '5153'),
('D14.3',  1, 'Cleaning supervisor', 'Organiseert en controleert de schoonmaak.', '5151'),
('D14.4',  1, 'Grounds keeper', 'Onderhoudt terrein en groenvoorziening.', '6113'),
('D14.5',  1, 'Security coordinator', 'Regelt bewaking, toegang en sleutelbeheer.', '5414'),
('D14.6',  1, 'Catering coordinator', 'Verzorgt eten, drinken en ontvangsten.', '1412'),
('D14.7',  1, 'Workplace ICT technician', 'Installeert en onderhoudt werkplekapparatuur.', '3512'),
('D14.8',  1, 'Office logistics clerk', 'Verwerkt post, documenten en interne stromen.', '4415'),
('D14.9',  1, 'Office manager', 'Leidt de kantooradministratie en ondersteuning.', '3341'),
('D14.10', 1, 'Facility manager', 'Voert regie over alle facilitaire diensten.', '1219'),
('D15.1',  1, 'Innovation manager', 'Bepaalt de innovatiekoers en de middelen.', '1223'),
('D15.7',  1, 'Researcher', 'Voert onderzoek uit en rapporteert bevindingen.', '2149'),
('D15.8',  1, 'Design engineer', 'Werkt concepten technisch uit en analyseert ze.', '2149'),
('D15.8',  2, 'Architect', 'Ontwerpt gebouwen en begeleidt de uitwerking.', '2161'),
('D15.10', 1, 'IP portfolio manager', 'Bouwt en beheert de octrooi- en merkenportefeuille.', '2619'),
('D15.11', 1, 'Grants and partnerships officer', 'Regelt subsidies en onderzoekssamenwerking.', '2422'),
('D16.1',  1, 'Transport planner', 'Plant transporten en volgt zendingen op.', '4323'),
('D16.2',  1, 'Warehouse coordinator', 'Beheert magazijn, opslag en goederenontvangst.', '4321'),
('D16.3',  1, 'Packaging coordinator', 'Regelt verpakking en verzendklaar maken.', '4321'),
('D16.4',  1, 'Customs declarant', 'Verzorgt douaneaangiften en handelsdocumenten.', '3331'),
('D16.5',  1, 'Supply chain due diligence officer', 'Beoordeelt en herstelt ketenrisico''s.', '2421'),
('D16.6',  1, 'Waste and returns coordinator', 'Beheert retourstromen en afvalverwerking.', '2133'),
('D17.1',  1, 'Information security officer', 'Draagt het beveiligingsbeleid en de risicoanalyses.', '2529'),
('D17.2',  1, 'Incident response coordinator', 'Detecteert, analyseert en handelt incidenten af.', '2529'),
('D17.3',  1, 'Backup and continuity administrator', 'Beheert back-up, uitwijk en hersteltests.', '2522'),
('D17.5',  1, 'Secure development engineer', 'Bouwt beveiliging in bij verwerving en ontwikkeling.', '2512'),
('D17.6',  1, 'Security assessor', 'Toetst periodiek of de maatregelen werken.', '2529'),
('D17.7',  1, 'Security awareness trainer', 'Traint medewerkers in cyberhygiene.', '2424'),
('D17.8',  1, 'Cryptography administrator', 'Beheert versleuteling en sleutels.', '2529'),
('D17.9',  1, 'Access and asset administrator', 'Beheert toegangsrechten en bedrijfsmiddelen.', '2522'),
('D17.10', 1, 'Authentication administrator', 'Beheert MFA en beveiligde communicatiekanalen.', '2522'),
('D17.11', 1, 'Data protection officer', 'Ziet toe op de bescherming van persoonsgegevens.', '2619')
ON CONFLICT DO NOTHING;

COMMIT;
