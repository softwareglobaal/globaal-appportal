-- 039 - verwerking meeting Mehdi 2026-07-04 (dashboard-feedback).
--
-- 1. Terminologie: "Intern gefactureerd aan" wordt "Gefactureerd aan". Het
--    woord intern verwarde: de factuur komt juist van extern binnen. Bij
--    "Interne doorfacturatie naar" is intern wel juist; die blijft.
-- 2. De samengestelde belvolgorde-kolom krijgt een woordenboek-definitie
--    (incl. uitleg van de bron-labels Xelion en register).
-- 3. "Gebruikt voor" mag vrije tekst zijn (dossiers, campagnes; hoeft niet
--    blauw): tekstveld naast de bestaande firma-koppeling.
-- 4. Contract-informatie hoort in het register, niet in de statistieken:
--    contracttype en opzegtermijn per nummer, met definities.

UPDATE kern.definitie
   SET term = 'Gefactureerd aan'
 WHERE sleutel = 'gefactureerd_aan';

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('belvolgorde', 'Belvolgorde',
     'De volgorde waarin een inkomende oproep aan mensen wordt aangeboden: 1 neemt eerst op. Het bron-label zegt waar de lijst vandaan komt: Xelion betekent live uit de telefooncentrale (bron van waarheid), register betekent handmatig bijgehouden (provider zonder API-koppeling).'),
    ('contract_type', 'Contracttype',
     'De contractvorm van het abonnement op dit nummer, bv. maandelijks opzegbaar of jaarcontract. Bepaalt samen met de opzegtermijn hoe snel er afgeschaald kan worden.'),
    ('opzegtermijn', 'Opzegtermijn',
     'Hoe lang van tevoren het abonnement op dit nummer opgezegd moet worden bij de leverancier.')
ON CONFLICT (sleutel) DO NOTHING;

ALTER TABLE communicatie.nummer
    ADD COLUMN gebruikt_voor_tekst text NOT NULL DEFAULT '',
    ADD COLUMN contract_type      text NOT NULL DEFAULT '',
    ADD COLUMN opzegtermijn       text NOT NULL DEFAULT '';
