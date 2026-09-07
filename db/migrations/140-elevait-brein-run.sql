-- 140: Brein-agent. Ophalen en destilleren van Elevait-gesprekken draait
-- vanaf nu automatisch (elevait-brein-agent, elk uur). Elke ronde laat een
-- rij achter, zodat het tabblad Gesprekken laat zien of de agent nog leeft
-- en waarom een ronde mislukte. Rechten voor elevait_app komen uit de
-- default privileges van migratie 083.

CREATE TABLE IF NOT EXISTS elevait.brein_run (
    id          bigserial PRIMARY KEY,
    begonnen_op timestamptz NOT NULL DEFAULT now(),
    klaar_op    timestamptz,
    nieuw       integer NOT NULL DEFAULT 0,   -- nieuwe gesprekken opgehaald
    bijgewerkt  integer NOT NULL DEFAULT 0,   -- bestaande bijgewerkt
    nagebeld    integer NOT NULL DEFAULT 0,   -- lege samenvattingen alsnog gevuld
    verwerkt    integer NOT NULL DEFAULT 0,   -- geclassificeerd/gedestilleerd
    fout        text                          -- NULL = geslaagd
);
CREATE INDEX IF NOT EXISTS ix_elevait_brein_run_begonnen
    ON elevait.brein_run (begonnen_op DESC);

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('brein-agent', 'Brein-agent',
   'De agent die de Second Brain bijhoudt: elk uur nieuwe gesprekken bij Fathom ophalen, classificeren op relevantie voor Elevait en destilleren tot beslissingen en open eindjes. Elke ronde staat in elevait.brein_run, met de fout als hij mislukte.')
ON CONFLICT (sleutel) DO NOTHING;
