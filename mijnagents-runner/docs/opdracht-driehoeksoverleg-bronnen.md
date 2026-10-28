# Opdracht driehoeksoverleg: Dagbundelaar, bronnen en statuspagina

In drie hoeken overleggen. Claude, Codex en Gemini: stem per punt (eens / oneens / onthouding).

## Context
- De Dagbundelaar (globaal-appportal/mijnagents-runner/dagbundelaar.py) draait op de VM en werkt: het dagbestand en het weekoverzicht komen elke nacht in Dropbox.
- WhatsApp en telefoon staan sinds de pc-wissel op "onbekend": de Mac-wachten draaien niet op de nieuwe Mac.
- Mehdi wil dat de Mac-data van zijn laptop komt. Daar staan al WhatsApp en Foto's. Hij wil geen zware pc nodig hebben.

## Punten om te stemmen
P1. Een pagina "Bronnen" op mijnagents.globaal.be (achter Authentik, geen eigen login). Per bron één rij, per dag van de laatste 14 dagen groen, oranje of rood. Ze leest alleen wat er al is: de dagboek-json per dag, de hartslag van elke wacht en de open noden. Er komt geen nieuwe dataopslag bij.
P2. Mac-wachten op de laptop: WhatsApp-wacht, Belwacht, iCloud-wacht (alleen metadata, Foto's op "Mac-opslag optimaliseren") en de Dropbox-kopie. Dropbox-mappen staan "alleen online". De oude machine gaat daarna uit, zodat niets dubbel loopt.
P3. iPhone-oproepen: op de iPhone "Bellen op andere apparaten" aanzetten voor de laptop, met dezelfde Apple ID. De Belwacht leest dan de oproepgeschiedenis op de laptop.
P4. De laptop hoeft niet wakker te blijven: de wachten halen tot 60 dagen in na een slaap. Alleen "niet slapen op netstroom" aanzetten.
P5. Toevoegen als bron: Xelion (zakelijke oproepen, server-side, geen laptop nodig).
P6. Toevoegen als bron: DeskTime (gewerkte tijd op de pc) voor het weekoverzicht "wat ik effectief gedaan heb".
P7. Niet toevoegen: Wispr, sessie-radar, Calendly. Wispr en sessie-radar zijn ruis, Calendly zit al in de agenda.
P8. Opruimen: de branch `dagvaststeller` (13 commits) was dubbel werk van 26-10 en wordt niet samengevoegd. Eerst nakijken of er iets in zit dat ontbreekt.

## Grenzen
Niets verwijderen, live zetten of versturen zonder Mehdi's ja.
