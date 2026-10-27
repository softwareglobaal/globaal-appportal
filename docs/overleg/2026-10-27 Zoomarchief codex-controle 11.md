**Niet klaar.** Met het sein aan kan het archief een Zoom-opnamebestand overslaan en toch groen geven. Ook kan een actieve wisregel onveilig worden zonder dat Mehdi de afgesproken waarschuwing krijgt.

### Voor Mehdi

Zoom kan naast de gewone opname aparte geluidsbestanden per deelnemer leveren. In een proef met twee bestanden zag het archief er maar één. Een tweede proef maakte de kopie terecht onveilig, maar gaf geen waarschuwing over de ingeschakelde wisregel.

### Voor Claude en Shaniel

50. **Hoog — `zoom.py`, `zoom_archief.py`.** `participant_audio_files` valt buiten de inventaris. Een geldig antwoord met `recording_count=2` leverde in de geheugenproef één verwerkt bestand op; daardoor kunnen `dekking` en `wisregel_veilig` vals groen worden. Zoom documenteert beide bestandslijsten afzonderlijk. **Fix:** neem beide lijsten mee, controleer het aantal tegen `recording_count` en voeg een regressieproef toe. [Zoom API-documentatie](https://developers.zoom.us/docs/api/meetings/).

51. **Hoog — `zoom_archief.py`.** De wisregelnood wordt vóór de tweede inventaris bepaald. Verschijnt daar een oude, onbewezen opname, dan wordt `veilig=False` zonder nood voor Mehdi. Bij een fout in de eerste inventaris stopt de ronde eveneens zonder die nood, hoewel de wisregel al als actief is gelezen. Beide gevallen zijn in het geheugen gereproduceerd. **Fix:** bepaal de nood na de laatste veiligheidscontrole en ook op vroege stoppaden met een bekende actieve wisregel.

52. **Middel — `zoom.py`.** Een tokenverversing gebruikt een vaste wachttijd van 30 seconden, ook nadat de rondegrens is verstreken. De geheugenproef bevestigde dat de tokenaanvraag dan nog start. **Fix:** pas de rondegrens ook op de tokenaanvraag toe.

Gedaan: alleen-lezen controle; niets gewijzigd.  
Nagekeken: commit e5f981d, de leesgrendels en drie geheugenproeven; de volledige suites zijn niet opnieuw gedraaid.  
Open: punten 50–52 herstellen en gericht testen.

**BESLISSING B (sein aan): niet klaar.**