-- 028 — Xelion-belvolgorde: spiegel van de call queue uit de telefooncentrale.
--
-- De communicatie-app heeft een achtergrond-poller (standaard UIT, aan via
-- XELION_ENABLED=true op app-communicatie) die de belvolgorde uit de Xelion-API
-- leest en hier neerlegt. Twee tabellen:
--   1. xelion_belvolgorde — per lijn+positie wie er in de queue staat, met
--      best-effort koppeling naar communicatie.nummer (op genormaliseerd nummer)
--      en kern.persoon; match_status zegt hoe de koppeling tot stand kwam.
--   2. xelion_sync — één rij met de laatste poll-run (wanneer, ok/fout, tellers),
--      zodat het dashboard kan tonen hoe vers de Xelion-kolom is.
-- De app-kant staat al live en degradeert netjes zolang deze tabellen ontbreken.
-- Context: docs/XELION-HANDOFF-STACKREPO.md en docs/XELION-INTEGRATIE.md in de
-- communicatie-repo.

BEGIN;

CREATE TABLE IF NOT EXISTS communicatie.xelion_belvolgorde (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  xelion_line_oid text,
  xelion_nummer   text NOT NULL DEFAULT '',
  genormaliseerd  text NOT NULL DEFAULT '',
  positie         int  NOT NULL,
  xelion_naam     text NOT NULL DEFAULT '',
  nummer_id       uuid REFERENCES communicatie.nummer(id) ON DELETE SET NULL,
  persoon_id      uuid REFERENCES kern.persoon(id)        ON DELETE SET NULL,
  match_status    text NOT NULL DEFAULT '',
  gesynct_op      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_xelion_belvolgorde_nummer ON communicatie.xelion_belvolgorde (nummer_id);
CREATE INDEX IF NOT EXISTS ix_xelion_belvolgorde_genorm ON communicatie.xelion_belvolgorde (genormaliseerd);

CREATE TABLE IF NOT EXISTS communicatie.xelion_sync (
  id           smallint PRIMARY KEY DEFAULT 1,
  laatste_run  timestamptz,
  ok           boolean,
  lijnen       int,
  leden        int,
  gekoppeld    int,
  fout         text
);

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.xelion_belvolgorde TO communicatie;
GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.xelion_sync        TO communicatie;

COMMIT;
