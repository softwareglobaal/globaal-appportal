-- 013 — "gebruikt voor" + per-gebruiker dashboard-views (meeting 2026-07-02).
--
-- 1. Derde firma-dimensie op een telefoonnummer (DEFINITIEBOEK):
--      gefactureerd aan  = wie de factuur van de leverancier krijgt (Unabo),
--      doorfactureren naar = aan wie wij de kost doorrekenen,
--      gebruikt voor     = voor welk bedrijf/dossier het nummer feitelijk werkt
--                          (het Contacts-voorbeeld van Mehdi). Firma-dropdown,
--                          geen vrije tekst; klant-entiteiten volgen later.
-- 2. Opslaanbare kolomkeuze per ingelogde gebruiker ("view van Mehdi" vs
--    "view van Siyan"): alles zit in het dashboard, de view kiest wat je ziet.
--    Rechten via de bestaande default privileges van migratie 002.

ALTER TABLE communicatie.nummer
    ADD COLUMN gebruikt_voor_firma_id uuid REFERENCES kern.firma(id);
CREATE INDEX ix_nummer_gebruikt_voor ON communicatie.nummer (gebruikt_voor_firma_id);

CREATE TABLE communicatie.view_instelling (
    gebruikersnaam text PRIMARY KEY,          -- Authentik-username uit de proxy
    kolommen       text NOT NULL DEFAULT '',  -- komma-gescheiden kolomsleutels; leeg = standaard
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now()
);
