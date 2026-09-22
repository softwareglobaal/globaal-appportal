-- 156: beoordeling van e-mailadressen (behouden / verifieren / elimineren).
--
-- Aanleiding: kritiekronde 22-09-2026 op het e-mailregister. Na migratie 155
-- kon je 88 adressen eruit filteren die uitgezet en leeg zijn, maar er
-- vervolgens niets mee doen behalve ze een voor een openen. Het register moet
-- een beslissing kunnen vasthouden, zodat het opruimen een lijst met een
-- oordeel wordt in plaats van een lijst met een gevoel.
--
-- Zelfde drieluik als bij nummers (migratie 026, kolom nummer.behouden):
-- behouden, verifieren, elimineren, en leeg voor "nog te beoordelen". Bewust
-- geen vierde waarde "archiveren": dat is geen oordeel maar een stap binnen
-- elimineren, en de app leidt het zelf af (elimineren + meer dan 1 GB = eerst
-- archiveren). Twee woorden voor hetzelfde oordeel op twee tabbladen zou
-- precies de inconsistentie zijn waar de kritiek over ging.
--
-- Wie het oordeel gaf en wanneer staat erbij: de audittrigger op de tabel
-- legt de wijziging vast, maar wie de lijst leest wil het in de rij zien.

BEGIN;

ALTER TABLE communicatie.emailadres
    ADD COLUMN behouden       text NOT NULL DEFAULT '',
    ADD COLUMN beoordeeld_door text NOT NULL DEFAULT '',
    ADD COLUMN beoordeeld_op   timestamptz;

ALTER TABLE communicatie.emailadres
    ADD CONSTRAINT emailadres_behouden_check
    CHECK (behouden IN ('', 'behouden', 'verifieren', 'elimineren'));

CREATE INDEX ix_emailadres_behouden ON communicatie.emailadres (behouden);

COMMENT ON COLUMN communicatie.emailadres.behouden IS
    'Beoordeling bij het opruimen: behouden, verifieren, elimineren; leeg = nog te beoordelen.';

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_behouden', 'Beoordeling',
     'Wat er met het e-mailadres moet gebeuren: behouden (blijft), verifieren (eerst navragen bij de eigenaar of de firma), elimineren (mag weg). Leeg betekent nog niet beoordeeld. Zelfde drieluik als de validatie van nummers. Een postbus van meer dan 1 GB die op elimineren staat, wordt eerst gearchiveerd en dan pas verwijderd. Verwijderen in dit register haalt alleen de registratie weg, nooit de mailbox bij de leverancier.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
