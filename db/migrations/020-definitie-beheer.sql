-- 020 — woordenboek-beheer via het Organisatie-dashboard.
--
-- De schrijfrol van de Organisatie-app mag definities toevoegen en bijwerken
-- (term + definitie; sleutels zijn stabiel en worden nooit hernoemd).
-- Bewust GEEN DELETE: een begrip verdwijnt niet — hooguit krijgt het een
-- betere definitie. Wie mag bewerken bepaalt de app (WOORDENBOEK_EDITORS,
-- default mehdi + akadmin); de rol is alleen het kanaal.

GRANT SELECT, INSERT, UPDATE ON kern.definitie TO medewerker_writer;
