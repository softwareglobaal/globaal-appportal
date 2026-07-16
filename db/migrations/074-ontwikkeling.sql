-- 074: ontwikkel-statistieken (besluit Shaniel 2026-07-16, brainstorm).
-- Management-inzicht: hoeveel tijd en werk er via Claude Code in elke
-- applicatie is gestoken, per persoon, per applicatie, per dag. Twee
-- bronnen: de git-historie (output: commits en regels; verzamelscript op
-- de host) en Claude Code-hooks (tijd: sessies en prompts; ingest via het
-- organisatie-dashboard). Bewust GEEN sessie-detail in de weergave en
-- nooit gespreksinhoud: alleen metadata (privacy-lijn, zelfde besluit als
-- de belminuten 2026-07-04).

CREATE SCHEMA IF NOT EXISTS ontwikkeling;

-- Welke repo hoort bij welke applicatie (de app-tegel).
CREATE TABLE IF NOT EXISTS ontwikkeling.app (
    repo      text PRIMARY KEY,      -- repo-naam zonder org, bv. globaal-kosten
    naam      text NOT NULL,
    url       text NOT NULL DEFAULT ''
);

-- Wie is verantwoordelijk voor een applicatie (lijst van Shaniel; ook het
-- koppelvlak voor latere weergave per app).
CREATE TABLE IF NOT EXISTS ontwikkeling.app_verantwoordelijke (
    repo       text NOT NULL REFERENCES ontwikkeling.app(repo) ON DELETE CASCADE,
    persoon_id uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE CASCADE,
    PRIMARY KEY (repo, persoon_id)
);

-- Koppeling van een technische identiteit (git-e-mail of hook-gebruiker)
-- naar de persoon in de centrale database.
CREATE TABLE IF NOT EXISTS ontwikkeling.gebruiker_koppeling (
    gebruiker  text PRIMARY KEY,     -- genormaliseerd lowercase
    persoon_id uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE CASCADE
);

-- Bron A: git-historie, per dag geaggregeerd door scripts/ontwikkeling-verzamel.sh.
CREATE TABLE IF NOT EXISTS ontwikkeling.git_dag (
    datum       date NOT NULL,
    repo        text NOT NULL,
    gebruiker   text NOT NULL,       -- git author-e-mail, lowercase
    commits     integer NOT NULL DEFAULT 0,
    regels_plus integer NOT NULL DEFAULT 0,
    regels_min  integer NOT NULL DEFAULT 0,
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (datum, repo, gebruiker)
);

-- Bron B: ruwe hook-events van Claude Code (start/prompt/einde). Klein en
-- append-only; de weergave aggregeert altijd naar dag-niveau.
CREATE TABLE IF NOT EXISTS ontwikkeling.cc_event (
    id        bigserial PRIMARY KEY,
    sessie    text NOT NULL DEFAULT '',
    repo      text NOT NULL,
    gebruiker text NOT NULL,         -- git-e-mail of OS-gebruiker, lowercase
    event     text NOT NULL CHECK (event IN ('start', 'prompt', 'einde')),
    ts        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ontw_cc_event_dag ON ontwikkeling.cc_event (repo, ts);

-- De ene weergave-waarheid: per (dag, repo, gebruiker) beide bronnen naast
-- elkaar, met de persoon-koppeling erbij. Sessieduur = laatste minus eerste
-- event van een sessie binnen de dag (wandkloktijd van de sessie, geen
-- aandachtsmeting - bewuste, benoemde keuze).
CREATE OR REPLACE VIEW ontwikkeling.dag AS
WITH sessie AS (
    SELECT sessie, repo, gebruiker, ts::date AS datum,
           extract(epoch FROM max(ts) - min(ts))::bigint AS duur_sec,
           count(*) FILTER (WHERE event = 'prompt') AS prompts
      FROM ontwikkeling.cc_event
     GROUP BY sessie, repo, gebruiker, ts::date),
cc AS (
    SELECT datum, repo, gebruiker,
           count(*) AS cc_sessies,
           sum(prompts) AS cc_prompts,
           sum(duur_sec) AS cc_duur_sec
      FROM sessie GROUP BY 1, 2, 3)
SELECT coalesce(g.datum, cc.datum) AS datum,
       coalesce(g.repo, cc.repo) AS repo,
       coalesce(g.gebruiker, cc.gebruiker) AS gebruiker,
       k.persoon_id,
       coalesce(g.commits, 0) AS commits,
       coalesce(g.regels_plus, 0) AS regels_plus,
       coalesce(g.regels_min, 0) AS regels_min,
       coalesce(cc.cc_sessies, 0) AS cc_sessies,
       coalesce(cc.cc_prompts, 0) AS cc_prompts,
       coalesce(cc.cc_duur_sec, 0) AS cc_duur_sec
  FROM ontwikkeling.git_dag g
  FULL OUTER JOIN cc ON cc.datum = g.datum AND cc.repo = g.repo
                    AND cc.gebruiker = g.gebruiker
  LEFT JOIN ontwikkeling.gebruiker_koppeling k
       ON k.gebruiker = coalesce(g.gebruiker, cc.gebruiker);

-- Rechten: organisatie-dashboard leest (portal) en schrijft events
-- (medewerker_writer); het verzamelscript draait als db-eigenaar.
GRANT USAGE ON SCHEMA ontwikkeling TO portal, medewerker_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA ontwikkeling TO portal;
GRANT SELECT ON ontwikkeling.dag TO portal;
GRANT INSERT ON ontwikkeling.cc_event TO medewerker_writer;
GRANT SELECT ON ontwikkeling.gebruiker_koppeling TO medewerker_writer;
GRANT USAGE ON SEQUENCE ontwikkeling.cc_event_id_seq TO medewerker_writer;

-- Seed: de bekende repo-naar-app-mapping.
INSERT INTO ontwikkeling.app (repo, naam, url) VALUES
    ('globaal-appportal',       'AppPortal (stack)',      'https://globaal.be'),
    ('globaal-organisatie',     'Organisatie-dashboard',  'https://organisatie.globaal.be'),
    ('globaal-kosten',          'Kosten-dashboard',       'https://kosten.globaal.be'),
    ('globaal-communicatie',    'Communicatie-dashboard', 'https://communicatie.globaal.be'),
    ('globaal-sales',           'Sales-dashboard',        'https://sales.globaal.be'),
    ('globaal-projecten',       'Projecten',              'https://projecten.globaal.be'),
    ('globaal-vermogen',        'Vermogen',               'https://vermogen.globaal.be'),
    ('globaal-draaiboek',       'Draaiboek',              'https://draaiboek.globaal.be'),
    ('globaal-stagebeoordeling','Stagebeoordeling',       'https://stagebeoordeling.globaal.be'),
    ('globaal-factuurrouter',   'Factuurrouter',          ''),
    ('globaal-schuldentracker', 'Schuldentracker',        '')
ON CONFLICT (repo) DO NOTHING;

-- Seed: de bekende identiteiten van Shaniel (git-auteur op alle repos).
INSERT INTO ontwikkeling.gebruiker_koppeling (gebruiker, persoon_id)
SELECT v.gebruiker, p.id
  FROM (VALUES ('mch@h-architects.be'), ('shaniel')) v(gebruiker),
       kern.persoon p
 WHERE p.voornaam ILIKE 'shaniel' AND p.in_dienst
ON CONFLICT (gebruiker) DO NOTHING;
