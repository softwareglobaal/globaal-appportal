-- 070 - kaartuitgevers markeren voor de verzamelpost-reconciliatie
-- (besluit Shaniel 2026-07-15: controleerbaar maken dat elke betaalde
-- kaart-euro zowel in de afschriften als in de boekhouding zit).
--
-- De boekhouding boekt creditcard-afrekeningen als verzamelposten op de
-- kaartuitgever als tegenpartij (KBC Brussels, Mastercard-kaartnummers),
-- zonder per-leverancier-detail; dat detail leeft in de PDF-afschriften
-- (kosten.bank_transactie). Door de kaartuitgever-partijen te markeren
-- kan het kosten-dashboard beide naast elkaar leggen: afschriften-totaal
-- per maand tegenover geboekte verzamelposten, en meldt de signalen-agent
-- het wanneer die uiteenlopen.
--
-- KBC VERZEKERINGEN NV is bewust GEEN kaartuitgever (echte verzekeringen).

ALTER TABLE kern.partij ADD COLUMN is_kaartuitgever boolean NOT NULL DEFAULT false;

UPDATE kern.partij
   SET is_kaartuitgever = true
 WHERE lower(btrim(naam)) IN ('kbc brussels', 'kbc bank', 'mastercard',
                              'mastercard 8133', 'mastercard 1153',
                              'mastercard 9024');

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('kaartuitgever', 'Kaartuitgever',
     'Een partij die geen echte leverancier is maar de uitgever van een betaalkaart (KBC, Mastercard). Aankoopboekingen op zo''n partij zijn verzamelposten: een hele kaartafrekening als een document, zonder detail per leverancier. Het detail leeft in de kaartafschriften; de reconciliatie in het kosten-dashboard legt beide naast elkaar.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
