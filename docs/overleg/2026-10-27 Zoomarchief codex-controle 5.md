## Voor Mehdi

**Niet klaar.** De agent wist zelf niets, maar zijn groene sein kan Mehdi wel aanleiding geven de wisregel in Zoom aan te zetten. Mijn geheugenproeven kregen nog twee keer een groen sein zonder voldoende bewezen kopie.

## Voor Claude en Shaniel

25. **Hoog — `zoom_archief.py:328`.** Twee bestanden zonder id met dezelfde soort en start krijgen één sleutel. Nadat beide verdwenen, leidde één goedkeuring tot `dekking: ja` en `wisregel_veilig: true`. Bewaar het aantal per kenmerk; laat een besluit expliciet voor dat aantal gelden en houd dubbelzinnige gevallen op `nee`.

26. **Hoog — `zoom_archief.py:566`.** Zoom meldde in de proef voor hetzelfde id later 2 bytes, terwijl de bewezen Dropbox-kopie 1 byte bleef. Beide signalen werden toch groen. Vergelijk de actuele Zoom-grootte met het opgeslagen bewijs en blokkeer bij verschil tot er een nieuwe bewezen kopie is.

27. **Hoog — `zoom_archief.py:435`.** Als een volle schijf beide schrijfpogingen voor het intrekken weigert en daarna de inventaris faalt, blijft het oude `ja` maximaal drie uur leesbaar. Laat De Zoomwacht een `ja` alleen vertrouwen wanneer ook de laatste archiefronde aantoonbaar geslaagd is; ontbreekt die bevestiging, toon `onbekend`.

28. **Middel — `zoom_archief.py:634`.** Een mislukte `opname.json` verdween als nood toen de meeting uit Zoom verdween, zonder herstel. Bewaar de blokkade en de gegevens voor een herpoging, of vraag een besluit over het ontbrekende document. De mediakopie was in deze proef wel aanwezig.

29. **Middel — `dropbox_prive.py:117`.** De tijd wordt vóór het vernieuwen van het token gemeten. Een gesimuleerde API-aanroep begon daardoor ná de rondegrens. Bereken de resterende tijd opnieuw na token- en rootcontrole en begrens ook die aanroepen.

Gedaan: diff en eerdere controles gelezen; niets gewijzigd.  
Nagekeken: vijf gerichte geheugenproeven; de opgegeven Mac-suites hier niet herhaald.  
Open: punten 25–29 herstellen en daarna opnieuw toetsen.

**BESLISSING: niet klaar.**