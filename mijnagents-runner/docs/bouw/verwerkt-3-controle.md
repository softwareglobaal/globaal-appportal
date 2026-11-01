# Verwerking controle 3 (Codex, 11 punten), 30-10-2026, Claude 1

Alle punten hersteld, met regressietests (`tests/test_bouw.py` 141 goed, `tests/test_regisseur.py` 55 goed).

- X1: nummers worden op cijfers vergeleken (016/79.32.96, 0491/94.68.79, BE0537405239 in elke schrijfwijze);
  `scheiding.laad_kern()` haalt ondernemingsnummer en adres van beide firma's uit kern.firma en kern.adres; beide
  runners laden het aan het begin van een ronde en melden een nood als kern niet leesbaar is.
- X2: een KBO-pagina is nooit de eigen pagina van een firma.
- X3: de vestiging telt alleen als de postcode (of de gemeente) op een gelezen pagina van de eigen website staat;
  anders is de afstand onbekend en komt de firma bij na te kijken.
- X4: de lessen en collega's naar het model zonder regels met iets dat op een persoon, adres of nummer lijkt.
- X5: elk bouwverslag krijgt als sleutel firma:vingerafdruk van de vraag (`vraag.sleutel`). De Regisseur rekent die
  sleutel uit de vraag die hij doorgaf, geeft ze terug als `lees_verslag` en leest met `klaargezet` (nieuw veld
  sleutel) precies dat verslag; zonder sleutel van een bouwagent alleen het laatste item.
- X6: een regel die alleen een naam is, wordt weggehaald. OFFERTE_NAAR_AI blijft uit.
- X7: het eindtotaal: eerst een regel die zich eindtotaal, netto, na korting of te betalen noemt, anders de laatste;
  nooit gewoon het grootste. Een totaal na korting telt als totaal.
- X8: Dropbox tot twintig pagina's; daarna staat in het verslag dat niet alle treffers gelezen zijn.
- X9: "groep D" en "groep 1" zijn bouwtaal.
- X10: de generator draait in een tijdelijke kopie zonder de echte runner; de echte werkboom wijzigt niet meer.
- X11: regressietests voor X1 tot X10.
