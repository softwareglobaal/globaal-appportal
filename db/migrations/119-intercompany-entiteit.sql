-- 119: intercompany - vier dossiers erbij, en de tegenpartij krijgt een firma.
--
-- Twee dingen die uit de eerste vulling en uit de Excel van HDS bleken
-- (19-08-2026):
--
-- 1. HDS komt in TIEN Octopus-dossiers voor als leverancier, niet in zes.
--    Migratie 118 zaaide de zes dossiers uit migratie 102; ENSTACO, H-Invest,
--    Melodie en Qoppa ontbraken. H-Invest weegt het zwaarst: in de Excel van
--    2026 staat daar 36.000 euro aan facturen op, de op een na grootste post,
--    en die viel dus volledig buiten beeld.
--
-- 2. "HIGH DESIGN STUDIO PVT. LTD." is NIET een dubbele fiche van de
--    Surinaamse N.V. maar een andere firma: de Indiase vestiging.
--    `kern.firma` wist dat allang (HDSI naast HDSS). Het bewijs sluit erop
--    aan: de PVT.-LTD.-boekingen komen in de Surinaamse facturatie-Excel
--    nergens voor, terwijl elke N.V.-factuur daar wel exact in staat.
--    Migratie 118 hield dat nog open ("twee entiteiten of een dubbele fiche");
--    dat is hiermee beslist.
--
-- Daarom krijgt tegenpartij een verwijzing naar kern.firma. Dan is een saldo
-- per entiteit te maken in plaats van per relatienummer, en valt het op als een
-- fiche bij de verkeerde firma hangt.
--
-- Bewust NIET in de graaf, op dezelfde grond als migratie 102 en 118: deze
-- verwijzing zegt "welke relatiefiche in welk dossier hoort bij welke firma".
-- Dat is boekhoudkundig leidingwerk tussen twee knopen die de graaf al kent en
-- al met elkaar verbindt via de firma-laag (kosten.octopus_boekhouding,
-- migratie 059). Een extra knoop zou de graaf drukker maken zonder iets nieuws
-- te verbinden.

ALTER TABLE intercompany.tegenpartij
    ADD COLUMN IF NOT EXISTS kern_firma_id uuid REFERENCES kern.firma(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_intercompany_tegenpartij_kern
    ON intercompany.tegenpartij (kern_firma_id);

INSERT INTO intercompany.firma (dossier_id, naam) VALUES
    (111725, 'H-Invest'),
    (12292,  'ENSTACO'),
    (119559, 'Melodie'),
    (155569, 'Qoppa')
ON CONFLICT (dossier_id) DO NOTHING;

UPDATE intercompany.firma i
   SET kern_firma_id = f.id
  FROM kern.firma f
 WHERE f.code = CASE i.dossier_id
                    WHEN 111725 THEN 'HINV'
                    WHEN 12292  THEN 'ENST'
                    WHEN 119559 THEN 'MELO'
                    WHEN 155569 THEN 'QOPP'
                END
   AND i.kern_firma_id IS NULL;

-- De fiches koppelen op naam. "PVT. LTD." en "Private Litd" zijn de Indiase
-- vestiging, al het andere de Surinaamse. De app zet dit voortaan bij elke
-- ontdekking, dit is de inhaalslag voor wat er al staat.
UPDATE intercompany.tegenpartij t
   SET kern_firma_id = f.id
  FROM kern.firma f
 WHERE f.code = CASE
                    WHEN lower(t.naam) LIKE '%pvt%'
                      OR lower(t.naam) LIKE '%private%' THEN 'HDSI'
                    ELSE 'HDSS'
                END
   AND t.kern_firma_id IS DISTINCT FROM f.id;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('intercompany.hdss', 'High Design Studio (Suriname)',
     'De Surinaamse vestiging, in Octopus terug te vinden als relatiefiche '
     '"High Design Studio N.V.". Dit is de firma waarvoor de maandelijkse '
     'facturatie-Excel wordt bijgehouden.'),
    ('intercompany.hdsi', 'High Design Studio (India)',
     'De Indiase vestiging, in Octopus terug te vinden als relatiefiche '
     '"HIGH DESIGN STUDIO PVT. LTD." of "Private Litd". Een andere firma dan '
     'de Surinaamse, met een eigen facturatiestroom die niet in de Surinaamse '
     'Excel staat.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
