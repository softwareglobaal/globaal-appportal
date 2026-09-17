-- 151: Duiding van gesprekken - wie belde waarover, en voor welk bedrijf.
--
-- Aanleiding: opdracht Mehdi 17-09-2026. Migratie 138 leverde de uitgeschreven
-- tekst van opgenomen gesprekken op. Tekst alleen is nog geen antwoord op de
-- vragen die hij stelt: voor welk bedrijf werd er gebeld, kennen we de persoon
-- aan de andere kant, ging het over een prospect of een lopend project, en waar
-- ging het inhoudelijk over. Deze migratie voegt drie dingen toe:
--
--   1. lijn_firma          - welke Xelion-lijn hoort bij welke firma. De lijn
--                            is in de praktijk de afdeling ("UNABO Sales",
--                            "Prospection H-Architects"); de firma erachter
--                            staat nergens hard. Bewust een tabel en geen
--                            regel in code: namen veranderen, code niet.
--   2. contact_herkenning  - het externe nummer opgezocht in Pipedrive. Een
--                            cache per nummer, niet per gesprek: hetzelfde
--                            nummer belt vaker en Pipedrive heeft rate limits.
--   3. gesprek_duiding     - per transcriptie een geduide samenvatting
--                            (onderwerp, soort gesprek, project, vervolgstap)
--                            van de AI, plus de firma die eronder hoort.
--
-- Privacy: de duiding is afgeleid van de letterlijke gesprekstekst en is dus
-- even gevoelig. De app toont hem daarom achter hetzelfde slot als de
-- transcriptie zelf (EDITOR_GROUPS) en de tabel gaat net als
-- gesprek_transcript in de _NOOIT-lijst van de graaf. Verwijderen van de
-- transcriptie wist de duiding mee (ON DELETE CASCADE): de samenvatting is de
-- inhoud van het gesprek in andere woorden, niet iets aparts.
--
-- contact_herkenning is bewust GEEN persoonsdossier: alleen de naam en de
-- organisatie zoals ze al in Pipedrive staan, met een link erheen. Wie meer
-- wil weten, klikt door naar de bron.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Xelion-lijn -> firma
-- ---------------------------------------------------------------------------
-- De spiegeltabel xelion_belvolgorde wordt door de poller telkens opnieuw
-- gevuld; een handmatige kolom daarin zou bij elke ronde sneuvelen. Vandaar een
-- eigen tabel op de lijnnaam, want dat is wat mensen herkennen en wat de
-- tenant-admin van Xelion als waarheid toont.
CREATE TABLE IF NOT EXISTS communicatie.lijn_firma (
    xelion_lijnnaam text PRIMARY KEY,
    firma_id        uuid NOT NULL REFERENCES kern.firma(id) ON DELETE CASCADE,
    bron            text NOT NULL DEFAULT 'handmatig',  -- naampatroon / handmatig
    aangemaakt_op   timestamptz NOT NULL DEFAULT now()
);

-- Eerste vulling op naampatroon, alleen waar de firmanaam letterlijk in de
-- lijnnaam staat. Alles wat daarbuiten valt (Sales Yannick Technics, Median
-- Solutions, Verbraecken & Co, de persoonlijke gsm's) blijft leeg en wacht op
-- een mens: raden welk bedrijf een gesprek toebehoort is erger dan niets weten.
INSERT INTO communicatie.lijn_firma (xelion_lijnnaam, firma_id, bron)
SELECT DISTINCT l.xelion_lijnnaam, f.id, 'naampatroon'
  FROM communicatie.xelion_belvolgorde l
  JOIN (VALUES
         ('%unabo%',              'UNAB'),
         ('%h-architects%',       'HARC'),
         ('%h-a %',               'HARC'),
         ('% h-a%',               'HARC'),
         ('%tkn-buro%',           'TKNB'),
         ('%harmoniebouw%',       'HARM'),
         ('%energie efficient%',  'ENEF'),
         ('%qoppa%',              'QOPP'),
         ('%contrax%',            'CONT')
       ) AS p(patroon, code) ON lower(l.xelion_lijnnaam) LIKE p.patroon
  JOIN kern.firma f ON f.code = p.code
 WHERE l.xelion_lijnnaam <> ''
ON CONFLICT (xelion_lijnnaam) DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.lijn_firma TO communicatie;

-- ---------------------------------------------------------------------------
-- 2. Nummerherkenning tegen Pipedrive
-- ---------------------------------------------------------------------------
-- Sleutel is het canonieke nummer (functie uit migratie 041), zodat
-- +32 472 95 88 54 en 0472/95.88.54 dezelfde rij zijn. Een rij zonder treffer
-- (bron = 'geen') is net zo goed een antwoord en wordt bewaard: anders blijft
-- de poller elke ronde dezelfde onbekende nummers opnieuw opzoeken.
CREATE TABLE IF NOT EXISTS communicatie.contact_herkenning (
    genormaliseerd text PRIMARY KEY,
    bron           text NOT NULL DEFAULT 'geen'
                   CHECK (bron IN ('pipedrive', 'register', 'geen')),
    naam           text NOT NULL DEFAULT '',
    organisatie    text NOT NULL DEFAULT '',
    administratie  text NOT NULL DEFAULT '',   -- welke Pipedrive-administratie
    url            text NOT NULL DEFAULT '',   -- deep-link naar het contact
    deal           text NOT NULL DEFAULT '',   -- open deal, als die er is
    pogingen       integer NOT NULL DEFAULT 0,
    fout           text NOT NULL DEFAULT '',
    gezocht_op     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_contact_herkenning_bron
    ON communicatie.contact_herkenning (bron);

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.contact_herkenning TO communicatie;

-- ---------------------------------------------------------------------------
-- 3. Duiding per gesprek
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS communicatie.gesprek_duiding (
    oid             text PRIMARY KEY
                    REFERENCES communicatie.gesprek_transcript(oid) ON DELETE CASCADE,
    status          text NOT NULL DEFAULT 'wachtend'
                    CHECK (status IN ('wachtend', 'klaar', 'mislukt', 'overgeslagen')),
    -- Context, afgeleid en niet door de AI bedacht.
    firma_id        uuid REFERENCES kern.firma(id) ON DELETE SET NULL,
    firma_bron      text NOT NULL DEFAULT ''
                    CHECK (firma_bron IN ('', 'nummer', 'lijn')),
    -- Duiding door de AI.
    soort           text NOT NULL DEFAULT ''
                    CHECK (soort IN ('', 'prospect', 'klant', 'leverancier',
                                     'intern', 'sollicitatie', 'overig')),
    onderwerp       text NOT NULL DEFAULT '',   -- één regel, de kapstok
    samenvatting    text NOT NULL DEFAULT '',   -- enkele zinnen
    project         text NOT NULL DEFAULT '',   -- projectnaam of -nummer, als genoemd
    vervolgstap     text NOT NULL DEFAULT '',   -- wat er afgesproken is
    ai_model        text NOT NULL DEFAULT '',
    pogingen        integer NOT NULL DEFAULT 0,
    fout            text NOT NULL DEFAULT '',
    aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
    klaar_op        timestamptz,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now()
);

-- De werkvoorraad van de duiding-poller.
CREATE INDEX IF NOT EXISTS ix_gesprek_duiding_werk
    ON communicatie.gesprek_duiding (aangemaakt_op)
    WHERE status = 'wachtend';
CREATE INDEX IF NOT EXISTS ix_gesprek_duiding_firma
    ON communicatie.gesprek_duiding (firma_id);
CREATE INDEX IF NOT EXISTS ix_gesprek_duiding_soort
    ON communicatie.gesprek_duiding (soort) WHERE soort <> '';

-- Status van de twee nieuwe pollers, op dezelfde statusrij als de andere.
ALTER TABLE communicatie.xelion_sync
    ADD COLUMN IF NOT EXISTS duiding_laatste_run timestamptz,
    ADD COLUMN IF NOT EXISTS duiding_fout        text,
    ADD COLUMN IF NOT EXISTS contact_laatste_run timestamptz,
    ADD COLUMN IF NOT EXISTS contact_fout        text;

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.gesprek_duiding TO communicatie;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
  ('gesprek_duiding', 'Duiding',
   'De geduide samenvatting van een uitgeschreven telefoongesprek: waar het over ging, of het een prospect, klant, leverancier of intern gesprek was, welk project genoemd werd en wat er is afgesproken. De duiding wordt door de AI gemaakt op basis van de transcriptie en is even afgeschermd als die transcriptie. Verdwijnt de transcriptie, dan verdwijnt de duiding mee.'),
  ('lijn_firma', 'Lijn-firma',
   'Welke firma hoort bij een telefoonlijn van de centrale. De lijnnaam in Xelion zegt in de praktijk de afdeling ("UNABO Sales"); deze koppeling maakt er een firma van, zodat gesprekken per bedrijf te tellen zijn. Leeg betekent: nog niet toegewezen, niet geraden.'),
  ('contact_herkenning', 'Contactherkenning',
   'Het resultaat van het opzoeken van een extern telefoonnummer in Pipedrive: naam, organisatie, de administratie waarin het contact staat en een link erheen. Per nummer bewaard, niet per gesprek. Geen treffer is ook een resultaat en wordt bewaard, zodat hetzelfde nummer niet elke ronde opnieuw wordt opgezocht.')
ON CONFLICT (sleutel) DO NOTHING;

COMMIT;
