-- 055 - sim-foto's bij een nummer (meeting Mehdi 2026-07-08: "alles van
-- Mega is de sim, en met de sim moeten we de foto's van de sim erop
-- zetten, omdat die heeft pin, die heeft puk").
--
-- Opslag als bytea in de database: het gaat om enkele kleine afbeeldingen
-- per simkaart (de client verkleint voor upload), en zo rijden ze
-- automatisch mee in de nachtelijke S3-backup. Bijlagen tonen in de
-- geheim-sectie van het detailpaneel: op de kaartfoto staan PIN en PUK.

CREATE TABLE communicatie.nummer_bijlage (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nummer_id     uuid NOT NULL REFERENCES communicatie.nummer(id) ON DELETE CASCADE,
    naam          text NOT NULL DEFAULT '',
    mime          text NOT NULL DEFAULT 'image/jpeg',
    data          bytea NOT NULL,
    geupload_door text NOT NULL DEFAULT '',
    geupload_op   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_nummer_bijlage_nummer ON communicatie.nummer_bijlage (nummer_id);
GRANT SELECT, INSERT, DELETE ON communicatie.nummer_bijlage TO communicatie;
