**Niet klaar.** V1 is voor dagen binnen de gewone terugblik opgelost en V3 klopt. Voor een oudere dag kan een vervallen dekking nog een verouderde dagvaststelling laten staan.

### Voor Mehdi

Als een eerder vastgelegde dag later zijn bewijs verliest, kan het dagoverzicht de oude telling blijven tonen. Dat speelt bij een inhaalronde voor een dag buiten de gewone terugblik van veertien dagen.

### Voor Claude en Shaniel

1. **W1, middel:** [dagbundelaar.py:346](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/dagbundelaar.py:346) sluit vervallen dekking uit van de inhaalkeuze. Bovendien werkt [app.py:772](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/app.py:772) bij het vervallen de wijzigingstijd niet bij. Een geheugenproef met een oudere dag gaf `[]` voor de inhaalkeuze, zelfs met een nieuwere tijd op de vervallen rij. Leg de wijzigingstijd vast, laat gewijzigde vervallen dekking een herberekening starten en test de route met een al vastgelegd dagoverzicht. [test_v1](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:827) controleert de dagtekst, maar toetst de inhaalkeuze alleen door brontekst te lezen.

V1 filtert vervallen dekking wel correct uit `gedekte_dagen`. V3 bewaart voor andere apps alleen tijdstippen en telt die binnen het venster; [test_u1](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:693) dekt dat af. Claudes reden om V2 als laag punt open te laten houdt: de sleutel en sloten voorkomen vergissingen, maar vormen geen grens tegen bewuste handelingen van hetzelfde gebruikersaccount.

Gedaan: laatste commit en geheel tegenover main alleen gelezen.  
Nagekeken: V1, V3, V2 en een geheugenproef; Claudes Mac testuitslag hier niet herhaald.  
Open: W1 van ernst middel; V2 blijft laag.

live: nee