-- 094: gemeten Claude Code-tijd per applicatie per dag
-- Aanleiding: vraag Shaniel 2026-07-29. De hook-meting (migratie 074) kent
-- twee gebreken: zij noemt de applicatie naar de MAP waarin gewerkt wordt
-- (werk vanuit een verzamelmap belandt onder een verzamelnaam), en zij meet
-- wandkloktijd tussen de eerste en laatste gebeurtenis van een sessie, dus
-- inclusief pauzes. Bovendien begint zij pas op 28-07-2026.
--
-- Deze tabel wordt gevuld door een verzamelaar op de ontwikkelmachine die de
-- Claude Code-transcripts leest: hij deelt de tijd toe aan de applicatie
-- waarvan de BESTANDEN worden aangeraakt, en telt alleen de gaten tussen
-- gebeurtenissen tot een pauzegrens. Er verlaat uitsluitend een optelsom de
-- machine: dag, applicatie, seconden, aantal sessies en prompts. Nooit
-- gespreksinhoud, nooit sessie-detail; zelfde lijn als migratie 074.

CREATE TABLE IF NOT EXISTS ontwikkeling.cc_tijd (
    datum          date NOT NULL,
    repo           text NOT NULL,
    gebruiker      text NOT NULL,
    machine        text NOT NULL DEFAULT '',
    actieve_sec    integer NOT NULL DEFAULT 0,
    sessies        integer NOT NULL DEFAULT 0,
    prompts        integer NOT NULL DEFAULT 0,
    -- Bij welke pauzelengte is gemeten; zonder dat getal is het cijfer niet
    -- te duiden (5 minuten geeft een ander antwoord dan 15).
    pauzegrens_sec integer NOT NULL DEFAULT 300,
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (datum, repo, gebruiker, machine)
);

CREATE INDEX IF NOT EXISTS ix_ontw_cc_tijd_repo
    ON ontwikkeling.cc_tijd (repo, datum);

GRANT SELECT, INSERT, UPDATE ON ontwikkeling.cc_tijd TO medewerker_writer;
GRANT SELECT ON ontwikkeling.cc_tijd TO portal, hr_app;
