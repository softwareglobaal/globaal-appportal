-- 033 - DeskTime-spiegel: wie heeft een DeskTime-account, rechtstreeks uit de
-- DeskTime-API (eis Unified Dashboard: integreren via API's, geen handwerk).
-- Zelfde filosofie als de Xelion-belvolgorde (028): de tool is de bron van
-- waarheid over zijn eigen gebruikers; wij spiegelen read-only en matchen op
-- kern.persoon (e-mail als sterkste sleutel, voornaam als vangnet). De
-- gebruik-relatie firma-discipline leest deze spiegel mee, dus seats hoeven
-- voor DeskTime niet meer handmatig toegewezen te worden. De poller draait in
-- de Organisatie-app (schrijft als medewerker_writer); zonder DESKTIME_API_KEY
-- in .env gebeurt er niets.

CREATE TABLE kosten.desktime_medewerker (
    desktime_id  text PRIMARY KEY,
    naam         text NOT NULL DEFAULT '',
    email        text NOT NULL DEFAULT '',
    persoon_id   uuid REFERENCES kern.persoon(id) ON DELETE SET NULL,
    match_status text NOT NULL DEFAULT '',
    gesynct_op   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_desktime_medewerker_persoon ON kosten.desktime_medewerker (persoon_id);

CREATE TABLE kosten.desktime_sync (
    id          smallint PRIMARY KEY DEFAULT 1,
    laatste_run timestamptz,
    ok          boolean,
    medewerkers int,
    gekoppeld   int,
    fout        text
);

GRANT SELECT ON kosten.desktime_medewerker, kosten.desktime_sync TO portal;
GRANT SELECT, INSERT, UPDATE, DELETE ON kosten.desktime_medewerker, kosten.desktime_sync
    TO medewerker_writer;
