## Voor Mehdi

**Niet klaar voor A of B.** Ik vond geen route die een Zoom-opname wist of een Dropbox-bestand overschrijft. Nieuwe kopieën krijgen pas bewijs na vergelijking van grootte en `content_hash`, en het vastgelegde Dropbox-account-id wordt vóór kopiëren gecontroleerd. Er blijven wel risico’s voor de gesprekkenketen en de privacy. Met het sein aan leverden geheugenproeven bovendien een vals groen resultaat op.

## Voor Claude en Shaniel

30. **Middel — `zoom_archief.py:389`.** Faalt `pgrep`, dan geldt de keten als afwezig. Een ronde om 07:05 kan daardoor naast een lopende keten starten. **Fix:** behandel een onbekende ketenstatus als blokkade en meld die.

31. **Middel — `zoom.py:363`, `zoom_archief.py:188`.** De tijdsbewaker loopt tussen datumvensters, niet tussen alle Zoom-pagina’s. Een nagebootste aanroep eindigde na 700 seconden bij een grens van 600. **Fix:** controleer de grens per pagina en begrens elke netwerkcall met de resterende tijd.

32. **Middel — `zoom.py:537`, `bord.py:445`.** Een afwijkend Zoom-antwoord met een link als `file_size` bracht die link via de fouttekst op het bord. **Fix:** meld onverwachte fouten met een vaste, veilige tekst.

33. **Hoog — `zoom_archief.py:481`.** Een wegens de keten overgeslagen ronde laat een oude `ja` staan. De geheugenproef liet De Zoomwacht daarna zowel dekking als wisregelveiligheid als `ja` lezen, zonder nieuwe inventaris. **Fix:** trek het sein bij overslaan in.

34. **Hoog — `zoom_archief.py:577`.** Als Zoom voor een eerder bewezen bestand nu grootte nul meldt, vervalt het bewijs niet. De proef gaf opnieuw tweemaal groen. **Fix:** behandel nul of ontbrekende actuele grootte als onbewezen.

35. **Middel — `zoom_archief.py:685`.** Een onbewezen opname met tijdstip `+02:00` van meer dan 30 dagen oud gaf `wisregel_veilig: true`: tekstvergelijking ziet haar als jonger. **Fix:** vergelijk geparste tijdstippen in UTC.

Gedaan: alleen gelezen; niets gewijzigd.  
Nagekeken: gerichte geheugenproeven; de opgegeven Mac-suites hier niet herhaald.  
Open: punten 30–35 herstellen en opnieuw toetsen.

**BESLISSING A (kopiëren live met sein uit): niet klaar.**  
**BESLISSING B (sein aan): niet klaar.**