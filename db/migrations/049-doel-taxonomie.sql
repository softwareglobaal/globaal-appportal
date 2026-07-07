-- 049 - doel-taxonomie (meeting Mehdi 2026-07-06, scheidsrechter-analogie):
-- het doel wordt een uniek, telbaar begrip op categorie-niveau, zodat de
-- vraag "hoeveel office-, sales-, finance-, spoofing-, cold-calling- en
-- prive-nummers hebben we" een gewone telling wordt.
--
-- Vaste categorieen (keuze Shaniel: "Algemeen" wint van office/main number;
-- Standaardprojecten wint van Light Projects, zonder HA-prefix). Daarnaast
-- twee patroon-vormen die geen optie zijn: de collega-naam bij
-- prive-nummers en "Klantnummer [firmanaam]" bij klantnummers.
-- Wie-informatie (TKN, Buro, Tekenwerk, Energie-efficient) hoort niet in
-- het doel: die staat in gebruikt-voor.

INSERT INTO communicatie.lijst (categorie, waarde, sort_order) VALUES
    ('Doel', 'Algemeen', 10),
    ('Doel', 'Sales', 20),
    ('Doel', 'Finance', 30),
    ('Doel', 'Spoofing', 40),
    ('Doel', 'Cold calling', 50),
    ('Doel', 'B2B', 60),
    ('Doel', 'Standaardprojecten', 70),
    ('Doel', 'WhatsApp', 80)
ON CONFLICT (categorie, waarde) DO NOTHING;

UPDATE kern.definitie
   SET definitie = 'Waarvoor het nummer dient, als uniek en telbaar begrip op categorie-niveau: Algemeen (kantoor/hoofdnummer), Sales, Finance, Spoofing, Cold calling, B2B, Standaardprojecten of WhatsApp. Twee patroon-vormen daarnaast: bij prive-nummers is het doel de naam van de collega, bij klantnummers "Klantnummer [firmanaam]". Wie het nummer gebruikt hoort NIET in het doel: dat staat in gebruikt-voor. Niet "functie", dat woord is voor personen.'
 WHERE sleutel = 'doel';
