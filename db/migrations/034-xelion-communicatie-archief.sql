-- 034 - Xelion-communicatielog als archief (laag 1 van het belstatistiek-plan).
--
-- Xelion produceert elke dag oproepdata waar niets mee gebeurt. Vanaf nu
-- spiegelt de poller het communicatielog incrementeel en append-only:
-- oproepen komen erbij en verdwijnen nooit. Naast de uitgeplozen velden
-- bewaren we per record de volledige ruwe API-respons (kolom ruw), zodat een
-- verkeerd geinterpreteerd veld altijd her-afleidbaar is: de tabel is het
-- archief. Offsite gaat hij vanzelf mee in de nachtelijke versleutelde
-- S3-backup. De 90 dagen uit het plan zijn alleen de backfill-diepte en de
-- trend-bril van de views (laag 2), geen bewaartermijn.
--
-- Bewust: de communicatie-rol krijgt GEEN DELETE op deze tabel (zelfde
-- principe als de audit en de run-log: een archief wist je niet). UPDATE wel,
-- want vlaggen als "bekeken" veranderen na het moment van de oproep.
-- Privacy: laag 1 slaat alleen op; er is nog geen enkele weergave. Wie wat
-- mag zien (aggregaten vs details, contentSummary) is een teambeslissing die
-- bij laag 2 hoort (zie TODO).

CREATE TABLE communicatie.xelion_communicatie (
    oid            text PRIMARY KEY,            -- Xelion-object-id
    datum          timestamptz,
    richting       text NOT NULL DEFAULT '',    -- inkomend / uitgaand / ''
    duur_sec       integer,
    status         text NOT NULL DEFAULT '',
    voicemail      boolean NOT NULL DEFAULT false,
    opname_status  text NOT NULL DEFAULT '',
    onderwerp      text NOT NULL DEFAULT '',
    genormaliseerd text NOT NULL DEFAULT '',    -- kanoniek gematcht nummer (indien gevonden)
    nummer_id      uuid REFERENCES communicatie.nummer(id) ON DELETE SET NULL,
    ruw            jsonb NOT NULL,              -- volledig API-record: het archief
    gesynct_op     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_xelion_comm_datum  ON communicatie.xelion_communicatie (datum DESC);
CREATE INDEX ix_xelion_comm_nummer ON communicatie.xelion_communicatie (nummer_id);
CREATE INDEX ix_xelion_comm_genorm ON communicatie.xelion_communicatie (genormaliseerd);

-- Sync-status: tellers op de bestaande statusrij van de Xelion-poller.
ALTER TABLE communicatie.xelion_sync
    ADD COLUMN comm_totaal    integer,
    ADD COLUMN comm_nieuwste  timestamptz,
    ADD COLUMN comm_fout      text;

-- Append-only voor de app-rol: lezen, toevoegen en vlaggen bijwerken; nooit wissen.
GRANT SELECT, INSERT, UPDATE ON communicatie.xelion_communicatie TO communicatie;
