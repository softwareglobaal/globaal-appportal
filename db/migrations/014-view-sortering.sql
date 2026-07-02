-- 014 — sortering als onderdeel van de persoonlijke view.
--
-- De kolomkiezer (migratie 013) krijgt kolomvolgorde en klikbare sortering;
-- de gekozen sortering wordt per gebruiker bewaard, formaat "kolomsleutel:asc"
-- of "kolomsleutel:desc". Leeg = standaardvolgorde (land → firma → doel).

ALTER TABLE communicatie.view_instelling
    ADD COLUMN sortering text NOT NULL DEFAULT '';
