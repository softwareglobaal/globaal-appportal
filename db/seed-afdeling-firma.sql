-- Lookup-data voor kern: 13 afdelingen + 13 firma's.
-- Idempotent (ON CONFLICT DO NOTHING) — her-draaien voegt niets dubbel toe.
-- Persoonsdata (kern.persoon-seed) staat bewust NIET in de repo.

INSERT INTO kern.afdeling (naam, actief) VALUES
    ('Scanning', true),
    ('Energy', true),
    ('Finance', true),
    ('Office', true),
    ('Engineering', true),
    ('Architecture', true),
    ('HR', true),
    ('Sales', true),
    ('Rendering', true),
    ('Construction', true),
    ('AI & ICT', true),
    ('Management', true),
    ('Safety', true)
ON CONFLICT (naam) DO NOTHING;

INSERT INTO kern.firma (naam, code, land) VALUES
    ('UnaBo',                          'UNAB', 'België'),
    ('Energie Efficiënt',              'ENEF', 'België'),
    ('Build for Future',               'BFUT', 'België'),
    ('Melodie',                        'MELO', 'België'),
    ('H-Architects',                   'HARC', 'België'),
    ('H-Invest',                       'HINV', 'België'),
    ('Qoppa',                          'QOPP', 'België'),
    ('Harmoniebouw',                   'HARM', 'België'),
    ('Zidi Construct',                 'ZIDI', 'België'),
    ('TKN-Buro',                       'TKNB', 'België'),
    ('High Design Studio (India)',     'HDSI', 'India'),
    ('High Design Studio (Suriname)',  'HDSS', 'Suriname'),
    ('Contrax',                        'CONT', 'België')
ON CONFLICT (code) DO NOTHING;
