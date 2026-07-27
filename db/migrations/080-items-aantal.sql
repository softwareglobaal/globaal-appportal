-- 080: aantal per item in het schema `items`.
-- De meeste tweedehands toestellen zijn uniek (aantal 1), maar van kabels,
-- adapters en docks liggen er vaak meerdere identieke stuks. Het beheer toont
-- het aantal en de verkoopsite kan er later voorraad mee tonen.
-- Bestaande rijen krijgen 1, want dat is wat er tot nu toe impliciet gold.

ALTER TABLE items.products
    ADD COLUMN IF NOT EXISTS aantal integer NOT NULL DEFAULT 1;

ALTER TABLE items.products
    DROP CONSTRAINT IF EXISTS products_aantal_niet_negatief;

ALTER TABLE items.products
    ADD CONSTRAINT products_aantal_niet_negatief CHECK (aantal >= 0);
