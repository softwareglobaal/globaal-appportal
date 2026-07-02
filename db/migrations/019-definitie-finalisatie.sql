-- 019 — woordenboek: finalisatie + KBO-nummer als begrippen (migratie 018 bouwde ze).

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('finalisatie', 'Finalisatie',
 'Het kwaliteitsstempel op data: een collega heeft de knoop gecontroleerd en goedgekeurd, vastgelegd met wie en wanneer (append-only — historie telt). Blauw = gefinaliseerd, rood = nog niet. Geen slot: data blijft bewerkbaar.'),
('kbo_nummer', 'KBO-nummer',
 'Het ondernemingsnummer van een firma in de Kruispuntbank van Ondernemingen — de sleutel naar officiële bronnen zoals KBO Public Search en de NBB-jaarrekeningen.');
