-- 139: Blog fase 2. De publieke site leest de gepubliceerde artikelen.
-- Aanleiding: het Blog-tabblad op het interne dashboard (migratie 137) schreef
-- naar elevait.blog, maar de site las nog alleen een markdown-bestand in git.
-- Vanaf nu: een eigen leesrol voor de website, en het ene bestaande artikel
-- uit git overgezet naar de tabel, zodat er nog maar een bron is.

-- 1. Leesrol. Alleen SELECT op elevait.blog; niets anders in het schema.
--    Wachtwoord zetten op de VM: ALTER ROLE elevait_web PASSWORD '...';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'elevait_web') THEN
        CREATE ROLE elevait_web LOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA elevait TO elevait_web;
GRANT SELECT ON elevait.blog TO elevait_web;
-- Een langlopende of hangende query van de site mag de rest niet raken.
ALTER ROLE elevait_web SET statement_timeout = '5s';
ALTER ROLE elevait_web SET idle_session_timeout = '10min';

-- 2. Het artikel dat tot nu toe als markdown in de site-repo stond
--    (src/content/blog/ai-in-suriname-waar-beginnen.md, 26-08-2026).
INSERT INTO elevait.blog (slug, titel, beschrijving, inhoud, tags, status, auteur, door,
                          gepubliceerd_op, aangemaakt_op, bijgewerkt_op)
VALUES (
  'ai-in-suriname-waar-beginnen',
  'AI in Suriname: waar u vandaag mee kunt beginnen',
  'AI is ook in Suriname geen toekomstmuziek meer. Drie processen waarmee u vandaag kunt beginnen, en wat hier wel en niet werkt.',
  $md$Kunstmatige intelligentie voelt voor veel Surinaamse ondernemers nog als iets van elders: iets voor de grote techbedrijven in Amerika, niet voor een kantoor aan de Limesgracht. Dat beeld klopt niet meer. De vraag is allang niet meer óf AI iets voor uw organisatie betekent, maar waar u het beste begint.

In dit artikel zetten we dat praktisch neer: wat AI wel en niet is, drie processen waarmee u vandaag kunt beginnen, en wat er in de Surinaamse context anders werkt dan de verhalen doen vermoeden.

## AI is geen robot die uw mensen vervangt

Het hardnekkigste misverstand is dat AI een slimme robot is die banen overneemt. In de praktijk werkt het anders. De grootste winst zit niet in het vervangen van mensen, maar in het overnemen van het werk dat niemand graag doet en dat toch elke dag af moet: gegevens overtypen, dezelfde rapportage opnieuw opmaken, facturen sorteren.

Dat is precies het werk waar uw medewerkers hun tijd niet aan willen besteden. Door dat door software te laten doen, houdt uw team tijd over voor het werk waar wél een mens voor nodig is: het klantcontact, het oordeel, de uitzonderingen. AI verschuift de aandacht, het schrapt die niet.

## Drie processen waarmee u vandaag kunt beginnen

Begin niet met een groot, allesomvattend systeem. Begin met één proces dat herkenbaar tijd kost. In de meeste Surinaamse organisaties komen drie processen steeds terug.

- **Facturatie en betalingsverwerking.** Facturen die binnenkomen via e-mail, handmatig worden overgetypt en gesorteerd. Software kan de inhoud lezen, de juiste gegevens eruit halen en het bericht naar de juiste persoon sturen.
- **Rapportages.** Overzichten die iemand elke maand opnieuw in elkaar zet uit dezelfde bronnen. Wanneer die gegevens eenmaal op een vaste plek staan, kan het overzicht zichzelf opmaken.
- **Gegevensoverdracht tussen systemen.** Informatie die van het ene pakket naar het andere moet, nu nog met kopiëren en plakken. Dit is vaak het stilste tijdverlies in een organisatie, en tegelijk het makkelijkst te automatiseren.

Wat deze drie gemeen hebben: het zijn taken met een duidelijke, terugkerende vorm. Juist daar is automatisering betrouwbaar, omdat de uitkomst voorspelbaar is.

## Wat in Suriname anders werkt

Veel wat u online leest over AI gaat uit van een Amerikaanse of Europese situatie. Hier gelden andere randvoorwaarden, en het is eerlijker om die te benoemen dan te doen alsof ze niet bestaan.

Het internet is niet overal even stabiel, en niet elke medewerker heeft dezelfde apparatuur. Betaaldiensten die in het buitenland vanzelfsprekend zijn, werken hier soms niet. Dat betekent niet dat AI niet kan; het betekent dat een oplossing die het hier moet volhouden, gebouwd moet zijn op de werkelijkheid van hier, en niet op een demo die alleen werkt onder ideale omstandigheden.

Dat is ook waarom wij niet geloven in het in één keer alles omgooien. Een oplossing die vandaag indruk maakt maar volgende maand afbrokkelt, heeft u niets aan.

## Begin klein, bouw uit

De verstandigste eerste stap is bescheiden: kies één proces, laat daar een werkende versie voor bouwen, en kijk of het in de praktijk standhoudt. Doorgaans staat zo'n eerste versie er binnen enkele weken. Werkt het, dan bouwt u van daaruit verder naar het volgende proces. Werkt het niet zoals gehoopt, dan heeft u weinig verloren.

Zo groeit AI mee met uw organisatie in plaats van dat u zich moet aanpassen aan een systeem. En elke oplossing die blijft draaien, wordt een bouwsteen waarmee de volgende stap sneller gaat.

AI is in Suriname geen belofte voor later. Voor het soort werk dat elke dag terugkomt, is het vandaag al bruikbaar. De kunst is niet om groot te dromen, maar om klein en concreet te beginnen.$md$,
  '["AI", "Suriname", "automatisering"]'::jsonb,
  'gepubliceerd',
  'Team Elevait',
  'migratie 139',
  '2026-08-26 12:00:00+00',
  '2026-08-26 12:00:00+00',
  '2026-08-26 12:00:00+00'
)
ON CONFLICT (slug) DO NOTHING;
