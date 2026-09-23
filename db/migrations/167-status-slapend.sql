-- 167: status "Slapend" voor telefoonnummers (proef Telefonie-tab, 23-09-2026).
--
-- Een nummer dat nog bestaat en betaald wordt, maar waar Xelion al langer
-- dan 180 dagen geen enkel gesprek over zag. De app stelt het voor op basis
-- van het belarchief; een editor bevestigt het als status. Anders dan
-- Vervallen (weg bij de provider) en Niet-actief (kan nog aan) is Slapend
-- een signaal om te beslissen: opzeggen, of bewust houden (bv. een
-- gepubliceerd nummer waar toevallig niet naar gebeld wordt).

ALTER TABLE communicatie.nummer
    DROP CONSTRAINT IF EXISTS ck_nummer_status;
ALTER TABLE communicatie.nummer
    ADD CONSTRAINT ck_nummer_status
    CHECK (status IN ('Actief', 'Niet-actief', 'Vervallen', 'Slapend', 'Onbekend'));

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('status_slapend', 'Slapend',
     'Het nummer bestaat en wordt betaald, maar er is al langer dan 180 dagen geen enkel gesprek over gegaan volgens Xelion. De app stelt Slapend voor; een editor bevestigt het. Daarna beslis je: opzeggen, of bewust houden omdat het nummer ergens gepubliceerd staat.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
