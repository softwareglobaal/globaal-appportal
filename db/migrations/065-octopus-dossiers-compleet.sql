-- 065 - alle Octopus-dossiers aan firma's gekoppeld (besluit Shaniel
-- 2026-07-14: "het moet completely up to date zijn met wat op Octopus is").
--
-- De productie-sync bracht 13 echte dossiers binnen; alleen H-Invest
-- koppelde automatisch omdat de KBO-nummers op de andere firma's leeg
-- stonden. Drie stappen, alles expliciet op dossier-ID (geen naam-raden,
-- de HA/Harmoniebouw-les):
--   1. KBO-nummers vullen op de bestaande firma's (uit de BTW-nummers
--      van hun eigen Octopus-dossier; alleen waar het veld leeg is).
--   2. Corenbo en ENSTACO aanmaken - de enige twee die nog niet
--      bestonden. (Aanname: eigen firma's van de groep, want hun
--      boekhouding leeft in onze eigen Octopus.)
--   3. kosten.octopus_boekhouding: elk dossier-ID aan zijn firma.
--      High Design Studio koppelt aan de Suriname-variant (HDSS,
--      dossier-BTW SR2000048935); die krijgt bewust geen KBO.

-- 1. KBO's op bestaande firma's (idempotent: alleen lege velden).
UPDATE kern.firma f SET kbo_nummer = v.kbo
  FROM (VALUES
    ('CONT', '1020.661.021'),
    ('ENEF', '1011.824.123'),
    ('HARC', '0646.974.162'),
    ('HARM', '0537.405.239'),
    ('MELO', '0882.824.912'),
    ('QOPP', '0782.356.072'),
    ('TKNB', '0792.656.680'),
    ('UNAB', '1008.337.269'),
    ('ZIDI', '0536.697.832')
  ) AS v(code, kbo)
 WHERE f.code = v.code AND f.kbo_nummer = '';

-- 2. De twee ontbrekende firma's.
INSERT INTO kern.firma (naam, code, land, actief, kbo_nummer)
SELECT v.naam, v.code, 'BE', true, v.kbo
  FROM (VALUES
    ('Corenbo', 'CORE', '0729.561.546'),
    ('ENSTACO', 'ENST', '0889.779.614')
  ) AS v(naam, code, kbo)
 WHERE NOT EXISTS (SELECT 1 FROM kern.firma b WHERE b.code = v.code);

-- 3. Dossier-ID's expliciet op de boekhouding-mapping. Bestaande rijen
--    krijgen hun dossier_id; nieuwe boekhoudingen komen erbij. De
--    firma-lookup loopt op code; ontbreekt een firma (kan alleen in een
--    kale testdatabase), dan wordt die rij overgeslagen i.p.v. te falen.
UPDATE kosten.octopus_boekhouding m SET dossier_id = v.dossier
  FROM (VALUES
    ('Contrax',  181481), ('EE',  164873), ('HA', 114703),
    ('Harmonie', 108893), ('TKN', 130699), ('UNABO', 164872),
    ('Zidi', 110906), ('H-Invest', 111725)
  ) AS v(fc, dossier)
 WHERE m.firma_code = v.fc AND m.dossier_id IS DISTINCT FROM v.dossier;

INSERT INTO kosten.octopus_boekhouding (firma_code, kern_firma_id, dossier_id)
SELECT v.fc, f.id, v.dossier
  FROM (VALUES
    ('Corenbo', 'CORE', 183049),
    ('ENSTACO', 'ENST', 12292),
    ('Melodie', 'MELO', 119559),
    ('Qoppa',   'QOPP', 155569),
    ('HDS',     'HDSS', 181482)
  ) AS v(fc, code, dossier)
  JOIN kern.firma f ON f.code = v.code
ON CONFLICT (firma_code) DO UPDATE SET dossier_id = EXCLUDED.dossier_id;
