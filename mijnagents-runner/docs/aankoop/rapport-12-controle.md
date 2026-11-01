**niet klaar**

Voor Mehdi: de muntcontrole werkt. De eerdere tegenproef met 50 Hz op de winkelpagina wordt nu afgekeurd. Toch kan een aanbod nog ten onrechte als geschikt voor Suriname worden aanbevolen zonder dat het getoonde bewijs de tegenspraak laat zien. Daarom raad ik de live proef nog af.

Voor Claude en Shaniel:

1. **Hoog, onderdeelbewijs: deels opgelost.** Mijn tegenproef: de winkelpagina noemt geen frequentie, de gekozen handleiding noemt 50/60 Hz en een derde gelezen pagina voor dezelfde modelcode noemt **basisstation: 50 Hz**. `verwerk()` geeft toch `compatibel=ja` en een beste aanbod. De controle in [aanbod.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:470) bekijkt alleen de winkelpagina en de gekozen handleiding; het [verslag](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:522) toont geen link naar de derde pagina. Toets ook gelezen pagina’s met dezelfde modelcode op tegenspraak.
2. **Munt: opgelost.** Mijn tegenproef laat “MOVA Europa 949 USD” met munt EUR weg en laat dezelfde prijs met munt USD toe. Zie [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:42).
3. **Nieuwe hoge fout:** geen gevonden. Punt 1 is het resterende probleem uit de vorige controle.

Gedaan: alleen gelezen; niets gewijzigd of gepusht.  
Nagekeken: diff, eigen tegenproeven en 180 geslaagde tests.  
Open: onderdeelbewijs herstellen vóór de MOVA-proef.