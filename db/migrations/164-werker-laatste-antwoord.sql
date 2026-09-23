-- 164: Wat de server de transcriptiewerker het laatst antwoordde.
--
-- Aanleiding: op 22-09-2026 herstartte de Linux-pc en lag de transcriptie
-- vijftien uur stil zonder dat iemand het merkte. De hartslag bleef gewoon
-- binnenkomen: de oude systeemdienst draaide nog en meldde zich elke ronde,
-- maar kreeg van het versieslot terecht geen werk. Een hartslag bewijst dus
-- dat er iets leeft, niet dat er iets gebeurt.
--
-- Vandaar twee kolommen die de server zelf bijhoudt bij elke vraag om werk:
-- wanneer er het laatst gevraagd werd, en wat het antwoord was (werk, leeg,
-- pauze of verouderd). De signalen-agent leest die en slaat alarm als er werk
-- klaarligt maar niemand het krijgt, tenzij de pauze bewust aan staat.

ALTER TABLE communicatie.xelion_sync
    ADD COLUMN IF NOT EXISTS werker_laatste_vraag    timestamptz,
    ADD COLUMN IF NOT EXISTS werker_laatste_antwoord text;
