-- 131: Afwezigheid Elevait (verlof/ziekte voor de loonberekening)
-- Aanleiding: gesprek Shaniel 25-08-2026. De hr.verlof_*-administratie (Google-
-- verlofdashboard) draait niet voor deze database: verlof_medewerker,
-- verlof_dag, verlof_regel en verlof_feestdag zijn alle leeg. De loon-agent
-- heeft dus een eigen, simpele bron nodig om verlof en ziekte mee te geven.
--
-- Bewust op desktime_id (niet op een verlof_medewerker-id): zo vervalt de
-- naam-koppeling met een administratie die toch leeg is, en telt afwezigheid
-- direct mee met de DeskTime-uren.
--
-- Besluit dekking: verlof en ziekte worden beide 100% doorbetaald (dekking 1).
-- De kolom staat er zodat een ander percentage later kan zonder migratie.
--
-- Ziekte is een gezondheidsgegeven. Net als de loonbedragen wordt deze tabel
-- afgeschermd van de portal-rol (Second Brain-graaf); 083 geeft die anders via
-- default privileges automatisch leesrecht.

CREATE TABLE IF NOT EXISTS elevait.afwezigheid (
    id            bigserial PRIMARY KEY,
    desktime_id   text NOT NULL,
    datum         date NOT NULL,
    soort         text NOT NULL CHECK (soort IN ('verlof', 'ziekte')),
    dekking       numeric(4,2) NOT NULL DEFAULT 1.00 CHECK (dekking BETWEEN 0 AND 1),
    door          text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now(),
    UNIQUE (desktime_id, datum)
);
CREATE INDEX IF NOT EXISTS ix_elevait_afwezigheid_mw
    ON elevait.afwezigheid (desktime_id, datum);

REVOKE SELECT ON elevait.afwezigheid FROM portal;

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('afwezigheid', 'Afwezigheid',
   'Verlof of ziekte van een medewerker op een bepaalde dag, ingevoerd op het Loon-tabblad. Telt in de loonberekening als doorbetaalde afwezigheid tegen de rooster-uren (verlof en ziekte beide 100%). Los van de DeskTime-uren: op een afwezige dag verwacht de loonlijst geen gewerkte uren en geeft hij geen gat-signaal.')
ON CONFLICT (sleutel) DO NOTHING;
