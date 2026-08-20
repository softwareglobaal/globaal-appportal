-- 121: intercompany - factuurnummerreeksen per firma.
--
-- Amy geeft de factuurnummers zelf uit, elke firma heeft een eigen doorlopende
-- reeks (bevestigd 20-08-2026). Zij vertrekt, dus die reeksen moeten ergens
-- staan in plaats van in haar hoofd.
--
-- Uit de facturatie-Excel van 2026 blijkt dat alle vijf de reeksen dezelfde
-- vorm hebben, alleen anders geschreven:
--
--   voorvoegsel + jaar + scheiding + volgnummer van twee cijfers
--
--   'HA' + 2026 + '-' + '05'  ->  HA2026-05
--   'EE ' + 2026 + ''  + '05' ->  EE 202605
--
-- Let op: het getal achter het jaar is een VOLGNUMMER en geen maand. EE 202604
-- is de vierde factuur van 2026 en slaat op juni, niet op april. Wie dat als
-- maand leest, leest de helft van het jaar verkeerd.
--
-- Een creditnota verbruikt geen nummer: HA2026-04 werd gecrediteerd en de
-- volgende factuur is gewoon HA2026-05.
--
-- Alleen de vijf firma's waarvoor Amy werkelijk factureert krijgen een reeks.
-- Dat is meteen de afbakening van haar werk: Contrax, Harmonie Bouw, Qoppa,
-- Melodie en ENSTACO hebben wel HDS-boekingen maar horen niet bij deze stroom.

CREATE TABLE IF NOT EXISTS intercompany.reeks (
    dossier_id     integer PRIMARY KEY
                   REFERENCES intercompany.firma(dossier_id) ON DELETE CASCADE,
    voorvoegsel    text NOT NULL,
    scheiding      text NOT NULL DEFAULT '',
    cijfers        smallint NOT NULL DEFAULT 2,
    jaar           smallint NOT NULL,
    laatste_nummer smallint NOT NULL DEFAULT 0,
    bron           text NOT NULL DEFAULT '',
    gewijzigd_op   timestamptz NOT NULL DEFAULT now(),
    gewijzigd_door text NOT NULL DEFAULT ''
);

INSERT INTO intercompany.reeks
    (dossier_id, voorvoegsel, scheiding, jaar, laatste_nummer, bron) VALUES
    (114703, 'HA',  '-', 2026, 5, 'Excel 2026, laatste HA2026-05'),
    (164873, 'EE ', '',  2026, 5, 'Excel 2026, laatste EE 202605'),
    (130699, 'TO ', '',  2026, 4, 'Excel 2026, laatste TO 202604'),
    (164872, 'UO ', '',  2026, 3, 'Excel 2026, laatste UO 202603'),
    (111725, 'HI',  '-', 2026, 2, 'Excel 2026, laatste HI2026-02')
ON CONFLICT (dossier_id) DO NOTHING;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('intercompany.factuurnummer', 'factuurnummer intercompany',
     'Voorvoegsel per firma, gevolgd door het jaar en een doorlopend '
     'volgnummer van twee cijfers. Het getal achter het jaar is een '
     'volgnummer en GEEN maand: EE 202604 is de vierde factuur van 2026 en '
     'slaat op juni. Een creditnota verbruikt geen nummer.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
