## Voor Mehdi

**Niet klaar.** Mijn geheugenproeven kregen nog `dekking: ja` terwijl een Zoom-bestand zonder bewezen kopie was verdwenen, en `wisregel_veilig: true` terwijl een oude opname onbewezen bleef. Ook kunnen waarschuwingen verdwijnen zonder herstel. Een nieuw besluit over de wisregel kan nog niet op deze uitkomsten steunen.

## Voor Claude en Shaniel

18. **Blokkerend — `zoom_archief.py:505`.** Verdwijnt een bestand zonder id uit een meeting die ook een bewezen bestand heeft, dan wist de volgende volledige inventaris `onvolledig`: `dekking` en `veilig` worden beide waar. Bewaar het onopgeloste geval per bestand; hef het pas op na herkenbare kopie of een besluit over verlies.

19. **Blokkerend — `zoom_archief.py:485`.** Een oude opname die ná de daginventaris in Zoom verschijnt, valt buiten het venster van een korte ronde. Mijn proef gaf beide waarden waar bij nul bewijzen. Lees oude actieve opnames voordat een korte ronde `ja` vernieuwt.

20. **Blokkerend — `zoom_archief.py:610`.** Na schijftekort blijft een oude onbewezen opname in `gezien`, maar een korte ronde schrijft `veilig: true`. Een bestand in `processing` wordt niet in `gezien` bewaard; na verdwijning volgt zelfs `dekking: ja`. Bewaar alle onbewezen bestands-id’s en tel hun ouderdom en verlies mee.

21. **Hoog — `zoom_archief.py:457`.** Een wegens de gesprekkenketen overgeslagen ronde laat een eerdere `ja` in staat én dekkingbestand staan. Laat ook deze vroege stop `intrekken` gebruiken.

22. **Hoog — `zoom_account.py:667`.** Bij een onleesbaar voorstellenbord verdwijnt de wisregelwaarschuwing; de volgende hartslag sluit de nood. Zet `noden_onbekend` en meld de leesfout.

23. **Middel — `zoom_archief.py:563`, `zoom_archief.py:588`.** Schijftekort of een mislukte upload van `opname.json` geeft een nood die in de volgende korte ronde zonder herstel sluit. Bewaar beide fouten tot een geslaagde hercontrole.

24. **Middel — `dropbox_prive.py:103`, `zoom_archief.py:291`.** HTTP-aanroepen en herpogingen kunnen voorbij de harde tijdsgrens lopen; `opname.json` krijgt geen bewaker mee. Begrens elke aanroep met de resterende tijd.

De sleutel per nieuw verlies en het overslaan van voorstellen bij een onleesbaar bord doorstonden mijn gerichte proeven (punten 11, 13 en 14). Punt 15 werkt voor een geheel verdwenen meeting, maar niet voor bevinding 18.

Gedaan: diff en werkafspraken gelezen; niets gewijzigd.  
Nagekeken: gerichte geheugenproeven; de zes opgegeven Mac-suites hier niet herhaald.  
Open: bevindingen 18–24; serverstatus van voorstel 40 niet onafhankelijk gelezen.

**BESLISSING: niet klaar.**