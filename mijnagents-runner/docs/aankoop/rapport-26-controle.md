**Niet klaar.** Optie A is grotendeels gebouwd, maar de nieuwe voorafstop faalt in twee concrete gevallen. Nog niet live zetten of de MOVA-vraag draaien.

1. **Hoog:** Bij 93% met een toekomstige `resetsAt` alleen op hoofdniveau bewaart [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:390) geen herstarttijd. De volgende vraag mag daardoor direct starten ([regel 293](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:293)). Dit is in het geheugen gereproduceerd. Neem die herstarttijd over; blokkeer bij een onbekende herstarttijd.
2. **Hoog:** `--proef-abonnement` controleert de vorige meting niet en bewaart een meting boven 90% niet wanneer de proef stopt ([onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:558)). Pas dezelfde voorafstop en opslag toe.

Gedaan: diff gelezen, scenario gereproduceerd, niets gewijzigd.  
Nagekeken: stops op `isUsingOverage`, 90% en een andere bron blijven aanwezig.  
Open: deze twee fouten herstellen en testen; daarna live en één MOVA-vraag.