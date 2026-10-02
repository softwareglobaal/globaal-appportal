-- 182: het tweede oor voor twijfels in transcripties (communicatie).
--
-- Een twijfel van de correctie-agent ("Maddie": Mehdi of Matthew?) wordt niet
-- door een mens of een taalmodel beslist maar door het geluid: de werker knipt
-- een paar seconden rond het woord en laat Scribe opnieuw luisteren. Elke klus
-- is een fragment met een kandidaat; de uitkomst zegt of Scribe de kandidaat,
-- het origineel of iets anders hoorde.
--
-- soort:
--   pos      meetset, het juiste antwoord is de kandidaat (correctie met sterk
--            bewijs, bv. een voorstelling op de eigen lijn)
--   neg      meetset, het juiste antwoord is het origineel (een goed gehoorde
--            naam met een valse kandidaat ernaast)
--   twijfel  een echte open twijfel uit een transcript
--
-- Eerst meten op pos/neg; pas daarna beslist het tweede oor echte twijfels.

CREATE TABLE IF NOT EXISTS communicatie.oor_klus (
  id          serial PRIMARY KEY,
  soort       text NOT NULL CHECK (soort IN ('pos', 'neg', 'twijfel')),
  oid         text NOT NULL,
  regel       integer NOT NULL,
  origineel   text NOT NULL,
  kandidaat   text NOT NULL,
  bron        text NOT NULL DEFAULT '',
  kanaal      text NOT NULL DEFAULT '',
  van_sec     numeric NOT NULL,
  tot_sec     numeric NOT NULL,
  gemaakt_op  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (soort, oid, regel, origineel, kandidaat)
);

CREATE TABLE IF NOT EXISTS communicatie.oor_uitkomst (
  klus_id     integer NOT NULL REFERENCES communicatie.oor_klus(id) ON DELETE CASCADE,
  variant     text NOT NULL,
  gehoord     text NOT NULL DEFAULT '',
  uitkomst    text NOT NULL CHECK (uitkomst IN ('kandidaat', 'origineel', 'anders', 'fout')),
  fout        text NOT NULL DEFAULT '',
  gemaakt_op  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (klus_id, variant)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.oor_klus, communicatie.oor_uitkomst TO communicatie;
GRANT USAGE ON SEQUENCE communicatie.oor_klus_id_seq TO communicatie;
