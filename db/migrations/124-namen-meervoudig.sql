-- 124: twee soorten erbij op de namenlijst, allebei voor meer dan een waarde
-- Aanleiding: vraag Sufa 21-08-2026. "Momenteel kan je bij selectie alleen 1
-- optie kiezen. Maar bijv in het geval waarbij 1 persoon meerdere email adressen
-- gebruikt zou het handig zijn als allemaal gekozen zouden kunnen worden."
--
-- Twee verschillende behoeften, dus twee soorten:
--   multiselectie  meerdere keuzes uit een VASTE lijst opties (Notion-stijl)
--   lijst          meerdere vrije waarden, een per regel. Voor het e-mailgeval:
--                  die adressen zijn niet vooraf bekend, dus een keuzelijst
--                  helpt daar niet.
--
-- De waarde blijft in dezelfde tekstkolom staan. Bij deze twee soorten bevat
-- die een JSON-lijst; bij de andere soorten gewoon de waarde zelf. Dat scheelt
-- een tabel en houdt oude waarden geldig.

ALTER TABLE organisatie.namen_kolom DROP CONSTRAINT IF EXISTS namen_kolom_soort_check;

ALTER TABLE organisatie.namen_kolom ADD CONSTRAINT namen_kolom_soort_check
    CHECK (soort IN ('tekst', 'selectie', 'multiselectie', 'lijst',
                     'vinkje', 'datum', 'getal'));
