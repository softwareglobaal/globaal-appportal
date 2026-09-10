-- 147: De brein-agent moet het verschil kunnen melden tussen "er was niets te
-- doen" en "ik kon er niet bij". Tot nu toe lazen die twee hetzelfde, waardoor
-- twintig gesprekken uit juli tot september maandenlang op 'onbeoordeeld'
-- stonden terwijl elke ronde 'verwerkt=0' rapporteerde alsof alles af was.
--
-- nabel_pogingen: hoe vaak er vergeefs bij Fathom is teruggevraagd om een
-- samenvatting. Fathom maakt die bij korte opnames domweg niet, en zonder
-- teller bleef de agent daar elk uur opnieuw naar vragen.
--
-- zonder_bron: hoeveel gesprekken een ronde moest overslaan omdat er noch een
-- transcript noch een samenvatting was. Nul hoort de normale stand te zijn;
-- staat er iets anders, dan is dat een signaal en geen stilte.

ALTER TABLE elevait.gesprek
    ADD COLUMN IF NOT EXISTS nabel_pogingen integer NOT NULL DEFAULT 0;

ALTER TABLE elevait.brein_run
    ADD COLUMN IF NOT EXISTS zonder_bron integer NOT NULL DEFAULT 0;
