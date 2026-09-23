-- 165: De proefset van de transcriptie in het dashboard, niet op een laptop.
--
-- Aanleiding (Mehdi, 23-09-2026): de testtranscripties, de referentie en de
-- opnames stonden als losse bestanden op de Windows-werkplek van Shaniel,
-- terwijl het communicatie-dashboard er al is voor gespreksanalyse. Dat gaf
-- twee waarheden (het dashboard toonde de productie, de proef stond elders),
-- niemand anders kon meekijken of verbeteren, en er stonden klantgesprekken
-- en opnames op een onbeheerde machine. Precies wat we bij Plaud niet wilden.
--
-- Vier tabellen:
--   gesprek_proefset       welke gesprekken de vaste proefset vormen
--   gesprek_proef_variant  per gesprek de uitkomst van elke geteste variant
--   gesprek_referentie     de door een mens verbeterde tekst, de meetlat
--   gesprek_meting         elke meting tegen de referentie, met de uitkomst
--
-- Privacy: dezelfde afscherming als de transcripties zelf (EDITOR_GROUPS in de
-- app) en dezelfde plek in _NOOIT van graaf.py. De opname zelf wordt niet
-- opgeslagen; het dashboard haalt hem bij Xelion als iemand op afspelen drukt.

BEGIN;

CREATE TABLE IF NOT EXISTS communicatie.gesprek_proefset (
    oid           text PRIMARY KEY
                  REFERENCES communicatie.xelion_communicatie(oid) ON DELETE CASCADE,
    reden         text NOT NULL DEFAULT '',   -- waarom dit gesprek erin zit
    toegevoegd_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS communicatie.gesprek_proef_variant (
    oid        text NOT NULL REFERENCES communicatie.gesprek_proefset(oid) ON DELETE CASCADE,
    variant    text NOT NULL,              -- bv. fw:large-v3+woorden+kanalen
    tekst      text NOT NULL DEFAULT '',
    segmenten  jsonb,                       -- [{start, eind, spreker, tekst}]
    seconden   numeric,                     -- rekentijd voor dit gesprek
    gemaakt_op timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (oid, variant)
);

CREATE TABLE IF NOT EXISTS communicatie.gesprek_referentie (
    oid            text PRIMARY KEY
                   REFERENCES communicatie.gesprek_proefset(oid) ON DELETE CASCADE,
    regels         jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{start, partij, tekst}]
    klaar          boolean NOT NULL DEFAULT false,
    concept_uit    text NOT NULL DEFAULT '',  -- variant waaruit het concept kwam
    nagekeken_door text NOT NULL DEFAULT '',
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS communicatie.gesprek_meting (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    gemeten_op timestamptz NOT NULL DEFAULT now(),
    door       text NOT NULL DEFAULT '',
    droog      boolean NOT NULL DEFAULT false,  -- tegen niet-nagekeken referentie
    uitkomst   jsonb NOT NULL                   -- per variant: samen + per gesprek
);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    communicatie.gesprek_proefset, communicatie.gesprek_proef_variant,
    communicatie.gesprek_referentie TO communicatie;
GRANT SELECT, INSERT ON communicatie.gesprek_meting TO communicatie;
GRANT USAGE ON SEQUENCE communicatie.gesprek_meting_id_seq TO communicatie;

-- De vaste proefset van 21-09-2026 (werker/proefset.txt): vijf lijnen, per
-- lijn kort en lang, vijf met en vijf zonder bekende tegenpartij.
INSERT INTO communicatie.gesprek_proefset (oid, reden) VALUES
    ('3949982', 'Sales Yannick Technics, 79s uitgaand, tegenpartij onbekend'),
    ('3966435', 'Sales Yannick Technics, 256s uitgaand, tegenpartij bekend'),
    ('3693014', 'Standard Projects H-A, 102s uitgaand, tegenpartij bekend'),
    ('3928726', 'Standard Projects H-A, 176s uitgaand, tegenpartij onbekend'),
    ('3836372', 'TKN-Buro Algemeen, 52s inkomend, tegenpartij onbekend'),
    ('3685688', 'TKN-Buro Algemeen, 158s inkomend, tegenpartij onbekend'),
    ('4007524', 'UNABO Office, 90s inkomend, tegenpartij onbekend'),
    ('3936828', 'UNABO Office, 123s inkomend, tegenpartij bekend'),
    ('3993003', 'UNABO Sales, 67s uitgaand, tegenpartij bekend'),
    ('3696162', 'UNABO Sales, 117s uitgaand, tegenpartij onbekend')
ON CONFLICT (oid) DO NOTHING;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
  ('gesprek_proefset', 'Proefset',
   'De vaste set gesprekken waarop varianten van de transcriptie getest worden voor er iets in bulk gebeurt. Vast, omdat je anders modellen vergelijkt op verschillend materiaal.'),
  ('gesprek_referentie', 'Referentie',
   'De tekst van een proefgesprek zoals die echt gezegd is, door een mens uitgeluisterd en verbeterd, met bij elke zin de juiste partij. De meetlat waartegen elke variant gemeten wordt. Zolang hij niet als klaar gemarkeerd is, telt hij niet als meting.')
ON CONFLICT (sleutel) DO NOTHING;

COMMIT;
