**Niet klaar.** Drie eerdere fouten blijven mogelijk en vallen onder de uitzondering op de stopregel: de aanbeveling kan verkeerd zijn terwijl het zichtbare citaat de beslissende context weglaat.

### Voor Mehdi

Een oude prijs kan nog als huidige prijs verschijnen. Ook kan een stekker van een accessoire als bewijs voor het toestel tellen, of gratis verzending voor een ander product als gratis verzending voor dit aanbod. Herstel de context en herkomst van die citaten vóór de eerste echte ronde.

### Voor Claude en Shaniel

1. **X1 — hoog, deels.** `100 euro (oude prijs)` wordt geweigerd, maar `X1 100 euro. (oude prijs) Vandaag 90 euro` wordt voor 100 euro aanbevolen. Het citaat toont alleen `X1 100 euro`. Controleer de prijsaanduiding ook voorbij de punt en toon die context. [aanbod.py:135](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:135)
2. **X2 — hoog, deels.** Bewijs van een andere pagina wordt geweigerd. Op de eigen pagina telt `Stekker type A/B.` van een accessoire echter voor een X1 met stekker type C; het citaat verbergt de accessoirecontext. Koppel bewijs aan het aangeboden product of toon de omliggende tekst. [aanbod.py:367](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:367)
3. **X9 — opgelost.** Bij 100 euro inclusief btw en 10 euro verzending met onbekende btw-status ontstaat geen totaal. Bij expliciet exclusieve verzend-btw wordt 112,10 euro berekend. [aanbod.py:298](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:298)
4. **X12 — hoog, deels.** `Geen gratis verzending` wordt geweigerd. Maar X1 met 25 euro verzendkosten wordt toch voor 100 euro aanbevolen wanneer product Y bij dezelfde winkel gratis verzending heeft. Het citaat noemt Y niet. Beperk het bewijs tot het aanbod of algemene winkelvoorwaarden en toon de bronpagina. [aanbod.py:392](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:392)
5. **X14 — opgelost.** `Verzendkosten nu 25 euro` wordt niet meer als productprijs aanvaard. [aanbod.py:42](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:42)
6. **X15 — opgelost.** Een tekstwaarde voor `compatibiliteit` laat het verslag niet meer crashen. [verslag.py:53](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/verslag.py:53)

**Nieuwe fouten van ernst hoog:** geen afzonderlijke vastgesteld in de gewijzigde regels. De drie resterende gevallen waren ook op `7195f46` mogelijk.

Gedaan: alleen gelezen en gerichte tegenproeven uitgevoerd; niets gewijzigd.  
Nagekeken: 137 bestaande tests goed, plus vergelijking van de drie resterende gevallen op beide commits.  
Open: X1, X2 en X12 herstellen en opnieuw gericht toetsen.