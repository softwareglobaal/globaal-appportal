-- 006 — firma-beheer vanuit het Organisatie-dashboard.
--
-- De Firma's-tab (medewerkers-app) laat een admin firma's toevoegen, hernoemen
-- en zacht uitzetten. De smalle schrijfrol krijgt daarvoor INSERT/UPDATE op
-- kern.firma (geen DELETE — uitzetten gaat via `actief`).

GRANT INSERT, UPDATE ON kern.firma TO medewerker_writer;
