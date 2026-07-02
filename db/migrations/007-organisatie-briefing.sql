-- 007 — dagbriefing van de organisatie-assistent (proactieve laag).
--
-- Eén briefing per dag: de AI vat 's ochtends (bij het eerste bezoek) de staat
-- van de organisatie-graaf + signalen samen. Opslag geeft (a) één AI-call per
-- dag i.p.v. per bezoek en (b) historie: terugbladeren wat eerder geadviseerd is.
-- Schema `organisatie` is het app-eigen spoke-schema van het Organisatie-dashboard.

CREATE SCHEMA organisatie;

CREATE TABLE organisatie.briefing (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    datum            date NOT NULL UNIQUE,
    tekst            text NOT NULL,
    aangemaakt_op    timestamptz NOT NULL DEFAULT now(),
    aangemaakt_door  text NOT NULL DEFAULT ''
);

-- Lezen: portal (dashboards). Schrijven: de smalle schrijfrol van de app
-- (INSERT + UPDATE voor de dagelijkse upsert/ververs; geen DELETE — historie blijft).
GRANT USAGE ON SCHEMA organisatie TO portal;
GRANT USAGE ON SCHEMA organisatie TO medewerker_writer;
GRANT SELECT ON organisatie.briefing TO portal;
GRANT SELECT, INSERT, UPDATE ON organisatie.briefing TO medewerker_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA organisatie
    GRANT SELECT ON TABLES TO portal;
