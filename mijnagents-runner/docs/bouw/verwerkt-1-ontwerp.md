# Verwerking overleg 1 (ontwerp afdeling Bouw), 30-10-2026, Claude 1

- X1, K2: twee agents, `aannemerszoeker` en `offertevergelijker`, in een nieuwe afdeling `bouw`. Zonder firma HA of HB
  stopt de ronde meteen (verslag "vraag onvolledig", geen model). De lege afdeling `harmoniebouw` blijft ongemoeid
  (K1 niet aangenomen, dus niets verwijderd en geen vraag). Een losse product- of materiaalprijs blijft bij De
  Prijsonderzoeker; zo staat het in beide werkwijzen.
- X2, G2: de vraag heeft vaste velden (firma, werk, omvang, gemeente of postcode, straal, tegen wanneer, project). De
  zoeker kijkt eerst in de bronnen van die ene firma (mapnamen in haar eigen Dropbox-mappen, en haar Octopus-relaties
  op btw-nummer), dan op het web. Een kandidaat staat bovenaan alleen met een gelezen eigen pagina en een gelezen
  KBO-pagina die actief toont; zonder KBO-bewijs komt hij onder "nog na te kijken", buiten de straal apart. Het
  ondernemingsnummer moet de modulo 97-controle halen. Inhoudingsplicht staat bij Harmonie Bouw als "niet
  gecontroleerd" met de handeling erbij (automatisch later, X7). Geen register in v1; later alleen firmacode,
  partij_id, vak, regio, bewijs en datum.
- X3, G3, K3: een mail per kandidaat, alleen als tekst in het verslag op het bord. De code bouwt de mail uit een vast
  sjabloon per firma (`bouw/mail.py`); het model schrijft alleen de werkomschrijving. `bouw/scheiding.py` toetst het
  onderwerp, de tekst en de afzender vlak voor het klaarzetten; een geweigerde mail bestaat niet en wordt een nood.
  Afzendergegevens: kern.firma heeft geen mailadres of telefoon, dus die staan in het sjabloon met hun bron (de mails
  van standaard@, de map van Harmonie Bouw); naar kern als die velden er komen.
- X4, G4: de vergelijker neemt firma plus project en lot, of een Dropbox-map. Hij leest de PDF's met pypdf; een pagina
  zonder tekst stopt die offerte als "OCR nodig". In de vergelijking heten de inschrijvers Inschrijver A, B, C; welke
  file welke letter is, staat apart in het verslag voor Mehdi. Zo komt de naam van de andere firma nooit in een stuk
  van de ene. De code rekent: totaal excl. btw, btw-tarief, incl. btw, verschil per inschrijver, rekenfouten (posten
  tegen totaal), ontbrekende posten als "ontbreekt", nooit nul. Geen gunning, geen aanbeveling van een inschrijver.
  Alleen het bord (G7 noemde Dropbox-opslag, K4 schrijven werd afgewezen): v1 schrijft niets in Dropbox.
- X5: tot Mehdi ja zegt, gaat geen offerte-inhoud naar het model. Zonder model haalt de code uit de tekst wat zeker is
  (totalen, btw, geldigheid, basis); de vergelijking per post komt pas na zijn ja. De schakelaar staat in de code
  (`OFFERTE_NAAR_AI`), zodat de wijziging een commit is met zijn antwoord erbij. De redactie van bouwheernaam, adres en
  contact gebeurt hoe dan ook lokaal, voor het model.
- X6, G6, K6: tests in `tests/test_bouw.py` voor kruisvermelding (ook Unicode-streepjes), ongelezen website, ongeldig
  ondernemingsnummer, KBO, afstand, ontbrekende post, btw-normalisatie, rekenfout, scan, een raming die geen offerte is,
  de andere firma als anonieme inschrijver, en 2145 ventilatie als goed voorbeeld (bedragen geanonimiseerd).
- X7, G7: vandaag beide runners, werkwijzen, grendels, regisseurkoppeling (vraag), tests, uitrol met eerste ronde
  zonder vraag. Bewijs daarna: een zoekvraag per firma en 2145 als vergelijking.
- K7: geen betaalde bedrijvengids (advies niet doen, aangenomen); web en KBO volstaan voor v1.
- G5, K5: naar buiten gaan alleen werk, gemeente en straal; nooit de bouwheer, het werfadres of de zoekende firma.
- Taal: in rapport-1 stond een woord dat een band legt; vervangen door "de andere firma" (regel van Mehdi).
