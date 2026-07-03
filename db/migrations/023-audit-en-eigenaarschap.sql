-- 023 — data governance, laag 1: audit-trail op databaseniveau + data-eigenaarschap.
--
-- AUDIT (kern.audit, append-only): élke INSERT/UPDATE/DELETE op de menselijk
-- beheerde tabellen wordt door triggers vastgelegd met wie (db-rol + optioneel
-- app-gebruiker), wanneer, welke rij, en de volledige oude/nieuwe waarden (jsonb).
-- Daarmee is "wie heeft dit veld veranderd en wat stond er eerst?" altijd
-- beantwoordbaar, en is een foute wijziging chirurgisch terug te draaien.
--   - De app-rollen kunnen de audit NIET schrijven of wijzigen: alleen de
--     triggerfunctie (SECURITY DEFINER) schrijft; lezen mag alleen portal.
--   - communicatie.geheim (PIN/PUK) wordt bewust ALLEEN als metadata geauditeerd
--     (actie + rij, géén waarden) — geheimen horen nergens gekopieerd te worden.
--   - Machine-geschreven tabellen (fathom-meetings, briefing, run_stap_log,
--     finalisatie) worden niet getriggerd: die hebben al eigen herkomst/append-only.
--   - `app.gebruiker` (de mens) is optioneel: apps kunnen per transactie
--     `SET LOCAL app.gebruiker = '<username>'` zetten (vervolgstap per app);
--     tot die tijd geeft de db-rol + de bijgewerkt_door-kolommen in oud/nieuw
--     voldoende houvast.
--
-- EIGENAARSCHAP (kern.data_domein): elk datadomein krijgt een menselijke
-- eigenaar (data steward). Geseed met lege eigenaars — invullen gebeurt in
-- overleg met de collega's; de Second Brain kan "domein zonder eigenaar"
-- later als signaal melden.

-- ---- Audit-tabel -------------------------------------------------------------
CREATE TABLE kern.audit (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    op            timestamptz NOT NULL DEFAULT now(),
    rol           text NOT NULL,           -- db-rol die schreef (welke app)
    app_gebruiker text,                    -- Authentik-username, indien doorgegeven
    tabel         text NOT NULL,           -- schema.tabel
    rij_id        text,                    -- id van de rij (NULL bij koppeltabellen)
    actie         text NOT NULL,           -- INSERT / UPDATE / DELETE
    oud           jsonb,                   -- volledige oude rij (UPDATE/DELETE)
    nieuw         jsonb                    -- volledige nieuwe rij (INSERT/UPDATE)
);
CREATE INDEX ix_audit_tabel_rij ON kern.audit (tabel, rij_id, op DESC);
CREATE INDEX ix_audit_op ON kern.audit (op DESC);

-- Alleen portal mag lezen; app-rollen expliciet niets (default privileges in
-- kern zouden anders SELECT geven).
GRANT SELECT ON kern.audit TO portal;
REVOKE ALL ON kern.audit FROM communicatie, vermogen, draaiboek, medewerker_writer;

-- ---- Triggerfuncties ----------------------------------------------------------
CREATE FUNCTION kern.audit_log() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = kern, pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO kern.audit (rol, app_gebruiker, tabel, rij_id, actie, oud)
        VALUES (session_user, current_setting('app.gebruiker', true),
                TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
                to_jsonb(OLD) ->> 'id', TG_OP, to_jsonb(OLD));
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO kern.audit (rol, app_gebruiker, tabel, rij_id, actie, oud, nieuw)
        VALUES (session_user, current_setting('app.gebruiker', true),
                TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
                to_jsonb(NEW) ->> 'id', TG_OP, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
    ELSE
        INSERT INTO kern.audit (rol, app_gebruiker, tabel, rij_id, actie, nieuw)
        VALUES (session_user, current_setting('app.gebruiker', true),
                TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
                to_jsonb(NEW) ->> 'id', TG_OP, to_jsonb(NEW));
        RETURN NEW;
    END IF;
END $$;

-- Metadata-variant: registreert dat er iets gebeurde, nooit de inhoud (geheimen).
CREATE FUNCTION kern.audit_log_meta() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = kern, pg_temp AS $$
BEGIN
    INSERT INTO kern.audit (rol, app_gebruiker, tabel, rij_id, actie)
    VALUES (session_user, current_setting('app.gebruiker', true),
            TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
            to_jsonb(COALESCE(NEW, OLD)) ->> 'id', TG_OP);
    RETURN COALESCE(NEW, OLD);
END $$;

-- ---- Triggers aanhangen (bestaat een tabel niet, dan melding + overslaan) -----
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        -- kern (de hub — hier is een fout het gevaarlijkst)
        'kern.persoon', 'kern.firma', 'kern.afdeling', 'kern.leverancier',
        'kern.definitie', 'kern.persoon_dienstfirma',
        -- communicatie
        'communicatie.nummer', 'communicatie.nummer_gebruiker',
        'communicatie.emailadres', 'communicatie.emailadres_gebruiker',
        'communicatie.lijst',
        -- kosten
        'kosten.software', 'kosten.account', 'kosten.seat',
        'kosten.charge_actual', 'kosten.firma',
        -- vermogen
        'vermogen.pand', 'vermogen.verzekering', 'vermogen.lening',
        'vermogen.syndicus',
        -- draaiboek (run_stap_log niet: zelf al append-only historie)
        'draaiboek.draaiboek', 'draaiboek.fase', 'draaiboek.stap',
        'draaiboek.veld', 'draaiboek.conditie_regel', 'draaiboek.dossier',
        'draaiboek.run', 'draaiboek.run_stap', 'draaiboek.veldwaarde',
        -- organisatie: alleen wat mensen bewerken
        'organisatie.meeting_actiepunt'
    ]
    LOOP
        IF to_regclass(t) IS NOT NULL THEN
            EXECUTE format(
                'CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON %s '
                'FOR EACH ROW EXECUTE FUNCTION kern.audit_log()', t);
        ELSE
            RAISE NOTICE 'audit: tabel % bestaat niet, overgeslagen', t;
        END IF;
    END LOOP;
END $$;

-- geheim: alleen metadata (nooit PIN/PUK-waarden in de audit)
DO $$
BEGIN
    IF to_regclass('communicatie.geheim') IS NOT NULL THEN
        CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE
            ON communicatie.geheim
            FOR EACH ROW EXECUTE FUNCTION kern.audit_log_meta();
    END IF;
END $$;

-- ---- Data-eigenaarschap --------------------------------------------------------
CREATE TABLE kern.data_domein (
    domein               text PRIMARY KEY,
    omschrijving         text NOT NULL DEFAULT '',
    eigenaar_persoon_id  uuid REFERENCES kern.persoon(id),  -- NULL = nog toe te wijzen
    bijgewerkt_op        timestamptz NOT NULL DEFAULT now()
);
GRANT UPDATE ON kern.data_domein TO medewerker_writer;  -- toewijzen via Organisatie-app (later)

INSERT INTO kern.data_domein (domein, omschrijving) VALUES
('personen',      'kern.persoon + afdelingen en firma-koppelingen — de identiteitsbron'),
('firmas',        'kern.firma incl. KBO-nummers'),
('terminologie',  'kern.definitie + DEFINITIEBOEK (nu feitelijk: Mehdi/akadmin)'),
('telefonie',     'communicatie.nummer + gebruikers/belvolgorde + geheimen'),
('emailadressen', 'communicatie.emailadres + gebruikers'),
('kosten',        'kosten-schema: software, seats, werkelijke kosten'),
('vermogen',      'panden, verzekeringen, leningen, syndici'),
('draaiboeken',   'draaiboek-sjablonen (proces-eigenaar per draaiboek staat op de sjabloonrij)');
