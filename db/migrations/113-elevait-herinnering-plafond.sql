-- 113: Plafond op de herinneringen van de postkamer
-- Aanleiding: Shaniel kreeg dagenlang meldingen over een eigen testbericht
-- van 3 augustus. De herinnering aan onbeantwoorde post herhaalde zich
-- oneindig en was alleen te stoppen door op het tabblad af te vinken; in het
-- meldkanaal zelf kon je er niets mee. Zo wordt een kanaal onbruikbaar.
--
-- Vanaf nu maximaal drie herinneringen per bericht. Daarna blijft het bericht
-- gewoon op het tabblad staan, maar zwijgt het kanaal erover.

ALTER TABLE elevait.bericht
    ADD COLUMN IF NOT EXISTS zoom_gemeld_aantal integer NOT NULL DEFAULT 0;

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('herinneringsplafond', 'Herinneringsplafond',
   'Een openstaand bericht wordt hoogstens drie keer in het meldkanaal herhaald, daarna alleen nog op het tabblad getoond. Een melding die oneindig terugkomt zonder dat je hem daar kunt wegklikken, leert de lezer het hele kanaal te negeren; dan mis je ook de melding die er wel toe doet.')
ON CONFLICT (sleutel) DO NOTHING;
