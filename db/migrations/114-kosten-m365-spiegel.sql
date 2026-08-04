-- 114: Microsoft 365-spiegel voor het kosten-dashboard.
--
-- Microsoft is met afstand de grootste softwarepost (18.248 euro sinds de
-- kaartdata begint), maar het dashboard kende alleen het BEDRAG, niet de
-- BEZETTING: hoeveel licenties zijn gekocht, aan wie zijn ze toegewezen en
-- welke staan leeg. De registratie zei "46 seats" terwijl Microsoft Graph
-- op 2026-08-04 melde: Business Basic 35 gekocht, 20 toegewezen, 15 leeg.
-- Dat is precies de opzeg-afweging die op de kaart als losse notitie stond.
--
-- Deze migratie zet de spiegel klaar. Net als de Octopus- en Xelion-spiegel
-- geldt: de bron (Microsoft) is de waarheid over wat er is, de curatie
-- (persoon-koppeling, soort account) is van ons en overleeft elke sync.
-- De sync (m365_sync.py in repo globaal-kosten) werkt bij met UPSERT en
-- raakt de curatiekolommen nooit aan.

CREATE TABLE kosten.m365_sku (
    sku_part    text PRIMARY KEY,              -- skuPartNumber, bv. O365_BUSINESS_ESSENTIALS
    naam        text NOT NULL,                 -- leesbare naam, bv. Microsoft 365 Business Basic
    sku_id      uuid,                          -- skuId zoals Graph hem geeft
    gekocht     integer NOT NULL DEFAULT 0,    -- prepaidUnits.enabled
    toegewezen  integer NOT NULL DEFAULT 0,    -- consumedUnits
    gesynct_op  timestamptz NOT NULL DEFAULT now()
);

-- Eén rij per (account, licentie). De sleutel is de UPN omdat dat is wat
-- Microsoft ons geeft; persoon_id is de koppeling naar de identiteits-hub
-- en blijft leeg tot iemand (of de naam-heuristiek) hem legt.
CREATE TABLE kosten.m365_licentie (
    upn           text NOT NULL,
    sku_part      text NOT NULL REFERENCES kosten.m365_sku(sku_part) ON DELETE CASCADE,
    weergavenaam  text,
    account_aan   boolean,                     -- accountEnabled
    laatste_login timestamptz,                 -- leeg zolang AuditLog.Read.All ontbreekt
    -- curatie, wordt door de sync met rust gelaten:
    persoon_id    uuid REFERENCES kern.persoon(id) ON DELETE SET NULL,
    soort         text NOT NULL DEFAULT 'onbekend'
                  CHECK (soort IN ('onbekend', 'persoon', 'gedeeld')),
    note          text,
    gesynct_op    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (upn, sku_part)
);
CREATE INDEX ix_m365_licentie_persoon ON kosten.m365_licentie (persoon_id);
CREATE INDEX ix_m365_licentie_sku ON kosten.m365_licentie (sku_part);

-- Versheid van de spiegel, zodat het dashboard kan tonen hoe oud het beeld
-- is en of de sign-in-data er al bij zat (die vereist AuditLog.Read.All in
-- Entra; zonder die permissie geeft Graph 403 op signInActivity).
CREATE TABLE kosten.m365_sync (
    id                 smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    laatste_ok         timestamptz,
    signin_beschikbaar boolean NOT NULL DEFAULT false,
    boodschap          text
);
INSERT INTO kosten.m365_sync (id) VALUES (1);

GRANT SELECT ON kosten.m365_sku, kosten.m365_licentie, kosten.m365_sync
    TO portal, communicatie, kosten;
GRANT INSERT, UPDATE, DELETE ON kosten.m365_sku, kosten.m365_licentie, kosten.m365_sync
    TO kosten;
