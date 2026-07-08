-- 059 - expliciete mapping van Octopus-boekhoudingcode naar kern.firma.
--
-- Reparatie op de naam-prefix-match in de graaf (2026-07-08): "HA" matchte
-- aan Harmoniebouw (begint ook met "ha") en "EE" matchte niets (firma heet
-- Energie Efficient, code ENEF). Nooit meer raden: de mapping is data.

CREATE TABLE kosten.octopus_boekhouding (
    firma_code    text PRIMARY KEY,
    kern_firma_id uuid NOT NULL REFERENCES kern.firma(id) ON DELETE CASCADE
);
GRANT SELECT ON kosten.octopus_boekhouding TO portal, communicatie, kosten;

INSERT INTO kosten.octopus_boekhouding (firma_code, kern_firma_id)
SELECT v.fc, f.id
  FROM (VALUES
        ('Contrax',  'CONT'),
        ('EE',       'ENEF'),
        ('H-Invest', 'HINV'),
        ('HA',       'HARC'),
        ('Harmonie', 'HARM'),
        ('TKN',      'TKNB'),
        ('UNABO',    'UNAB'),
        ('Zidi',     'ZIDI')
       ) AS v(fc, code)
  JOIN kern.firma f ON f.code = v.code
ON CONFLICT (firma_code) DO UPDATE SET kern_firma_id = EXCLUDED.kern_firma_id;
