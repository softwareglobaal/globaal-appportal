-- 159: het domein als eigen ding, met zijn pakket, zijn prijs en zijn firma.
--
-- Aanleiding: kritiekronde 22-09-2026, punten 11 en 5 van de tweede ronde.
-- Het e-mailregister toonde 502 adressen en geen euro. De vraag "wat kost dit"
-- kon de app niet beantwoorden, en de vraag "mag deze postbus weg" werd daardoor
-- op het verkeerde niveau gesteld.
--
-- Wat de facturen laten zien (one.com, nagerekend op 22-09-2026): bij one.com is
-- het AANTAL POSTBUSSEN ONBEPERKT binnen een hostingpakket. Een postbus wissen
-- bespaart dus niets. De kosten zitten per domein: het pakket, de add-ons en de
-- domeinregistratie, samen EUR 1.769,14 per jaar over 17 domeinen. Daarom hangt
-- de prijs hier aan het domein en niet aan het adres; een kolom "kostprijs" op
-- emailadres zou een bedrag suggereren dat niet bestaat.
--
-- Meteen ook de tweede taak van dezelfde tabel: firma per domein. 258 adressen
-- stonden zonder firma terwijl het domein het antwoord is - behalve op
-- globaal.be, het gedeelde groepsdomein, waar de prefixen (ha., ee., tkn., hb.)
-- afdelingen zijn en geen firma's. Die 238 blijven bewust leeg: liever een open
-- eindje dan een gok. firma_id is daarom nullable en er staat een opmerking bij.
--
-- Twee verbruikscijfers, bewust naast elkaar:
--   pakket_verbruik_gb  = wat de leverancier meet voor het hele pakket, dus
--                         inclusief webhosting (h-architects: 243,1 GB)
--   de som van emailadres.opslag_mb = alleen de postbussen (h-architects: 213,1 GB)
-- Ze verschillen en dat verschil is informatie; een van de twee weglaten maakt
-- het cijfer onuitlegbaar.

BEGIN;

CREATE TABLE communicatie.email_domein (
    domein             text PRIMARY KEY,
    firma_id           uuid REFERENCES kern.firma(id),
    firma_afleiden     boolean     NOT NULL DEFAULT true,
    pakket             text        NOT NULL DEFAULT '',
    quota_gb           numeric,
    pakket_verbruik_gb numeric,
    opslag_addon       text        NOT NULL DEFAULT '',
    jaarbedrag         numeric,
    factuurdatum       date,
    verlengdatum       date,
    factuurregels      text        NOT NULL DEFAULT '',
    opmerking          text        NOT NULL DEFAULT '',
    bron               text        NOT NULL DEFAULT '',
    bron_bijgewerkt_op timestamptz,
    bijgewerkt_door    text        NOT NULL DEFAULT '',
    bijgewerkt_op      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_email_domein_firma ON communicatie.email_domein (firma_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.email_domein TO communicatie;

COMMENT ON TABLE communicatie.email_domein IS
    'Een e-maildomein bij de leverancier: het pakket, wat het per jaar kost, en de firma waar adressen op dit domein bij horen.';
COMMENT ON COLUMN communicatie.email_domein.firma_afleiden IS
    'Of een nieuw adres op dit domein automatisch de firma van het domein krijgt. Uit voor gedeelde domeinen zoals globaal.be.';
COMMENT ON COLUMN communicatie.email_domein.pakket_verbruik_gb IS
    'Verbruik van het hele pakket volgens de leverancier, inclusief webhosting. Niet hetzelfde als de som van de postbussen.';
COMMENT ON COLUMN communicatie.email_domein.jaarbedrag IS
    'Bedrag van de laatste jaarfactuur, excl. BTW zoals de leverancier het toont. Het aantal postbussen is onbeperkt binnen een pakket, dus dit bedrag verandert niet als er een postbus bij komt of weggaat.';

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_domein', 'Domein',
     'Het deel van het e-mailadres na de apenstaart. Bij one.com is een domein een eigen hostingpakket met een eigen quotum, een eigen factuur en een eigen verlengdatum; per domein filteren laat zien wat er per pakket in gebruik is. De lijst komt uit de adressen zelf, niet uit een bijgehouden tabel.'),
    ('email_pakket', 'Pakket',
     'Het hostingpakket dat onder een e-maildomein hangt (bij one.com bv. Basic, Email, Beginner, Explorer, Enthusiast), met eventuele add-ons zoals extra e-mailopslag. Het pakket bepaalt de prijs en het quotum; het aantal postbussen is onbeperkt. Een postbus wissen verlaagt de factuur dus niet: dat doe je door het pakket te verlagen, een add-on op te zeggen of het domein niet te verlengen.'),
    ('email_jaarbedrag', 'Jaarbedrag',
     'Wat een e-maildomein per jaar kost volgens de laatste factuur van de leverancier: pakket, add-ons en domeinregistratie samen. Naast het bedrag staat de prijs per postbus, puur als verhoudingsgetal om dure en goedkope domeinen te vergelijken - het is geen bedrag dat je bespaart door een postbus te wissen.'),
    ('email_verlengdatum', 'Verlengdatum',
     'De datum waarop het pakket van een e-maildomein automatisch verlengt. Wie een domein wil opzeggen of een pakket wil verlagen, moet dat vóór die datum doen; daarna is het weer een jaar betaald.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
