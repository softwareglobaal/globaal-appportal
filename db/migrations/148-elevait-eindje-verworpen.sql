-- 148: Een actiepunt kan onzin zijn. Het model haalt ruim vijf punten uit een
-- gesprek en soms is er een bij die nooit een taak was. Dat wegwerken als
-- "afgerond" vervuilt de historie: dan staat er dat iets gedaan is wat nooit
-- gedaan hoefde te worden.
--
-- Daarom verwerpen als aparte toestand. Niet hard verwijderen, om twee redenen:
-- je kunt je vergissen, en het is nuttig te kunnen zien wat het model erbij
-- verzint. Een verworpen punt verdwijnt uit de werklijst en uit alle tellingen,
-- maar blijft terug te halen.

ALTER TABLE elevait.open_eindje
    ADD COLUMN IF NOT EXISTS verworpen boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS verworpen_op timestamptz,
    ADD COLUMN IF NOT EXISTS verworpen_door text;

-- Gesprekken worden opnieuw gedestilleerd zodra een mens het oordeel wijzigt,
-- en dat wist de openstaande punten van dat gesprek voordat het model nieuwe
-- schrijft. Zonder deze index zou een verworpen punt daarbij verdwijnen en
-- meteen weer terugkomen; de destillatie slaat nu over wat al verworpen is en
-- zoekt daarvoor op gesprek en tekst.
CREATE INDEX IF NOT EXISTS ix_elevait_eindje_verworpen
    ON elevait.open_eindje (gesprek_id) WHERE verworpen;
