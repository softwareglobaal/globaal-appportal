-- 172: Bron van de waarheid, als tabel in het platform in plaats van als document.
--
-- Aanleiding: vergadering 22-09-2026, Mehdi: "Wat is de source of the truth?"
-- Op 23-09 is een eerste voorstel uitgewerkt als gedeeld document, met drie
-- regels (persoon, telefoonnummer, e-mailadres). Twee problemen daarmee: een
-- document over "een bron" is zelf een tweede plek, en de getypte cijfers
-- verouderden binnen een dag (communicatie telde op 24-09 al 97 nummers in
-- plaats van 94). Besluit Shaniel 24-09: de besliste regels op het dashboard.
--
-- Per gegeven een regel. Een regel heeft EEN beslisser (Authentik-username):
-- twee namen betekent dat iedereen op de ander wacht. Alleen die beslisser
-- (of de beheerders uit BRON_BEHEER in de organisatie-app) zet de status. De
-- live controles staan niet in de tabel: die rekent de app uit bij elk bezoek,
-- op basis van de sleutel van de regel.

BEGIN;

CREATE TABLE kern.bron_regel (
    sleutel        text PRIMARY KEY CHECK (sleutel ~ '^[a-z][a-z0-9_]{1,40}$'),
    volgorde       integer NOT NULL DEFAULT 0,
    gegeven        text NOT NULL,
    bron           text NOT NULL,
    wie_wijzigt    text NOT NULL DEFAULT '',
    kopieen        text NOT NULL DEFAULT '',
    hoe            text NOT NULL DEFAULT '',
    status         text NOT NULL DEFAULT 'voorstel'
                   CHECK (status IN ('voorstel', 'besloten', 'afgewezen')),
    beslisser      text NOT NULL DEFAULT '',
    besloten_door  text NOT NULL DEFAULT '',
    besloten_op    timestamptz,
    opmerking      text NOT NULL DEFAULT '',
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON kern.bron_regel
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();

GRANT SELECT ON kern.bron_regel TO portal;
GRANT SELECT, UPDATE ON kern.bron_regel TO medewerker_writer;

-- De drie regels uit het voorstel van 23-09, allemaal nog Voorstel en nog
-- zonder beslisser: wie beslist, kiest Shaniel, niet de migratie.
INSERT INTO kern.bron_regel (sleutel, volgorde, gegeven, bron, wie_wijzigt, kopieen, hoe) VALUES
    ('persoon', 10, 'Persoon: naam, in dienst, werkgever',
     'Personenregister (organisatie-app)', 'Angela (HR)',
     'DeskTime, Authentik, namen-app',
     'DeskTime spiegelt dagelijks; Authentik is niet gekoppeld'),
    ('telefoon', 20, 'Telefoonnummer',
     'Communicatie-dashboard, lijnen live uit Xelion', 'Siyan',
     'Telefoonregister, losse opzeglijst',
     'Xelion live; het telefoonregister niet'),
    ('email', 30, 'E-mailadres: bestaat, staat aan of uit',
     'one.com', 'Siyan',
     'Register (communicatie), Authentik, personenregister, Bitwarden',
     'Niet: het register is eenmalig geladen op 22-09-2026')
ON CONFLICT (sleutel) DO NOTHING;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('bron_van_de_waarheid', 'Bron van de waarheid',
     'Per soort gegeven het ene systeem waar dat gegeven ontstaat of beslist wordt. Alles wat elders staat is een kopie die alleen leest; bij verschil wint de bron, en een kopie wordt nooit rechtstreeks aangepast. Een kopie zonder sync is een probleem en wordt als probleem getoond. Elke regel heeft een beslisser; tot die hem op Besloten zet, is het een voorstel.'),
    ('bron_regel_status', 'Status',
     'Voorstel: nog niet beslist. Besloten: de beslisser heeft de bron aangewezen, en de live controle op de pagina toetst of de kopieen met de bron overeenkomen. Afgewezen: het voorstel klopt niet en moet opnieuw.'),
    ('bron_beslisser', 'Beslisser',
     'De ene persoon die over een regel van de bron van de waarheid beslist. Bewust een naam en niet twee: bij twee namen wacht iedereen op de ander.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
