**Beslissing: niet klaar.** H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; geen stuk van de ene noemt de andere of laat een band vermoeden. De letterlijke voorbeelden uit controle 7 zijn hersteld, maar vier grendels zijn nog te omzeilen.

X1 hoog, [regisseur.py:293](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/regisseur.py:293): de tooltekst noemt beide firmanamen en codes samen en gaat bij iedere Regisseur-ronde naar het externe model. De uitvoergrendel werkt pas achteraf. Zodra Mehdi de Regisseur gebruikt, houdt geen menselijke controle dit meer tegen.

X2 hoog, [bouw/offertes.py:117](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:117): `Totaal excl. btw: nog te bepalen, geldig tot 30.10.2026` wordt 30,10 euro en kan als laagste eindigen. Mehdi houdt dit alleen tegen door het totaal in de originele PDF na te kijken.

X3 hoog, [bouw/zoeken.py:178](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/zoeken.py:178): `Dakwerken Fantasio` kwam groen terwijl de site nergens `Fantasio` noemde; het algemene langste woord `dakwerken` volstond. Actieve KBO en afstand maakten de kandidaat volledig groen. Mehdi moet elke site zelf openen.

X4 middel, [bouw/offertes.py:30](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:30): een echte offerte met `Indicatieve uitvoeringstermijn` in de kop wordt als raming uitgesloten. Mehdi ziet de waarschuwing en kan de PDF controleren.

X5 middel, [bouw/scheiding.py:18](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/scheiding.py:18): `h a bv`, `Gerzenstraat nr. 5A` en `19 Hoveniersstraat` passeren. Mehdi ziet dit nog op het bord of vóór het kopiëren van een mail.

X6 middel, [bouw/offertes.py:158](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:158): documentbasis, inclusies en uitsluitingen worden zonder AI niet gelezen, maar totalen worden wel gerangschikt. Mehdi moet daarom de scopes van de PDF’s zelf vergelijken.

X7 laag, [bouw/offertes.py:231](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:231): `3 Rue Neuve, 1000 Bruxelles` blijft staan. `OFFERTE_NAAR_AI=False` voorkomt nu blootstelling; Mehdi’s weigering is de huidige stop.

X8 laag, [tests/test_bouw.py:481](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/tests/test_bouw.py:481): tests voor X1 tot X7 ontbreken, waardoor 202 tests toch groen zijn. Alleen Mehdi’s handmatige controle vangt ze nu.

Gedaan: volledige takdiff gelezen, niets gewijzigd.  
Nagekeken: modulo 97, SQL-scheiding, Dropbox-vorm, Agentnorm en uitrol gaven geen extra bevinding.  
Open: bovenstaande herstelpunten en regressietests; Regisseur-tests konden zonder schrijfbare tijdelijke map niet starten.