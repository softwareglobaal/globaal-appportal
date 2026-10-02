-- 184: schema `project`, het projectregister. Eerste firma: H-Architects.
--
-- Aanleiding: Mehdi, 02-10-2026: "in Source of the Truth de basis opzetten voor H-Architects,
-- ter vervanging van Monday.com en Teamleader ... alleen de projecten ... de gegevens van de
-- klanten zodat we die correct kunnen linken aan Google Contacts ... er wordt niets gekopieerd,
-- alles wordt gelinkt." Eerst 2025 en 2026.
--
-- De app is H-A Projecten (ha-projecten.globaal.be, repo softwareglobaal/globaal-ha-projecten),
-- vanaf v0.2. Deze migratie maakt enkel het schema, de rol, de rechten, twee regels voor de
-- Bron van de waarheid en de termen. De tabellen maakt de app zelf bij de start
-- (app/schema.sql in de app-repo, idempotent), zoals bij 176 (doorbelasting). Het schema is
-- eigendom van de app-rol.
--
-- Wat er gelinkt wordt en niet gekopieerd:
--   firma      -> kern.firma(id)         (REFERENCES)
--   collega's  -> kern.persoon(id)       (REFERENCES, naam altijd live uit kern.persoon)
--   klant      -> Google Contacts        (resourceName people/c..., de vaste sleutel van Google;
--                                         de naam ernaast is alleen linktekst)
--   fase, adres, type -> de projectmap   (afspraak A12, niet in de databank)
--
-- Klantnamen en e-mailadressen komen nooit via deze migratie of een seed in git: de app
-- leest ze bij het importeren rechtstreeks uit de bron en zet ze rechtstreeks in de databank.
--
-- Leesrecht voor `portal`: het register is bedoeld om vanuit andere dashboards naar te
-- linken. Er staan geen bedragen of lonen in.
--
-- Eigen LOGIN-rol ha_projecten_app (wachtwoord via ALTER ROLE op de VM, in ~/ha-projecten/.env
-- als HA_DB_URL). Nog niet in de graaf: dat volgt in een eigen migratie zodra het register
-- besloten is (status op de pagina Bron van de waarheid).

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ha_projecten_app') THEN
        CREATE ROLE ha_projecten_app LOGIN;
    END IF;
END $$;

CREATE SCHEMA IF NOT EXISTS project AUTHORIZATION ha_projecten_app;
GRANT USAGE, CREATE ON SCHEMA project TO ha_projecten_app;

-- Lezen en verwijzen naar de kern, nooit schrijven.
GRANT USAGE ON SCHEMA kern TO ha_projecten_app;
GRANT SELECT, REFERENCES ON kern.firma, kern.persoon TO ha_projecten_app;
GRANT SELECT ON kern.afdeling TO ha_projecten_app;

GRANT USAGE ON SCHEMA project TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE ha_projecten_app IN SCHEMA project GRANT SELECT ON TABLES TO portal;

-- Twee regels voor de Bron van de waarheid (172). Status blijft Voorstel tot de beslisser
-- beslist op organisatie.globaal.be/bronnen.
INSERT INTO kern.bron_regel (sleutel, volgorde, gegeven, bron, wie_wijzigt, kopieen, hoe, beslisser) VALUES
    ('project_ha', 50, 'H-A-project: nummer, status, opvolging, wie eraan werkt, klant',
     'H-A Projecten (ha-projecten.globaal.be), schema project',
     'Wie het project opvolgt, op het dashboard',
     'Monday (H-A Light Projects, H-A Projects_STA), vroeger Teamleader',
     'Monday 2025-2026 eenmalig overgenomen op 02-10-2026 en daarna alleen nog gelezen. '
     'Fase, adres en type blijven uit de mapnaam komen (A12).',
     'mehdi'),
    ('klant', 60, 'Klant: naam, telefoon, e-mail',
     'Google Contacts (centraal account van Contactsync)',
     'Sales en wie het project opvolgt, in Google Contacts of met Nieuw contact op contactsync',
     'Xelion (gespiegeld door Contactsync), Monday-klantbord, Pipedrive-personen, contractsysteem',
     'Xelion volgt elke minuut via Contactsync. Projecten linken met de Google-sleutel '
     '(resourceName), niet met een kopie van naam of nummer.',
     'mehdi')
ON CONFLICT (sleutel) DO NOTHING;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('projectregister', 'Projectregister',
     'De lijst van alle projecten van een firma, een rij per projectnummer, in het schema project. '
     'Een project staat erin vanaf het moment dat het een nummer heeft, ook zonder projectmap. '
     'Het register bewaart alleen wat nergens anders ontstaat (status, opvolging) en de links '
     'naar wat elders ontstaat: de klant in Google Contacts, de collega in het personenregister, '
     'het Monday-item, het contract.'),
    ('klantkoppeling', 'Klantkoppeling',
     'De link tussen een project en een contact in Google Contacts, bewaard als de Google-sleutel '
     '(people/c...). Naam, telefoon en e-mail blijven in Google; een hernoeming daar breekt de '
     'link niet.'),
    ('bevinding', 'Bevinding',
     'Iets wat de bronnen van een project elkaar tegenspreken of wat ontbreekt, gevonden bij het '
     'importeren of live (bv. een Monday-klant die in Google bij een ander nummer staat). Een '
     'bevinding wordt opgelost in de bron, nooit door het register stil aan te passen.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
