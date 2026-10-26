**Niet klaar.** Het ochtendbericht wordt bij een onbekende bordstand niet meer tot 10:30 tegengehouden, maar oude noden kunnen daardoor stil verdwijnen.

1. **Hoog, nieuw in 6d95549:** bij een mislukte ochtendvaststelling behandelt [dagbundelaar.py:287](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:287) onbekende open noden als een lege lijst. De normale afsluiting stuurt dan een onvolledige lijst ([bord.py:441](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/koppelingen/bord.py:441)); het bord sluit de ontbrekende noden ([app.py:2194](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents/app.py:2194)). De nieuwe test gebruikt geen echte rondeafsluiting ([test_dagbundelaar_vaststelling.py:662](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/tests/test_dagbundelaar_vaststelling.py:662)). Herstel: stuur bij onbekende open lijst geen afsluitende noodlijst en toets dit met de echte `Ronde`.

2. **Hoog, al aanwezig op `origin/main`:** een geslaagde nachtronde slaat `bundelen()` over ([dagbundelaar.py:236](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:236)), maar sluit via dezelfde volledige lijst nog open ochtendnoden, zoals ontbrekende foto’s. Een *brekende* nachtronde bewaart ze wel. Behoud bij een geslaagde nachtronde noden die zij niet controleerde.

Bij een leesbaar bord werkt de nieuwe ochtendfilter: een opgeloste bundelnood sluit, vaststellingsnoden blijven open. Een actuele nachtketennood wordt vóór de vaststellingspoging toegevoegd ([dagbundelaar.py:253](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:253)) en blijft bij een ochtendfout staan. Verder vond ik geen nieuw hoog of middel punt in de PR-diff.

Gedaan: commit en volledige diff alleen gelezen.  
Nagekeken: ochtend, nacht, bordafsluiting; werkmap bleef schoon.  
Open: beide fouten in het behoud van noden.

**BESLISSING: niet klaar.**