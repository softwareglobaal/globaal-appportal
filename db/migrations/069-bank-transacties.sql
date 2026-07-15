-- 069 - banktransacties in de database (herbouw kosten-dashboard,
-- besluit Shaniel 2026-07-15).
--
-- Het oude kosten-dashboard bakte de geparste KBC/VISA-afschriften in een
-- statische HTML-pagina; annotaties leefden deels in localStorage. De
-- herbouw maakt de database de ene waarheid: de host-pijplijn (extract_cc,
-- PyMuPDF op de PDF-afschriften) blijft bestaan als invoerpijplijn en
-- schrijft de transacties hierheen; de nieuwe stack-app leest alleen nog
-- uit de database. Import is een volledige vervanging per run (de CSV van
-- de pijplijn is altijd het complete beeld), dus geen dedupe-sleutels.
--
-- Het bedrag staat zoals op het afschrift (negatief = uitgave), de bron
-- eerlijk gespiegeld. De leverancier-link loopt via de bestaande trigger
-- kosten.link_leverancier (migratie 012): vendor-tekst blijft weergave,
-- kern.leverancier is de verwijzing.

CREATE TABLE kosten.bank_transactie (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    firma_code      text NOT NULL,
    datum           date NOT NULL,
    vendor          text NOT NULL,
    categorie       text NOT NULL DEFAULT '',
    bedrag          numeric(12,2) NOT NULL,
    omschrijving    text NOT NULL DEFAULT '',
    bron            text NOT NULL DEFAULT '',
    leverancier_id  uuid REFERENCES kern.leverancier(id),
    geimporteerd_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_bank_tx_firma_vendor ON kosten.bank_transactie (firma_code, vendor);
CREATE INDEX ix_bank_tx_datum ON kosten.bank_transactie (datum);
CREATE INDEX ix_bank_tx_leverancier ON kosten.bank_transactie (leverancier_id);

CREATE TRIGGER trg_bank_tx_link_leverancier
    BEFORE INSERT OR UPDATE OF vendor ON kosten.bank_transactie
    FOR EACH ROW EXECUTE FUNCTION kosten.link_leverancier();

-- Lezen voor de dashboards; schrijven (volledige vervanging bij import)
-- voor de kosten-rol.
GRANT SELECT ON kosten.bank_transactie TO portal, communicatie, kosten;
GRANT INSERT, UPDATE, DELETE ON kosten.bank_transactie TO kosten;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('bank_transactie', 'Banktransactie',
     'Een regel van een KBC/VISA-kaartafschrift zoals de invoerpijplijn hem uit de PDF haalt: firma van de kaart, datum, leverancier (vendor), categorie en het bedrag zoals op het afschrift (negatief is een uitgave). De databasetabel is de ene waarheid voor het kosten-dashboard; de PDF-afschriften op de server blijven het brondocument.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
