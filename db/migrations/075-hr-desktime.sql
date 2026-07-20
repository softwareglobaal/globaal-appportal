-- 075: HR-dashboard (HDS) op eigen benen - DeskTime-dagdata in Postgres.
--
-- Het HR-dashboard was een PowerShell-generator die de DeskTime-API dag voor
-- dag bevroeg en alles in een HTML-bestand bakte: elke verversing haalde de
-- hele periode opnieuw op (15-25 min, tot 1,5 uur). Deze tabellen zijn de
-- INCREMENTELE CACHE: een dag die eenmaal is opgehaald blijft staan, dus een
-- verversing haalt alleen de nieuwe dagen op. De weergave blijft het
-- bestaande, zelfstandige HTML-dashboard (bewuste keuze Shaniel 2026-07-20:
-- de logica zit in de HTML en dat mag zo blijven); de generator leest voortaan
-- uit deze tabellen in plaats van uit de API.
--
-- Bewust GEEN salarisdata (zelfde lijn als het dashboard zelf). De inhoud is
-- vertrouwelijke HR-data: leesrechten alleen voor de portal-rol, en de
-- AI-lagen (briefing, duiding, agenten) lezen dit schema niet.

CREATE SCHEMA IF NOT EXISTS hr;

-- De DeskTime-medewerker, met het rooster als DATA in plaats van als
-- hardgecodeerde array in het script.
CREATE TABLE IF NOT EXISTS hr.medewerker (
    desktime_id       text PRIMARY KEY,
    naam              text NOT NULL DEFAULT '',
    email             text NOT NULL DEFAULT '',
    afdeling          text NOT NULL DEFAULT '',
    persoon_id        uuid REFERENCES kern.persoon(id) ON DELETE SET NULL,
    match_status      text NOT NULL DEFAULT '',
    work_starts       text NOT NULL DEFAULT '',
    work_ends         text NOT NULL DEFAULT '',
    flex              boolean NOT NULL DEFAULT false,
    uren_week         numeric,
    -- Rooster handmatig gezet door HR? Dan overschrijft de sync het niet.
    rooster_handmatig boolean NOT NULL DEFAULT false,
    actief            boolean NOT NULL DEFAULT true,
    bijgewerkt_op     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_hr_medewerker_persoon
    ON hr.medewerker (persoon_id);

-- Eén rij per medewerker per dag. Dit is de cache: aanwezig = niet opnieuw
-- ophalen (behalve binnen het herzieningsvenster van de sync).
CREATE TABLE IF NOT EXISTS hr.dag (
    desktime_id     text NOT NULL,
    datum           date NOT NULL,
    at_work         integer NOT NULL DEFAULT 0,   -- aankomst tot vertrek
    online          integer NOT NULL DEFAULT 0,   -- actief aan de pc
    offline         integer NOT NULL DEFAULT 0,   -- handmatig ingegeven
    productief      integer NOT NULL DEFAULT 0,
    productiviteit  numeric NOT NULL DEFAULT 0,
    efficientie     numeric NOT NULL DEFAULT 0,
    voor_werk       integer NOT NULL DEFAULT 0,
    na_werk         integer NOT NULL DEFAULT 0,
    aangekomen      text NOT NULL DEFAULT '',
    vertrokken      text NOT NULL DEFAULT '',
    te_laat         boolean NOT NULL DEFAULT false,
    heeft_rooster   boolean NOT NULL DEFAULT false,
    -- Detailcall (apps + handmatige redenen) gedaan? NULL = nog niet; zo
    -- wordt een dag nooit twee keer in detail opgehaald.
    detail_op       timestamptz,
    opgehaald_op    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (desktime_id, datum)
);
CREATE INDEX IF NOT EXISTS ix_hr_dag_datum ON hr.dag (datum);

-- Handmatige (offline) tijd met reden, uit de detailcall.
CREATE TABLE IF NOT EXISTS hr.handmatig (
    desktime_id text NOT NULL,
    datum       date NOT NULL,
    reden       text NOT NULL DEFAULT '',
    seconden    integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_hr_handmatig ON hr.handmatig (desktime_id, datum);

-- App-gebruik uit de steekproefdagen (geen paginatitels, alleen app/domein).
CREATE TABLE IF NOT EXISTS hr.app_gebruik (
    desktime_id text NOT NULL,
    datum       date NOT NULL,
    app         text NOT NULL DEFAULT '',
    soort       text NOT NULL DEFAULT '',
    productief  smallint NOT NULL DEFAULT 0,   -- 1 productief, 0 neutraal, -1 niet
    categorie   text NOT NULL DEFAULT '',
    categorie_id text NOT NULL DEFAULT '',
    seconden    integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_hr_app ON hr.app_gebruik (desktime_id, datum);

-- Sync- en generatiestatus (versheid op het dashboard en in de app).
CREATE TABLE IF NOT EXISTS hr.sync (
    id             smallint PRIMARY KEY DEFAULT 1,
    laatste_run    timestamptz,
    ok             boolean,
    dagen_nieuw    integer NOT NULL DEFAULT 0,
    dagen_totaal   integer NOT NULL DEFAULT 0,
    api_calls      integer NOT NULL DEFAULT 0,
    gegenereerd_op timestamptz,
    fout           text
);
INSERT INTO hr.sync (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- Rollen: de HR-app leest en schrijft met een eigen rol; portal mag lezen
-- voor koppelingen (bv. het persoonsprofiel). Bewust geen grants aan de
-- communicatie- of kosten-rollen.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hr_app') THEN
        CREATE ROLE hr_app LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA hr TO hr_app, portal;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA hr TO hr_app;
GRANT SELECT ON ALL TABLES IN SCHEMA hr TO portal;
-- De HR-app leest kern.persoon (naam-matching) en de bestaande
-- DeskTime-spiegel, zodat de koppeling met de rest van het platform klopt.
GRANT USAGE ON SCHEMA kern, kosten TO hr_app;
GRANT SELECT ON kern.persoon, kern.afdeling, kern.firma TO hr_app;
GRANT SELECT ON kosten.desktime_medewerker TO hr_app;
