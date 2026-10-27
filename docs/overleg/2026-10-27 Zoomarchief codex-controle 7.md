**Niet klaar voor A of B.** Ik vond geen route die een Zoom-opname wist, een Dropbox-bestand overschrijft of een mediakopie bewijst zonder gelijke grootte en `content_hash`. De accountcontrole en het eigen rondeslot zijn aanwezig. De keten en het groene sein hebben nog deze open punten.

## Voor Claude en Shaniel

36. **Middel — `zoom_archief.py`.** Bij een draaiende keten kopieert de agent niets, maar leest hij wel de volledige Zoom-inventaris en controleert hij Dropbox. Dat zijn op deze datum 108 datumvensters plus de prullenbak, naast De Zoomwacht in dezelfde keten. Of dit de keten *daadwerkelijk* vertraagt, is niet gemeten; de droge ronde van 39 seconden meet geen gelijktijdige belasting. **Kleinste oplossing:** bij `keten=True` het sein intrekken en vóór de netwerkvragen stoppen; toets dat beide bronnen dan niet worden aangeroepen.

37. **Hoog — `zoom_archief.py`, `zoom_archief.py`.** Mijn geheugenproef liet een oude, onbewezen opname verschijnen nadat haar datumvenster was gelezen. De ronde miste haar en publiceerde zowel `dekking: true` als `wisregel_veilig: true`. **Kleinste oplossing:** herlees de volledige lijst vlak vóór groen en publiceer bij een verschil `nee`; leg dit tijdsgeval als proef vast.

38. **Hoog — `zoom_archief.py`, `zoom_account.py`.** Een droge ronde die een oude onbewezen opname vindt, laat een eerder groen dekkingbestand staan. Haar bordstatus kan daarna `klaar` zijn; een geheugenproef liet De Zoomwacht beide oude groene waarden opnieuw als `ja` lezen. **Kleinste oplossing:** laat de bordcontrole alleen een aantoonbaar geslaagde, niet-droge ronde aan het dekkingbestand koppelen.

Gedaan: commit `ee8c443` en controles 1–6 alleen lezend onderzocht.  
Nagekeken: drie gerichte geheugenproeven; geen live ketenproef of volledige Mac-suites herhaald.  
Open: punten 36–38 herstellen en toetsen; niets gewijzigd.

**BESLISSING A (kopiëren live met sein uit): niet klaar.**  
**BESLISSING B (sein aan): niet klaar.**