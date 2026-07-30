-- 099: bouwtijd per medewerker per applicatie sluitend maken. Vraag Mehdi
-- 2026-07-30: "ik moet de tijd die een medewerker aan een applicatie besteedde
-- kunnen zien". Dat kon al per app, maar een kwart van het werk hing aan
-- niemand: van de 881 commits stonden er 217 op een gedeeld of een
-- agent-adres (software@globaal.be 105, noreply@anthropic.com 85,
-- ops@globaal.be 27).
--
-- Drie dingen erbij:
-- 1. `machine_koppeling`: een machinenaam wijst naar een mens. Vangnet voor de
--    hooks, die soms alleen een kale gebruikersnaam meesturen ("shaniel",
--    "installatiecontrole"). Bewust NIET de hoofdsleutel: een cloud-sessie
--    heeft geen machine en een machine kan van eigenaar wisselen.
-- 2. `gebruiker_koppeling.soort`: mens, agent of gedeeld. Een gedeeld account
--    is niet aan een mens toe te wijzen en hoort ook niet stilzwijgend bij
--    iemand te belanden; het krijgt een eigen emmer op de tab.
-- 3. `git_dag.commits_bouw` en `commits_onderhoud`: het onderscheid nieuwbouw
--    tegenover onderhoud, afgeleid uit de commit-prefix (feat = bouw, fix,
--    docs, chore, refactor, test = onderhoud). Kost niets extra, want de
--    prefix is al huisregel in deze repo's.
--
-- De weergave `ontwikkeling.dag` lost de persoon nu op via de identiteit en,
-- als die niets geeft, via de machine.

BEGIN;

-- 1. Soort identiteit -------------------------------------------------------
ALTER TABLE ontwikkeling.gebruiker_koppeling
    ALTER COLUMN persoon_id DROP NOT NULL;
ALTER TABLE ontwikkeling.gebruiker_koppeling
    ADD COLUMN IF NOT EXISTS soort text NOT NULL DEFAULT 'mens';
ALTER TABLE ontwikkeling.gebruiker_koppeling
    ADD CONSTRAINT gebruiker_koppeling_soort_check
    CHECK (soort IN ('mens', 'agent', 'gedeeld'));
-- Een mens hoort een persoon te hebben; agent en gedeeld juist niet.
ALTER TABLE ontwikkeling.gebruiker_koppeling
    ADD CONSTRAINT gebruiker_koppeling_mens_heeft_persoon
    CHECK (soort <> 'mens' OR persoon_id IS NOT NULL);
COMMENT ON COLUMN ontwikkeling.gebruiker_koppeling.soort IS
  'mens = toe te wijzen aan een persoon; agent = door een agent gemaakt; gedeeld = gedeeld account, niet toewijsbaar.';

INSERT INTO ontwikkeling.gebruiker_koppeling (gebruiker, persoon_id, soort) VALUES
('noreply@anthropic.com', NULL, 'agent'),
('software@globaal.be',   NULL, 'gedeeld'),
('ops@globaal.be',        NULL, 'gedeeld')
ON CONFLICT (gebruiker) DO NOTHING;

-- 2. Machine naar mens -----------------------------------------------------
CREATE TABLE IF NOT EXISTS ontwikkeling.machine_koppeling (
    machine       text NOT NULL PRIMARY KEY,
    persoon_id    uuid REFERENCES kern.persoon (id) ON DELETE CASCADE,
    opmerking     text NOT NULL DEFAULT '',
    bijgewerkt_op timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE ontwikkeling.machine_koppeling IS
  'Vangnet: machinenaam naar persoon, voor werk dat binnenkomt zonder herkenbare identiteit (migratie 099).';

-- De twee machines die vandaag tijd insturen, gekoppeld aan de persoon die er
-- op werkt. Alleen zetten als de identiteit al bekend is; anders blijft de
-- machine als werkvoorraad op de tab staan.
INSERT INTO ontwikkeling.machine_koppeling (machine, persoon_id, opmerking)
SELECT 'DESKTOP-72T7K5R', k.persoon_id, 'werkmachine Shaniel'
  FROM ontwikkeling.gebruiker_koppeling k
 WHERE k.gebruiker = 'mch@h-architects.be' AND k.persoon_id IS NOT NULL
ON CONFLICT (machine) DO NOTHING;

-- 3. Bouw tegenover onderhoud ----------------------------------------------
ALTER TABLE ontwikkeling.git_dag
    ADD COLUMN IF NOT EXISTS commits_bouw      integer NOT NULL DEFAULT 0;
ALTER TABLE ontwikkeling.git_dag
    ADD COLUMN IF NOT EXISTS commits_onderhoud integer NOT NULL DEFAULT 0;
COMMENT ON COLUMN ontwikkeling.git_dag.commits_bouw IS
  'Commits met prefix feat (nieuwbouw), geteld door scripts/ontwikkeling-verzamel.sh.';
COMMENT ON COLUMN ontwikkeling.git_dag.commits_onderhoud IS
  'Commits met prefix fix, docs, chore, refactor, test, style of perf (onderhoud).';

-- 4. Weergave: persoon oplossen via identiteit, anders via machine ----------
DROP VIEW IF EXISTS ontwikkeling.dag;
CREATE VIEW ontwikkeling.dag AS
WITH sessie AS (
    SELECT sessie, repo, gebruiker,
           coalesce(nullif(machine, ''), '') AS machine,
           ts::date AS datum,
           extract(epoch FROM max(ts) - min(ts))::bigint AS duur_sec,
           count(*) FILTER (WHERE event = 'prompt') AS prompts
      FROM ontwikkeling.cc_event
     GROUP BY 1, 2, 3, 4, 5
), hook AS (
    SELECT datum, repo, gebruiker, max(machine) AS machine,
           count(*) AS sessies, sum(prompts) AS prompts,
           sum(duur_sec) AS duur_sec
      FROM sessie GROUP BY 1, 2, 3
), gemeten AS (
    SELECT datum, repo, gebruiker,
           max(coalesce(nullif(machine, ''), '')) AS machine,
           sum(actieve_sec) AS sec, sum(sessies) AS sessies,
           sum(prompts) AS prompts
      FROM ontwikkeling.cc_tijd GROUP BY 1, 2, 3
), sleutel AS (
    SELECT datum, repo, gebruiker FROM ontwikkeling.git_dag
    UNION SELECT datum, repo, gebruiker FROM hook
    UNION SELECT datum, repo, gebruiker FROM gemeten
)
SELECT s.datum, s.repo, s.gebruiker,
       -- Machine is hier een kenmerk, geen sleutel: hij dient alleen om de
       -- persoon te vinden als de identiteit niets oplevert. Werkt iemand op
       -- twee machines aan dezelfde app op dezelfde dag, dan staat er een van
       -- de twee; de machinetabel op de tab toont de verdeling.
       nullif(coalesce(m.machine, h.machine, ''), '') AS machine,
       coalesce(k.persoon_id, mk.persoon_id) AS persoon_id,
       coalesce(k.soort, CASE WHEN mk.persoon_id IS NOT NULL
                             THEN 'mens' ELSE 'onbekend' END) AS soort,
       coalesce(g.commits, 0) AS commits,
       coalesce(g.commits_bouw, 0) AS commits_bouw,
       coalesce(g.commits_onderhoud, 0) AS commits_onderhoud,
       coalesce(g.regels_plus, 0) AS regels_plus,
       coalesce(g.regels_min, 0) AS regels_min,
       coalesce(m.sessies, h.sessies, 0::bigint) AS cc_sessies,
       coalesce(m.prompts::numeric, h.prompts, 0::numeric) AS cc_prompts,
       coalesce(h.duur_sec, 0::numeric) AS cc_duur_sec,
       coalesce(m.sec, 0::bigint)::numeric AS gemeten_sec,
       coalesce(g.commit_venster_sec, 0)::numeric AS venster_sec
  FROM sleutel s
  LEFT JOIN ontwikkeling.git_dag g
         ON g.datum = s.datum AND g.repo = s.repo AND g.gebruiker = s.gebruiker
  LEFT JOIN hook h
         ON h.datum = s.datum AND h.repo = s.repo AND h.gebruiker = s.gebruiker
  LEFT JOIN gemeten m
         ON m.datum = s.datum AND m.repo = s.repo AND m.gebruiker = s.gebruiker
  LEFT JOIN ontwikkeling.gebruiker_koppeling k ON k.gebruiker = s.gebruiker
  LEFT JOIN ontwikkeling.machine_koppeling mk
         ON mk.machine = nullif(coalesce(m.machine, h.machine, ''), '');
COMMENT ON VIEW ontwikkeling.dag IS
  'Bouwwerk per dag, app en identiteit: commits (git), sessies (hooks) en gemeten tijd naast elkaar, nooit opgeteld. Persoon via identiteit, anders via machine (migratie 099).';

-- Leesrecht zoals de vorige weergave had (hr_app leest de weergave ook, zie
-- migratie 093), plus de nieuwe tabel voor de portal.
GRANT SELECT ON ontwikkeling.dag TO portal, hr_app;
GRANT SELECT ON ontwikkeling.machine_koppeling TO portal;

COMMIT;
