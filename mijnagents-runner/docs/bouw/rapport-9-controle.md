**Beslissing: niet klaar.** H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; geen stuk van de ene noemt de andere. Controle 8 is deels opgelost, maar X1 blijft hoog.

X1 hoog, [regisseur.py:1374](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/regisseur.py:1374): bij een HB-bouwvraag krijgt het externe model nog de andere firmanaam via de vaste systeemtekst. De uitvoergrendel werkt pas achteraf. Geen handeling van Mehdi houdt dit tegen zodra hij De Regisseur gebruikt.

X2 middel, [scheiding.py:21](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/scheiding.py:21): `h.a. bv` en `h.b. bv` passeren de grendel, terwijl de vormen zonder punten nu wel worden herkend. Mehdi kan dit nog zien op het bord of vóór hij een conceptmail kopieert.

X3 middel, [offertes.py:308](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:308): een verlopen offerte blijft meedoen en kan bovenaan als laagste staan. De waarschuwing staat pas lager. Mehdi houdt dit tegen door “Om op te letten” en de PDF te lezen.

X4 middel, [offertes.py:30](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:30): `Indicatieve offerte` wordt als raming uitgesloten. Mehdi ziet “raming” en kan het originele document controleren.

X5 middel, [zoeken.py:246](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/zoeken.py:246): e-mail en telefoon worden niet tegen de gelezen site gecontroleerd. Een gerichte proef zette verzonnen contactgegevens toch groen. Mehdi moet de site openen vóór verzending.

X6 laag, [offertes.py:238](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:238): `3 Voorbeeldlaan` en een losse achternaam blijven na `redigeer` staan. `OFFERTE_NAAR_AI=False` houdt dit nu tegen; Mehdi’s toestemming is de extra grens.

X7 middel, [offertes.py:154](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/bouw/offertes.py:154): `pypdf` ontbreekt in de runtimevereisten en het [uitrolscript:18](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/docs/bouw/uitrol.sh:18) installeert het niet. Zonder toevallige VM-installatie worden alle PDF’s onleesbaar; Mehdi ziet dan geen bruikbare vergelijking.

X8 laag, [test_bouw.py:498](/Users/mehdichegini/dev/_bouwagents/mijnagents-runner/tests/test_bouw.py:498): regressietests voor X1 tot X7 hierboven ontbreken.

Gedaan: volledige takdiff gelezen, niets gewijzigd.  
Nagekeken: 212 Bouw-tests groen; modulo 97, SQL, Dropbox-vorm, wachttijden en Agentnorm statisch akkoord.  
Open: volledige Regisseur- en Agentnorm-tests konden in deze leesomgeving geen tijdelijke map maken.