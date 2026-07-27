-- 084: vaste analyse-rapporten over de huidige Monday (wens Mehdi 27-07-2026).
--
-- Twee rapporten, eenmalig gegenereerd uit de al opgehaalde borddata en daarna
-- STATISCH bewaard: zo hoeft Claude niet bij elke vraag het hele account te
-- heranalyseren, en blijft het oordeel reproduceerbaar. Het rapport is het
-- naslagwerk waar we naar terugverwijzen ("ons boek van Monday").
--   opzet   - hoe de huidige Monday is opgebouwd
--   fouten  - waar het misgaat, tegen de anti-patterns

CREATE TABLE IF NOT EXISTS monday.rapport (
    soort          text PRIMARY KEY CHECK (soort IN ('opzet', 'fouten')),
    titel          text NOT NULL,
    inhoud         text NOT NULL,
    model          text NOT NULL DEFAULT '',
    bron           text NOT NULL DEFAULT '',   -- waarop het rapport is gebaseerd
    gegenereerd_op timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE ON monday.rapport TO monday_app;
GRANT SELECT ON monday.rapport TO portal;
