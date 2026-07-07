-- 050 - HR terug in de doel-lijst (verdween in de terugdraai van de
-- doel-hermapping): rekruteringsverkeer is telbaar en komt voor (HDS-HR,
-- MEDIAN Sollicitanten). De lijst dient nu als invoer-dropdown voor het
-- handmatige datawerk; vrije tekst blijft mogelijk voor wat nog onduidelijk
-- is, tot alles verzameld is en het veld dropdown-only wordt.

INSERT INTO communicatie.lijst (categorie, waarde, sort_order)
VALUES ('Doel', 'HR', 55)
ON CONFLICT (categorie, waarde) DO NOTHING;
