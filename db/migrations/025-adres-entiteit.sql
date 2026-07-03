-- 025 — adres als gelinkte kern-entiteit ("alles moet blauw", meeting 2026-07-03).
--
-- Adressen waren losse tekst per app (pand.adres, dossier.adres). Nu één
-- centrale entiteit `kern.adres` waar firma, pand en dossier naar verwijzen —
-- zodat één adres één knoop is met al zijn relaties (Second Brain) i.p.v.
-- herhaalde vrije tekst. Dedup op een genormaliseerde vorm: hetzelfde adres
-- twee keer ingevoerd = één rij, twee relaties.
--
-- Schrijven gaat via de SECURITY DEFINER-functie `kern.adres_vind_of_maak`
-- (vind-of-maak, dedup gecentraliseerd) — de app-rollen hoeven geen directe
-- INSERT op kern.adres, alleen EXECUTE. Zelfde patroon als de link-trigger
-- van migratie 012.

CREATE TABLE kern.adres (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    weergave        text NOT NULL,               -- volledige weergavevorm
    genormaliseerd  text NOT NULL UNIQUE,        -- dedup-sleutel (lower, alfanumeriek)
    straat          text NOT NULL DEFAULT '',    -- gestructureerde delen (later vulbaar)
    huisnummer      text NOT NULL DEFAULT '',
    postcode        text NOT NULL DEFAULT '',
    gemeente        text NOT NULL DEFAULT '',
    land            text NOT NULL DEFAULT '',
    lat             numeric(9,6),
    lon             numeric(9,6),
    actief          boolean NOT NULL DEFAULT true,
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_door text NOT NULL DEFAULT ''
);

-- Normalisatie: kleine letters, alleen alfanumeriek, enkele spaties.
CREATE FUNCTION kern.adres_norm(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT trim(regexp_replace(lower(coalesce(t, '')), '[^a-z0-9]+', ' ', 'g'))
$$;

-- Vind-of-maak: geeft de id van het (bestaande of nieuwe) adres terug.
CREATE FUNCTION kern.adres_vind_of_maak(p_weergave text, p_door text DEFAULT '')
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = kern, pg_temp AS $$
DECLARE
    v_norm text := kern.adres_norm(p_weergave);
    v_id   uuid;
BEGIN
    IF v_norm = '' THEN
        RETURN NULL;
    END IF;
    SELECT id INTO v_id FROM kern.adres WHERE genormaliseerd = v_norm;
    IF v_id IS NULL THEN
        BEGIN
            INSERT INTO kern.adres (weergave, genormaliseerd, bijgewerkt_door)
            VALUES (trim(p_weergave), v_norm, p_door)
            RETURNING id INTO v_id;
        EXCEPTION WHEN unique_violation THEN   -- race: intussen aangemaakt
            SELECT id INTO v_id FROM kern.adres WHERE genormaliseerd = v_norm;
        END;
    END IF;
    RETURN v_id;
END $$;

-- Audit (migratie 023 draaide al; nieuwe tabel apart aanhangen).
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON kern.adres
    FOR EACH ROW EXECUTE FUNCTION kern.audit_log();

-- ---- Koppelingen -------------------------------------------------------------
ALTER TABLE kern.firma      ADD COLUMN adres_id uuid REFERENCES kern.adres(id);
ALTER TABLE vermogen.pand   ADD COLUMN adres_id uuid REFERENCES kern.adres(id);
ALTER TABLE draaiboek.dossier ADD COLUMN adres_id uuid REFERENCES kern.adres(id);
CREATE INDEX ix_firma_adres   ON kern.firma (adres_id);
CREATE INDEX ix_pand_adres    ON vermogen.pand (adres_id);
CREATE INDEX ix_dossier_adres ON draaiboek.dossier (adres_id);

-- Backfill: bestaande vrije-tekst-adressen → entiteiten (via de dedup-functie).
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT id, adres FROM vermogen.pand WHERE coalesce(adres, '') <> '' LOOP
        UPDATE vermogen.pand SET adres_id = kern.adres_vind_of_maak(r.adres, 'backfill-025')
         WHERE id = r.id;
    END LOOP;
    FOR r IN SELECT id, adres FROM draaiboek.dossier WHERE coalesce(adres, '') <> '' LOOP
        UPDATE draaiboek.dossier SET adres_id = kern.adres_vind_of_maak(r.adres, 'backfill-025')
         WHERE id = r.id;
    END LOOP;
END $$;

-- ---- Rechten -----------------------------------------------------------------
GRANT SELECT ON kern.adres TO portal, communicatie, vermogen, draaiboek, medewerker_writer;
GRANT EXECUTE ON FUNCTION kern.adres_vind_of_maak(text, text)
    TO medewerker_writer, vermogen, draaiboek, communicatie;

-- ---- Woordenboek -------------------------------------------------------------
INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('adres', 'Adres',
 'Een fysiek adres als gelinkte entiteit (kern.adres) — niet als losse tekst. Eén adres = één knoop waar firma''s, panden en dossiers aan hangen; hetzelfde adres twee keer ingevoerd wordt automatisch samengevoegd (dedup).'),
('pand', 'Pand',
 'Een gebouw of eigendom uit het vermogen-dashboard, gekoppeld aan zijn adres en zijn eigenaar-firma.')
ON CONFLICT (sleutel) DO NOTHING;
