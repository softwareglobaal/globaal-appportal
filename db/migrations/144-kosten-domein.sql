-- 144: Domeinregister. Alle domeinen van de groep staan op één one.com-account
-- (Mehdi) en de facturen komen op info@h-architects.be binnen; nergens stond
-- welk domein van welke firma is en wat het per jaar kost. Dit register is
-- gevuld uit de one.com-mails in die mailbox (uitgelezen 8 september 2026).
-- firma = NULL betekent: nog te bevestigen door een mens.

CREATE TABLE IF NOT EXISTS kosten.domein (
    domein          text PRIMARY KEY,
    firma           text,                          -- naam zoals in kosten.firma; NULL = te bevestigen
    leverancier     text NOT NULL DEFAULT 'one.com',
    inhoud          text NOT NULL DEFAULT '',      -- wat erin zit: domein, mail, hosting, dns
    jaarbedrag      numeric(10,2),                 -- laatst bekende jaarbedrag
    valuta          text NOT NULL DEFAULT 'EUR',
    verlengt_op     date,                          -- start van de volgende periode
    incasso_op      date,                          -- one.com int 30 dagen eerder
    factuur_mailbox text NOT NULL DEFAULT 'info@h-architects.be',
    laatste_factuur text,                          -- factuurnummer of order
    doorsturen_naar text,                          -- mailbox van de firma die de factuur moet krijgen
    status          text NOT NULL DEFAULT 'actief', -- actief | verlopen | opgezegd
    opmerking       text NOT NULL DEFAULT '',
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE kosten.domein IS
    'Domeinen van de groep met eigenaar-firma en jaarbedrag; bron: one.com-mails op info@h-architects.be.';

INSERT INTO kosten.domein (domein, firma, inhoud, jaarbedrag, verlengt_op, incasso_op, laatste_factuur, doorsturen_naar, status, opmerking) VALUES
  ('elevaitnv.com',        'Elevait',           'domein + e-mail',        73.87, DATE '2027-07-08', DATE '2027-06-08', 'order 8 jul 2026',   'admin@elevaitnv.com', 'actief',   'jaar 1 met korting EUR 19,08; factuuradres H-Architects'),
  ('hdssr.com',            'HDS',               'domein + hosting',      169.75, DATE '2026-10-12', DATE '2026-09-12', 'factuur 45009806',   NULL,                  'actief',   ''),
  ('contrax.be',           'Contrax',           'domein + hosting',      193.87, DATE '2026-10-10', DATE '2026-09-10', 'factuur 44989207',   NULL,                  'actief',   ''),
  ('highdesignstudio.in',  NULL,                'domein + hosting',       63.87, DATE '2026-09-14', DATE '2026-08-15', 'factuur 44760378',   NULL,                  'actief',   'firma te bevestigen (HDS?)'),
  ('epbvlaanderen.be',     NULL,                'domein + hosting',       40.27, DATE '2026-08-22', DATE '2026-07-23', 'factuur 44562791',   NULL,                  'actief',   'firma te bevestigen (H-Architects / EPB?)'),
  ('energie-efficient.be', 'Energie Efficient', 'domein + hosting + extra mailopslag', 175.75, DATE '2026-07-28', DATE '2026-06-28', 'factuur 44342388', NULL, 'actief', ''),
  ('medianselections.com', NULL,                'domein + hosting',      217.75, DATE '2026-06-05', DATE '2026-05-06', 'factuur 43841213',   NULL,                  'actief',   'firma te bevestigen (Median?)'),
  ('unabo.be',             'UNABO',             'domein + hosting + extra mailopslag (bundel, "en meer")', 445.62, DATE '2026-01-19', DATE '2025-12-20', 'facturen 42615674/42615675', NULL, 'actief', 'bundelfactuur; welke domeinen erin zitten staat in de PDF'),
  ('orvantisnv.com',       NULL,                'domein + dns',           25.99, DATE '2027-06-10', DATE '2027-05-11', 'order 10 jun 2026',  NULL,                  'actief',   'jaar 1 met korting EUR 10,99; firma te bevestigen'),
  ('regulariseren.be',     'H-Architects',      'domein + dns',           25.99, DATE '2027-08-03', DATE '2027-07-04', 'order 3 aug 2026',   NULL,                  'actief',   'jaar 1 met korting EUR 1,99; regularisatie-site'),
  ('mijnregularisatie.be', 'H-Architects',      'domein + dns',           25.99, DATE '2027-08-03', DATE '2027-07-04', 'order 3 aug 2026',   NULL,                  'actief',   'jaar 1 met korting EUR 1,99; regularisatie-site'),
  ('techpointhds.com',     'HDS',               'domein',                  NULL, NULL,              NULL,              NULL,                 NULL,                  'verlopen', 'verlopen op 7 feb 2026 volgens one.com'),
  ('h-architects.be',      'H-Architects',      'domein',                  NULL, NULL,              NULL,              NULL,                 NULL,                  'actief',   'geen one.com-factuur gevonden; de "vernieuwing vereist"-mails van derden zijn spam')
ON CONFLICT (domein) DO NOTHING;
