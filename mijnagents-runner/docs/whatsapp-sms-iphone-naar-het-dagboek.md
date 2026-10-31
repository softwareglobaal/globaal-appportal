# WhatsApp, sms en iMessage naar het Dagboek

Versie 1.0 (31-10-2026). Voor Mehdi (iPhone, drie schakelaars) en Claude 1 (laptop).

Waarom: het Dagboek toont WhatsApp en telefoon pas als de laptop ze leest. Sms en
iMessage komen via de app Messages op de laptop binnen. Er wordt nooit tekst van
een bericht bewaard, alleen met wie, wanneer en hoeveel.

Vaste regels: alle toestellen van Mehdi staan in het Engels, de menunamen hier ook.
Nooit uitloggen of opnieuw inloggen bij Claude. Niets wissen, niets
versturen. Geen wachtwoord in chat of git. Twijfel: stop en meld.

## Deel 1. Mehdi, eenmalig op de iPhone (vijf minuten)

1. Settings, tik op je naam bovenaan, iCloud, See All, Messages in iCloud: zet "Use on this iPhone" aan.
   Zo staan je sms en iMessages ook op de laptop.
2. Settings, Apps, Messages, Text Message Forwarding: zet de laptop aan.
   Zo komen ook gewone sms (groene ballonnen) op de laptop.
3. Settings, Apps, Phone, Calls on Other Devices: aan, en zet de laptop aan.
   Zo komen je iPhone-oproepen op de laptop.

## Deel 2. Claude 1 op de laptop

1. Voer het document "Laptop inrichten voor de Dagbundelaar" uit, stap 1 tot en met 3
   (WhatsApp en telefoon). Dat staat in de repo globaal-appportal, map
   mijnagents-runner/docs, en in de projectmap dagbundelaar.
2. Open de app Messages op de laptop. Staat er een aanmeldscherm, dan meldt Mehdi zich
   aan met zijn Apple ID (dat is Apple, niet Claude). Controle: de berichten van vandaag
   van de iPhone staan erin, ook een sms.
3. In Messages: menu Messages, Settings, tab iMessage, en zet
   "Enable Messages in iCloud" aan.
4. Meld aan Mehdi in vijf regels: ok of fout per stap, met de foutregel.

## Deel 3. Daarna (Claude 2 bouwt, Claude 1 zet aan)

Claude 2 bouwt de Berichtenwacht: die telt per dag per persoon de sms en iMessages,
zoals de WhatsApp-wacht. Als die klaar is, krijgt Claude 1 een korte opdracht om ze
op de laptop aan te zetten, met één klik van Mehdi in System Settings, Privacy & Security, Full Disk Access.

## Wat Mehdi daarna ziet

Op dagboek.globaal.be per dag de tegels WhatsApp, Telefoon en Onderweg ingevuld, en
later ook Sms. Op de dagpagina het blok "Waar was ik" met plekken, projecten en ritten.
