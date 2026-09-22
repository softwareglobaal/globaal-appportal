-- 154: items - intern artikelnummer en verkoopstatistieken.
--
-- Twee vragen uit het overleg van 21-09-2026 met Mehdi:
--   1. elk artikel moet een intern nummer krijgen dat je op het toestel kunt
--      plakken en in een gesprek kunt noemen, los van de database-id;
--   2. we moeten kunnen zien wat er snel weggaat en wat blijft liggen
--      ("soms verkoop je iets meteen, soms staat het zes maanden").
--
-- Het nummer wordt door de database zelf gezet, en de statuswissels worden
-- door de database zelf gelogd. Zo tellen ook wijzigingen via de MCP-tools of
-- met de hand mee, en hoeft de app op geen enkele plek iets te onthouden.

-- ---------------------------------------------------------------------------
-- 1. Intern artikelnummer: A-00042
-- ---------------------------------------------------------------------------
ALTER TABLE items.products ADD COLUMN IF NOT EXISTS artikelnummer text;

UPDATE items.products
   SET artikelnummer = 'A-' || lpad(id::text, 5, '0')
 WHERE artikelnummer IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_items_products_artikelnummer
    ON items.products (artikelnummer);

CREATE OR REPLACE FUNCTION items.zet_artikelnummer() RETURNS trigger AS $$
BEGIN
    -- NEW.id is hier al gevuld: kolomstandaarden gaan voor BEFORE-triggers.
    IF NEW.artikelnummer IS NULL OR btrim(NEW.artikelnummer) = '' THEN
        NEW.artikelnummer := 'A-' || lpad(NEW.id::text, 5, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_items_artikelnummer ON items.products;
CREATE TRIGGER tr_items_artikelnummer
    BEFORE INSERT ON items.products
    FOR EACH ROW EXECUTE FUNCTION items.zet_artikelnummer();

-- ---------------------------------------------------------------------------
-- 2. Verkoopmoment en verkoopprijs op het artikel zelf
-- ---------------------------------------------------------------------------
ALTER TABLE items.products ADD COLUMN IF NOT EXISTS verkocht_op timestamptz;
ALTER TABLE items.products ADD COLUMN IF NOT EXISTS verkocht_prijs_cents integer;

CREATE OR REPLACE FUNCTION items.zet_verkocht() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'verkocht' AND OLD.status IS DISTINCT FROM 'verkocht' THEN
        NEW.verkocht_op := coalesce(NEW.verkocht_op, now());
        NEW.verkocht_prijs_cents := coalesce(NEW.verkocht_prijs_cents,
                                             NEW.prijs_definitief_cents);
    ELSIF NEW.status IS DISTINCT FROM 'verkocht' AND OLD.status = 'verkocht' THEN
        -- Teruggedraaid: dan is er ook geen verkoop geweest.
        NEW.verkocht_op := NULL;
        NEW.verkocht_prijs_cents := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_items_verkocht ON items.products;
CREATE TRIGGER tr_items_verkocht
    BEFORE UPDATE OF status ON items.products
    FOR EACH ROW EXECUTE FUNCTION items.zet_verkocht();

-- Bestaande verkochte artikelen: bijgewerkt_op is het beste dat we hebben.
UPDATE items.products
   SET verkocht_op = bijgewerkt_op,
       verkocht_prijs_cents = prijs_definitief_cents
 WHERE status = 'verkocht' AND verkocht_op IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Statuslog: de bron voor doorlooptijden
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items.status_log (
    id            bigserial PRIMARY KEY,
    product_id    bigint NOT NULL REFERENCES items.products(id) ON DELETE CASCADE,
    van           text,
    naar          text NOT NULL,
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_items_status_log_product
    ON items.status_log (product_id, naar);

CREATE OR REPLACE FUNCTION items.log_status() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO items.status_log (product_id, van, naar)
        VALUES (NEW.id, NULL, NEW.status);
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO items.status_log (product_id, van, naar)
        VALUES (NEW.id, OLD.status, NEW.status);
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_items_status_log ON items.products;
CREATE TRIGGER tr_items_status_log
    AFTER INSERT OR UPDATE OF status ON items.products
    FOR EACH ROW EXECUTE FUNCTION items.log_status();

-- Terugwerkend vullen voor wat er al staat, zodat de cijfers niet bij nul
-- beginnen. Meer dan dit weten we niet: de wissels zelf zijn nooit bewaard.
INSERT INTO items.status_log (product_id, van, naar, aangemaakt_op)
SELECT p.id, NULL, 'live', coalesce(p.gepubliceerd_op, p.aangemaakt_op)
  FROM items.products p
 WHERE p.gepubliceerd_op IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM items.status_log l
                    WHERE l.product_id = p.id AND l.naar = 'live');

INSERT INTO items.status_log (product_id, van, naar, aangemaakt_op)
SELECT p.id, NULL, p.status, coalesce(p.verkocht_op, p.bijgewerkt_op)
  FROM items.products p
 WHERE p.status <> 'live'
   AND NOT EXISTS (SELECT 1 FROM items.status_log l
                    WHERE l.product_id = p.id AND l.naar = p.status);

-- ---------------------------------------------------------------------------
-- Rechten (zelfde patroon als 079)
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON items.status_log TO items_writer;
GRANT USAGE, SELECT ON SEQUENCE items.status_log_id_seq TO items_writer;
GRANT SELECT ON items.status_log TO portal;
