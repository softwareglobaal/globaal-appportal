-- App-rollen voor de appportal-database (cluster-niveau; niet in de baseline-dump).
-- Draai op een VERSE cluster vóór 000-baseline.sql (de grants daarin verwijzen ernaar).
-- ⚠ Vervang de CHANGE_ME-wachtwoorden in een LOKALE kopie; commit nooit echte wachtwoorden.
-- Idempotent: bestaande rollen worden overgeslagen (wachtwoord wijzig je met ALTER ROLE / \password).

DO $$
BEGIN
  -- Read-only leesrol voor de dashboards (medewerkers-app e.a.).
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'portal') THEN
    CREATE ROLE portal LOGIN PASSWORD 'CHANGE_ME';
  END IF;

  -- Kosten-dashboard: lezen op kern, schrijven op eigen schema kosten.
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kosten') THEN
    CREATE ROLE kosten LOGIN PASSWORD 'CHANGE_ME';
  END IF;

  -- Smalle schrijfrol medewerkers-app: enkel persoon.werkgever_firma_id (UPDATE)
  -- + de koppeltabel persoon_dienstfirma (INSERT/DELETE). Grants staan in de baseline.
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'medewerker_writer') THEN
    CREATE ROLE medewerker_writer LOGIN PASSWORD 'CHANGE_ME';
  END IF;
END $$;
