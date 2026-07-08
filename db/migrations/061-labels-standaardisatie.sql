-- 061 - labels-standaardisatie (impromptu meeting Mehdi + Siyan 2026-07-08):
-- (1) "Algemene communicatie" als vaste gebruikt-voor-waarde voor algemene
--     klantcommunicatie (de WhatsApp-nummers) - einde van de wildgroei
--     office/bureau/kantoor ("dat is echt broeie broeie").
-- (2) De doel-categorie "WhatsApp" heet voortaan "Klantencommunicatie":
--     het doel mag nooit herhalen wat platform of gebruikt-voor al zegt,
--     het beschrijft wat een buitenstaander anders niet zou snappen
--     (daarom blijft "Spoofing" juist wel: zonder dat woord begrijpt
--     niemand het nummer). De doel-waarden op de nummers zelf worden
--     apart hernoemd via een data-fix met preview.

INSERT INTO communicatie.lijst (categorie, waarde, sort_order) VALUES
    ('Gebruikt voor', 'Algemene communicatie', 5)
ON CONFLICT (categorie, waarde) DO NOTHING;

UPDATE communicatie.lijst
   SET waarde = 'Klantencommunicatie'
 WHERE categorie = 'Doel' AND waarde = 'WhatsApp'
   AND NOT EXISTS (SELECT 1 FROM communicatie.lijst
                    WHERE categorie = 'Doel' AND waarde = 'Klantencommunicatie');

DELETE FROM communicatie.lijst
 WHERE categorie = 'Doel' AND waarde = 'WhatsApp';

UPDATE kern.definitie
   SET definitie = 'Waarvoor het nummer dient, als uniek en telbaar begrip op categorie-niveau: Algemeen (kantoor/hoofdnummer), Sales, Finance, Spoofing, Cold calling, B2B, Standaardprojecten of Klantencommunicatie. Het doel mag nooit herhalen wat platform of gebruikt-voor al zegt: het beschrijft in mensentaal wat een buitenstaander anders niet zou snappen (regel meeting 2026-07-08; "WhatsApp" is daarom geen doel meer, "Spoofing" juist wel). Twee patroon-vormen daarnaast: bij prive-nummers is het doel de naam van de collega, bij klantnummers "Klantnummer [firmanaam]". Wie het nummer gebruikt hoort NIET in het doel: dat staat in gebruikt-voor. Niet "functie", dat woord is voor personen.'
 WHERE sleutel = 'doel';

UPDATE kern.definitie
   SET definitie = 'Waarvoor het nummer feitelijk gebruikt wordt, gekozen uit een vaste keuzelijst: Algemene communicatie (algemene klantcommunicatie, bv. de WhatsApp-nummers), Contrax, Tekenwerk, Energie-efficient, de sales-campagnes, klanten en personen (Prive). Een vaste term, geen wildgroei: office, bureau en kantoor bestaan niet als aparte waarden (meeting 2026-07-08). Alleen invullen wanneer dat afwijkt van wie betaalt: aan jezelf hoef je niets uit te leggen. Opties beheren kan in communicatie.lijst, categorie "Gebruikt voor".'
 WHERE sleutel = 'gebruikt_voor';
