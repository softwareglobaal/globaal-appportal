-- 030 — de 17 disciplines als centrale entiteit (PLAN.md stap 1; Mehdi 2026-07-04).
--
-- Het Unified Dashboard-principe: niet de firma's zijn de vaste structuur, maar
-- de 17 bedrijfsdisciplines die elke servicefirma nodig heeft. Firma's (±15)
-- zijn de variabele laag erbovenop; een firma zonder invulling van een
-- discipline laat hem leeg, maar het raamwerk verandert nooit (ziekenhuis-
-- model: je ziet wat er ontbreekt). De lijst is door Mehdi vastgepind — de
-- sleutels zijn stabiel (komen straks in FK's, code en views), namen mogen
-- later verfijnd worden. Tool→discipline-mapping volgt in stap 2 (migratie
-- 031); dan krijgen deze rijen hun eerste inkomende verwijzingen.

CREATE TABLE kern.discipline (
    sleutel         text PRIMARY KEY,
    naam            text NOT NULL,
    volgorde        int  NOT NULL UNIQUE,   -- de vaste 1..17 uit de lijst
    bijgewerkt_door text NOT NULL DEFAULT '',
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now()
);

-- Kern-wijzigingen zijn auditeerbaar (migratie 023).
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE
    ON kern.discipline
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();

INSERT INTO kern.discipline (sleutel, naam, volgorde) VALUES
    ('hr_recruitment',              'HR & rekrutering',                  1),
    ('sales_bizdev',                'Sales & business development',      2),
    ('marketing_communicatie',      'Marketing & communicatie',          3),
    ('finance_accounting',          'Finance & accounting',              4),
    ('operations_projectmanagement','Operations & projectmanagement',    5),
    ('legal_compliance',            'Legal & compliance',                6),
    ('customer_service',            'Customer service & support',        7),
    ('it_systemen',                 'IT & systemen',                     8),
    ('procurement_vendormanagement','Procurement & vendor management',   9),
    ('quality_assurance',           'Quality assurance',                10),
    ('risk_management',             'Risk management',                  11),
    ('strategische_planning',       'Strategische planning',            12),
    ('data_analytics',              'Data & analytics',                 13),
    ('facilities_administratie',    'Facilities & administratie',       14),
    ('research_development',        'Research & development',           15),
    ('supply_chain',                'Supply chain management',          16),
    ('partnerships_vendorrelaties', 'Partnerships & vendor relations',  17);

-- Lezen mag elke app (views per discipline komen overal terug); namen
-- bijwerken loopt later via de beheer-UI (medewerker_writer).
GRANT SELECT ON kern.discipline TO portal, communicatie, kosten, vermogen, draaiboek;
GRANT SELECT, UPDATE ON kern.discipline TO medewerker_writer;

-- Woordenboek: het begrip zelf + één definitie per discipline (zelfde sleutel
-- als de discipline, zodat UI's hem rechtstreeks kunnen opzoeken).
INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('discipline', 'Discipline',
     'Vast bedrijfsdomein uit het 17-disciplines-raamwerk. Elke servicefirma heeft dezelfde disciplines; een firma die er een niet nodig heeft laat hem leeg, maar het raamwerk verandert nooit — zo zie je meteen wat ontbreekt.'),
    ('hr_recruitment', 'HR & rekrutering',
     'Werving, contracten, verlof, evaluaties en alles rond het personeelsbestand.'),
    ('sales_bizdev', 'Sales & business development',
     'Verkoop en commerciële groei: leads, offertes, deals en de verkooppijplijn.'),
    ('marketing_communicatie', 'Marketing & communicatie',
     'Zichtbaarheid en boodschap: campagnes, website, sociale media en externe communicatie.'),
    ('finance_accounting', 'Finance & accounting',
     'Boekhouding en financieel beheer: facturatie, kosten, budgetten en rapportering.'),
    ('operations_projectmanagement', 'Operations & projectmanagement',
     'De uitvoering van het werk: projecten, planning, capaciteit en voortgang.'),
    ('legal_compliance', 'Legal & compliance',
     'Contracten, vergunningen, regelgeving en juridische risico''s.'),
    ('customer_service', 'Customer service & support',
     'Klantenservice: vragen, klachten, bereikbaarheid en opvolging.'),
    ('it_systemen', 'IT & systemen',
     'Systemen, software, accounts, netwerk en beveiliging.'),
    ('procurement_vendormanagement', 'Procurement & vendor management',
     'Inkoop en leveranciersbeheer: bestellingen, contracten en prijsafspraken.'),
    ('quality_assurance', 'Quality assurance',
     'Kwaliteitsbewaking: normen, controles en verbeteracties.'),
    ('risk_management', 'Risk management',
     'Risico''s identificeren, beoordelen en beheersen — van verzekering tot continuïteit.'),
    ('strategische_planning', 'Strategische planning',
     'Richting en doelen op lange termijn, en de opvolging ervan.'),
    ('data_analytics', 'Data & analytics',
     'Data verzamelen, koppelen en analyseren als basis voor beslissingen.'),
    ('facilities_administratie', 'Facilities & administratie',
     'Gebouwen, werkplekken en de dagelijkse administratie.'),
    ('research_development', 'Research & development',
     'Onderzoek en ontwikkeling van nieuwe diensten, methodes of producten.'),
    ('supply_chain', 'Supply chain management',
     'De keten van toelevering: goederen, materialen en logistiek.'),
    ('partnerships_vendorrelaties', 'Partnerships & vendor relations',
     'Partnerschappen en duurzame leveranciersrelaties.')
ON CONFLICT (sleutel) DO NOTHING;
