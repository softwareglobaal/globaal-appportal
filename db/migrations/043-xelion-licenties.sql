-- 043 - spiegel van het Xelion-licenses-endpoint (verkenning 2026-07-06).
--
-- De API geeft geen kosten (bewezen: 0 kostvelden in 720 archiefrecords,
-- alle facturatie-endpoints 404), maar wel de kostendrager: licenties met
-- max en gebruikt. Twee signalen in de Second Brain leven hierop:
--   1. gebruikerslicenties vol (12/12): nieuwe medewerker vereist eerst een
--      licentie bij Businesscom - weten voor de onboarding, niet erop;
--   2. betaald maar ongebruikt (max > gebruikt): het DeskTime-seats-signaal,
--      maar dan voor telefonie.
-- Full-refresh-spiegel, zelfde patroon als xelion_gebruiker. De vele
-- feature-vlaggen (max 0 of onbekend) worden wel gespiegeld maar wegen
-- nergens mee: alleen telbare licenties (max > 0) voeden signalen.

CREATE TABLE communicatie.xelion_licentie (
    naam         text PRIMARY KEY,
    soort        text NOT NULL DEFAULT '',
    per_user     boolean NOT NULL DEFAULT false,
    actief       boolean NOT NULL DEFAULT true,
    max_aantal   integer,
    gebruikt     integer,
    gesynct_op   timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.xelion_licentie TO communicatie;
