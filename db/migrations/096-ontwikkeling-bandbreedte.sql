-- 096: bouwtijd als bandbreedte in plaats van een enkel getal
-- Besluit Shaniel 2026-07-29, na drie correcties op de meting: een enkel
-- getal suggereert een precisie die er bij AI-sessies niet is. Voortaan staan
-- er twee grenzen naast elkaar:
--
--   ondergrens = gemeten sessietijd (ontwikkeling.cc_tijd, migratie 094).
--       Telt alleen de tijd rond een aangeraakt bestand; werk zonder spoor
--       valt weg.
--   bovengrens = het commit-venster: de tijd van de eerste tot de laatste
--       commit van die dag, met gaten boven het uur eruit. Elke invoer staat
--       in `git log` en is dus zonder onze meting na te rekenen; pauzes
--       binnen een blok tellen wel mee.
--
-- De waarheid ligt ertussenin. Gemeten op globaal-hr, 20-07: 43 minuten
-- gemeten tegen 98 minuten venster.

ALTER TABLE ontwikkeling.git_dag
    ADD COLUMN IF NOT EXISTS commit_venster_sec integer NOT NULL DEFAULT 0;

-- De view opnieuw opbouwen: drie bronnen (git, hook, gemeten) op dezelfde
-- sleutel, en niets wordt opgeteld wat niet hetzelfde meet.
DROP VIEW IF EXISTS ontwikkeling.dag;

CREATE VIEW ontwikkeling.dag AS
WITH sessie AS (
    SELECT sessie, repo, gebruiker, ts::date AS datum,
           extract(epoch FROM max(ts) - min(ts))::bigint AS duur_sec,
           count(*) FILTER (WHERE event = 'prompt') AS prompts
      FROM ontwikkeling.cc_event
     GROUP BY sessie, repo, gebruiker, (ts::date)
), hook AS (
    SELECT datum, repo, gebruiker, count(*) AS sessies,
           sum(prompts) AS prompts, sum(duur_sec) AS duur_sec
      FROM sessie GROUP BY datum, repo, gebruiker
), gemeten AS (
    SELECT datum, repo, gebruiker, sum(actieve_sec) AS sec,
           sum(sessies) AS sessies, sum(prompts) AS prompts
      FROM ontwikkeling.cc_tijd GROUP BY datum, repo, gebruiker
), sleutel AS (
    SELECT datum, repo, gebruiker FROM ontwikkeling.git_dag
    UNION
    SELECT datum, repo, gebruiker FROM hook
    UNION
    SELECT datum, repo, gebruiker FROM gemeten
)
SELECT s.datum, s.repo, s.gebruiker, k.persoon_id,
       coalesce(g.commits, 0) AS commits,
       coalesce(g.regels_plus, 0) AS regels_plus,
       coalesce(g.regels_min, 0) AS regels_min,
       -- Sessies en prompts: de gemeten telling gaat voor, de hook vult aan.
       coalesce(m.sessies, h.sessies, 0)::bigint AS cc_sessies,
       coalesce(m.prompts, h.prompts, 0)::numeric AS cc_prompts,
       -- Wandkloktijd van de hook; blijft staan als derde, grofste signaal.
       coalesce(h.duur_sec, 0)::numeric AS cc_duur_sec,
       coalesce(m.sec, 0)::numeric AS gemeten_sec,
       coalesce(g.commit_venster_sec, 0)::numeric AS venster_sec
  FROM sleutel s
  LEFT JOIN ontwikkeling.git_dag g
         ON g.datum = s.datum AND g.repo = s.repo AND g.gebruiker = s.gebruiker
  LEFT JOIN hook h
         ON h.datum = s.datum AND h.repo = s.repo AND h.gebruiker = s.gebruiker
  LEFT JOIN gemeten m
         ON m.datum = s.datum AND m.repo = s.repo AND m.gebruiker = s.gebruiker
  LEFT JOIN ontwikkeling.gebruiker_koppeling k ON k.gebruiker = s.gebruiker;

GRANT SELECT ON ontwikkeling.dag TO portal, hr_app;
