-- 160: Median Selections & Consultancy als firma, en het besluit over globaal.be.
--
-- Aanleiding: besluit Shaniel 22-09-2026 na de tweede kritiekronde op het
-- e-mailregister. Twee open punten lagen bij hem, dit legt beide vast.
--
-- 1. medianselections.com had veertien adressen zonder firma omdat er geen
--    firma-record bestond. Dat record komt er nu. Naam, land en adres komen van
--    hun eigen website (medianselections.com, gelezen 22-09-2026): "Median
--    Selections & Consultancy", Limesgracht 143 Paramaribo, telefoon +597.
--    Dus Suriname, en geen ondernemingsnummer: kbo_nummer is een Belgisch
--    gegeven en blijft leeg, net als bij High Design Studio (Suriname),
--    Orvantis en Elevait NV.
--
-- 2. De prefixregel voor globaal.be gaat NIET door. De prefixen ha. (37),
--    ee. (16), tkn. (8) en hb. (5) verwijzen wel naar een firma, maar globaal.be
--    is het gedeelde groepsdomein en een prefix is geen eigendomsbewijs. De 238
--    adressen daar blijven zonder firma tot iemand ze bewust toewijst. Het
--    besluit staat in de opmerking bij het domein zodat de vraag niet over een
--    half jaar opnieuw wordt gesteld.

BEGIN;

INSERT INTO kern.firma (naam, code, land, actief) VALUES
    ('Median Selections & Consultancy', 'MEDI', 'Suriname', true)
ON CONFLICT (code) DO NOTHING;

-- Het domein hangt voortaan aan de firma, en nieuwe adressen erven hem.
UPDATE communicatie.email_domein
   SET firma_id        = (SELECT id FROM kern.firma WHERE code = 'MEDI'),
       firma_afleiden  = true,
       opmerking       = 'Firma aangemaakt op 22-09-2026 (besluit Shaniel): Median Selections & Consultancy, Paramaribo. 217,75 euro per jaar voor 1,9 GB van 50 GB, waarvan een groot deel de add-on Website Builder Premium; nakijken of die nog gebruikt wordt.',
       bijgewerkt_door = 'migratie 160',
       bijgewerkt_op   = now()
 WHERE domein = 'medianselections.com';

UPDATE communicatie.emailadres e
   SET firma_id        = (SELECT id FROM kern.firma WHERE code = 'MEDI'),
       bijgewerkt_door = 'firma uit domein',
       bijgewerkt_op   = now()
 WHERE split_part(e.adres::text, '@', 2) = 'medianselections.com'
   AND e.firma_id IS NULL;

-- Besluit vastleggen: geen prefixregel op het gedeelde groepsdomein.
UPDATE communicatie.email_domein
   SET opmerking       = 'Gedeeld groepsdomein: het domein zegt niets over de firma. Besluit Shaniel 22-09-2026: er komt GEEN prefixregel, ook niet voor ha. (37), ee. (16), tkn. (8) en hb. (5). Een prefix is geen eigendomsbewijs; deze 238 adressen krijgen hun firma als iemand ze bewust toewijst.',
       bijgewerkt_door = 'migratie 160',
       bijgewerkt_op   = now()
 WHERE domein = 'globaal.be';

COMMIT;
