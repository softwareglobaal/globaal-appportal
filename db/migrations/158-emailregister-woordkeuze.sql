-- 158: een woordenschat voor het e-mailregister, uit het bestaande woordenboek.
--
-- Aanleiding: kritiekronde 22-09-2026, punt 6. Tab 2 gebruikte zes woorden
-- voor twee toestanden (Staat, Status, Actief, Uitgezet, Niet-actief, Actief
-- als chip) en een eigen term "Beoordeling" voor precies het drieluik dat bij
-- nummers "Behouden" heet. Afspraak Shaniel: bestaande termen hergebruiken,
-- nieuwe termen in het woordenboek zetten. Dus:
--
--   status      bestaat (Actief / Niet-actief / Onbekend) en geldt nu ook
--               voor e-mailadressen; "Uitgezet" en "Staat" verdwijnen.
--   behouden    bestaat als validatie van nummers en wordt de validatie van
--               elke resource; email_behouden was een dubbel en gaat weg.
--   open_eindje nieuw: het gat dat de tab laat zien (geen verantwoordelijke,
--               of bij e-mail ook geen firma). Het woord stond al in de app,
--               maar nergens gedefinieerd.
--   email_domein, email_aandacht  nieuw: kolom en filterrij die nog geen
--               definitie hadden.

BEGIN;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('status', 'Status',
     'Actief / Niet-actief / Onbekend. Niet-actief verwijdert niets: het nummer of e-mailadres blijft bewaard en vindbaar. Voor een e-mailadres is dit de stand bij de leverancier: Niet-actief betekent dat de postbus is uitgezet (niet inloggen, geen post), maar dat de inhoud er nog is. Zie ook Vervallen voor nummers die definitief weg zijn.'),
    ('behouden', 'Behouden',
     'Validatie bij het opschonen van een register, voor nummers en e-mailadressen hetzelfde drieluik: behouden (blijft), verifieren (eerst navragen bij de eigenaar of de firma), elimineren (mag weg); leeg = nog te beoordelen. Elimineren gebeurt pas na verificatie, nooit zomaar. Bij een e-mailadres van meer dan 1 GB op elimineren geldt: eerst archiveren, dan pas verwijderen; en verwijderen in het register haalt alleen de registratie weg, nooit de mailbox bij de leverancier. Ontstaan bij de nummer-opschoning (register ~92 vs Xelion 41, meeting 2026-07-03).'),
    ('open_eindje', 'Open eindje',
     'Een resource waarvan niemand eigenaar is: een nummer of e-mailadres zonder verantwoordelijke, of een e-mailadres dat aan geen enkele firma hangt. Zolang het open staat is niemand aanspreekbaar en weet niemand of het weg mag. De OPEN-markering in de tabel verschijnt alleen als het de uitzondering is; is leeg de regel, dan zegt het kerncijfer het aantal.'),
    ('email_domein', 'Domein',
     'Het deel van het e-mailadres na de apenstaart. Bij one.com is een domein een eigen pakket met een eigen quotum en factuur; per domein filteren laat zien wat er per pakket in gebruik is. De lijst komt uit de adressen zelf, niet uit een bijgehouden tabel.'),
    ('email_aandacht', 'Aandacht',
     'Signalen op een e-mailadres die een blik verdienen: spamfilter uit, automatisch antwoord aan, doorsturen (naar een ander adres, of naar buiten de groep) en meer dan 1 GB opslag. Geen oordeel, wel een reden om te kijken; het oordeel zelf staat onder Behouden.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

-- Dubbel weg: het drieluik heet op beide tabbladen Behouden.
DELETE FROM kern.definitie WHERE sleutel = 'email_behouden';

COMMIT;
