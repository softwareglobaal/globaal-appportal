**Niet klaar.** T1 is opgelost en de nieuwe test houdt de rem vast. T2 is gedeeltelijk opgelost. Bij de controle van het geheel kwam bovendien een nieuw punt van middelmatige ernst naar voren.

### Voor Mehdi

De Mac helper zet ook gegevens van oproepen uit andere apps en van WhatsApp sessies die niet meetellen in zijn tijdelijke uitvoer. De wachten slaan die gegevens pas daarna over. De helper moet ze al bij het lezen uitsluiten.

Een rechtstreekse interne uitrol stopt nu als er geen slot vastzit. Als een andere uitrol de sloten vasthoudt, kan diezelfde aanroep toch doorgaan.

### Voor Claude en Shaniel

1. **U1, middel:** [macgesprekken_kopie.c:71](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:71) neemt alle sessies met recente berichten op, ongeacht sessietype. [De telefoonvraag op regel 80](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:80) neemt alle aanbieders op en selecteert daarna ook contacten bij hun nummers. De runner filtert pas later. Filter in de helper op toegelaten sessies en op Telephony en FaceTime. Test dat een uitgesloten sessie, oproep en contact ontbreken in de uitvoer.

2. **U2, laag, T2 gedeeltelijk:** [uitrol_mac_gesprekken.sh:106](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:106) bewijst dat *iemand* de sloten houdt, niet dat het eigen uitrolproces dat doet. [De test op regel 987](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:987) probeert de directe aanroep alleen wanneer de sloten vrij zijn. Bind de interne wissel aan eigen slotbezit en test een directe aanroep terwijl een andere uitrol de sloten houdt.

Gedaan: de laatste commit en het geheel tegenover main alleen gelezen.  
Nagekeken: T1 en zijn drie brongevallen zijn afgedekt; de door Claude gemelde Mac tests zijn hier niet herhaald.  
Open: U1 en U2.

live: nee