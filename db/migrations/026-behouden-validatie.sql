-- 026 — nummer-validatie: de "behouden"-status (meeting 2026-07-03, Mehdi).
--
-- Het register telt ~92 nummers, Xelion maar 41 — het team gaat valideren.
-- Tijdelijke werkkolom: per nummer markeren wat ermee moet gebeuren.
-- '' = nog niet beoordeeld. Kolom kan na de opschoonactie blijven (validatie-
-- status) of via een latere migratie weg.

ALTER TABLE communicatie.nummer
    ADD COLUMN behouden text NOT NULL DEFAULT ''
    CONSTRAINT ck_nummer_behouden
        CHECK (behouden IN ('', 'behouden', 'verifieren', 'elimineren'));

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('behouden', 'Behouden',
 'Tijdelijke validatiestatus voor de nummer-opschoning (register ~92 vs Xelion 41): behouden / verifiëren / elimineren; leeg = nog niet beoordeeld. Elimineren gebeurt pas ná verificatie — nooit zomaar verwijderen.')
ON CONFLICT (sleutel) DO NOTHING;
