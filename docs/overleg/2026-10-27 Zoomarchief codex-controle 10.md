**Niet klaar: `SEIN_AAN` moet uit blijven.** De herstellingen van punten 40–44 staan in de diff, maar nieuwe geheugenproeven leveren nog een onterecht groen sein en ontbrekende waarschuwingen op.

### Voor Mehdi

De VM heeft al een archiefstand in de oude vorm. Als die stand vóór de eerste ronde met de nieuwe code verdwijnt, kan het systeem eerdere opnames vergeten en toch melden dat alles gedekt en veilig is. Ook een verkeerde `opname.json` naast de mediabestanden levert in de proef tweemaal groen op.

De Zoomwacht mist de waarschuwing voor een actieve wisregel wanneer het voorstellenbord onleesbaar is. Ziet een nieuwe accountscan dat de wisregel is aangezet, dan gebruikt de waarschuwing nog de vorige scanstand.

### Voor Claude en Shaniel

45. **Hoog — `zoom_archief.py:120`.** De marker `.in_gebruik` bestaat niet voor oude VM-rondes. Zonder `staat.json` én marker gaf een volledige geheugenronde `dekking=true`, `wisregel_veilig=true`. **Fix:** migreer de bestaande installatie aantoonbaar vóór groen mogelijk wordt; behandel een ontbrekende oude stand als fout.

46. **Hoog — `zoom_archief.py:303` en `zoom_archief.py:342`.** Een uploadconflict bij `opname.json` wordt zonder controle aanvaard; later volstaat elk bestaand object. Met een verkeerde inhoud gaf de volledige geheugenronde `true/true`, zonder nood. **Fix:** toets bestandstype en grootte/hash tegen de verwachte beschrijving; blokkeer afwijkingen zonder te overschrijven.

47. **Hoog — `zoom_account.py:691`.** Bij een onleesbaar voorstellenbord keert `wisregel_wacht` terug vóór de onafhankelijke controle van een actieve wisregel. De proef gaf alleen een bordfout, geen waarschuwing voor Mehdi. **Fix:** controleer de bekende wisregelstand ook bij een bordfout.

48. **Middel — `zoom_account.py:1340`.** De waarschuwing loopt vóór de nieuwe accountscan. Bij een omslag van uit naar aan verschijnt zij die ronde niet; mislukt het bewaren van de nieuwe basis, dan blijft dit langer zo. **Fix:** toets ook de vers gelezen instelling.

49. **Laag — `zoom_account.py:646`.** Een dekkingstijdstip één minuut in de toekomst gaf in de proef tweemaal `ja`. **Fix:** wijs ieder toekomstig tijdstip af.

Gedaan: alleen-lezen controle en geheugenproeven; niets gewijzigd.  
Nagekeken: commit 8ee9f1d en de herstellingen van punten 40–44; de opgegeven suites niet opnieuw gedraaid.  
Open: punten 45–49 herstellen en met regressieproeven vastzetten.

**BESLISSING B (sein aan): niet klaar.**