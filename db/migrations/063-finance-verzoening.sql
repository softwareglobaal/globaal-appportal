-- 063 - stap 5: de verzoening (PLAN.md). Twee koppelingen:
--
-- (1) Octopus-dossier -> onze firma: dossier_id op de bestaande
--     boekhouding-mapping (migratie 059). De sync vult hem automatisch
--     door het BTW-nummer van het dossier tegen kern.firma.kbo_nummer te
--     leggen (cijfers vergelijken, laatste 9 - leading zero-proof).
--     Expliciete kolom, geen naam-raden (de HA/Harmoniebouw-les).
-- (2) Octopus-relatie -> kern.partij: spiegel van de relaties per dossier
--     uit de API (vervangt op termijn Joan's handmatige exports), met
--     partij_id via BTW-match en exacte-naam-vangnet - zelfde regels als
--     de partijen-opbouw-seed (migratie 058).

ALTER TABLE kosten.octopus_boekhouding
    ADD COLUMN dossier_id integer;

GRANT SELECT ON kosten.octopus_boekhouding TO medewerker_writer, vermogen;
GRANT UPDATE (dossier_id) ON kosten.octopus_boekhouding TO medewerker_writer;

CREATE TABLE finance.octopus_relatie (
    dossier_id     integer NOT NULL,
    octopus_id     text NOT NULL,
    naam           text NOT NULL DEFAULT '',
    btw_nummer     text NOT NULL DEFAULT '',
    is_klant       boolean NOT NULL DEFAULT false,
    is_leverancier boolean NOT NULL DEFAULT false,
    actief         boolean NOT NULL DEFAULT true,
    partij_id      uuid REFERENCES kern.partij(id) ON DELETE SET NULL,
    ruw            jsonb NOT NULL DEFAULT '{}'::jsonb,
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier_id, octopus_id)
);
CREATE INDEX ix_frel_partij ON finance.octopus_relatie (partij_id);

-- Lezen komt via de default privileges van migratie 062; schrijven
-- expliciet voor de sync.
GRANT SELECT, INSERT, UPDATE, DELETE ON finance.octopus_relatie TO medewerker_writer;

UPDATE kern.definitie
   SET definitie = 'De automatische kopie van de Octopus-boekhouddata (boekjaren, boekingen en relaties per dossier) in het finance-schema, ververst door de poller in de organisatie-app. Octopus blijft de bron van waarheid: de spiegel is alleen-lezen richting Octopus en de sync-status toont per dossier hoe vers de data is. Dossiers koppelen aan firma''s via BTW/KBO, relaties aan partijen via BTW met exacte naam als vangnet; wat niet koppelt blijft zichtbaar als los. Een dag stilstand is een signaal, geen stilte.'
 WHERE sleutel = 'octopus_spiegel';
