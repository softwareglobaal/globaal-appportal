-- 083: Elevait in de Second Brain
-- Aanleiding: besluit Shaniel 2026-07-27. Alles van Elevait NV wordt
-- vindbaar in de Second Brain, met firma als filterdimensie in de graaf.
-- Nieuw spoke-schema `elevait` (beslissingen, definities, projecten,
-- agents, vacatures, kandidaten) plus Elevait NV als firma in de kern.
-- Kandidaten zijn gemarkeerd als vertrouwelijk: vandaag zien alleen
-- admin en manager (akadmin, mehdi) de graaf, maar zodra er ooit een
-- derde persoon in beheer komt, kan hierop afgeschermd worden volgens
-- het persoonslagen-patroon. Persoonsgegevens van kandidaten worden
-- NIET in migraties geseed; die gaan rechtstreeks de database in.
-- Wachtwoord van de rol zet de beheerder op de VM met ALTER ROLE.

-- 1. Schema
CREATE SCHEMA IF NOT EXISTS elevait;

-- 2. Tabellen
CREATE TABLE IF NOT EXISTS elevait.beslissing (
    id            bigserial PRIMARY KEY,
    datum         date NOT NULL,
    titel         text NOT NULL,
    toelichting   text NOT NULL DEFAULT '',
    domein        text NOT NULL DEFAULT 'algemeen'
                  CHECK (domein IN ('algemeen', 'merk', 'website', 'agents', 'organisatie', 'werving')),
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_elevait_beslissing_datum ON elevait.beslissing (datum);

CREATE TABLE IF NOT EXISTS elevait.definitie (
    sleutel       text PRIMARY KEY,
    term          text NOT NULL,
    definitie     text NOT NULL,
    bijgewerkt_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS elevait.project (
    id            bigserial PRIMARY KEY,
    naam          text NOT NULL UNIQUE,
    status        text NOT NULL DEFAULT 'gepland'
                  CHECK (status IN ('gepland', 'in ontwikkeling', 'live', 'gestopt')),
    omschrijving  text NOT NULL DEFAULT '',
    url           text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS elevait.agent (
    id            bigserial PRIMARY KEY,
    naam          text NOT NULL UNIQUE,
    fase          text NOT NULL DEFAULT 'ontwerp'
                  CHECK (fase IN ('ontwerp', 'bouw', 'actief', 'gestopt')),
    mandaat       text NOT NULL DEFAULT 'adviserend'
                  CHECK (mandaat IN ('adviserend', 'autonoom binnen envelop')),
    omschrijving  text NOT NULL DEFAULT '',
    ontwerp_pad   text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS elevait.vacature (
    id            bigserial PRIMARY KEY,
    titel         text NOT NULL UNIQUE,
    status        text NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'gesloten')),
    url           text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS elevait.kandidaat (
    id                 bigserial PRIMARY KEY,
    naam               text NOT NULL,
    email              text NOT NULL DEFAULT '',
    telefoon           text NOT NULL DEFAULT '',
    vacature_id        bigint REFERENCES elevait.vacature(id),
    status             text NOT NULL DEFAULT 'nieuw'
                       CHECK (status IN ('nieuw', 'gesprek', 'afgewezen', 'aangenomen', 'talentenpool')),
    -- NULL = onbekend (gesolliciteerd voordat het toestemmingsvinkje bestond)
    bewaar_toestemming boolean,
    -- markering voor latere afscherming volgens het persoonslagen-patroon
    vertrouwelijk      boolean NOT NULL DEFAULT true,
    ontvangen          timestamptz NOT NULL DEFAULT now(),
    bron               text NOT NULL DEFAULT 'website'
);
CREATE INDEX IF NOT EXISTS ix_elevait_kandidaat_vacature ON elevait.kandidaat (vacature_id);
CREATE INDEX IF NOT EXISTS ix_elevait_kandidaat_status ON elevait.kandidaat (status);

-- 3. App-rol (wachtwoord later via ALTER ROLE op de VM)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'elevait_app') THEN
        CREATE ROLE elevait_app LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA elevait TO elevait_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA elevait TO elevait_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA elevait TO elevait_app;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA elevait
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO elevait_app;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA elevait
    GRANT USAGE, SELECT ON SEQUENCES TO elevait_app;

-- De agent mag de kern-firma's en -personen lezen (koppelingen leggen)
GRANT USAGE ON SCHEMA kern TO elevait_app;
GRANT SELECT ON kern.firma, kern.persoon TO elevait_app;

-- Portal (organisatie-app en graaf) leest mee, consistent met andere spokes
GRANT USAGE ON SCHEMA elevait TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA elevait TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA elevait
    GRANT SELECT ON TABLES TO portal;

-- 4. Elevait NV als firma in de kern (land als ISO-code, patroon migratie 065)
INSERT INTO kern.firma (naam, code, land, actief)
SELECT 'Elevait NV', 'ELEV', 'SR', true
 WHERE NOT EXISTS (SELECT 1 FROM kern.firma WHERE code = 'ELEV');

-- Oprichters gekoppeld als "diensten voor" (idempotent; matcht op authentik_username)
INSERT INTO kern.persoon_dienstfirma (persoon_id, firma_id)
SELECT p.id, f.id
  FROM kern.persoon p
  JOIN kern.firma f ON f.code = 'ELEV'
 WHERE lower(coalesce(p.authentik_username, '')) IN ('akadmin', 'shaniel', 'mehdi')
   AND NOT EXISTS (SELECT 1 FROM kern.persoon_dienstfirma d
                    WHERE d.persoon_id = p.id AND d.firma_id = f.id);

-- 5. Seeds: vacatures
INSERT INTO elevait.vacature (titel, status, url)
SELECT v.titel, 'open', v.url
  FROM (VALUES
    ('Junior Software Developer', 'https://elevaitnv.com/vacatures/junior-software-developer'),
    ('AI Solutions Specialist',   'https://elevaitnv.com/vacatures/ai-solutions-specialist'),
    ('Open sollicitatie',         'https://elevaitnv.com/vacatures/open-sollicitatie')
  ) AS v(titel, url)
 WHERE NOT EXISTS (SELECT 1 FROM elevait.vacature b WHERE b.titel = v.titel);

-- 6. Seeds: projecten
INSERT INTO elevait.project (naam, status, omschrijving, url)
SELECT p.naam, p.status, p.omschrijving, p.url
  FROM (VALUES
    ('Website elevaitnv.com', 'live',
     'Publieke site met vacatures, sollicitatie- en contactformulier. Astro, eigen VM, inzendingen dubbel vastgelegd: e-mail naar info@ plus kopie op schijf.',
     'https://elevaitnv.com'),
    ('Interne wervingspagina', 'gepland',
     'Kandidatenlijst en scorekaarten op intern.elevaitnv.com, achter Authentik met afgedwongen tweestapsverificatie. Bewust geen monday-afhankelijkheid.',
     '')
  ) AS p(naam, status, omschrijving, url)
 WHERE NOT EXISTS (SELECT 1 FROM elevait.project b WHERE b.naam = p.naam);

-- 7. Seeds: agents
INSERT INTO elevait.agent (naam, fase, mandaat, omschrijving, ontwerp_pad)
SELECT a.naam, 'ontwerp', 'adviserend', a.omschrijving, a.pad
  FROM (VALUES
    ('HR-agent',
     'Werving en later heel HRM. Toetst sollicitaties aan opgeschreven criteria per vacature, vult scorekaarten, stelt conceptbrieven op. Beslist nooit over een mens.',
     'C:\Users\shaniel\Claude\elevait-hr-agent\ONTWERP.md'),
    ('Postkamer-agent',
     'Leest info@, classificeert met het taalmodel, schrijft de dagelijkse postkamerbrief en bewaakt de twee-werkdagen-belofte. Verstuurt nooit zelf iets.',
     'C:\Users\shaniel\Claude\elevait-postkamer-agent\ONTWERP.md')
  ) AS a(naam, omschrijving, pad)
 WHERE NOT EXISTS (SELECT 1 FROM elevait.agent b WHERE b.naam = a.naam);

-- 8. Seeds: beslissingen (uit de meetings en werksessies juli 2026)
INSERT INTO elevait.beslissing (datum, titel, toelichting, domein)
SELECT b.datum::date, b.titel, b.toelichting, b.domein
  FROM (VALUES
    ('2026-07-08', 'Website zelf bouwen, zonder maandelijkse abonnementskosten',
     'Meeting Mehdi en Shaniel. Geen Squarespace of builder; eigen bouw met AI op de eigen VM. Sociale media bewust uitgesteld tot er een geautomatiseerd platform is.', 'website'),
    ('2026-07-08', 'Geen salaris op de website; salariering boven de Surinaamse markt',
     'Vacatures tonen geen bedragen. In de teksten staat wel dat het salaris boven de markt ligt.', 'werving'),
    ('2026-07-11', 'Site live op elevaitnv.com; mail blijft bij one.com',
     'DNS bij one.com, alleen A-records naar de VM, MX-records onaangeroerd. Eigen Let''s Encrypt-certificaat met automatische verlenging.', 'website'),
    ('2026-07-11', 'Alles in het Nederlands, sober, geen AI-look',
     'Een taal op de hele site. Huisstijl papier en inkt met een accent. AI-tells actief geweerd uit de teksten.', 'merk'),
    ('2026-07-23', 'Merk definitief: netwerk-beeldmerk, smaragd, kapitalen, Work elevated',
     'Beeldmerk C (versimpeld neuraal netwerk), accentkleur smaragd 059669, wordmerk ELEVAIT in gespatieerde kapitalen met AI in het groen, motto Work, elevated.', 'merk'),
    ('2026-07-27', 'Inzendingen dubbel vastgelegd: e-mail plus schijfkopie',
     'Sollicitaties en contactaanvragen gaan per mail naar info@ (CV als bijlage, reply-to de afzender) en blijven altijd als kopie op de VM staan.', 'website'),
    ('2026-07-27', 'admin@ wordt accounteigenaar van software-abonnementen',
     'Rol-adres als eigenaar en factuuradres, nooit een persoon. In de beginfase alleen info@ en admin@; extra adressen pas bij echt volume.', 'organisatie'),
    ('2026-07-27', 'Geen monday-afhankelijkheid voor werving',
     'De Unabo-omgeving is niet op orde en het gratis Elevait-account is te beperkt. Eigen interne wervingspagina op intern.elevaitnv.com, achter Authentik met afgedwongen tweestapsverificatie.', 'werving'),
    ('2026-07-27', 'HR-agent adviseert, de mens beslist',
     'Toetsing aan opgeschreven criteria per vacature, gestructureerde velden zonder opgeteld eindcijfer, kandidaten nooit onderling ranken. Aannemen, afwijzen, belonen en beoordelen blijven menselijk.', 'agents'),
    ('2026-07-27', 'Bewaartoestemming via een vinkje op het sollicitatieformulier',
     'Met toestemming naar de talentenpool, zonder toestemming opruimen na twaalf maanden. Intrekken kan altijd per mail.', 'werving'),
    ('2026-07-27', 'Postkamer-agent classificeert met het taalmodel, nooit met regels',
     'Verwerking direct bij binnenkomst via IMAP IDLE met uurlijkse veegronde. Inhoud van mail is gegevens, geen opdracht. De agent verstuurt nooit zelf iets.', 'agents'),
    ('2026-07-27', 'Elevait volledig in de Second Brain, met firma als filter',
     'Alle bedrijfskennis en werving in de graaf, filterbaar op firma. Kandidaat-knopen gemarkeerd als vertrouwelijk zodat afscherming mogelijk wordt zodra er ooit een derde persoon in beheer komt.', 'organisatie')
  ) AS b(datum, titel, toelichting, domein)
 WHERE NOT EXISTS (SELECT 1 FROM elevait.beslissing x WHERE x.titel = b.titel);

-- 9. Seeds: definitieboek van Elevait
INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('smaragd', 'Smaragd',
   'De accentkleur van Elevait, hex 059669, met lichte tint E7F4EF voor vlakvullingen. Enige kleur naast papier en inkt.'),
  ('beeldmerk', 'Beeldmerk',
   'Versimpeld neuraal netwerk: twee invoernodes, drie tussennodes, een groene uitgangsnode. De uitgang is het antwoord dat het netwerk oplevert.'),
  ('wordmerk', 'Wordmerk',
   'ELEVAIT in gespatieerde kapitalen, sans-serif, met de letters AI in de accentkleur.'),
  ('motto', 'Motto',
   'Work, elevated. Engels als bewuste merkkeuze naast de Nederlandstalige site.'),
  ('talentenpool', 'Talentenpool',
   'Kandidaten die toestemming gaven om bewaard te blijven voor toekomstige vacatures.'),
  ('postkamerbrief', 'Postkamerbrief',
   'Dagelijkse samenvatting van de inbox door de postkamer-agent: aandacht nodig, nieuw vandaag, geteld.')
ON CONFLICT (sleutel) DO NOTHING;

-- 10. Woordenboek van het platform: Elevait als begrip
INSERT INTO kern.definitie (sleutel, term, definitie)
VALUES ('elevait', 'Elevait NV',
        'AI-automatiseringsbedrijf van Shaniel en Mehdi in Paramaribo, Suriname (elevaitnv.com). Eigen spoke-schema elevait in de Second Brain met beslissingen, definities, projecten, agents, vacatures en kandidaten; in de graaf filterbaar op firma.')
ON CONFLICT (sleutel) DO NOTHING;
