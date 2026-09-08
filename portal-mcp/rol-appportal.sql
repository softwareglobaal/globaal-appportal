-- GEGENEREERD door portal-mcp/genereer_rollen.py. Niet met de hand aanpassen:
-- wijzig bronnen.py en draai het script opnieuw.
--
-- Draaien vanuit ~/appportal (de rol mcp_lezer bestaat dan al uit
-- portal-mcp/rol-authentik.sql):
--   docker compose exec -T postgresql psql -U authentik -d appportal \
--       -v ON_ERROR_STOP=1 -f - < portal-mcp/rol-appportal.sql
--
-- mcp_lezer krijgt hier bewust GEEN rechten op de app-schema's. Per app en per
-- rechtenniveau is er een rol; de server wisselt daar met SET LOCAL ROLE
-- naartoe. Vergeet hij dat, dan volgt permission denied.

GRANT CONNECT ON DATABASE appportal TO mcp_lezer;
ALTER ROLE mcp_lezer NOINHERIT;

-- mcp_lezer mag hier zelf niets. Rechten liggen bij de per-app rollen; alleen
-- na SET LOCAL ROLE komt er data. Deze intrekking staat er ook voor het geval
-- een eerdere opzet wel rechtstreeks rechten heeft gegeven.
ALTER DEFAULT PRIVILEGES IN SCHEMA angela, boekhouding, communicatie, draaiboek, elevait, finance, hr, intercompany, items, kern, kosten, monday, namen, omv, ontwikkeling, organisatie, quickbooks, schuldentracker, vermogen REVOKE SELECT ON TABLES FROM mcp_lezer;
REVOKE ALL ON ALL TABLES IN SCHEMA angela, boekhouding, communicatie, draaiboek, elevait, finance, hr, intercompany, items, kern, kosten, monday, namen, omv, ontwikkeling, organisatie, quickbooks, schuldentracker, vermogen FROM mcp_lezer;
REVOKE ALL ON SCHEMA angela, boekhouding, communicatie, draaiboek, elevait, finance, hr, intercompany, items, kern, kosten, monday, namen, omv, ontwikkeling, organisatie, quickbooks, schuldentracker, vermogen FROM mcp_lezer;

-- angela-sr: angela, items
SELECT 'CREATE ROLE mcp_app_angela_sr NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_angela_sr')
\gexec

GRANT USAGE ON SCHEMA angela, items TO mcp_app_angela_sr;
GRANT SELECT ON ALL TABLES IN SCHEMA angela, items TO mcp_app_angela_sr;
GRANT mcp_app_angela_sr TO mcp_lezer;

-- boekhouding: boekhouding, monday
SELECT 'CREATE ROLE mcp_app_boekhouding NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_boekhouding')
\gexec

GRANT USAGE ON SCHEMA boekhouding, monday TO mcp_app_boekhouding;
GRANT SELECT ON ALL TABLES IN SCHEMA boekhouding, monday TO mcp_app_boekhouding;
GRANT mcp_app_boekhouding TO mcp_lezer;

-- communicatie: communicatie
SELECT 'CREATE ROLE mcp_app_communicatie NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_communicatie')
\gexec

GRANT USAGE ON SCHEMA communicatie TO mcp_app_communicatie;
GRANT SELECT ON ALL TABLES IN SCHEMA communicatie TO mcp_app_communicatie;
GRANT mcp_app_communicatie TO mcp_lezer;

-- draaiboek: draaiboek, kern
SELECT 'CREATE ROLE mcp_app_draaiboek NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_draaiboek')
\gexec

GRANT USAGE ON SCHEMA draaiboek, kern TO mcp_app_draaiboek;
GRANT SELECT ON ALL TABLES IN SCHEMA draaiboek, kern TO mcp_app_draaiboek;
REVOKE ALL ON kern.audit FROM mcp_app_draaiboek;
REVOKE ALL ON kern.audit_overzicht FROM mcp_app_draaiboek;
REVOKE ALL ON kern.persoon_afwezigheid FROM mcp_app_draaiboek;
REVOKE ALL ON kern.persoon_beloning FROM mcp_app_draaiboek;
REVOKE ALL ON kern.persoon_dienstfirma FROM mcp_app_draaiboek;
REVOKE ALL ON kern.persoon_hr FROM mcp_app_draaiboek;
REVOKE ALL ON kern.persoon_inzage FROM mcp_app_draaiboek;
GRANT mcp_app_draaiboek TO mcp_lezer;

-- draaiboek met financiele gegevens (banktransacties, kosten, audit)
SELECT 'CREATE ROLE mcp_app_draaiboek_financieel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_draaiboek_financieel')
\gexec

GRANT mcp_app_draaiboek TO mcp_app_draaiboek_financieel;
GRANT SELECT ON kern.audit TO mcp_app_draaiboek_financieel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_draaiboek_financieel;
GRANT mcp_app_draaiboek_financieel TO mcp_lezer;

-- draaiboek met personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_draaiboek_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_draaiboek_personeel')
\gexec

GRANT mcp_app_draaiboek TO mcp_app_draaiboek_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_draaiboek_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_draaiboek_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_draaiboek_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_draaiboek_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_draaiboek_personeel;
GRANT mcp_app_draaiboek_personeel TO mcp_lezer;

-- draaiboek met financiele gegevens (banktransacties, kosten, audit) + personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_draaiboek_financieel_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_draaiboek_financieel_personeel')
\gexec

GRANT mcp_app_draaiboek TO mcp_app_draaiboek_financieel_personeel;
GRANT SELECT ON kern.audit TO mcp_app_draaiboek_financieel_personeel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_draaiboek_financieel_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_draaiboek_financieel_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_draaiboek_financieel_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_draaiboek_financieel_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_draaiboek_financieel_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_draaiboek_financieel_personeel;
GRANT mcp_app_draaiboek_financieel_personeel TO mcp_lezer;

-- hr: hr, kern
SELECT 'CREATE ROLE mcp_app_hr NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_hr')
\gexec

GRANT USAGE ON SCHEMA hr, kern TO mcp_app_hr;
GRANT SELECT ON ALL TABLES IN SCHEMA kern TO mcp_app_hr;
REVOKE ALL ON kern.audit FROM mcp_app_hr;
REVOKE ALL ON kern.audit_overzicht FROM mcp_app_hr;
REVOKE ALL ON kern.persoon_afwezigheid FROM mcp_app_hr;
REVOKE ALL ON kern.persoon_beloning FROM mcp_app_hr;
REVOKE ALL ON kern.persoon_dienstfirma FROM mcp_app_hr;
REVOKE ALL ON kern.persoon_hr FROM mcp_app_hr;
REVOKE ALL ON kern.persoon_inzage FROM mcp_app_hr;
-- hr is in zijn geheel gevoelig: alleen USAGE.
REVOKE ALL ON ALL TABLES IN SCHEMA hr FROM mcp_app_hr;
GRANT mcp_app_hr TO mcp_lezer;

-- hr met financiele gegevens (banktransacties, kosten, audit)
SELECT 'CREATE ROLE mcp_app_hr_financieel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_hr_financieel')
\gexec

GRANT mcp_app_hr TO mcp_app_hr_financieel;
GRANT SELECT ON kern.audit TO mcp_app_hr_financieel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_hr_financieel;
GRANT mcp_app_hr_financieel TO mcp_lezer;

-- hr met personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_hr_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_hr_personeel')
\gexec

GRANT mcp_app_hr TO mcp_app_hr_personeel;
GRANT USAGE ON SCHEMA hr TO mcp_app_hr_personeel;
GRANT SELECT ON ALL TABLES IN SCHEMA hr TO mcp_app_hr_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_hr_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_hr_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_hr_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_hr_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_hr_personeel;
GRANT mcp_app_hr_personeel TO mcp_lezer;

-- hr met financiele gegevens (banktransacties, kosten, audit) + personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_hr_financieel_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_hr_financieel_personeel')
\gexec

GRANT mcp_app_hr TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON kern.audit TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_hr_financieel_personeel;
GRANT USAGE ON SCHEMA hr TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON ALL TABLES IN SCHEMA hr TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_hr_financieel_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_hr_financieel_personeel;
GRANT mcp_app_hr_financieel_personeel TO mcp_lezer;

-- intercompany: intercompany, kern
SELECT 'CREATE ROLE mcp_app_intercompany NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_intercompany')
\gexec

GRANT USAGE ON SCHEMA intercompany, kern TO mcp_app_intercompany;
GRANT SELECT ON ALL TABLES IN SCHEMA intercompany, kern TO mcp_app_intercompany;
REVOKE ALL ON kern.audit FROM mcp_app_intercompany;
REVOKE ALL ON kern.audit_overzicht FROM mcp_app_intercompany;
REVOKE ALL ON kern.persoon_afwezigheid FROM mcp_app_intercompany;
REVOKE ALL ON kern.persoon_beloning FROM mcp_app_intercompany;
REVOKE ALL ON kern.persoon_dienstfirma FROM mcp_app_intercompany;
REVOKE ALL ON kern.persoon_hr FROM mcp_app_intercompany;
REVOKE ALL ON kern.persoon_inzage FROM mcp_app_intercompany;
GRANT mcp_app_intercompany TO mcp_lezer;

-- intercompany met financiele gegevens (banktransacties, kosten, audit)
SELECT 'CREATE ROLE mcp_app_intercompany_financieel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_intercompany_financieel')
\gexec

GRANT mcp_app_intercompany TO mcp_app_intercompany_financieel;
GRANT SELECT ON kern.audit TO mcp_app_intercompany_financieel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_intercompany_financieel;
GRANT mcp_app_intercompany_financieel TO mcp_lezer;

-- intercompany met personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_intercompany_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_intercompany_personeel')
\gexec

GRANT mcp_app_intercompany TO mcp_app_intercompany_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_intercompany_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_intercompany_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_intercompany_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_intercompany_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_intercompany_personeel;
GRANT mcp_app_intercompany_personeel TO mcp_lezer;

-- intercompany met financiele gegevens (banktransacties, kosten, audit) + personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_intercompany_financieel_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_intercompany_financieel_personeel')
\gexec

GRANT mcp_app_intercompany TO mcp_app_intercompany_financieel_personeel;
GRANT SELECT ON kern.audit TO mcp_app_intercompany_financieel_personeel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_intercompany_financieel_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_intercompany_financieel_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_intercompany_financieel_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_intercompany_financieel_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_intercompany_financieel_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_intercompany_financieel_personeel;
GRANT mcp_app_intercompany_financieel_personeel TO mcp_lezer;

-- kosten: kosten, kern, finance
SELECT 'CREATE ROLE mcp_app_kosten NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_kosten')
\gexec

GRANT USAGE ON SCHEMA kosten, kern, finance TO mcp_app_kosten;
GRANT SELECT ON ALL TABLES IN SCHEMA kern, finance TO mcp_app_kosten;
REVOKE ALL ON kern.audit FROM mcp_app_kosten;
REVOKE ALL ON kern.audit_overzicht FROM mcp_app_kosten;
REVOKE ALL ON kern.persoon_afwezigheid FROM mcp_app_kosten;
REVOKE ALL ON kern.persoon_beloning FROM mcp_app_kosten;
REVOKE ALL ON kern.persoon_dienstfirma FROM mcp_app_kosten;
REVOKE ALL ON kern.persoon_hr FROM mcp_app_kosten;
REVOKE ALL ON kern.persoon_inzage FROM mcp_app_kosten;
-- kosten is in zijn geheel gevoelig: alleen USAGE.
REVOKE ALL ON ALL TABLES IN SCHEMA kosten FROM mcp_app_kosten;
GRANT mcp_app_kosten TO mcp_lezer;

-- kosten met financiele gegevens (banktransacties, kosten, audit)
SELECT 'CREATE ROLE mcp_app_kosten_financieel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_kosten_financieel')
\gexec

GRANT mcp_app_kosten TO mcp_app_kosten_financieel;
GRANT USAGE ON SCHEMA kosten TO mcp_app_kosten_financieel;
GRANT SELECT ON ALL TABLES IN SCHEMA kosten TO mcp_app_kosten_financieel;
GRANT SELECT ON kern.audit TO mcp_app_kosten_financieel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_kosten_financieel;
GRANT mcp_app_kosten_financieel TO mcp_lezer;

-- kosten met personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_kosten_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_kosten_personeel')
\gexec

GRANT mcp_app_kosten TO mcp_app_kosten_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_kosten_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_kosten_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_kosten_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_kosten_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_kosten_personeel;
GRANT mcp_app_kosten_personeel TO mcp_lezer;

-- kosten met financiele gegevens (banktransacties, kosten, audit) + personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_kosten_financieel_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_kosten_financieel_personeel')
\gexec

GRANT mcp_app_kosten TO mcp_app_kosten_financieel_personeel;
GRANT USAGE ON SCHEMA kosten TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON ALL TABLES IN SCHEMA kosten TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON kern.audit TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_kosten_financieel_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_kosten_financieel_personeel;
GRANT mcp_app_kosten_financieel_personeel TO mcp_lezer;

-- medewerkers: kern, organisatie, kosten
SELECT 'CREATE ROLE mcp_app_medewerkers NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_medewerkers')
\gexec

GRANT USAGE ON SCHEMA kern, organisatie, kosten TO mcp_app_medewerkers;
GRANT SELECT ON ALL TABLES IN SCHEMA kern, organisatie TO mcp_app_medewerkers;
REVOKE ALL ON kern.audit FROM mcp_app_medewerkers;
REVOKE ALL ON kern.audit_overzicht FROM mcp_app_medewerkers;
REVOKE ALL ON kern.persoon_afwezigheid FROM mcp_app_medewerkers;
REVOKE ALL ON kern.persoon_beloning FROM mcp_app_medewerkers;
REVOKE ALL ON kern.persoon_dienstfirma FROM mcp_app_medewerkers;
REVOKE ALL ON kern.persoon_hr FROM mcp_app_medewerkers;
REVOKE ALL ON kern.persoon_inzage FROM mcp_app_medewerkers;
-- kosten is in zijn geheel gevoelig: alleen USAGE.
REVOKE ALL ON ALL TABLES IN SCHEMA kosten FROM mcp_app_medewerkers;
GRANT mcp_app_medewerkers TO mcp_lezer;

-- medewerkers met financiele gegevens (banktransacties, kosten, audit)
SELECT 'CREATE ROLE mcp_app_medewerkers_financieel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_medewerkers_financieel')
\gexec

GRANT mcp_app_medewerkers TO mcp_app_medewerkers_financieel;
GRANT USAGE ON SCHEMA kosten TO mcp_app_medewerkers_financieel;
GRANT SELECT ON ALL TABLES IN SCHEMA kosten TO mcp_app_medewerkers_financieel;
GRANT SELECT ON kern.audit TO mcp_app_medewerkers_financieel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_medewerkers_financieel;
GRANT mcp_app_medewerkers_financieel TO mcp_lezer;

-- medewerkers met personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_medewerkers_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_medewerkers_personeel')
\gexec

GRANT mcp_app_medewerkers TO mcp_app_medewerkers_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_medewerkers_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_medewerkers_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_medewerkers_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_medewerkers_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_medewerkers_personeel;
GRANT mcp_app_medewerkers_personeel TO mcp_lezer;

-- medewerkers met financiele gegevens (banktransacties, kosten, audit) + personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_medewerkers_financieel_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_medewerkers_financieel_personeel')
\gexec

GRANT mcp_app_medewerkers TO mcp_app_medewerkers_financieel_personeel;
GRANT USAGE ON SCHEMA kosten TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON ALL TABLES IN SCHEMA kosten TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON kern.audit TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_medewerkers_financieel_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_medewerkers_financieel_personeel;
GRANT mcp_app_medewerkers_financieel_personeel TO mcp_lezer;

-- monday: monday
SELECT 'CREATE ROLE mcp_app_monday NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_monday')
\gexec

GRANT USAGE ON SCHEMA monday TO mcp_app_monday;
GRANT SELECT ON ALL TABLES IN SCHEMA monday TO mcp_app_monday;
GRANT mcp_app_monday TO mcp_lezer;

-- namen: namen, organisatie, kern
SELECT 'CREATE ROLE mcp_app_namen NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_namen')
\gexec

GRANT USAGE ON SCHEMA namen, organisatie, kern TO mcp_app_namen;
GRANT SELECT ON ALL TABLES IN SCHEMA namen, organisatie, kern TO mcp_app_namen;
REVOKE ALL ON kern.audit FROM mcp_app_namen;
REVOKE ALL ON kern.audit_overzicht FROM mcp_app_namen;
REVOKE ALL ON kern.persoon_afwezigheid FROM mcp_app_namen;
REVOKE ALL ON kern.persoon_beloning FROM mcp_app_namen;
REVOKE ALL ON kern.persoon_dienstfirma FROM mcp_app_namen;
REVOKE ALL ON kern.persoon_hr FROM mcp_app_namen;
REVOKE ALL ON kern.persoon_inzage FROM mcp_app_namen;
GRANT mcp_app_namen TO mcp_lezer;

-- namen met financiele gegevens (banktransacties, kosten, audit)
SELECT 'CREATE ROLE mcp_app_namen_financieel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_namen_financieel')
\gexec

GRANT mcp_app_namen TO mcp_app_namen_financieel;
GRANT SELECT ON kern.audit TO mcp_app_namen_financieel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_namen_financieel;
GRANT mcp_app_namen_financieel TO mcp_lezer;

-- namen met personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_namen_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_namen_personeel')
\gexec

GRANT mcp_app_namen TO mcp_app_namen_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_namen_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_namen_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_namen_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_namen_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_namen_personeel;
GRANT mcp_app_namen_personeel TO mcp_lezer;

-- namen met financiele gegevens (banktransacties, kosten, audit) + personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_namen_financieel_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_namen_financieel_personeel')
\gexec

GRANT mcp_app_namen TO mcp_app_namen_financieel_personeel;
GRANT SELECT ON kern.audit TO mcp_app_namen_financieel_personeel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_namen_financieel_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_namen_financieel_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_namen_financieel_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_namen_financieel_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_namen_financieel_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_namen_financieel_personeel;
GRANT mcp_app_namen_financieel_personeel TO mcp_lezer;

-- omv: omv
SELECT 'CREATE ROLE mcp_app_omv NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_omv')
\gexec

GRANT USAGE ON SCHEMA omv TO mcp_app_omv;
GRANT SELECT ON ALL TABLES IN SCHEMA omv TO mcp_app_omv;
GRANT mcp_app_omv TO mcp_lezer;

-- omv-v2: omv
SELECT 'CREATE ROLE mcp_app_omv_v2 NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_omv_v2')
\gexec

GRANT USAGE ON SCHEMA omv TO mcp_app_omv_v2;
GRANT SELECT ON ALL TABLES IN SCHEMA omv TO mcp_app_omv_v2;
GRANT mcp_app_omv_v2 TO mcp_lezer;

-- panden-dashboard: vermogen
SELECT 'CREATE ROLE mcp_app_panden_dashboard NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_panden_dashboard')
\gexec

GRANT USAGE ON SCHEMA vermogen TO mcp_app_panden_dashboard;
GRANT SELECT ON ALL TABLES IN SCHEMA vermogen TO mcp_app_panden_dashboard;
GRANT mcp_app_panden_dashboard TO mcp_lezer;

-- quickbooks: quickbooks
SELECT 'CREATE ROLE mcp_app_quickbooks NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_quickbooks')
\gexec

GRANT USAGE ON SCHEMA quickbooks TO mcp_app_quickbooks;
GRANT SELECT ON ALL TABLES IN SCHEMA quickbooks TO mcp_app_quickbooks;
GRANT mcp_app_quickbooks TO mcp_lezer;

-- vermogen: vermogen, kern
SELECT 'CREATE ROLE mcp_app_vermogen NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_vermogen')
\gexec

GRANT USAGE ON SCHEMA vermogen, kern TO mcp_app_vermogen;
GRANT SELECT ON ALL TABLES IN SCHEMA vermogen, kern TO mcp_app_vermogen;
REVOKE ALL ON kern.audit FROM mcp_app_vermogen;
REVOKE ALL ON kern.audit_overzicht FROM mcp_app_vermogen;
REVOKE ALL ON kern.persoon_afwezigheid FROM mcp_app_vermogen;
REVOKE ALL ON kern.persoon_beloning FROM mcp_app_vermogen;
REVOKE ALL ON kern.persoon_dienstfirma FROM mcp_app_vermogen;
REVOKE ALL ON kern.persoon_hr FROM mcp_app_vermogen;
REVOKE ALL ON kern.persoon_inzage FROM mcp_app_vermogen;
GRANT mcp_app_vermogen TO mcp_lezer;

-- vermogen met financiele gegevens (banktransacties, kosten, audit)
SELECT 'CREATE ROLE mcp_app_vermogen_financieel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_vermogen_financieel')
\gexec

GRANT mcp_app_vermogen TO mcp_app_vermogen_financieel;
GRANT SELECT ON kern.audit TO mcp_app_vermogen_financieel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_vermogen_financieel;
GRANT mcp_app_vermogen_financieel TO mcp_lezer;

-- vermogen met personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_vermogen_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_vermogen_personeel')
\gexec

GRANT mcp_app_vermogen TO mcp_app_vermogen_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_vermogen_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_vermogen_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_vermogen_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_vermogen_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_vermogen_personeel;
GRANT mcp_app_vermogen_personeel TO mcp_lezer;

-- vermogen met financiele gegevens (banktransacties, kosten, audit) + personeelsgegevens (beloning, verlof, hr-dossier)
SELECT 'CREATE ROLE mcp_app_vermogen_financieel_personeel NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_app_vermogen_financieel_personeel')
\gexec

GRANT mcp_app_vermogen TO mcp_app_vermogen_financieel_personeel;
GRANT SELECT ON kern.audit TO mcp_app_vermogen_financieel_personeel;
GRANT SELECT ON kern.audit_overzicht TO mcp_app_vermogen_financieel_personeel;
GRANT SELECT ON kern.persoon_beloning TO mcp_app_vermogen_financieel_personeel;
GRANT SELECT ON kern.persoon_hr TO mcp_app_vermogen_financieel_personeel;
GRANT SELECT ON kern.persoon_afwezigheid TO mcp_app_vermogen_financieel_personeel;
GRANT SELECT ON kern.persoon_inzage TO mcp_app_vermogen_financieel_personeel;
GRANT SELECT ON kern.persoon_dienstfirma TO mcp_app_vermogen_financieel_personeel;
GRANT mcp_app_vermogen_financieel_personeel TO mcp_lezer;

-- Apps die hier niet staan zijn niet leesbaar via de gedeelde
-- database. Waarom niet, staat per app in bronnen.py en komt terug in
-- het antwoord van de tool `apps`.
