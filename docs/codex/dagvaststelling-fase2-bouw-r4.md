**Niet klaar.** De gewone paden van R1 tot R6 zijn hersteld, maar de overstap naar nieuwe sleutels en twee uitrolsituaties kunnen nog fout lopen.

### Voor Mehdi

Als er al oproepen met de oude sleutels op het bord staan, kan de eerste ronde dezelfde oproepen dubbel tellen. Ook kan de uitrol bestanden wisselen terwijl een wacht nog draait, of een proefbewijs afgeven voor code die niet volledig beproefd is.

| Punt | Code en test |
|---|---|
| R1 | Sleutels blijven stabiel bij een opschuivend venster; test aanwezig. Overstap vanaf oude sleutels ontbreekt, zie S1. |
| R2 | Eigen uitvoer per aanvraag en `.lezen` zijn aanwezig. Tests gebruiken opeenvolgende aanvragen; opruiming heeft S2. |
| R3 | Fout, ronde ID en open nood worden samen nagekeken; tests aanwezig. |
| R4 | Stopopdrachten komen vóór de wissel; de test bewijst niet dat stoppen gelukt is, zie S3. |
| R5 | Bezette wachten geven 75; een proef eist een bevestigde ronde ID. De volledige `proef` opdracht is niet getest, zie S4. |
| R6 | Drie opeenvolgende uitrollen en één terugkeer zijn getest. Gelijktijdige opdrachten ontbreken, zie S4. |

### Voor Claude en Shaniel

1. **S1, hoog:** [mac_gesprekken.py:364](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:364) en [mac_gesprekken.py:608](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:608). In een geheugenproef bleven vijf oude en vijf nieuwe telefoonrijen meetellen: de nieuwe rijen werden geschreven, waarna de vervallencontrole stopte. Maak de sleuteloverstap expliciet en test een bord met oude rijen. Of zulke rijen live bestaan, kon ik niet lezen.

2. **S2, middel:** [macgesprekken_kopie.c:229](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:229). `ruim_op` verwijdert ook een ouder bestand zoals `gesprekken-archief.sqlite`. Beperk de naamcontrole tot de exacte uitvoernamen en test dat andere bestanden blijven staan.

3. **S3, hoog:** [uitrol_mac_gesprekken.sh:55](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:55). Een mislukte `bootout` wordt genegeerd; daarna begint de codewissel. Controleer vóór de wissel dat beide wachten werkelijk uit zijn en test een falende stop.

4. **S4, hoog:** [uitrol_mac_gesprekken.sh:82](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:82) en [uitrol_mac_gesprekken.sh:139](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:139). Zonder exclusief slot kan `installeer` tijdens `proef` de code wisselen; `proef` stempelt daarna de nieuwe versie. Geef deze opdrachten één gedeeld slot en test de overlap.

Gedaan: commit `c210c3c` alleen gelezen.  
Nagekeken: code, verschillen, tests, shellsyntaxis en de geheugenproef; Mac-tests niet herhaald in deze zandbak.  
Open: S1 tot S4.

live: nee