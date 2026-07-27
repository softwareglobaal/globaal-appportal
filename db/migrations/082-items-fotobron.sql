-- 082: herkomst van een productfoto vastleggen.
-- Naast eigen foto's van het echte toestel halen we officiele fabrikantsfoto's op
-- via de productcatalogus (Icecat). Die twee moeten uit elkaar te houden zijn: in
-- de etalage komen eigen foto's eerst en fabrikantsbeeld krijgt een label, zodat
-- een koper niet denkt dat de glanzende catalogusfoto het toestel zelf is.
-- Bestaande foto's zijn allemaal door onszelf geupload.

ALTER TABLE items.product_images
    ADD COLUMN IF NOT EXISTS bron text NOT NULL DEFAULT 'eigen';

ALTER TABLE items.product_images
    DROP CONSTRAINT IF EXISTS product_images_bron_geldig;

ALTER TABLE items.product_images
    ADD CONSTRAINT product_images_bron_geldig
    CHECK (bron IN ('eigen', 'fabrikant'));

-- Waar de afbeelding vandaan komt, voor naslag en verantwoording.
ALTER TABLE items.product_images
    ADD COLUMN IF NOT EXISTS bron_url text;
