-- 022 — schema `draaiboek`: het draaiboek-platform (ontwerp v2, docs/ontwerp-
-- draaiboek-datamodel.md; ★-einddoel op de TODO).
--
-- Sjabloon-kant: draaiboek → fase → stap, plus veld (kickoff/stapvelden) en
-- conditie_regel (kickoff-antwoord → conditie-label). Run-kant: dossier → run →
-- run_stap (SNAPSHOT van de stap: lopende runs blijven waar bij sjabloon-
-- wijzigingen) + veldwaarde + run_stap_log (append-only — historie telt).
-- Onderaan: seed van het eerste draaiboek "Veiligheidscoördinatie"
-- (KB 25/01/2001, uit de deep-research van 2026-07-03).
--
-- LET OP: vereist de rol `draaiboek` (db/roles.sql) — eerst aanmaken.

CREATE SCHEMA draaiboek;

-- ---- Sjabloon-kant ----------------------------------------------------------
CREATE TABLE draaiboek.draaiboek (
    id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam                       text NOT NULL,
    omschrijving               text NOT NULL DEFAULT '',
    proces_eigenaar_persoon_id uuid REFERENCES kern.persoon(id),
    actief                     boolean NOT NULL DEFAULT true,
    bijgewerkt_op              timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door            text NOT NULL DEFAULT ''
);

CREATE TABLE draaiboek.fase (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    draaiboek_id uuid NOT NULL REFERENCES draaiboek.draaiboek(id) ON DELETE CASCADE,
    naam         text NOT NULL,
    volgorde     integer NOT NULL
);
CREATE INDEX ix_fase_draaiboek ON draaiboek.fase (draaiboek_id, volgorde);

CREATE TABLE draaiboek.stap (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fase_id             uuid NOT NULL REFERENCES draaiboek.fase(id) ON DELETE CASCADE,
    naam                text NOT NULL,
    omschrijving        text NOT NULL DEFAULT '',   -- de instructie (hoe/waarmee)
    volgorde            integer NOT NULL,
    soort               text NOT NULL DEFAULT 'taak'
        CONSTRAINT ck_stap_soort CHECK (soort IN ('taak', 'goedkeuring', 'document', 'mijlpaal')),
    hangt_af_van_stap_id uuid REFERENCES draaiboek.stap(id),
    conditie            text NOT NULL DEFAULT '',   -- leeg = altijd; anders conditie-label
    resultaat           text NOT NULL DEFAULT '',   -- op te leveren (bv. "werfverslag")
    rol_hint            text NOT NULL DEFAULT '',
    termijn_dagen       integer,                    -- richtdeadline t.o.v. run-start
    verplicht           boolean NOT NULL DEFAULT true
);
CREATE INDEX ix_stap_fase ON draaiboek.stap (fase_id, volgorde);

CREATE TABLE draaiboek.veld (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    draaiboek_id uuid NOT NULL REFERENCES draaiboek.draaiboek(id) ON DELETE CASCADE,
    stap_id      uuid REFERENCES draaiboek.stap(id),  -- NULL = kickoff-veld
    naam         text NOT NULL,                        -- machinesleutel, bv. 'oppervlakte'
    label        text NOT NULL,                        -- weergave
    type         text NOT NULL DEFAULT 'tekst'
        CONSTRAINT ck_veld_type CHECK (type IN ('tekst', 'getal', 'ja_nee', 'keuze', 'datum')),
    opties       text[] NOT NULL DEFAULT '{}',
    verplicht    boolean NOT NULL DEFAULT false,
    volgorde     integer NOT NULL DEFAULT 0
);
CREATE INDEX ix_veld_draaiboek ON draaiboek.veld (draaiboek_id, volgorde);

CREATE TABLE draaiboek.conditie_regel (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    draaiboek_id uuid NOT NULL REFERENCES draaiboek.draaiboek(id) ON DELETE CASCADE,
    veld_id      uuid NOT NULL REFERENCES draaiboek.veld(id) ON DELETE CASCADE,
    operator     text NOT NULL
        CONSTRAINT ck_regel_operator CHECK (operator IN ('>=', '<', '=', 'bevat')),
    waarde       text NOT NULL,
    label        text NOT NULL   -- conditie-label dat waar wordt (bv. 'groot_project')
);

-- ---- Run-kant ---------------------------------------------------------------
CREATE TABLE draaiboek.dossier (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    naam            text NOT NULL,
    adres           text NOT NULL DEFAULT '',
    firma_id        uuid REFERENCES kern.firma(id),
    actief          boolean NOT NULL DEFAULT true,
    aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
    aangemaakt_door text NOT NULL DEFAULT ''
);
-- Licht; gaat later op in de kern-projectentiteit (extra FK, geen breuk).

CREATE TABLE draaiboek.run (
    id                           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id                   uuid NOT NULL REFERENCES draaiboek.dossier(id),
    draaiboek_id                 uuid NOT NULL REFERENCES draaiboek.draaiboek(id),
    verantwoordelijke_persoon_id uuid REFERENCES kern.persoon(id),
    labels                       text[] NOT NULL DEFAULT '{}',  -- geëvalueerde condities
    status                       text NOT NULL DEFAULT 'lopend'
        CONSTRAINT ck_run_status CHECK (status IN ('lopend', 'afgerond', 'gestopt')),
    gestart_op                   timestamptz NOT NULL DEFAULT now(),
    afgerond_op                  timestamptz,
    aangemaakt_door              text NOT NULL DEFAULT ''
);
CREATE INDEX ix_run_dossier ON draaiboek.run (dossier_id);

CREATE TABLE draaiboek.run_stap (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                   uuid NOT NULL REFERENCES draaiboek.run(id) ON DELETE CASCADE,
    stap_id                  uuid REFERENCES draaiboek.stap(id),  -- afkomst; NULL = handmatig toegevoegd
    fase_naam                text NOT NULL DEFAULT '',            -- snapshot
    naam                     text NOT NULL,                       -- snapshot
    omschrijving             text NOT NULL DEFAULT '',            -- snapshot
    soort                    text NOT NULL DEFAULT 'taak',        -- snapshot
    resultaat                text NOT NULL DEFAULT '',            -- snapshot
    volgorde                 integer NOT NULL,
    hangt_af_van_run_stap_id uuid REFERENCES draaiboek.run_stap(id),
    toegewezen_aan_persoon_id uuid REFERENCES kern.persoon(id),
    deadline                 date,
    status                   text NOT NULL DEFAULT 'open'
        CONSTRAINT ck_run_stap_status CHECK (status IN ('open', 'bezig', 'klaar', 'overgeslagen')),
    resultaat_verwijzing     text NOT NULL DEFAULT '',
    notitie                  text NOT NULL DEFAULT ''
);
CREATE INDEX ix_run_stap_run ON draaiboek.run_stap (run_id, volgorde);

CREATE TABLE draaiboek.veldwaarde (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      uuid NOT NULL REFERENCES draaiboek.run(id) ON DELETE CASCADE,
    veld_id     uuid NOT NULL REFERENCES draaiboek.veld(id),
    run_stap_id uuid REFERENCES draaiboek.run_stap(id),
    waarde      text NOT NULL DEFAULT ''
);
CREATE INDEX ix_veldwaarde_run ON draaiboek.veldwaarde (run_id);

CREATE TABLE draaiboek.run_stap_log (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_stap_id uuid NOT NULL REFERENCES draaiboek.run_stap(id) ON DELETE CASCADE,
    status      text NOT NULL,
    door        text NOT NULL,
    op          timestamptz NOT NULL DEFAULT now(),
    notitie     text NOT NULL DEFAULT ''
);
CREATE INDEX ix_run_stap_log ON draaiboek.run_stap_log (run_stap_id, op DESC);

-- ---- Rechten ----------------------------------------------------------------
GRANT USAGE ON SCHEMA kern TO draaiboek;
GRANT SELECT ON kern.persoon, kern.afdeling, kern.firma, kern.definitie TO draaiboek;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kern GRANT SELECT ON TABLES TO draaiboek;

GRANT USAGE ON SCHEMA draaiboek TO draaiboek;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA draaiboek TO draaiboek;
-- Append-only afgedwongen: de log mag alleen gelezen en toegevoegd worden.
REVOKE UPDATE ON draaiboek.run_stap_log FROM draaiboek;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA draaiboek
    GRANT SELECT, INSERT, UPDATE ON TABLES TO draaiboek;

GRANT USAGE ON SCHEMA draaiboek TO portal;
GRANT SELECT ON ALL TABLES IN SCHEMA draaiboek TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA draaiboek
    GRANT SELECT ON TABLES TO portal;

-- ---- Seed: draaiboek "Veiligheidscoördinatie" (KB 25/01/2001) -----------------
DO $$
DECLARE
    db_id uuid;
    f0 uuid; f1 uuid; f2 uuid; f3 uuid; f4 uuid;
    v_opp uuid; v_aann uuid; v_risico uuid; v_mand uuid; v_arch uuid;
    s_aanstel_ontwerp uuid; s_plananalyse uuid; s_risico uuid;
    s_vgp uuid; s_vgp_klein uuid; s_aanstel_verwez uuid;
BEGIN
    INSERT INTO draaiboek.draaiboek (naam, omschrijving, bijgewerkt_door)
    VALUES ('Veiligheidscoördinatie',
            'Veiligheidscoördinatie voor tijdelijke of mobiele bouwplaatsen (KB 25/01/2001). '
            'Het kickoff-formulier bepaalt automatisch het klein- of groot-projectpad (grens 500 m²).',
            'seed-022')
    RETURNING id INTO db_id;

    -- Kickoff-velden
    INSERT INTO draaiboek.veld (draaiboek_id, naam, label, type, verplicht, volgorde)
    VALUES (db_id, 'oppervlakte', 'Totale oppervlakte (m²)', 'getal', true, 1) RETURNING id INTO v_opp;
    INSERT INTO draaiboek.veld (draaiboek_id, naam, label, type, verplicht, volgorde)
    VALUES (db_id, 'aantal_aannemers', 'Aantal aannemers (gelijktijdig of achtereenvolgens)', 'getal', true, 2) RETURNING id INTO v_aann;
    INSERT INTO draaiboek.veld (draaiboek_id, naam, label, type, verplicht, volgorde)
    VALUES (db_id, 'verhoogd_risico', 'Werken met verhoogd risico (art. 26 §1)?', 'ja_nee', true, 3) RETURNING id INTO v_risico;
    INSERT INTO draaiboek.veld (draaiboek_id, naam, label, type, verplicht, volgorde)
    VALUES (db_id, 'mandagen', 'Geraamd aantal mandagen', 'getal', false, 4) RETURNING id INTO v_mand;
    INSERT INTO draaiboek.veld (draaiboek_id, naam, label, type, verplicht, volgorde)
    VALUES (db_id, 'architect', 'Is er een architect betrokken?', 'ja_nee', false, 5) RETURNING id INTO v_arch;

    -- Conditie-regels
    INSERT INTO draaiboek.conditie_regel (draaiboek_id, veld_id, operator, waarde, label) VALUES
    (db_id, v_opp, '>=', '500', 'groot_project'),
    (db_id, v_opp, '<', '500', 'klein_project'),
    (db_id, v_mand, '>=', '5000', 'coordinatiestructuur'),
    (db_id, v_risico, '=', 'ja', 'verhoogd_risico');

    -- Fases
    INSERT INTO draaiboek.fase (draaiboek_id, naam, volgorde) VALUES (db_id, 'Intake & aanstelling', 0) RETURNING id INTO f0;
    INSERT INTO draaiboek.fase (draaiboek_id, naam, volgorde) VALUES (db_id, 'Ontwerpfase (VC-ontwerp)', 1) RETURNING id INTO f1;
    INSERT INTO draaiboek.fase (draaiboek_id, naam, volgorde) VALUES (db_id, 'Aanbesteding & gunning', 2) RETURNING id INTO f2;
    INSERT INTO draaiboek.fase (draaiboek_id, naam, volgorde) VALUES (db_id, 'Verwezenlijkingsfase (VC-verwezenlijking)', 3) RETURNING id INTO f3;
    INSERT INTO draaiboek.fase (draaiboek_id, naam, volgorde) VALUES (db_id, 'Oplevering & overdracht', 4) RETURNING id INTO f4;

    -- Fase 0 — Intake & aanstelling
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, resultaat, rol_hint, termijn_dagen)
    VALUES (f0, 'Overeenkomst veiligheidscoördinatie opstellen en laten ondertekenen',
            'Overeenkomst tussen opdrachtgever/architect en de veiligheidscoördinator.',
            1, 'document', 'ondertekende overeenkomst', 'administratie', 7);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, rol_hint, termijn_dagen)
    VALUES (f0, 'Veiligheidscoördinator-ontwerp aanstellen',
            'Bij < 500 m² stelt de architect (bouwdirectie-ontwerp) aan; bij ≥ 500 m² de opdrachtgever.',
            2, 'taak', 'architect / opdrachtgever', 7)
    RETURNING id INTO s_aanstel_ontwerp;
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, rol_hint, termijn_dagen)
    VALUES (f0, 'Dossier openen en administratieve gegevens verzamelen',
            'Projectgegevens, betrokken partijen, contactpersonen.', 3, 'taak', 'veiligheidscoördinator', 7);

    -- Fase 1 — Ontwerpfase
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, hangt_af_van_stap_id, rol_hint, termijn_dagen)
    VALUES (f1, 'Plananalyse en plaatsbezoek',
            'Ontwerpplannen analyseren; veiligheid vanaf de tekenplank integreren.',
            1, 'taak', s_aanstel_ontwerp, 'veiligheidscoördinator', 21)
    RETURNING id INTO s_plananalyse;
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, hangt_af_van_stap_id, resultaat, rol_hint, termijn_dagen)
    VALUES (f1, 'Risicoanalyse opstellen',
            'Risico''s van het ontwerp en de latere uitvoering in kaart brengen.',
            2, 'taak', s_plananalyse, 'risicoanalyse', 'veiligheidscoördinator', 30)
    RETURNING id INTO s_risico;
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, hangt_af_van_stap_id, conditie, resultaat, rol_hint, termijn_dagen)
    VALUES (f1, 'Veiligheids- en gezondheidsplan (VGP) opstellen — volledig',
            'Volledig VGP conform bijlage I deel A: risicoanalyse, preventiemaatregelen, raming duur.',
            3, 'document', s_risico, 'groot_project', 'VGP', 'veiligheidscoördinator', 45)
    RETURNING id INTO s_vgp;
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, hangt_af_van_stap_id, conditie, resultaat, rol_hint, termijn_dagen)
    VALUES (f1, 'Vereenvoudigd VGP opstellen',
            'Inventaris van gevaren + risicobeoordeling (vereenvoudigde regeling < 500 m²). Bij beperkt belang zonder verhoogd risico mag een schriftelijke overeenkomst volstaan (art. 29).',
            4, 'document', s_risico, 'klein_project', 'vereenvoudigd VGP', 'veiligheidscoördinator', 45)
    RETURNING id INTO s_vgp_klein;
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, resultaat, rol_hint, termijn_dagen)
    VALUES (f1, 'Postinterventiedossier (PID) openen',
            'Structurele/essentiële elementen; blijft bij het gebouw gedurende de hele levensduur.',
            5, 'document', 'geopend PID', 'veiligheidscoördinator', 45);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, conditie, resultaat, rol_hint, termijn_dagen)
    VALUES (f1, 'Coördinatiedagboek openen',
            'Genummerde, onwisbare bladzijden (verplicht ≥ 500 m²).',
            6, 'document', 'groot_project', 'coördinatiedagboek', 'veiligheidscoördinator', 45);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, conditie, resultaat, rol_hint, termijn_dagen)
    VALUES (f1, 'Schriftelijke inkennisstelling opstellen',
            'Vervangt het coördinatiedagboek bij < 500 m².',
            7, 'document', 'klein_project', 'inkennisstelling', 'veiligheidscoördinator', 45);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, rol_hint, termijn_dagen)
    VALUES (f1, 'VGP als afzonderlijk deel in bestek/prijsaanvraag opnemen',
            'Zodat aannemers de preventiemaatregelen apart begroten.', 8, 'taak', 'veiligheidscoördinator', 60);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, rol_hint, termijn_dagen)
    VALUES (f1, 'Advies aan opdrachtgever over de offertes',
            'Conformiteit preventiemaatregelen beoordelen; een tweede persoon keurt goed.',
            9, 'goedkeuring', 'veiligheidscoördinator', 75);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, resultaat, rol_hint, termijn_dagen)
    VALUES (f1, 'Overdracht ontwerpdocumenten aan de opdrachtgever',
            'Einde opdracht VC-ontwerp (art. 12): VGP, PID en dagboek/inkennisstelling overdragen.',
            10, 'goedkeuring', 'overdrachtsbewijs', 'veiligheidscoördinator', 90);

    -- Fase 2 — Aanbesteding & gunning
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, rol_hint, termijn_dagen)
    VALUES (f2, 'Aannemersdocumenten en prijsberekening preventiemaatregelen nazien',
            'Conformiteit met het VGP controleren.', 1, 'taak', 'veiligheidscoördinator', 100);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, conditie, resultaat, rol_hint, termijn_dagen)
    VALUES (f2, 'Werfmelding (voorafgaande kennisgeving) indienen',
            'Minstens 15 dagen vóór opening van de bouwplaats aan de toezichthoudende ambtenaar.',
            2, 'document', 'groot_project', 'werfmelding', 'veiligheidscoördinator', 110);

    -- Fase 3 — Verwezenlijkingsfase
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, rol_hint, termijn_dagen)
    VALUES (f3, 'Veiligheidscoördinator-verwezenlijking aanstellen',
            'De werken mogen pas starten ná de aanstelling (art. 15).', 1, 'taak', 'opdrachtgever / architect', 115)
    RETURNING id INTO s_aanstel_verwez;
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, hangt_af_van_stap_id, resultaat, rol_hint, termijn_dagen)
    VALUES (f3, 'VGP aanpassen en verspreiden',
            'VGP actualiseren naar de werkelijke uitvoering en verspreiden naar de betrokken partijen.',
            2, 'document', s_aanstel_verwez, 'geactualiseerd VGP', 'veiligheidscoördinator', 125);
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, resultaat, rol_hint)
    VALUES (f3, 'Werfbezoek uitvoeren en werfverslag opstellen',
            'HERHALEND: dupliceer deze stap per bezoek (kritieke fasen: graafwerken, ruwbouw, dak, technieken). Verslag verspreiden naar opdrachtgever, hoofdaannemer en architect.',
            3, 'document', 'werfverslag', 'veiligheidscoördinator');
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, conditie, rol_hint)
    VALUES (f3, 'Coördinatiedagboek bijhouden',
            'Prestaties, vergaderingen, vaststellingen, tekortkomingen — doorlopend.',
            4, 'taak', 'groot_project', 'veiligheidscoördinator');
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, rol_hint)
    VALUES (f3, 'Tekortkomingen schriftelijk melden',
            'Aan opdrachtgever en betrokken aannemers; opvolgen tot ze verholpen zijn.',
            5, 'taak', 'veiligheidscoördinator');
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, resultaat, rol_hint)
    VALUES (f3, 'PID aanvullen',
            'As-built-plannen, technische fiches, instructies voor latere werken.',
            6, 'document', 'aangevuld PID', 'veiligheidscoördinator');
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, conditie, rol_hint)
    VALUES (f3, 'Coördinatiestructuur samenroepen en voorzitten',
            'Verplicht bij > 5000 mandagen of > €2,5 mln met ≥ 3 aannemers gelijktijdig.',
            7, 'taak', 'coordinatiestructuur', 'veiligheidscoördinator');

    -- Fase 4 — Oplevering & overdracht
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, resultaat, rol_hint)
    VALUES (f4, 'Geactualiseerd VGP overdragen',
            'Bij (voorlopige) oplevering aan de opdrachtgever.', 1, 'goedkeuring', 'geactualiseerd VGP',
            'veiligheidscoördinator');
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, conditie, resultaat, rol_hint)
    VALUES (f4, 'Coördinatiedagboek afsluiten en overdragen',
            'Tegen ontvangstbewijs.', 2, 'goedkeuring', 'groot_project', 'afgesloten dagboek', 'veiligheidscoördinator');
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort, resultaat, rol_hint)
    VALUES (f4, 'PID overdragen tegen ontvangstbewijs',
            'Het PID blijft bij het gebouw, ook bij verkoop (art. 48).', 3, 'goedkeuring', 'ontvangstbewijs', 'veiligheidscoördinator');
    INSERT INTO draaiboek.stap (fase_id, naam, omschrijving, volgorde, soort)
    VALUES (f4, 'Dossier afronden', 'Alle documenten overgedragen; run afronden.', 4, 'mijlpaal');
END $$;
