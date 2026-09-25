-- 173: Welke logins hangen aan een e-mailadres (uit Bitwarden, zonder geheimen).
--
-- Aanleiding: vergadering 22-09-2026, Mehdi: "waar staat het, en wat is het
-- gelinkt", en 25-09: de kanalen-inventaris. De eerste kruising met Bitwarden
-- (25-09) liet zien dat er diensten hangen aan adressen die uit staan, niet
-- meer bestaan of binnenkort vervallen: qoppa.be vervalt op 29-09-2026 en
-- draagt Pipedrive, de Monday-admin en SD Worx. Wie zo'n adres opruimt zonder
-- de login eerst te verhuizen, kan het wachtwoord van die dienst niet meer
-- herstellen.
--
-- Wat hier staat is metadata, nooit een geheim: de naam van het item, de host
-- van de login-URL en de collectie. Wachtwoorden, TOTP, notities en velden
-- worden weggefilterd voordat er iets de pc van Shaniel verlaat
-- (scripts/bitwarden-diensten-laden.py). Het Bitwarden-id staat erbij om het
-- item in de kluis terug te vinden, het geeft zelf geen toegang.
--
-- soort:
--   dienst    - een login met een URL buiten de mailbox (Pipedrive, Monday)
--   mailbox   - het wachtwoord van de mailbox zelf (one.com, webmail)
--   onbekend  - een item zonder URL; de naam zegt wat het is (bv. BPOST)

BEGIN;

CREATE TABLE communicatie.emailadres_dienst (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    emailadres_id      uuid NOT NULL REFERENCES communicatie.emailadres(id) ON DELETE CASCADE,
    bitwarden_id       text NOT NULL,
    soort              text NOT NULL CHECK (soort IN ('dienst', 'mailbox', 'onbekend')),
    dienst             text NOT NULL DEFAULT '',
    naam               text NOT NULL DEFAULT '',
    collectie          text NOT NULL DEFAULT '',
    bron               text NOT NULL DEFAULT 'bitwarden',
    bron_bijgewerkt_op timestamptz,
    UNIQUE (emailadres_id, bitwarden_id)
);
CREATE INDEX ix_emailadres_dienst_adres ON communicatie.emailadres_dienst (emailadres_id);

CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON communicatie.emailadres_dienst
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();

-- De standaardrechten uit migratie 002 dekken dit al; hier expliciet zodat het
-- niet van een onzichtbare regel afhangt.
GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.emailadres_dienst TO communicatie;
GRANT SELECT ON communicatie.emailadres_dienst TO portal;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_dienst', 'Gelinkt aan',
     'De logins die aan een e-mailadres hangen, uit Bitwarden: de dienst (Pipedrive, Monday, Google) of, zonder URL, de naam van het item. Alleen metadata, nooit een wachtwoord. Een adres met logins ruim je niet zomaar op: verhuis eerst de login naar een adres dat blijft, anders kan niemand het wachtwoord van die dienst nog herstellen. Het wachtwoord van de mailbox zelf staat apart en telt niet als dienst.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
