**Klaar.** W1 is opgelost. Een gewijzigde koppeling krijgt een nieuwe tijdstempel, ook wanneer een dekkingsrij vervalt. De nacht kiest daardoor een oudere dag opnieuw; een vervallen dekking telt dan niet meer als bewijs. De API-test en de test voor een dag van 26 dagen terug bewaken beide stappen. [app.py](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/app.py:753), [dagbundelaar.py](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/dagbundelaar.py:338), [API-test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/test_gesprekken_api.py:459), [inhaaltest](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:855).

De Zoomwacht gebruikt dezelfde koppelroute. Zijn gewijzigde koppelingen en terugleescontrole blijven met de nieuwe code werken. In het geheel tegenover main vond ik geen nieuw punt van ernst hoog of middel. Er zijn daarom geen X-bevindingen. V2 blijft laag, met de eerder aanvaarde reden. [zoom_wacht.py](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/zoom_wacht.py:871).

Gedaan: laatste commit en geheel tegenover main alleen gelezen.  
Nagekeken: W1, de tests en De Zoomwacht; Claudes gemelde testuitslagen niet zelf herhaald.  
Open: geen punt van ernst hoog of middel.

live: ja