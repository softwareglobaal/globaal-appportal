**Voor Mehdi — niet klaar.** Ik vond twee rondes waarin een echt ontbrekend bestand geen verliesmelding geeft. Een derde houdt een verliesmelding vast nadat een passende vervanger alsnog is gekopieerd. `SEIN_AAN = False` voorkomt een groen sein, maar corrigeert deze meldingen niet.

1. Twee plaatshouders beginnen vier seconden na elkaar. Daarna verschijnt één afgerond bestand en verdwijnen beide plaatshouders. De archivaris telt dat ene bestand voor beide en meldt geen verlies.
2. Twee plaatshouders hebben hetzelfde begin. Eén wordt onder hetzelfde id afgerond; de andere verdwijnt zonder vervanger. Het afgeronde bestand telt ten onrechte ook als vervanger voor de verdwenen plaatshouder.
3. Een plaatshouder wordt na 24 uur als verlies gemeld. Verschijnt en wordt zijn passende vervanger later gekopieerd, dan blijft de verliesmelding staan.

**Voor Claude en Shaniel**

49. **Hoog — `zoom_archief.py:483`.** Kandidaten worden per groep verzameld zonder gezamenlijke toewijzing. Laat ieder afgerond id hoogstens één groep dekken; test twee groepen binnen vijf seconden met één kandidaat.
50. **Hoog — `zoom_archief.py:478`.** Na verwijdering uit `plaatshouders` wordt een onder hetzelfde id afgerond bestand op regel 483 opnieuw kandidaat. Bewaar de historische plaatshouderids en sluit die uit als kandidaat voor andere plaatshouders.
51. **Middel — `zoom_archief.py:490`.** Een opgeloste groep wordt na een late kandidaat niet opnieuw beoordeeld; ook de opruiming van `verdwenen` op regel 659 herkent die vervanger niet. Herbereken het tekort en trek een achterhaald verlies in.

Gedaan: commit ad05dca en eerdere verslagen alleen lezend gecontroleerd; niets gewijzigd.  
Nagekeken: drie geheugenproeven met de huidige functies bevestigen beide gemiste verliezen en het blijvende valse verlies. De gemelde 83 tests heb ik niet herhaald.  
Open: herstellen, de drie rondes als regressietests vastleggen en opnieuw controleren vóór live kopiëren.

BESLISSING: niet klaar