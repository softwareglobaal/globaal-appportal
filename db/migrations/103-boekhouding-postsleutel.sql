-- 103: een openstaande post is pas uniek met zijn datum erbij.
--
-- Migratie 102 gebruikte (dossier_id, soort, documentnummer) als sleutel. Dat
-- leek veilig, maar Octopus nummert per dagboek per boekjaar, dus hetzelfde
-- nummer komt in een volgend boekjaar terug. Bij Contrax bestonden twee
-- leveranciersposten A1/00000002, een uit 2025 en een uit 2026. De tweede
-- overschreef de eerste bij het ophalen: een openstaande post van 749,68 euro
-- verdween zonder melding uit de spiegel.
--
-- Vanaf nu draagt `sleutel` de identiteit (documentnummer plus datum) en
-- `document` het nummer zoals het getoond wordt. De datum onderscheidt de
-- boekjaren; binnen een dagboek en een boekjaar is een nummer al uniek.
--
-- De markeringen hangen aan `sleutel` en verhuizen dus mee. Op het moment van
-- deze migratie bestaan er nog geen, dus er gaat niets verloren; staan ze er
-- later wel, dan hoort een herbouw van de sleutel ze mee te nemen.

ALTER TABLE boekhouding.post
    ADD COLUMN IF NOT EXISTS document text NOT NULL DEFAULT '';

UPDATE boekhouding.post SET document = sleutel WHERE document = '';

-- De spiegel is weggooibaar en wordt bij de eerstvolgende verversing opnieuw
-- opgebouwd, deze keer volledig. Leeggooien is eerlijker dan half oude
-- sleutels naast nieuwe laten staan.
TRUNCATE boekhouding.post;

COMMENT ON COLUMN boekhouding.post.sleutel IS
    'Identiteit van de post: documentnummer plus datum. Draagt de markeringen.';
COMMENT ON COLUMN boekhouding.post.document IS
    'Het documentnummer zoals Octopus het toont, bijvoorbeeld A1/00000002.';

-- Aantal posten dat de laatste verversing opleverde tegenover wat er beland
-- is. Loopt dat uiteen, dan is er stil iets samengevallen en hoort dat op te
-- vallen in plaats van weg te zakken.
ALTER TABLE boekhouding.verversing
    ADD COLUMN IF NOT EXISTS aantal_opgehaald integer NOT NULL DEFAULT 0;
