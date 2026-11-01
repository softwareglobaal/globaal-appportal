# Verwerking controle 4 (Codex, 10 punten), 30-10-2026, Claude 1

Alle punten hersteld, met regressietests (`tests/test_bouw.py` 159 goed, `tests/test_regisseur.py` 55 goed).

- X1: zonder de gegevens van beide firma's uit kern werkt geen van beide agents; de vragen blijven klaarstaan en er
  is een nood.
- X2: HARC en HARM ongeacht hoofdletters (Harm BV); HA en HB alleen in hoofdletters, anders is hectare een firma.
- X3: een vestiging telt alleen als het adres van de firma op haar eigen pagina staat, met haar postcode als eerste
  postcode erna; een postcode in een lijst van het werkgebied bewijst niets.
- X4: `vraag.persoonsgegevens()` herkent ook namen en adressen in hoofdletters en een straat als los woord met een
  nummer (Grote Markt 12); dezelfde toets voor de lessen naar het model. Een naam helemaal in kleine letters is niet
  van een gewoon woord te onderscheiden: daar blijft de regel voor De Regisseur (nooit een naam doorgeven).
- X5: De Regisseur houdt bij welke firma een antwoord raakte (de firma uit de vraag van de ronde, het voorvoegsel van
  de sleutel van een gelezen verslag). Raakt het twee firma's, dan geeft hij ze niet samen; haalt het antwoord de
  scheiding van die firma niet, dan geeft hij een vaste zin. Zijn systeemtekst noemt de tweede firma niet meer.
- X6: `redigeer()` haalt ook namen na voor of bij en losse adressen binnen een zin weg. OFFERTE_NAAR_AI blijft uit.
- X7: "Totaal excl. btw na 10% korting" is een eindtotaal; prijsindicatie, budgetraming en dergelijke zijn een raming.
- X8: "onze groep warmtepompen" is bouwtaal; alleen dezelfde groep, tot de groep en groep van bedrijven blijven verboden.
- X9: de uitrol stopt als ~/appportal niet op main staat of na de pull niet gelijk is aan origin/main.
- X10: regressietests voor X1 tot X9. De CI van Bouw installeert nu ook de pakketten van het bord, voor de toets van
  De Regisseur.
