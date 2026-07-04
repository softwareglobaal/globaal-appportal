-- 038 - Xelion-gebruikers gemapt aan kern + beller per oproep
-- (besluit 2026-07-04: belminuten per persoon, personeelsmonitoring akkoord).
--
-- Twee bouwstenen die de keten sluiten oproep -> Xelion-gebruiker -> persoon:
--   1. communicatie.xelion_gebruiker: spiegel van het users-endpoint met de
--      match naar kern.persoon (zelfde principes als DeskTime: nooit gokken).
--   2. gebruiker_oid op het oproep-archief: wie het gesprek voerde
--      (userProfile uit het detail-record). De backfill hieronder haalt hem
--      met terugwerkende kracht uit de ruwe records - daarvoor is het
--      archief er.

CREATE TABLE communicatie.xelion_gebruiker (
    oid            text PRIMARY KEY,
    gebruikersnaam text NOT NULL DEFAULT '',
    naam           text NOT NULL DEFAULT '',
    persoon_id     uuid REFERENCES kern.persoon(id) ON DELETE SET NULL,
    match_status   text NOT NULL DEFAULT '',
    gesynct_op     timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.xelion_gebruiker TO communicatie;

ALTER TABLE communicatie.xelion_communicatie
    ADD COLUMN gebruiker_oid text;
CREATE INDEX ix_xelion_comm_gebruiker
    ON communicatie.xelion_communicatie (gebruiker_oid);

-- Backfill uit het ruwe archief: verrijkte records hebben userProfile al.
UPDATE communicatie.xelion_communicatie
   SET gebruiker_oid = ruw->'userProfile'->>'oid'
 WHERE gebruiker_oid IS NULL
   AND ruw ? 'userProfile';
