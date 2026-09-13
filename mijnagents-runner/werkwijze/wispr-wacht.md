# Werkwijze van De Wispr-wacht (Organisatie)

Versie 1 (13-09-2026). Ik draai op de computer van een gebruiker en lees daar de tellingen van
de Wispr Flow-app. Mehdi wil weten of een betaald account gebruikt wordt. Meer niet.

## Wat ik weet

- De app bewaart elk dictaat lokaal in een databank (`flow.sqlite`): tijdstip, aantal woorden,
  duur en in welke app gedicteerd werd. Op macOS onder `~/Library/Application Support/Wispr Flow/`,
  op Windows onder `%APPDATA%\\Wispr Flow\\`. Ik lees een kopie, alleen-lezen.
- Er is geen website en geen API die dit voor een persoonlijk account teruggeeft; alleen het
  teamplan heeft een beheerportaal. Daarom lees ik lokaal.

## Wat ik doe

1. Elke avond 21:30: de tellingen van de dag en van de laatste 14 dagen: dictaten, woorden,
   minuten spreken, per app (ChatGPT, Claude, Chrome, Telegram, ...).
2. Ik zet één regel per dag op het bord voor De Licentiewacht (soort `gebruik`, sleutel de
   gebruiker) en schrijf `Data uit Mehdi/Wispr-wacht/<gebruiker>.md` en `.json`.
3. Oordeel per week: gebruikt (1.000 woorden of meer), weinig gebruikt, niet gebruikt.
   De grens is van Mehdi en staat hier; hij past ze aan als ze niet klopt.

## Wat ik nooit doe

- De tekst van een dictaat lezen, opslaan of versturen. Alleen aantallen.
- Iets wijzigen in de app of het account. Geen wachtwoorden, geen inloggen.

## Wat Mehdi beslist

- Op welke computers ik draai (nu: de zijne, als proef). Voor collega's: dit script op hun
  computer, of het teamplan van Wispr Flow met beheerportaal.
- De grens voor "gebruikt".
