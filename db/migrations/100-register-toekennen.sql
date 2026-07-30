-- 100: het organisatieregister wordt een werkblad. Uit het overleg van
-- 30-07-2026 (Mehdi): hij wil per subpijler namen en een status kunnen
-- toekennen, software aan een pijler EN een subpijler hangen, en zien welke
-- agents ergens werken. Toekennen doet hij zelf; wij bouwen de plaats ervoor.
--
-- Expliciet NIET in deze migratie: gewicht of uren per subpijler. Zijn woorden:
-- eerst zien wie erbij betrokken is; waarde toekennen is een latere stap.
--
-- Vijf statussen, zoals afgesproken. `vraagt_persoon` maakt de
-- vooruitgangsregel data in plaats van code: een subpijler is BELEGD als hij
-- een status heeft en, voor de statussen die werk betekenen, minstens een
-- persoon. Zo blijft "niet van toepassing" een volwaardige beslissing en geen
-- gat in de teller.

BEGIN;

-- 1. Statussen --------------------------------------------------------------
CREATE TABLE kern.subdiscipline_status (
    code           text    NOT NULL PRIMARY KEY,
    naam           text    NOT NULL,
    uitleg         text    NOT NULL,
    vraagt_persoon boolean NOT NULL DEFAULT true,
    volgorde       integer NOT NULL
);
COMMENT ON TABLE kern.subdiscipline_status IS
  'De vijf statussen van een subpijler (migratie 100). vraagt_persoon = deze status betekent werk, dus hoort er iemand aan te hangen.';
INSERT INTO kern.subdiscipline_status (code, naam, uitleg, vraagt_persoon, volgorde) VALUES
('PRIORITEIT', 'prioriteit',          'Nu aanpakken, gaat voor op de rest.',                          true,  1),
('KORT',       'korte termijn',       'Binnenkort aanpakken.',                                        true,  2),
('LANG',       'lange termijn',       'Staat op de kaart, nog niet aan de orde.',                     true,  3),
('UITGESTELD', 'uitgesteld',          'Momenteel niet van toepassing, later opnieuw bekijken.',       false, 4),
('NVT',        'niet van toepassing', 'Geldt niet voor dit bureau; bewust en definitief.',            false, 5);

ALTER TABLE kern.subdiscipline
    ADD COLUMN IF NOT EXISTS status_code text
        REFERENCES kern.subdiscipline_status (code);
COMMENT ON COLUMN kern.subdiscipline.status_code IS
  'Status uit kern.subdiscipline_status; leeg = nog geen beslissing genomen.';

-- 2. Wie werkt eraan -------------------------------------------------------
CREATE TABLE kern.subdiscipline_toewijzing (
    subdiscipline_code text        NOT NULL REFERENCES kern.subdiscipline (code) ON DELETE CASCADE,
    persoon_id         uuid        NOT NULL REFERENCES kern.persoon (id) ON DELETE CASCADE,
    bijgewerkt_op      timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door    text        NOT NULL DEFAULT '',
    PRIMARY KEY (subdiscipline_code, persoon_id)
);
CREATE INDEX ix_subdiscipline_toewijzing_persoon
    ON kern.subdiscipline_toewijzing (persoon_id);
COMMENT ON TABLE kern.subdiscipline_toewijzing IS
  'Wie werkt aan welke subpijler (migratie 100). Meer dan een persoon mag; de pijler erboven toont de namen van al zijn subpijlers.';
CREATE TRIGGER trg_audit AFTER INSERT OR DELETE OR UPDATE
    ON kern.subdiscipline_toewijzing
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();

-- 3. Software ook op subpijlerniveau ---------------------------------------
-- De verantwoordelijke bestaat al als kosten.software.beheerder_persoon_id en
-- kan iemand anders zijn dan de gebruikers; die kolom wordt nu ook op deze tab
-- getoond in plaats van alleen in het kosten-dashboard.
ALTER TABLE kosten.software
    ADD COLUMN IF NOT EXISTS subdiscipline_code text
        REFERENCES kern.subdiscipline (code) ON UPDATE CASCADE;
COMMENT ON COLUMN kosten.software.subdiscipline_code IS
  'Fijnere plaatsing dan discipline_sleutel: welke subpijler gebruikt deze software (migratie 100).';

-- 4. Agents ----------------------------------------------------------------
CREATE TABLE kern.agent (
    code     text        NOT NULL PRIMARY KEY,
    naam     text        NOT NULL,
    uitleg   text        NOT NULL,
    url      text        NOT NULL DEFAULT '',
    actief   boolean     NOT NULL DEFAULT true,
    volgorde integer     NOT NULL DEFAULT 0
);
COMMENT ON TABLE kern.agent IS
  'Register van de agents die op het platform draaien, zodat een subpijler kan tonen welke agent daar werkt (migratie 100). Aanvullen zodra er een agent bijkomt.';
INSERT INTO kern.agent (code, naam, uitleg, url, actief, volgorde) VALUES
('signalen', 'Signalen-agent',
 'Bewaakt de bedrijfsdata met vaste regels en geeft een keer per dag een AI-duiding.',
 'https://organisatie.globaal.be/signalen', true, 1),
('gezondheid', 'Gezondheidsagent',
 'Sondeert de containers, duidt storingen en herstart zelf waar dat helpt.',
 'https://agents.globaal.be/', true, 2),
('ingestie', 'Ingestie-agent',
 'Beheert de kennisbanken: chunken, embedden, laden en bewaken.',
 'https://agents.globaal.be/', true, 3),
('factuurrouter', 'Factuurrouter',
 'Leest inkomende facturen en stelt de routering naar het juiste dossier voor.',
 'https://agents.globaal.be/', true, 4),
('elevait_finance', 'Elevait finance-agent',
 'Volgt de kosten van Elevait en meldt een kostensprong.',
 'https://agents.globaal.be/', true, 5),
('klikbaarheid', 'Klikbaarheids-agent',
 'Zoekt KPI-cijfers zonder drill-down. Pilot gedaan, nog niet productioneel.',
 '', false, 6);

CREATE TABLE kern.subdiscipline_agent (
    subdiscipline_code text        NOT NULL REFERENCES kern.subdiscipline (code) ON DELETE CASCADE,
    agent_code         text        NOT NULL REFERENCES kern.agent (code) ON DELETE CASCADE,
    bijgewerkt_op      timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door    text        NOT NULL DEFAULT '',
    PRIMARY KEY (subdiscipline_code, agent_code)
);
CREATE INDEX ix_subdiscipline_agent_agent ON kern.subdiscipline_agent (agent_code);
COMMENT ON TABLE kern.subdiscipline_agent IS
  'Welke agent werkt in welke subpijler (migratie 100).';

-- 5. Rechten ---------------------------------------------------------------
GRANT SELECT ON kern.subdiscipline_status, kern.subdiscipline_toewijzing,
                kern.agent, kern.subdiscipline_agent TO portal;
GRANT SELECT, INSERT, DELETE ON kern.subdiscipline_toewijzing TO medewerker_writer;
GRANT SELECT, INSERT, DELETE ON kern.subdiscipline_agent TO medewerker_writer;
GRANT SELECT ON kern.subdiscipline_status, kern.agent TO medewerker_writer;
GRANT UPDATE (status_code) ON kern.subdiscipline TO medewerker_writer;
GRANT SELECT ON kern.subdiscipline TO medewerker_writer;
-- Software plaatsen gebeurt vanaf deze tab; het kosten-dashboard blijft de
-- eigenaar van de rest van de kaart.
GRANT SELECT ON kosten.software TO medewerker_writer;
GRANT UPDATE (discipline_sleutel, subdiscipline_code) ON kosten.software TO medewerker_writer;

-- 6. Woordenboek -----------------------------------------------------------
INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('subpijler_status', 'Status van een subpijler',
 'Prioriteit, korte termijn, lange termijn, uitgesteld of niet van toepassing. Zegt wanneer we er iets mee doen, niet hoeveel werk het is.'),
('subpijler_belegd', 'Belegd',
 'Een subpijler is belegd als er een status op staat en, bij een status die werk betekent, minstens een naam aan hangt. De vooruitgang op de Disciplines-tab is het aandeel belegde subpijlers.'),
('agent', 'Agent',
 'Een zelfstandig draaiend programma dat werk overneemt en zich verantwoordt op de agents-tegel. Geen medewerker; agentwerk wordt apart geteld.')
ON CONFLICT (sleutel) DO UPDATE SET term = excluded.term,
    definitie = excluded.definitie, bijgewerkt_op = now();

COMMIT;
