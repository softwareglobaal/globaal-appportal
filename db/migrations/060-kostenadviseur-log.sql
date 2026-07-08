-- 060 - het advies-logboek van de kostenadviseur (blueprint fase 2,
-- beslissingen Shaniel 2026-07-07: on-demand lijst in het dashboard,
-- accepteer/afwijs met logging zodat het beleid controleerbaar is).
--
-- Append-only: een beslissing wordt nooit gewijzigd of verwijderd
-- (bewust geen UPDATE/DELETE-grants). Een beslissing onderdrukt hetzelfde
-- advies 60 dagen; daarna mag de adviseur het opnieuw voorstellen.

CREATE TABLE communicatie.advies_log (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nummer_id uuid NOT NULL REFERENCES communicatie.nummer(id) ON DELETE CASCADE,
    advies    text NOT NULL,
    reden     text NOT NULL DEFAULT '',
    besparing numeric,
    beslissing text NOT NULL,
    door      text NOT NULL DEFAULT '',
    op        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_advies_log_nummer ON communicatie.advies_log (nummer_id, op);
GRANT SELECT, INSERT ON communicatie.advies_log TO communicatie;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('kostenadviseur', 'Kostenadviseur',
     'De advieslijst op de Xelion-statistieken die kosten naast gebruik legt en per nummer voorstelt: afbouwen of navragen, met de redenering en de besparing per maand erbij. Geen gebruik is nooit automatisch opzeggen: doelen als WhatsApp, ItsMe of een datasim en de opzegtermijn wegen mee. Een mens accepteert of wijst af; elke beslissing wordt gelogd en onderdrukt hetzelfde advies 60 dagen.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
