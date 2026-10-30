# Verwerking controle 6 (Codex, 8 punten), 30-10-2026, Claude 1

Dezelfde lijn als na controle 5: liever een officiele bron dan een patroon.

- X1: als gebied gaat alleen de postcode en gemeente naar buiten zoals Geopunt ze teruggeeft (`officiele_gemeente`),
  nooit de tekst van de vraag. Wat Geopunt niet kent of als Geopunt onbereikbaar is: niet gestart.
- X2: een site hoort pas bij de onderneming als haar ondernemingsnummer op een gelezen pagina van die site staat (een
  Belgische firmasite moet het tonen); anders na te kijken, nooit bovenaan.
- X3: het dossier van een bouwagent bevat geen verslagen meer, en `klaargezet` geeft zonder sleutel geen enkel
  bouwverslag; De Regisseur leest alleen met de sleutel uit lees_verslag.
- X4: btw verlegd alleen in een zin zonder ontkenning; verlegd en toch een tarief: niets berekend, wel gemeld. Een
  raming alleen als het document zichzelf zo noemt (kop of "dit/deze ... raming" zonder verwijzing naar een vorig stuk).
- X5: H.A., H.B., "H A Architects", afgekorte straten en een huisnummer voor de straat, ook voor het adres uit kern.
- X6: een naam vlak voor een weggehaald adres gaat mee weg. OFFERTE_NAAR_AI blijft uit.
- X7: "eigen aannemer", "vaste aannemer" en "partner van de fabrikant" zijn gewone taal; "onze vaste aannemer",
  "onze eigen aannemer" en "onze vaste partner" blijven verboden.
- X8: regressietests: 193 bouwtests, 55 regisseurtests.
