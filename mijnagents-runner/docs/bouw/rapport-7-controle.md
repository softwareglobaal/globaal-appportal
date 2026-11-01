**Beslissing: niet klaar.** H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; geen stuk van de ene noemt de andere of laat een band vermoeden. Controle 6 is niet volledig opgelost.

X1 hoog, [bouw/zoeken.py:160](mijnagents-runner/bouw/zoeken.py:160): een ongerelateerde gelezen pagina met alleen het ondernemingsnummer in de footer kwam met actieve KBO en 3,5 km afstand toch bij `goed`. Controleer ook kandidaatnaam en activiteit op de pagina. Mehdi houdt dit alleen tegen door elke link zelf te openen.

X2 hoog, [bouw/offertes.py:97](mijnagents-runner/bouw/offertes.py:97): latere getallen op dezelfde totaalregel erven het totaallabel. `Totaal excl. BTW 10.000,00, geldig 30 dagen` werd 30 euro; `levering in 6 weken` werd 6 euro. Dit kan de rangschikking omkeren. Mehdi moet de originele PDF-totalen vergelijken.

X3 middel, [bouw/scheiding.py:18](mijnagents-runner/bouw/scheiding.py:18): varianten `H B BV`, `H A BV`, `Gerzenstraat 5A` en `5A Gerzenstraat` passeren. Telefoons worden bovendien niet uit kern geladen. Mehdi ziet dit op het bord of vóór hij een concept kopieert en verstuurt.

X4 laag, [bouw/offertes.py:208](mijnagents-runner/bouw/offertes.py:208): `Klantnaam: Jan Peeters` en `Rue Neuve 3` blijven ongewijzigd in `redigeer()`. `OFFERTE_NAAR_AI=False` voorkomt nu blootstelling; Mehdi’s weigering houdt dit tegen.

X5 laag, [bouw/scheiding.py:38](mijnagents-runner/bouw/scheiding.py:38): gewone bouwtaal `zusterbalk` wordt door het losse patroon `zuster` geblokkeerd. Mehdi kan alleen herformuleren.

X6 laag, [tests/test_bouw.py:451](mijnagents-runner/tests/test_bouw.py:451): tests voor X1 tot X5 ontbreken; daardoor blijven 193 tests groen.

Gedaan: volledige gevraagde diff gelezen, niets gewijzigd.  
Nagekeken: 193 Bouw-tests groen; gerichte lokale reproducties bevestigen X1 tot X5.  
Open: herstel en regressietests; Agentnorm en uitrolscript gaven geen extra bevinding.