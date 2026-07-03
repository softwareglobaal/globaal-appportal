-- 029 — de Second Brain wordt schema-gedreven (besluit 2026-07-03).
--
-- Probleem: graaf.py was een handgeschreven kopie van de relaties die al in de
-- database bestaan (FK's/koppeltabellen); elke nieuwe migratie moest apart in de
-- graaf worden verwerkt en bleef anders onzichtbaar (zoals de Xelion-queue).
-- Vanaf nu leest de graaf de relaties zélf uit de Postgres-catalogus (laag 1),
-- met curatie als data i.p.v. code (laag 2) en signalen voor het onbenoemde
-- (laag 3). Deze migratie levert de datakant:
--   1. kern.graaf_regel   — curatie per relatie of tabel: mooier label,
--      verbergen, woordenboek-sleutel. Sleutel = 'schema.tabel.kolom' (relatie)
--      of 'schema.tabel' (tabel). Beheer via de graph-pagina (wb-editors).
--   2. organisatie.graaf_versie — snapshot per gewijzigde graaf-opbouw
--      (versiebeheer: in één klap terug naar een eerdere versie).
--   3. organisatie.graaf_instelling — vastpinnen op een versie + de
--      automatische laag aan/uit (noodrem).

CREATE TABLE kern.graaf_regel (
    sleutel          text PRIMARY KEY,
    soort            text NOT NULL DEFAULT 'relatie',  -- 'relatie' | 'tabel'
    label            text NOT NULL DEFAULT '',          -- override; leeg = afgeleid van kolomnaam
    verborgen        boolean NOT NULL DEFAULT false,
    definitie_sleutel text NOT NULL DEFAULT '',
    opmerking        text NOT NULL DEFAULT '',
    bijgewerkt_door  text NOT NULL DEFAULT '',
    bijgewerkt_op    timestamptz NOT NULL DEFAULT now()
);

-- Curatie is een kern-wijziging: volledig auditeerbaar (migratie 023).
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE
    ON kern.graaf_regel
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();

CREATE TABLE organisatie.graaf_versie (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    gemaakt_op timestamptz NOT NULL DEFAULT now(),
    hash       text NOT NULL,
    knopen     int NOT NULL,
    kanten     int NOT NULL,
    payload    jsonb NOT NULL
);

CREATE TABLE organisatie.graaf_instelling (
    id              smallint PRIMARY KEY DEFAULT 1,
    vaste_versie_id bigint REFERENCES organisatie.graaf_versie(id) ON DELETE SET NULL,
    auto_actief     boolean NOT NULL DEFAULT true,
    bijgewerkt_door text NOT NULL DEFAULT '',
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now()
);
INSERT INTO organisatie.graaf_instelling (id) VALUES (1);

-- Rechten: portal leest (default privileges 007 dekken organisatie al);
-- de organisatie-app schrijft via medewerker_writer.
GRANT SELECT ON kern.graaf_regel TO portal;
GRANT SELECT ON organisatie.graaf_versie, organisatie.graaf_instelling TO portal;
GRANT SELECT, INSERT, UPDATE, DELETE ON kern.graaf_regel TO medewerker_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON organisatie.graaf_versie     TO medewerker_writer;
GRANT SELECT, INSERT, UPDATE        ON organisatie.graaf_instelling TO medewerker_writer;
-- (portal-leesrechten op vermogen/draaiboek/communicatie bestaan al: 016/022/002.)

-- Woordenboek: het begrip bestaat vanaf nu ook als term.
INSERT INTO kern.definitie (sleutel, term, definitie)
VALUES ('graaf_regel', 'Graaf-regel',
        'Curatie-instelling van de Second Brain: geeft een relatie of tabel uit de database een benoemd label in de graaf, of verbergt hem. Nieuwe relaties verschijnen automatisch en krijgen een signaal tot ze benoemd zijn.')
ON CONFLICT (sleutel) DO NOTHING;
