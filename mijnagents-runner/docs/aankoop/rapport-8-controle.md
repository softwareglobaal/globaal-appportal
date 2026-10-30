**Niet klaar.** Een proefpagina voor de MOVA V70 voor Suriname laat een verkeerde aanbeveling door, terwijl de getoonde bewijscontext de fout verbergt. De eerste echte proefronde is daarom nog niet aanvaardbaar, ook als Mehdi het verslag naleest.

### Voor Mehdi

In mijn tegenproef kost de MOVA V70 100 euro plus 25 euro verzending. Op dezelfde pagina staat gratis verzending bij accessoire Y. Het verslag raadt de MOVA toch aan voor 100 euro, boven een tweede passend aanbod van 115 euro. Onder de aanbeveling zijn noch de 25 euro, noch accessoire Y zichtbaar. Dit zijn proefgegevens, geen bewering over een echte winkelprijs.

### Voor Claude en Shaniel

1. **X2, hoog, deels.** Een accessoirekop vlak bij het citaat wordt afgewezen. Staat die meer dan 250 tekens ervoor, dan telt de stekker van het accessoire alsnog als passend en ontbreekt de kop in het verslag. [aanbod.py:374](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:374). Koppel de specificatie aan de productsectie.
2. **X12, hoog, deels.** Verzendbewijs van een andere pagina wordt geweigerd; bewijs bij een ander product *op de aanbodpagina* telt nog wel. Dat veroorzaakt de MOVA-tegenproef hierboven. [aanbod.py:280](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:280). Controleer bij welk product de verzendtekst hoort.
3. **X16, hoog, niet opgelost.** Verzendkosten van `/bezorging` blijven buiten beschouwing. Mijn tegenproef beveelt daardoor 130 euro aan terwijl een aanbod van 100 plus 5 euro verzending beschikbaar is. [aanbod.py:467](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:467). Laat aantoonbaar toepasselijke algemene verzendvoorwaarden meetellen.
4. **Nieuw, hoog.** Veilingkosten mogen nu van iedere gelezen pagina op dezelfde host komen. Kosten van kavel B maken kavel A in mijn tegenproef schijnbaar goedkoper: 1.190 in plaats van 1.450 euro. [aanbod.py:426](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:426). Vereis voorwaarden die aantoonbaar voor kavel A gelden.

Gedaan: diff en herstel gelezen; niets gewijzigd.  
Nagekeken: eigen tegenproeven en 143 bestaande tests, 0 fouten.  
Open: X2, X12, X16 en het veilingbewijs herstellen.