-- 168: leidinggevende per afdeling, voor de Telefonie-tab (proef, 23-09-2026).
--
-- Bij elk nummer op Xelion toont de tab wie 1e staat in de belrij (de
-- verantwoordelijke) en wie diens leidinggevende is. Dat is het hoofd van
-- zijn afdeling (kern.persoon.rol = 'Hoofd'). Niet elke afdeling heeft een
-- hoofd: Sales bijvoorbeeld niet, en daar wil Siyan zelf als leidinggevende
-- staan. Deze tabel is de instelbare uitzondering; wat erin staat wint van de
-- rol-regel. Bewust in het schema communicatie en niet in kern: het is een
-- keuze van dit platform, HR beheert de rollen.

CREATE TABLE IF NOT EXISTS communicatie.afdeling_leidinggevende (
    afdeling_id   uuid PRIMARY KEY REFERENCES kern.afdeling(id) ON DELETE CASCADE,
    persoon_id    uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE CASCADE,
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.afdeling_leidinggevende TO communicatie;
GRANT SELECT ON communicatie.afdeling_leidinggevende TO portal;

-- Startwaarde: Sales heeft geen hoofd, Siyan is er de leidinggevende.
INSERT INTO communicatie.afdeling_leidinggevende (afdeling_id, persoon_id, bijgewerkt_door)
SELECT a.id, p.id, 'migratie 168'
  FROM kern.afdeling a, kern.persoon p
 WHERE a.naam = 'Sales' AND p.voornaam = 'Siyan' AND p.in_dienst
ON CONFLICT (afdeling_id) DO NOTHING;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('leidinggevende_nummer', 'Leidinggevende',
     'De leidinggevende van wie 1e staat in de belrij van een nummer: het hoofd van zijn afdeling. Heeft de afdeling geen hoofd, dan de persoon die daarvoor in de Telefonie-tab is ingesteld.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
