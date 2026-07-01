-- 005 — leesrecht op kern.persoon_dienstfirma voor de communicatie-rol.
--
-- Het firma-detail in het Communicatie-dashboard toont ook wie diensten
-- verricht voor de firma. persoon_dienstfirma bestond al vóór migratie 002
-- (dus buiten de default privileges van de communicatie-rol) — expliciet granten.

GRANT SELECT ON kern.persoon_dienstfirma TO communicatie;
