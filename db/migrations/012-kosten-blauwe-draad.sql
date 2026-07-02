-- 012 — de blauwe draad: het kosten-schema koppelen aan kern.
--
-- Het kosten-schema was een eiland: vendor als vrije tekst, kosten.firma als
-- eigen tekstlijst naast kern.firma. Deze migratie legt echte verwijzingen:
--   1. alle vendors worden rijen in kern.leverancier (de centrale lijst die
--      hiervoor bedoeld was: "telefonie nu, software later" — dit is later);
--   2. kosten.software en kosten.charge_actual krijgen leverancier_id, met een
--      trigger die de link automatisch legt bij nieuwe/gewijzigde rijen — de
--      host-app op kosten.globaal.be blijft vendor-tekst schrijven en breekt niet;
--   3. kosten.firma krijgt kern_firma_id als brug naar kern.firma; de tekst-ids
--      (software.firma_id / dest_firma_id) blijven bestaan voor de host-app.
--      Volledige verzoening (tekst-ids weg) volgt pas als de host-app meegaat.
-- De vendor-tekstkolommen blijven de weergavenaam in de host-app; kern is bron
-- voor de links. Naam-mismatches vallen op via de Second Brain-signalen.

-- Eén canonieke naam voor Close Call (leverancier = Close Call BV; Xelion is
-- het platform en staat in plan/note en in Communicatie).
UPDATE kosten.software     SET vendor = 'Close Call BV' WHERE vendor = 'Close Call (Xelion)';
UPDATE kosten.charge_actual SET vendor = 'Close Call BV' WHERE vendor = 'Close Call (Xelion)';

-- 1) Vendors de centrale leverancierslijst in (case-insensitief samensmelten:
--    bestaande rijen zoals Zoom en Microsoft worden hergebruikt).
INSERT INTO kern.leverancier (naam)
SELECT DISTINCT s.vendor
  FROM kosten.software s
 WHERE s.vendor <> ''
   AND NOT EXISTS (SELECT 1 FROM kern.leverancier l
                    WHERE lower(l.naam) = lower(s.vendor));

-- 2) Verwijzingen + backfill.
ALTER TABLE kosten.software      ADD COLUMN leverancier_id uuid REFERENCES kern.leverancier(id);
ALTER TABLE kosten.charge_actual ADD COLUMN leverancier_id uuid REFERENCES kern.leverancier(id);

UPDATE kosten.software s      SET leverancier_id = l.id
  FROM kern.leverancier l WHERE lower(l.naam) = lower(s.vendor);
UPDATE kosten.charge_actual c SET leverancier_id = l.id
  FROM kern.leverancier l WHERE lower(l.naam) = lower(c.vendor);

CREATE INDEX ix_software_leverancier      ON kosten.software (leverancier_id);
CREATE INDEX ix_charge_actual_leverancier ON kosten.charge_actual (leverancier_id);

-- Trigger: houdt de link blauw, ook voor rijen die de host-app straks schrijft.
-- SECURITY DEFINER zodat de kosten-rol via deze weg een ontbrekende leverancier
-- mag aanmaken zonder zelf schrijfrechten op kern.leverancier te krijgen.
CREATE FUNCTION kosten.link_leverancier() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = kern, kosten, public AS $$
DECLARE lid uuid;
BEGIN
    IF NEW.vendor IS NULL OR NEW.vendor = '' THEN
        NEW.leverancier_id := NULL;
        RETURN NEW;
    END IF;
    SELECT id INTO lid FROM kern.leverancier WHERE lower(naam) = lower(NEW.vendor);
    IF lid IS NULL THEN
        INSERT INTO kern.leverancier (naam) VALUES (NEW.vendor) RETURNING id INTO lid;
    END IF;
    NEW.leverancier_id := lid;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_software_link_leverancier
    BEFORE INSERT OR UPDATE OF vendor ON kosten.software
    FOR EACH ROW EXECUTE FUNCTION kosten.link_leverancier();
CREATE TRIGGER trg_charge_link_leverancier
    BEFORE INSERT OR UPDATE OF vendor ON kosten.charge_actual
    FOR EACH ROW EXECUTE FUNCTION kosten.link_leverancier();

-- 3) Brug kosten.firma → kern.firma (naam-match; wat niet matcht blijft NULL
--    en wordt door de Second Brain als verzoen-signaal gemeld).
ALTER TABLE kosten.firma ADD COLUMN kern_firma_id uuid REFERENCES kern.firma(id);

UPDATE kosten.firma kf SET kern_firma_id = f.id
  FROM kern.firma f WHERE lower(f.naam) = lower(kf.naam);
