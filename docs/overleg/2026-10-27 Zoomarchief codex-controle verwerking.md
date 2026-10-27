**Voor Mehdi — niet klaar.** Het gemeten valse alarm wordt voor nieuwe rondes voorkomen, maar de wijziging kan ook een echt ontbrekende opname vergeten. Stel dat een MP4 nog verwerkt wordt en dezelfde meeting al een afgerond audiobestand heeft. Verdwijnt daarna de MP4 zonder vervanger, dan kopieert de archivaris de audio en meldt hij het verlies van de MP4 niet. `SEIN_AAN = False` voorkomt een groen sein, maar herstelt die ontbrekende melding niet. Zoom beschrijft ook [gevallen waarin verwerking niet tot een beschikbare opname leidt](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0057720).

**Voor Claude en Shaniel**

39. **Hoog — `zoom_archief.py:612`.** Bij een verdwenen `processing`-id wist regel 614 het spoor zodra de meeting-uuid nog voorkomt. Een ander bestand in die meeting is daarvoor al genoeg; er hoeft geen vervangende MP4 te zijn. `problemen():329` bewaakt dit niet. De oude code meldde A als verdwenen; de nieuwe kan zelfs een `opname.json` met alleen het overgebleven bestand schrijven. Bewaar A als wachtend op vervanging. Voer het pas af na een aantoonbaar passend *nieuw* afgerond bestand; meld het als die vervanging uitblijft. Test ook een meeting die blijft bestaan met uitsluitend een ander bestand.

40. **Middel — `zoom_archief.py:583`.** Het reeds gemelde voorlopige id A wordt door deze wijziging niet uit `verdwenen` gehaald: daarvoor moet juist A terugkomen of bewezen zijn. De bestaande nood en voorstel 44 blijven dus bestaan als die nog in de live staat staan. Verifieer de bewezen vervangers en corrigeer dat bestaande geval afzonderlijk, inclusief het bordvoorstel.

Gedaan: diff en verliesroute alleen lezend gecontroleerd; niets gewijzigd.  
Nagekeken: `git diff --check` en Python-syntaxis goed. De gevraagde test stopte vóór de eerste test: de alleen-lezen omgeving kon geen tijdelijke map maken.  
Open: beide gevallen herstellen en de volledige testreeks in een schrijfbare testomgeving draaien.

**BESLISSING: niet klaar.**