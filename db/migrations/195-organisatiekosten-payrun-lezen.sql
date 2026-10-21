-- 195: Organisatie kosten leest het loonwerkblad van Payrun (loon.payrun_werkblad).
--
-- Waarom: de factuur Suriname moet per maand rekenen met wat echt uitbetaald werd op de gewerkte uren
-- ("te betalen" per loonperiode, 16de tot 15de), met de commissies erbij. Tot nu rekende Organisatie kosten met
-- het vaste contractloon uit de kostenplaat (Siyan, 21-10-2026).
--
-- Alleen lezen. Organisatie kosten toont nooit een loon per persoon: het loon gaat alleen in de kost per firma.

GRANT USAGE ON SCHEMA loon TO doorbelasting_app;
GRANT SELECT (versie, doc, gewijzigd) ON loon.payrun_werkblad TO doorbelasting_app;
