**Niet klaar.** De gemelde oude prijs wordt nu geweigerd, maar de fouten rond zichtbaar bewijs en verzending zijn deels hersteld. De nieuwe paginaselectie kan bovendien een duurder aanbod aanbevelen.

### Voor Mehdi

- **X1 — opgelost voor het gemelde geval.** `X1 100 euro. (oude prijs)` wordt niet meer als huidige prijs aanvaard; mijn tegenproef bevestigt dat.
- **X2 — deels.** Staat ‘accessoire’ wat verder vóór de stekkerspecificatie, dan verdwijnt dat woord uit het zichtbare bewijs terwijl het toestel aanbevolen blijft. De context is dus niet altijd zichtbaar genoeg.
- **X12 — deels.** Een gewone pagina van product Y telt niet meer mee. Een productpagina met `service` in de URL telt wél mee: X1 met 25 euro verzendkosten wordt dan voor 100 euro aanbevolen op basis van gratis verzending voor Y.
- **X16 — nieuw, hoog.** De algemene winkelpagina `/bezorging` wordt juist uitgesloten. In mijn vergelijking werd daardoor het aanbod van 105 euro gepasseerd en dat van 130 euro aanbevolen.

### Voor Claude en Shaniel

1. **X1 — opgelost:** [aanbod.py:155](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:155). Tegenproef: prijsbewijs `X1 100,00 euro` op `X1 100,00 euro. (oude prijs) Vandaag 90,00 euro` wordt geweigerd.
2. **X2 — hoog, deels:** [aanbod.py:132](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:132), [verslag.py:57](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/verslag.py:57). De grens van 70 tekens vóór het citaat verbergt in mijn proef de kop ‘Accessoire laadstation’. Toon de relevante sectie inclusief kop; maak bewijs onvolledig als die context wordt afgekapt.
3. **X12 — hoog, deels:** [aanbod.py:419](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:419). `/producten/service-kit-y` passeert de filter als algemene pagina. Controleer of de verzendvoorwaarde voor het aangeboden product geldt, niet alleen of de URL een trefwoord bevat.
4. **X16 — hoog, nieuw:** [aanbod.py:38](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:38). `/bezorging` mist de URL-filter. Dezelfde tegenproef kiest op `d5a7cf1` X1 voor 105 euro en op `6ea690f` product Z voor 130 euro. Herken algemene voorwaarden op hun inhoud en toepassingsgebied.

Gedaan: alleen gelezen; niets gewijzigd.  
Nagekeken: eigen tegenproeven en 141 bestaande tests, alle geslaagd.  
Open: X2, X12 en X16 herstellen en gericht opnieuw toetsen.