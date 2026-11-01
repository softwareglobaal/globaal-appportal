# Waar haalt de Dagbundelaar zijn data, en wat doet hij

In drie hoeken overleggen.

Stand 28-10-2026, uit de code in GitHub (globaal-appportal, map mijnagents-runner).

## Wat hij doet

De Dagbundelaar (`dagbundelaar.py`) draait op de VM (globaal.be). Hij haalt zelf bijna niets op. Andere "wachten" zetten de gegevens klaar, en hij legt ze samen.

1. **Elke nacht om 00:30** (Brusselse tijd, winter) maakt hij een dagbestand van gisteren: de afspraken en of ze doorgingen, wat er ongepland gebeurde, en de communicatie. Hij maakt ook de 13 dagen daarvoor opnieuw, als er nog iets bijkwam. Daarna maakt hij het weekoverzicht.
2. **Elke werkdag om 08:00** maakt hij per dossier een bundel voor de afdeling, en het dagverslag voor jou.
3. Hij bewaart alleen wie, wanneer, hoeveel en hoe lang. Nooit de tekst van een bericht of mail. Van privé staat er alleen "privé".

## Waar elke bron vandaan komt

| Bron | Machine | Welke wacht | Wanneer | Wat hij eruit haalt |
|---|---|---|---|---|
| Agenda's | VM | De Agendawacht (`agenda_wacht.py`) | elke 2 uur | wat gepland stond |
| Locatie van de auto | VM | De Locatiewacht (`locatie_wacht.py`) | elk uur, dagboek om 21:30 | of de auto bij een afspraak stond, bezoeken zonder afspraak |
| Zoom | VM | De Zoomwacht (`zoom_wacht.py`) | 08:00, 14:00 en 's nachts | gesprekken en Zoom-chats |
| Fathom | VM | De Fathomwacht (`fathom_wacht.py`) | 08:00 en 14:00 | opgenomen gesprekken |
| Plaud | Mac haalt op, VM leest | De Plaudwacht (`plaud_wacht.py`) | elk uur | opnames |
| Mail: 7 werkpostvakken | VM | de mailwachten (`mail_*.py`) | doorlopend | alleen koppen: binnen, verzonden, per postvak |
| Mail: hotmail | VM maakt elk uur zelf een kopie (sinds 26-10) | `hotmail_server.py` | elk uur | alleen koppen |
| WhatsApp | **Mac** | De WhatsApp-wacht (`whatsapp_wacht.py`) | elk uur als de Mac wakker is | per gesprek: aantal berichten en oproepen, met wie |
| Telefoon (iPhone) | **Mac** | De Belwacht (`belwacht.py`) | elk uur als de Mac wakker is | oproepen: wie, wanneer, hoe lang |
| Foto's | **Mac** | De iCloud-wacht (`icloud_wacht.py`) | elke avond 21:15 | alleen tijd en plaats van de foto's, niet de foto zelf |

## Waar het resultaat heen gaat

- Op de VM: `~/appportal/mijnagents-data/dagboek/2026/`, per dag een .md en een .json.
- Naar jouw Dropbox: `Data uit Mehdi/Dagboek`. De kopie gebeurt door een taak op de **Mac** (`data_uit_mehdi_sync.sh`, elke 30 minuten).
- Op het bord (mijnagents.globaal.be): een kaart per dag en de pagina Week.

## Wat nu niet werkt

- WhatsApp en telefoon staan sinds de overstap op "onbekend". Ze hebben een Mac nodig die aan staat, met WhatsApp Desktop en de iPhone-oproepen.
- Op de nieuwe Mac staat geen enkele van de drie Mac-wachten, en ook de Dropbox-kopie niet. Die lopen nog op een oudere machine.
