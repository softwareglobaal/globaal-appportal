-- 155: postvakgegevens bij een e-mailadres (bron: one.com controlepaneel).
--
-- Aanleiding: opdracht Shaniel 22-09-2026. Het e-mailregister in het
-- communicatie-dashboard (tab 2) was nog leeg en kende alleen adres, firma,
-- verantwoordelijke en gebruikers. De mailboxen zelf staan bij one.com, en daar
-- ligt de enige harde informatie over wat een adres feitelijk is: staat het aan,
-- is het een echte postbus of een alias, hoeveel ruimte gebruikt het, staat de
-- spamfilter aan, staat er een automatisch antwoord klaar en waar wordt naartoe
-- doorgestuurd. Zonder die velden kun je het register wel vullen, maar niet
-- gebruiken om op te ruimen: 228 van de 502 adressen blijken uitgezet te zijn
-- en 88 daarvan zijn bovendien leeg.
--
-- Bewust GEEN aparte spiegeltabel zoals xelion_belvolgorde. Een e-mailadres is
-- geen wisselende meetwaarde maar een vast gegeven met een handvol eigenschappen,
-- en het register moet ook adressen kunnen bevatten die niet bij one.com staan
-- (Microsoft 365, of een adres dat iemand handmatig toevoegt). Daarom kolommen
-- op emailadres zelf, met bron + bron_bijgewerkt_op erbij zodat zichtbaar is
-- waar een rij vandaan komt en hoe oud die waarde is. Een leeg bron-veld
-- betekent: met de hand ingevoerd, niet van een leverancier overgenomen.
--
-- De bestaande kolom actief blijft het aan/uit van het adres. Bij one.com heet
-- dat mailAddressStatus ACTIVE/INACTIVE en dat vullen we daarin; het groene
-- "Active" dat one.com in de lijst toont hoort bij Backup & Restore en staat
-- hier dus in backup_restore, niet in actief.

BEGIN;

ALTER TABLE communicatie.emailadres
    ADD COLUMN soort              text NOT NULL DEFAULT 'postbus',
    ADD COLUMN opslag_mb          numeric,
    ADD COLUMN quota_gb           numeric,
    ADD COLUMN spamfilter         boolean,
    ADD COLUMN autoreply          boolean,
    ADD COLUMN forwards           text NOT NULL DEFAULT '',
    ADD COLUMN backup_restore     text NOT NULL DEFAULT '',
    ADD COLUMN bron               text NOT NULL DEFAULT '',
    ADD COLUMN bron_bijgewerkt_op timestamptz;

ALTER TABLE communicatie.emailadres
    ADD CONSTRAINT emailadres_soort_check CHECK (soort IN ('postbus', 'alias'));

-- Filteren op wat opgeruimd kan worden: uitgezet en (bijna) leeg.
CREATE INDEX ix_emailadres_soort ON communicatie.emailadres (soort);
CREATE INDEX ix_emailadres_opslag ON communicatie.emailadres (opslag_mb);

COMMENT ON COLUMN communicatie.emailadres.soort IS
    'postbus (eigen mailbox met opslag) of alias (doorgeefluik naar een postbus).';
COMMENT ON COLUMN communicatie.emailadres.opslag_mb IS
    'Verbruikte ruimte in MB op de peildatum in bron_bijgewerkt_op.';
COMMENT ON COLUMN communicatie.emailadres.quota_gb IS
    'Toegekende ruimte in GB volgens de leverancier.';
COMMENT ON COLUMN communicatie.emailadres.forwards IS
    'Doorstuuradressen, gescheiden door een puntkomma; leeg = niet doorsturen.';
COMMENT ON COLUMN communicatie.emailadres.bron IS
    'Waar de postvakgegevens vandaan komen, bv. one.com. Leeg = met de hand ingevoerd.';

-- Woordenboek: de kolomkoppen en tooltips in de app komen hiervandaan.
INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_soort', 'Soort',
     'Of een e-mailadres een eigen postbus is (met opslag en een wachtwoord) of een alias: een adres dat alleen doorgeeft aan een postbus. Een alias kost geen opslag en kan niet inloggen.'),
    ('email_opslag', 'Opslag',
     'Hoeveel ruimte de postbus gebruikt, met de toegekende ruimte erachter. Dit is de enige indicatie van gebruik die de leverancier geeft: one.com bewaart geen laatste-login of laatste-mail-datum. Een uitgezette postbus die bijna niets gebruikt, is een opruimkandidaat.'),
    ('email_spamfilter', 'Spamfilter',
     'Of de spamfilter van de leverancier aanstaat op dit adres. Uit betekent dat alles ongefilterd binnenkomt; op drukke adressen is dat meestal niet de bedoeling.'),
    ('email_autoreply', 'Automatisch antwoord',
     'Of er een automatisch antwoord (afwezigheidsbericht) klaarstaat. Blijft na een vertrek of een verlofperiode makkelijk aan staan, en antwoordt dan namens iemand die er niet meer is.'),
    ('email_forwards', 'Doorsturen naar',
     'De adressen waar binnenkomende post naartoe wordt doorgestuurd. Een doorstuur naar een adres buiten de groep betekent dat bedrijfspost het bedrijf verlaat, en verdient een bewuste keuze.'),
    ('email_backup', 'Back-up',
     'De staat van de back-up-en-herstel-dienst van de leverancier op dit adres: actief, beschikbaar (niet afgenomen) of leeg voor een alias.'),
    ('email_bron', 'Bron',
     'Waar de postvakgegevens vandaan komen en wanneer ze zijn opgehaald. Leeg betekent dat de rij met de hand is ingevoerd en niet van een leverancier is overgenomen.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
