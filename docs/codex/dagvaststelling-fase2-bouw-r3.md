**Niet klaar.** Een iPhone-oproep kan op het bord de plaats van een oudere oproep innemen. De uitrol kan bovendien gewijzigde code laten draaien voordat de nieuwe proef is bewezen.

### Voor Mehdi

De telefoonsleutels moeten stabiel blijven als het leesvenster opschuift. Ook moet de Mac-uitrol de wachten tijdig stoppen, een eigen geslaagde ronde bewijzen en de volledige vorige versie kunnen terugzetten.

### Voor Claude en Shaniel

| Punt | Code en test | Oordeel |
|---|---|---|
| Q1 | [code](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:357), [test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:685) | Deels |
| Q2 | [code](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:604), [grensproef](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:706) | Opgelost |
| Q3 | [code](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:110), [wisselproef](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:768) | Opgelost |
| Q4 | [META-controle](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:568), [test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:420) | Deels |
| Q5 | [code](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:616), [test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:732) | Opgelost |
| Q6 | [code](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:627), [test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:745) | Deels |
| Q7 | [uitrol](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:58) | Deels, geen gerichte uitroltest |
| Q8 | [code](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/app.py:723), [API-test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/test_gesprekken_api.py:405) | Opgelost |

1. **R1, hoog, Q1.** De sleutel van de tweede oproep verliest zijn tijdsuffix zodra de eerste buiten het leesvenster valt. Een geheugenproef bevestigde dit. Gebruik een blijvend unieke sleutel per bronoproep en test twee opeenvolgende vensters.

2. **R2, middel, Q4.** Na de META-controle opent [lees](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:222) het vaste bestand opnieuw voor iedere vraag. Een andere start kan het tussentijds vervangen. Geef iedere aanvraag een eigen uitvoerbestand en test overlappende starts.

3. **R3, middel, Q6.** [De eindcontrole](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:635) accepteert iedere teruggelezen status `fout`, ook een oude wanneer het versturen faalde. Bevestig de fout en nood met de huidige ronde-ID; test een mislukte verzending.

4. **R4, hoog, Q7.** [Installeer](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:123) vervangt code voordat de wachten uitgaan. Bij alleen gewijzigde Python-code blijven ze zelfs actief. Stop ze vóór de wissel en eis daarna een nieuwe proef.

5. **R5, middel, Q7.** [Proef](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:76) schrijft bewijs terwijl een bezette wacht met [exitcode 0](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/whatsapp_wacht.py:113) geen eigen ronde deed. Eis een nieuwe, bevestigde ronde-ID.

6. **R6, middel, Q7.** [Terug](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:91) herstelt de codecommit niet en kan oude plists mengen. Bewaar en herstel één volledige versie; test drie opeenvolgende uitrollen.

Gedaan: commit `3d4b2f9` alleen gelezen.  
Nagekeken: code, tests en een geheugenproef; Mac-testuitslagen zijn die van Claude.  
Open: R1 tot R6 en een gerichte uitroltest.

live: nee