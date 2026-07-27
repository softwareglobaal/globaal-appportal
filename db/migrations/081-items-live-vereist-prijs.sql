-- 081: een item mag alleen op live staan met een echte prijs.
-- Zonder prijs verschijnt een toestel in de etalage met "Prijs op aanvraag",
-- wat we niet willen; live betekent te koop voor een bedrag. De regel geldt in
-- de database zelf, zodat geen enkele route eromheen kan.
-- Eerst eventuele bestaande overtreders terugzetten, anders kan de regel niet
-- toegevoegd worden. Bij het schrijven hiervan waren dat er nul.

UPDATE items.products
   SET status = 'te_controleren', bijgewerkt_op = now()
 WHERE status = 'live'
   AND (prijs_definitief_cents IS NULL OR prijs_definitief_cents <= 0);

ALTER TABLE items.products
    DROP CONSTRAINT IF EXISTS products_live_vereist_prijs;

ALTER TABLE items.products
    ADD CONSTRAINT products_live_vereist_prijs
    CHECK (status <> 'live'
           OR (prijs_definitief_cents IS NOT NULL AND prijs_definitief_cents > 0));
