# Verwerking controle 8 (Codex, 8 punten), 30-10-2026, Claude 1

- X1: de tooltekst van De Regisseur noemt geen firma meer; hij geeft de firma door zoals Mehdi ze noemt, en de agent
  leidt de code eruit af (`vraag.firma_uit`).
- X2: datums worden blanco gemaakt voor bedragen gezocht worden; "geldig tot 30.10.2026" is geen 30,10 euro.
- X3: de naam telt alleen met de eigen woorden van de naam (niet een vakwoord als dakwerken); zonder eigen woord de
  volledige naam als geheel.
- X4: "indicatief" is alleen een raming als het over een prijs, kost, bedrag of raming gaat.
- X5: "h a bv" en "h b bv" in kleine letters, "nr." of "n°" tussen straat en nummer, het nummer voor de straat.
- X6: zonder vergelijking per post zegt de eerste regel van het verslag dat alleen de totalen vergeleken zijn.
- X7: Franse adressen met het nummer vooraan. OFFERTE_NAAR_AI blijft uit.
- X8: regressietests: 212 bouwtests.

Stopregel: controle 7 had twee punten van ernst hoog, controle 8 drie. Na deze ronde volgt nog een controle; blijft er
dan een punt van ernst hoog open, dan beslist Mehdi over de ingebruikname (werkafspraken 4.7).
