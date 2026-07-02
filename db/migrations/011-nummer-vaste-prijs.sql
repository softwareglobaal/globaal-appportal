-- 011 — vaste prijs op telefoonnummers.
--
-- Eerste facturatie-veld op communicatie.nummer: het vaste (maand)bedrag van het
-- abonnement, in euro. Leeg = onbekend/variabel. De volledige facturatie-
-- terminologie (doorfactureerbaar ja/nee + basis: maandelijks/vast/percentage/
-- effectief) staat op de TODO en bouwt hier later op voort.

ALTER TABLE communicatie.nummer
    ADD COLUMN vaste_prijs numeric(10,2);
