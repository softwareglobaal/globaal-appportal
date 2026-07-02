-- 008 — vrije elementen-laag voor de organisatie-graph.
--
-- Zelfbediening: nieuwe soorten knopen (projecten, tools, documenten, ...) en hun
-- relaties toevoegen via de UI van het Organisatie-dashboard — zonder code of AI.
-- Getypeerde kernentiteiten (met echte kolommen/FK's) blijven de norm voor alles
-- dat afdwingbare structuur nodig heeft; dit is de lichtgewicht/experimenteer-laag.
-- Wordt een vrije soort belangrijk, dan promoveren we die naar een echt schema.

CREATE TABLE kern.element_soort (
    id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam   text NOT NULL UNIQUE,
    kleur  text NOT NULL DEFAULT '#7a8693',   -- hex; bepaalt graph-kleur + filter-chip
    actief boolean NOT NULL DEFAULT true
);

CREATE TABLE kern.element (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    soort_id         uuid NOT NULL REFERENCES kern.element_soort(id),
    naam             text NOT NULL,
    omschrijving     text NOT NULL DEFAULT '',
    url              text NOT NULL DEFAULT '',   -- optionele link (document, site, ...)
    actief           boolean NOT NULL DEFAULT true,
    aangemaakt_op    timestamptz NOT NULL DEFAULT now(),
    aangemaakt_door  text NOT NULL DEFAULT ''
);
CREATE INDEX ix_element_soort ON kern.element (soort_id);

-- Relatie van een element naar ELKE knoop in de graph (persoon/firma/nummer/element/...).
-- `doel` gebruikt de knoop-notatie van de graph: 'p:<uuid>', 'f:<uuid>', 'n:<uuid>',
-- 'x:<uuid>' (ander element), enz. Zachte verwijzing (kan niet als FK over meerdere
-- tabellen); de graph filtert kapotte kanten automatisch weg.
CREATE TABLE kern.element_relatie (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    element_id uuid NOT NULL REFERENCES kern.element(id) ON DELETE CASCADE,
    doel       text NOT NULL,
    label      text NOT NULL DEFAULT 'hoort bij',
    UNIQUE (element_id, doel, label)
);

-- Lezen: automatisch gedekt door de default privileges van migratie 001.
-- Schrijven: de smalle schrijfrol van het Organisatie-dashboard.
GRANT INSERT, UPDATE ON kern.element_soort TO medewerker_writer;
GRANT INSERT, UPDATE ON kern.element TO medewerker_writer;
GRANT INSERT, DELETE ON kern.element_relatie TO medewerker_writer;
