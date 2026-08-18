-- 118: schema `intercompany` - onderlinge facturatie tussen de eigen firma's.
--
-- Waarover dit gaat: High Design Studio (Suriname) factureert maandelijks aan
-- de Belgische firma's van de groep. Amy maakte die facturen met de hand in een
-- Excel en boekte ze daarna in Octopus. Zij vertrekt, dus het proces moet
-- overneembaar zijn. Deze app is de eerste stap: zichtbaar maken wat er
-- werkelijk in Octopus staat, zodat het bedrag niet langer alleen in iemands
-- hoofd zit.
--
-- Niet te verwarren met schema `boekhouding` (migratie 102). Dat is Joan's app
-- en gaat over facturatie aan KLANTEN vanuit Monday. Dit gaat over facturatie
-- tussen de eigen firma's ONDERLING. Twee aparte werkstromen, twee apps.
--
-- Wat gemeten is voor deze migratie geschreven werd (18-08-2026, via
-- reports/suppliers/history op de Belgische dossiers):
--   - HDS staat in de Belgische dossiers als LEVERANCIER, rekening 602000.
--   - Elk dossier heeft twee HDS-relatiefiches naast elkaar: een Surinaamse
--     N.V. en een 'PVT. LTD.'. Allebei met echte boekingen. Of dat twee
--     entiteiten zijn of een dubbele fiche is een OPENSTAANDE VRAAG. Daarom is
--     de tegenpartij een aparte tabel met een schakelaar per fiche, en geen
--     kolom op firma: welke fiche meetelt is een menselijke keuze, en die
--     keuze hoort zichtbaar en omkeerbaar te zijn.
--   - Over de hele historie komt gefactureerd exact uit op betaald, per fiche
--     tot op de cent. Betalingen lopen wel over de maandgrens en in stukken.
--     Het cijfer met betekenis is dus het lopende saldo, niet de kalendermaand.
--
-- Lagen (ontwerp-prompt docs/prompt-dashboard-ontwerp.md):
--   entiteiten = firma, tegenpartij, boeking
--   relaties   = tegenpartij.dossier_id -> firma, firma.kern_firma_id -> kern
--   views      = queries in de app, niets opgeslagen
--
-- Bewust NIET in de graaf, op dezelfde grond als migratie 102: boeking is een
-- spiegel en verversing een logboek, en de firma-laag tekent de graaf al via
-- kosten.octopus_boekhouding (migratie 059). Tegenpartij is de enige echt
-- nieuwe relatie, maar die wijst naar een Octopus-relatienummer en niet naar
-- een knoop die de graaf kent. Een knoop toevoegen zou de graaf drukker maken
-- zonder iets te verbinden dat er nog niet staat.
--
-- Discipline: financial management, met intercompany accounting eronder.
-- Eigen LOGIN-rol intercompany_writer (wachtwoord via ALTER ROLE op de VM).

CREATE SCHEMA IF NOT EXISTS intercompany;

-- Firma: het Belgische Octopus-dossier dat aan HDS betaalt. Dossiernummer als
-- sleutel, want dat is wat de Octopus-API teruggeeft.
CREATE TABLE IF NOT EXISTS intercompany.firma (
    dossier_id    integer PRIMARY KEY,
    naam          text NOT NULL,
    kern_firma_id uuid REFERENCES kern.firma(id) ON DELETE SET NULL,
    volgen        boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS ix_intercompany_firma_kern
    ON intercompany.firma (kern_firma_id);

-- Tegenpartij: een HDS-relatiefiche binnen dat dossier. Meervoudig per dossier,
-- zie de kop. `volgen` staat standaard aan: een fiche die meetelt terwijl dat
-- niet hoort valt op in de cijfers, een fiche die stilletjes wegvalt niet.
-- `ontdekt_op` maakt zichtbaar dat een fiche later is opgedoken.
CREATE TABLE IF NOT EXISTS intercompany.tegenpartij (
    dossier_id integer NOT NULL
        REFERENCES intercompany.firma(dossier_id) ON DELETE CASCADE,
    relatie_id integer NOT NULL,
    naam       text NOT NULL,
    land       text NOT NULL DEFAULT '',
    email      text NOT NULL DEFAULT '',
    volgen     boolean NOT NULL DEFAULT true,
    opmerking  text NOT NULL DEFAULT '',
    ontdekt_op timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier_id, relatie_id)
);

-- Boeking: spiegel van reports/suppliers/history. Bij elke verversing volledig
-- vervangen voor die firma, dus bewust GEEN zakelijke sleutel. Migratie 103
-- moest een sleutel repareren die twee facturen liet samenvallen; dat risico
-- bestaat hier niet als er niets op sleutel wordt samengevoegd.
-- Een rij is ofwel een factuur (gefactureerd > 0, dagboek A-reeks) ofwel een
-- betaling (betaald > 0, dagboek F-reeks). Octopus levert dat als credit en
-- debet; de namen hier zeggen wat het betekent.
CREATE TABLE IF NOT EXISTS intercompany.boeking (
    id            bigserial PRIMARY KEY,
    dossier_id    integer NOT NULL,
    relatie_id    integer NOT NULL,
    datum         date,
    dagboek       text NOT NULL DEFAULT '',
    referentie    text NOT NULL DEFAULT '',
    volgnr        integer,
    boekjaar_id   integer,
    periode       integer,
    gefactureerd  numeric(14,2) NOT NULL DEFAULT 0,
    betaald       numeric(14,2) NOT NULL DEFAULT 0,
    valuta        text NOT NULL DEFAULT 'EUR',
    opgehaald_op  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_intercompany_boeking_firma
    ON intercompany.boeking (dossier_id, relatie_id, datum);

-- Verversing: wanneer de spiegel voor deze firma voor het laatst echt is
-- opgehaald, en of dat lukte. `klaar_op` schuift alleen op bij een geslaagde
-- ophaling, anders lijken oude cijfers vers (fout uit migratie 104).
CREATE TABLE IF NOT EXISTS intercompany.verversing (
    dossier_id       integer PRIMARY KEY,
    gestart_op       timestamptz,
    klaar_op         timestamptz,
    ok               boolean,
    aantal           integer NOT NULL DEFAULT 0,
    aantal_opgehaald integer NOT NULL DEFAULT 0,
    fout             text NOT NULL DEFAULT '',
    door             text NOT NULL DEFAULT ''
);

-- Dezelfde zes dossiers als migratie 102. Welke daarvan werkelijk aan HDS
-- betalen blijkt uit de eerste verversing; de tegenpartijen worden door de app
-- ontdekt en hier niet vastgelegd, want relatienummers verschillen per dossier.
INSERT INTO intercompany.firma (dossier_id, naam) VALUES
    (114703, 'H-Architects'),
    (164873, 'Energie Efficient'),
    (164872, 'UNABO'),
    (130699, 'TKN-Buro'),
    (181481, 'Contrax'),
    (108893, 'Harmonie Bouw')
ON CONFLICT (dossier_id) DO NOTHING;

-- Koppeling naar de centrale firma-laag via de codes uit migratie 059.
UPDATE intercompany.firma i
   SET kern_firma_id = f.id
  FROM kern.firma f
 WHERE f.code = CASE i.dossier_id
                    WHEN 114703 THEN 'HARC'
                    WHEN 164873 THEN 'ENEF'
                    WHEN 164872 THEN 'UNAB'
                    WHEN 130699 THEN 'TKNB'
                    WHEN 181481 THEN 'CONT'
                    WHEN 108893 THEN 'HARM'
                END
   AND i.kern_firma_id IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'intercompany_writer') THEN
        CREATE ROLE intercompany_writer LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA intercompany TO intercompany_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA intercompany
    TO intercompany_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intercompany TO intercompany_writer;
GRANT USAGE ON SCHEMA kern TO intercompany_writer;
GRANT SELECT ON kern.firma TO intercompany_writer;
GRANT USAGE ON SCHEMA intercompany TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA intercompany TO portal;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('intercompany.facturatie', 'intercompany-facturatie',
     'Facturatie tussen firma''s van de eigen groep onderling, niet aan klanten. '
     'Concreet: High Design Studio in Suriname factureert maandelijks aan de '
     'Belgische firma''s voor administratieve werkzaamheden.'),
    ('intercompany.tegenpartij', 'tegenpartij',
     'De relatiefiche van de andere groepsfirma binnen een Octopus-dossier. '
     'Een dossier kan er meerdere hebben voor dezelfde firma; welke meetelt is '
     'een keuze die per fiche wordt gezet.'),
    ('intercompany.saldo', 'intercompany-saldo',
     'Gefactureerd min betaald over de hele historie van een tegenpartij. Nul '
     'betekent dat alles vereffend is. Dit is het cijfer met betekenis, want '
     'betalingen lopen over de maandgrens en komen in stukken.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
