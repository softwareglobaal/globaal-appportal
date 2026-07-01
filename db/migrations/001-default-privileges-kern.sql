-- 001 — default privileges voor schema kern.
--
-- De schema's kosten/omv/schuldentracker hebben al default privileges (zie baseline),
-- kern nog niet. Daardoor moest tot nu toe bij elke nieuwe kern-tabel handmatig een
-- GRANT gedaan worden (persoon, firma, persoon_dienstfirma...) — vergeten = stille
-- 403/500 later. Vanaf nu krijgt elke nieuwe kern-tabel automatisch SELECT voor de
-- leesrollen.

ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kern GRANT SELECT ON TABLES TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kern GRANT SELECT ON TABLES TO kosten;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kern GRANT SELECT ON TABLES TO medewerker_writer;
