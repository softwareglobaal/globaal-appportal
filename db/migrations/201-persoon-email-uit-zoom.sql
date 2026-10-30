-- 201: Het e-mailadres van 28 collega's, uit de gebruikerslijst van Zoom.
--
-- Mehdi, 30-10-2026: per persoon een e-mailadres, dat ook het Zoom-adres is (migratie 200). Bron: Zoom-API /users, de 54
-- actieve gebruikers op 30-10-2026, gekoppeld op de Zoom-naam tegen kern.persoon.weergavenaam. Gul, Luc en Mukesh
-- staan in Zoom onder een andere naam (Gul Samad, P-VC, S-EPB) en zijn op voornaam gekoppeld. Akkoord Shaniel 30-10-2026.
-- Niet hierin: Mehdi (hier mch@h-architects.be, in Zoom info@h-invest.be) en Angela (in Zoom
-- sollicitaties@medianselections.com, lijkt een functie-adres); die wachten op een antwoord. Een bestaand adres wordt nooit
-- overschreven, en elke regel moet precies een persoon in dienst raken, anders faalt de migratie.

BEGIN;

CREATE TEMP TABLE _zoom_adres (voornaam text PRIMARY KEY, adres text NOT NULL) ON COMMIT DROP;

INSERT INTO _zoom_adres (voornaam, adres) VALUES
    ('Abi-Gail', 'qa.abi-gail@globaal.be'),
    ('Alexander', 'ha.alexander@globaal.be'),
    ('Aqib', 'tkn.aqib@globaal.be'),
    ('Ashvand', 'ee.ashvand@globaal.be'),
    ('Catalin', 'catalin@globaal.be'),
    ('Chesron', 'ha.chesron@globaal.be'),
    ('Chilton', 'ha.chilton@globaal.be'),
    ('Gul', 'tkn.gul@globaal.be'),
    ('Isaiah', 'ee.isaiah@globaal.be'),
    ('Ishara', 'ishara@globaal.be'),
    ('Jean-Charles', 'ee.jean-charles@globaal.be'),
    ('Joan', 'joan@globaal.be'),
    ('Joey', 'sls.joey@globaal.be'),
    ('Luc', 'luc@globaal.be'),
    ('Marise', 'ha.marise@globaal.be'),
    ('Matthew', 'ha.matthew@globaal.be'),
    ('Matthias', 'matthias@globaal.be'),
    ('Mukesh', 'ee.mukesh@globaal.be'),
    ('Natanael', 'ha.natanael@globaal.be'),
    ('Raisha', 'ha.raisha@globaal.be'),
    ('Shaniel', 'shaniel@globaal.be'),
    ('Shelton', 'sls.shelton@globaal.be'),
    ('Siyan', 'sls.siyan@globaal.be'),
    ('Sufa', 'qa.sufa@globaal.be'),
    ('Tom', 'tkn.tom@globaal.be'),
    ('Ultischa', 'hb.ultischa@globaal.be'),
    ('Xaviera', 'dat.xaviera@globaal.be'),
    ('Zjafhira', 'qa.zjafhira@globaal.be');

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM _zoom_adres v
                WHERE (SELECT count(*) FROM kern.persoon p
                        WHERE p.voornaam = v.voornaam AND p.in_dienst AND p.email IS NULL) <> 1) THEN
        RAISE EXCEPTION 'elk adres hoort bij precies een persoon in dienst zonder e-mailadres';
    END IF;
END $$;

UPDATE kern.persoon p SET email = v.adres
  FROM _zoom_adres v
 WHERE p.voornaam = v.voornaam AND p.in_dienst AND p.email IS NULL;

DO $$
BEGIN
    IF (SELECT count(*) FROM kern.persoon p JOIN _zoom_adres v ON p.email = v.adres AND p.voornaam = v.voornaam) <> 28 THEN
        RAISE EXCEPTION 'de 28 adressen horen bij precies 28 personen';
    END IF;
END $$;

COMMIT;
