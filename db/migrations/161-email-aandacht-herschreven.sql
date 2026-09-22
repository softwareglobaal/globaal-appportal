-- 161: Aandacht opnieuw gedefinieerd, nu vanuit de vraag in plaats van vanuit
-- de velden die de leverancier toevallig teruggeeft.
--
-- Aanleiding: 22-09-2026. De filterrij Aandacht had vijf items, en die zijn
-- niet gekozen maar overgebleven: one.com geeft spamFilter, autoReply, forwards
-- en diskUsage terug, en van elk veld is een knop gemaakt. Daarna is de
-- definitie geschreven zodat ze bij de knoppen paste. Dat is achterstevoren, en
-- twee van de vijf houden geen stand:
--
--   "Stuurt door" (31)      - doorsturen is normaal, 26 van de 31 blijven
--                             binnen de groep. Het is een feit, geen signaal,
--                             en het staat al in de kolom Doorsturen naar.
--   "Groter dan 1 GB" (33)  - waarvan 18 actief en in gebruik, waaronder de
--                             drukste adressen van het bedrijf. De motivering
--                             was "eerst archiveren", maar uit de facturen
--                             bleek dat opslag niets kost: het aantal
--                             postbussen is onbeperkt binnen een pakket. Voor
--                             adressen die al op elimineren staan toont de rij
--                             die hint zelf al.
--
-- Wat overblijft zijn drie uitzonderingen op 502 adressen, en alle drie kosten
-- ze iemand iets als je ze laat liggen.

BEGIN;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_aandacht', 'Aandacht',
     'De drie dingen aan een e-mailadres die nagekeken moeten worden: de spamfilter staat uit, er staat een automatisch antwoord aan, of er wordt doorgestuurd naar een domein buiten de groep. Alle drie zijn uitzonderingen op ruim vijfhonderd adressen, en alle drie kosten ze iemand iets als je ze laat liggen: ongefilterde post, een antwoord namens iemand die er niet meer werkt, of bedrijfspost die het bedrijf verlaat. Bewust géén signaal: doorsturen op zich (dat is normaal en blijft meestal binnen de groep) en de omvang van een postbus (die kost niets, want het aantal postbussen is onbeperkt binnen een pakket). Meerdere signalen aanvinken toont alles met minstens een ervan; welke signalen een adres precies heeft, staat als markering in de rij zelf.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
