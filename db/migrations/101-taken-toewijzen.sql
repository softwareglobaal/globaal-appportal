-- 101: toewijzen gebeurt op de TAAK, niet op de subpijler. Correctie op 100
-- (Shaniel, 30-07-2026), en het klopt met wat Mehdi in het overleg beschreef:
-- onder Office & reception wees hij "benodigdheden" aan Mukesh toe en "klein
-- onderhoud" aan Ashvan, en zei daarna dat boven de subpijler dan zowel Ashvan
-- als Mukesh komt te staan. De namen rollen dus op van taak naar subpijler naar
-- pijler; alleen het laagste niveau wordt echt toegekend.
--
-- Twee niveaus blijven bestaan, met een duidelijke werkverdeling:
--   * subpijler-status = beslissing over het hele blok. Staat die op
--     "niet van toepassing" of "uitgesteld", dan is het blok afgehandeld en
--     hoeven de taken eronder niets meer te dragen (zijn voorbeeld: we hebben
--     geen receptie, dus die hele subpijler is niet van toepassing).
--   * taak-status, namen en agents = het werkniveau.
--
-- De toewijzingstabellen op subpijlerniveau uit migratie 100 waren nog leeg
-- (alleen door mij getest en meteen opgeruimd) en verdwijnen daarom zonder
-- dataverlies. De status op de subpijler blijft wel.

BEGIN;

-- 1. Een stabiele sleutel per taak: A1.1.1, A1.1.2, ...
ALTER TABLE kern.subelement ADD COLUMN IF NOT EXISTS code text;
UPDATE kern.subelement
   SET code = subdiscipline_code || '.' || volgorde
 WHERE code IS NULL;
ALTER TABLE kern.subelement ALTER COLUMN code SET NOT NULL;
ALTER TABLE kern.subelement ADD CONSTRAINT subelement_code_uniek UNIQUE (code);
COMMENT ON COLUMN kern.subelement.code IS
  'Stabiele sleutel van de taak (A1.1.1), doelwit van de toewijzingen (migratie 101).';

-- 2. Status, namen en agents op de taak ------------------------------------
ALTER TABLE kern.subelement ADD COLUMN IF NOT EXISTS status_code text
    REFERENCES kern.subdiscipline_status (code);
COMMENT ON COLUMN kern.subelement.status_code IS
  'Status van de taak; leeg = nog geen beslissing, tenzij de subpijler zelf al afgehandeld is.';

CREATE TABLE kern.subelement_toewijzing (
    subelement_code text        NOT NULL REFERENCES kern.subelement (code) ON DELETE CASCADE,
    persoon_id      uuid        NOT NULL REFERENCES kern.persoon (id) ON DELETE CASCADE,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text        NOT NULL DEFAULT '',
    PRIMARY KEY (subelement_code, persoon_id)
);
CREATE INDEX ix_subelement_toewijzing_persoon
    ON kern.subelement_toewijzing (persoon_id);
COMMENT ON TABLE kern.subelement_toewijzing IS
  'Wie doet welke taak (migratie 101). Rolt op naar de subpijler en de pijler.';
CREATE TRIGGER trg_audit AFTER INSERT OR DELETE OR UPDATE
    ON kern.subelement_toewijzing
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();

CREATE TABLE kern.subelement_agent (
    subelement_code text        NOT NULL REFERENCES kern.subelement (code) ON DELETE CASCADE,
    agent_code      text        NOT NULL REFERENCES kern.agent (code) ON DELETE CASCADE,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text        NOT NULL DEFAULT '',
    PRIMARY KEY (subelement_code, agent_code)
);
CREATE INDEX ix_subelement_agent_agent ON kern.subelement_agent (agent_code);
COMMENT ON TABLE kern.subelement_agent IS
  'Welke agent doet welke taak (migratie 101).';

-- 3. De lege subpijler-toewijzingen uit 100 vervallen ----------------------
DROP TABLE IF EXISTS kern.subdiscipline_toewijzing;
DROP TABLE IF EXISTS kern.subdiscipline_agent;
COMMENT ON COLUMN kern.subdiscipline.status_code IS
  'Beslissing over de hele subpijler. Niet van toepassing of uitgesteld handelt ook alle taken eronder af (migratie 101).';

-- 4. Rechten ---------------------------------------------------------------
GRANT SELECT ON kern.subelement_toewijzing, kern.subelement_agent TO portal;
GRANT SELECT, INSERT, DELETE ON kern.subelement_toewijzing TO medewerker_writer;
GRANT SELECT, INSERT, DELETE ON kern.subelement_agent TO medewerker_writer;
GRANT SELECT ON kern.subelement TO medewerker_writer;
GRANT UPDATE (status_code) ON kern.subelement TO medewerker_writer;

-- 5. Woordenboek -----------------------------------------------------------
INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('subpijler_belegd', 'Belegd',
 'Een taak is belegd als er een status op staat en, bij een status die werk betekent, minstens een naam aan hangt. Een subpijler die zelf op niet van toepassing of uitgesteld staat, handelt al zijn taken in een keer af. De vooruitgang op de Disciplines-tab is het aandeel belegde taken.')
ON CONFLICT (sleutel) DO UPDATE SET term = excluded.term,
    definitie = excluded.definitie, bijgewerkt_op = now();

COMMIT;
