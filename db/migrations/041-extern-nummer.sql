-- 041 - de externe partij (beller/gebelde) als echte kolom in het archief.
--
-- Tot nu toe werd de klant per oproep op leesmoment uit het ruwe record
-- geparsed; voor veelbeller-statistieken en de externe-contacten-laag in de
-- Second Brain moet het een kolom zijn. Zelfde extractieketen als de
-- drill-down, live geverifieerd:
--   1. deelnemers (beantwoorde gesprekken): eerste adres dat niet ons eigen
--      registernummer is, plus de naam uit het Xelion-adresboek;
--   2. het terugbelnummer uit het detail-record;
--   3. het pijl-patroon in commonName (gemiste oproepen:
--      "Lijnnaam <- +32..., datum"); "Onbekend" blijft leeg = echt anoniem.
-- De kanonieke nummervorm bestaat nu ook als SQL-functie, zodat databank en
-- poller dezelfde regels hanteren.

CREATE FUNCTION communicatie.canoniek_nummer(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN d LIKE '00%' THEN substr(d, 3)
        WHEN d LIKE '0%'  THEN '32' || substr(d, 2)
        ELSE d
    END
    FROM (SELECT regexp_replace(coalesce(t, ''), '\D', '', 'g') AS d) x
$$;

ALTER TABLE communicatie.xelion_communicatie
    ADD COLUMN extern_nummer text NOT NULL DEFAULT '',
    ADD COLUMN extern_naam   text NOT NULL DEFAULT '';
CREATE INDEX ix_xelion_comm_extern
    ON communicatie.xelion_communicatie (extern_nummer)
    WHERE extern_nummer <> '';

-- Backfill 1: uit de deelnemers (verrijkte, beantwoorde gesprekken). De naam
-- vervalt als hij zelf gewoon het nummer is (Xelion vult dat soms zo).
UPDATE communicatie.xelion_communicatie c
   SET extern_nummer = k.adres,
       extern_naam   = coalesce(k.naam, '')
  FROM (
        SELECT x.oid,
               btrim(d.p->>'address') AS adres,
               CASE WHEN communicatie.canoniek_nummer(d.p->'addressable'->>'commonName')
                         = communicatie.canoniek_nummer(d.p->>'address')
                    THEN NULL
                    ELSE NULLIF(btrim(d.p->'addressable'->>'commonName'), '')
               END AS naam,
               row_number() OVER (PARTITION BY x.oid ORDER BY d.volgorde) AS rn
          FROM communicatie.xelion_communicatie x
          CROSS JOIN LATERAL jsonb_array_elements(x.ruw->'participants')
               WITH ORDINALITY AS d(p, volgorde)
         WHERE x.extern_nummer = ''
           AND jsonb_typeof(x.ruw->'participants') = 'array'
           AND communicatie.canoniek_nummer(d.p->>'address') <> ''
           AND communicatie.canoniek_nummer(d.p->>'address') <>
               coalesce((SELECT communicatie.canoniek_nummer(n.telefoonnummer)
                           FROM communicatie.nummer n WHERE n.id = x.nummer_id), '')
       ) AS k
 WHERE k.oid = c.oid AND k.rn = 1;

-- Backfill 2: het terugbelnummer uit het detail-record.
UPDATE communicatie.xelion_communicatie c
   SET extern_nummer = btrim(c.ruw->>'callbackPhoneNumber')
 WHERE c.extern_nummer = ''
   AND btrim(coalesce(c.ruw->>'callbackPhoneNumber', ''))
       ~ '^\+?[0-9][0-9 ()./-]{6,18}[0-9]$'
   AND communicatie.canoniek_nummer(c.ruw->>'callbackPhoneNumber') <>
       coalesce((SELECT communicatie.canoniek_nummer(n.telefoonnummer)
                   FROM communicatie.nummer n WHERE n.id = c.nummer_id), '');

-- Backfill 3: het pijl-patroon in commonName (gemiste oproepen).
UPDATE communicatie.xelion_communicatie c
   SET extern_nummer = btrim(substring(c.ruw->>'commonName' FROM '(?:<-|->) *([^,]+)'))
 WHERE c.extern_nummer = ''
   AND c.ruw->>'commonName' ~ '(?:<-|->)'
   AND btrim(substring(c.ruw->>'commonName' FROM '(?:<-|->) *([^,]+)'))
       ~ '^\+?[0-9][0-9 ()./-]{6,18}[0-9]$'
   AND communicatie.canoniek_nummer(substring(c.ruw->>'commonName' FROM '(?:<-|->) *([^,]+)')) <>
       coalesce((SELECT communicatie.canoniek_nummer(n.telefoonnummer)
                   FROM communicatie.nummer n WHERE n.id = c.nummer_id), '');
