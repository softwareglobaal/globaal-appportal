**Voor Mehdi — niet klaar.** Er is nog een geval waarin een bewezen vervanger toch als ontbrekende opname wordt gemeld. Verschijnt het definitieve bestand terwijl het voorlopige id nog één ronde zichtbaar is, dan behandelt de archivaris dat definitieve bestand later als “al bestaand”. Na 24 uur volgt een vals verlies en mogelijk een voorstel aan jou. `SEIN_AAN = False` voorkomt een wisadvies, maar niet die melding.

**Voor Claude en Shaniel**

44. **Middel — `zoom_archief.py:657`.** `andere` wordt elke ronde opnieuw opgebouwd. Daardoor sluit de match op regel 642 een bestand uit dat *na de eerste waarneming* verscheen. Mijn geheugenproef met de bronregels gaf: eerst voorlopig A, daarna A plus definitief B, daarna alleen B; ondanks bewezen B komt A na 25 uur in `verdwenen`. Bewaar `andere` vanaf de eerste waarneming en voeg een proef met deze tussenronde toe.

Gedaan: commit `5f7ec58` alleen lezend gecontroleerd; niets gewijzigd.  
Nagekeken: het randgeval bevestigd met uitvoer van de betreffende bronregels. De gemelde 76 tests kon ik in deze alleen-lezen omgeving niet herhalen.  
Open: punt 44 herstellen en hertesten; de live staat vlak voor uitrol opnieuw controleren.

BESLISSING: niet klaar