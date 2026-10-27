**Voor Mehdi**

Kopiëren met het sein uit is klaar. De controle van commit `7039c0b` vond geen route die een Zoom-opname wist of een bestaand Dropbox-bestand overschrijft. Tijdens de gesprekkenketen stopt de ronde vóór vragen aan Zoom of Dropbox.

Het sein aanzetten is **niet klaar**. Een oude opname die tijdens de ronde verandert, kan nog als veilig worden gemeld terwijl de Dropbox-kopie niet meer dezelfde grootte heeft.

**Voor Claude en Shaniel**

39. **Hoog — `zoom_archief.py:735`.** De tweede inventaris controleert bij een bekend bestands-id alleen of het in de staat staat. In een geheugenproef veranderde Zooms grootte van 1 naar 2 byte tussen de twee lezingen; de bewezen Dropbox-kopie bleef 1 byte, maar `dekking` en `wisregel_veilig` werden beide `True`. **Kleinste oplossing:** vergelijk in de tweede inventaris ook de actuele, niet-nul Zoom-grootte met het opgeslagen bewijs; trek bij verschil beide seinen in en voeg deze proef als regressietest toe.

Gedaan: alleen gelezen; niets gewijzigd.  
Nagekeken: diff, kopieerroute, seinroute en de geheugenproef; de opgegeven Mac-tests hier niet herhaald.  
Open: punt 39 herstellen en B opnieuw toetsen.

**BESLISSING A (kopiëren live met sein uit): klaar.**  
**BESLISSING B (sein aan): niet klaar.**