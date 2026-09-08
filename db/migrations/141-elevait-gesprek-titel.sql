-- 141: Eigen titel voor Elevait-gesprekken.
-- Negen op de tien opnames heten bij Fathom "Impromptu Zoom Meeting". Zodra
-- een mens bevestigt dat een gesprek over Elevait gaat, krijgt het een titel
-- die de inhoud dekt (model, op de samenvatting). De Fathom-titel blijft
-- bewaard in titel_fathom, zodat niets verloren gaat en het terug kan.

ALTER TABLE elevait.gesprek
    ADD COLUMN IF NOT EXISTS titel_fathom text,
    ADD COLUMN IF NOT EXISTS titel_door   text;   -- 'model na validatie' of een gebruikersnaam

COMMENT ON COLUMN elevait.gesprek.titel_fathom IS
    'Oorspronkelijke titel van Fathom, gezet zodra titel is vervangen.';
COMMENT ON COLUMN elevait.gesprek.titel_door IS
    'Wie de huidige titel heeft gezet; NULL = nog de Fathom-titel.';
