-- 169: status "Opgezegd" voor telefoonnummers (23-09-2026).
--
-- Op 4 september 2026 zegde Vof Unabo twintig nummers en twee gebruikers op
-- bij Franne BV; Nele Franck bevestigde op 7 september dat de stopzetting
-- aan de provider is doorgegeven en dat de facturatie vanaf de volgende
-- ronde daalt naar 12 gebruikers en 21 nummers (EUR 146 vaste kost).
-- Zo'n nummer staat nog op de trunk tot de provider het weghaalt, maar het
-- hoort niet meer mee te tellen als betalend of actief. Opgezegd is dus een
-- eigen status: zichtbaar en filterbaar, buiten de tellingen. Zodra het
-- nummer echt weg is bij de provider wordt het Vervallen.

ALTER TABLE communicatie.nummer
    DROP CONSTRAINT IF EXISTS ck_nummer_status;
ALTER TABLE communicatie.nummer
    ADD CONSTRAINT ck_nummer_status
    CHECK (status IN ('Actief', 'Niet-actief', 'Vervallen', 'Slapend', 'Opgezegd', 'Onbekend'));

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('status_opgezegd', 'Opgezegd',
     'Het nummer is bij de leverancier opgezegd en wordt niet meer aangerekend vanaf de volgende factuur, maar staat technisch nog op de centrale tot de provider het weghaalt. Telt niet mee in de cijfers; wel te filteren. Daarna wordt het Vervallen.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
