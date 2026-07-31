-- 108 — vermogen: planner voor terugkerende rijen (via MCP te beheren).
--
-- "Maak elke maand een betaalrij aan": een plan is een sjabloon (tab +
-- velden) met een interval en een volgende datum. De app draait er elk uur
-- een planner-thread overheen (planner.py; FOR UPDATE SKIP LOCKED tegen
-- races tussen de gunicorn-workers) en maakt de rijen aan alsof een
-- gebruiker het deed; audit ziet 'vermogen-planner'. Een gemist uur of een
-- herstart haalt zichzelf in: de datum schuift per aangemaakte rij één
-- interval op tot hij in de toekomst ligt.

CREATE TABLE vermogen.plan (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam            text NOT NULL,
    tab             text NOT NULL,   -- vaste tab of sectie-slug
    velden          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- sjabloon {kolom: waarde}
    interval        text NOT NULL
        CONSTRAINT ck_plan_interval CHECK (interval IN
            ('dagelijks', 'wekelijks', 'maandelijks', 'driemaandelijks', 'jaarlijks')),
    volgende_datum  date NOT NULL,
    datum_kolom     text NOT NULL DEFAULT '',  -- datumveld dat de rundatum krijgt
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

GRANT SELECT, INSERT, UPDATE, DELETE ON vermogen.plan TO vermogen;
GRANT SELECT ON vermogen.plan TO portal;

CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON vermogen.plan
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();
