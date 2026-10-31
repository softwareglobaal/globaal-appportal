# Opdracht driehoeksoverleg: het Dagboek compleet, alle kanalen en de inhoud

In drie hoeken overleggen. Claude, Codex en Gemini: stem per punt (eens / oneens / onthouding).

## Context
- De Dagbundelaar (globaal-appportal/mijnagents-runner/dagbundelaar.py) maakt elke nacht om 00:30 per dag een
  dagbestand (mijnagents-data/dagboek/<jaar>/<dag>.md en .json). Het Dagboek (dagboek.globaal.be, map dagboek/)
  toont die bestanden, met sinds 31-10-2026 ook locatie (Onderweg, Waar was ik) uit app-locatie.
- Werkt nu op de laptop: WhatsApp-wacht en Belwacht (stand aangesloten, 190 tot 290 WhatsApp-berichten per dag).
  Zoom, Fathom en Plaud staan in de gesprekkentabel en het dagbestand, maar alleen als telling en lijst.
- Sms en iMessage komen sinds 31-10-2026 op de laptop binnen (app Messages), maar geen wacht leest ze nog.
- Bewust tot nu toe: nooit de tekst van een bericht of mail bewaren, alleen wie, wanneer, hoeveel en hoe lang
  (werkwijze v3.0, helper mac/kopie/macgesprekken_kopie.c kopieert geen tekstkolom).
- Mehdi, 31-10-2026: "al mijn kanalen moeten erbij komen, zodat we weten wat voor kanalen er zijn en hoeveel daar
  is binnengekomen; als er niks is, dan is er niks in dat kanaal die dag. De communicatie moet per kanaal staan, en
  de berichten ook, en de inhoud van Plaud, Zoom, Fathom, zodat de volgende agent niet zelf nog eens moet gaan
  zoeken. De foto's zijn er ook niet. Alles wat in de dagbundel komt, moet hier getoond worden."
- Er komt een aparte Mehdi-agent die het dagbestand leest en taken en to-do's klaarzet.

## Punten om te stemmen
P1. Elk kanaal staat elke dag als vaste rij in het dagbestand (.json) en in het Dagboek: agenda, Zoom-gesprekken,
    Zoom-chat, Fathom, Plaud, WhatsApp, sms en iMessage, telefoon, mail per postvak, foto's, locatie. Per rij:
    aantal, minuten waar dat telt, en een stand. 0 alleen als het kanaal die dag gelezen werd; anders "onbekend".
P2. De inhoud van gesprekken in het dagbestand: per Fathom-, Zoom- en Plaud-gesprek de samenvatting en de
    actiepunten die de wacht al ophaalt (geen volledig transcript), met een verwijzing naar het transcript.
    Zo hoeft de Mehdi-agent niet zelf te zoeken. Nakijken welke wacht welke samenvatting al bewaart (fathom_wacht.py,
    plaud_wacht.py, zoom_wacht.py, tabel klaarzet).
P3. Een Berichtenwacht voor sms en iMessage op de laptop, zoals de WhatsApp-wacht: een derde set in
    MacGesprekkenKopie (~/Library/Messages/chat.db, alleen datum, richting, gesprek, deelnemer), een kanaal
    "berichten" in dagvaststelling, bordstand, weekoverzicht en het bord. Eén nieuwe Full Disk Access-klik.
P4. Foto's: de iCloud-wacht (tijd en plaats per foto, nooit de foto) als kanaal in het dagbestand en het Dagboek,
    en de plaats van een foto als extra spoor bij "Waar was ik".
P5. De Dagbundelaar draait zes keer per dag in plaats van een keer per nacht (bijvoorbeeld 07, 10, 13, 16, 19, 22 uur),
    met de dag van vandaag als voorlopig. De nachtronde blijft de vaststelling.
P6. Het dagbestand is de enige bron voor de Mehdi-agent: die leest alleen .json en .md, nooit zelf de wachten.
    GRENS: berichttekst. WhatsApp-, sms- en iMessage-tekst bewaren of laten lezen is een privacykeuze van Mehdi.
    Advies gevraagd: ja of nee, en zo ja alleen werk (geen privé) en alleen voor de Mehdi-agent, nooit op het bord.
P7. De bundel is het dagbestand op de server (mijnagents-data/dagboek/<jaar>/<dag>.md en .json), hetzelfde bestand
    dat naar Dropbox "Dagbundelaar/<jaar>/<dag>" gaat. Vaste regelvorm voor de Mehdi-agent: bovenaan het tijdstip van
    maken; per gesprek in Fathom, Zoom, Plaud tijd, met wie, minuten, titel, samenvatting, actiepunten (tekst en wie)
    en een verwijzing (fathom:<id>, plaud:<id>, zoom:<id>); per werkgesprek in WhatsApp, sms en telefoon met wie,
    aantal in en uit, tijd van het laatste bericht, of het laatste van de ander kwam (wacht op antwoord), gemiste
    oproepen zonder terugbellen, met een verwijzing (privé blijft "privé"); per postvak de mails die op antwoord
    wachten (afzender, onderwerp, sinds), zonder tekst; de afspraken van vandaag, en in de laatste ronde ook morgen.

## Grenzen
Niets verwijderen, live zetten of versturen zonder Mehdi's ja. Geen berichttekst bewaren zonder Mehdi's ja (P6).
