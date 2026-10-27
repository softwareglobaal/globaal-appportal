**Niet klaar.** Punt 44 is hersteld voor de geteste volgorde A → A+B → B. Er blijven twee volgordes over waarin de archivaris een verlies verkeerd beoordeelt. `SEIN_AAN = False` voorkomt een wisadvies, maar geen gemiste of onterechte verliesmelding.

**Voor Claude en Shaniel**

45. **Hoog — `zoom_archief.py:641`, `zoom_archief.py:437`.** A is in verwerking; daarna verschijnt een *afzonderlijk* bestand B van hetzelfde type, met een begintijd één minuut later; vervolgens verdwijnt A zonder kopie. De bronlus koppelt B aan A en wist A uit `vervanging`, zonder verliesmelding. Dat B een afzonderlijk deel kan zijn, is reëel: [Zoom maakt na stoppen en opnieuw starten een nieuw cloudbestand](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062627). De code bewijst geen verband tussen de bestanden. Wis A daarom niet uitsluitend op basis van type en twee minuten tijdsverschil; houd een onbewezen koppeling zichtbaar en test dit geval.

46. **Middel — `zoom_archief.py:641`, `zoom_archief.py:650`.** A → A+B → A → alleen het overige meetingbestand: B is intussen bewezen gekopieerd, maar verdwijnt uit de Zoom-lijst vóór A. De match zoekt B pas na het verdwijnen van A en alleen in de *huidige* lijst. Mijn geheugenproef met de echte `_ronde`-functie gaf na 27 uur `verdwenen: A`, ondanks het bewijs voor B. Bewaar ook eerder verschenen kandidaatvervangers en hun bewijs; meld een onzekere koppeling niet als vastgesteld verlies.

Gedaan: commit `9af45ec` alleen lezend gecontroleerd; niets gewijzigd.  
Nagekeken: beide routes met broncode in het geheugen uitgevoerd; Python-syntaxis goed. De gemelde 77 tests kon ik in deze leesomgeving niet herhalen.  
Open: beide routes herstellen en met regressieproeven vastzetten. De geplande controle van de live staat blijft nodig, maar verhelpt deze codepaden niet.

BESLISSING: niet klaar