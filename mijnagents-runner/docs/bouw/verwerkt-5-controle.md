# Verwerking controle 5 (Codex, 9 punten), 30-10-2026, Claude 1

Na vijf rondes kwamen telkens nieuwe randgevallen in dezelfde drie soorten terug (namen in vrije tekst, het adres van
de vestiging, totalen). Volgens de stopregel (werkafspraken 4.7) is het ontwerp daar herbekeken, in plaats van nog
een patroon toe te voegen:

- Zoekvraag (X3, ook X4 van controle 4): naar buiten gaan alleen vakwoorden, getallen en eenheden
  (`bouw/vakwoorden.py`, met samengestelde woorden uit stammen). Elk ander woord valt weg en het verslag noemt het;
  ook de mail gebruikt alleen het gefilterde werk. Een naam hoeft dus niet meer herkend te worden.
- Vestiging (X1, ook X3 van controle 3 en 4): de afstand komt alleen van de zetel op de gelezen KBO-pagina
  (`kbo_zetel`), nooit van een adres op de website of van het model. Zonder zetel: na te kijken.
- Totalen (X2): elk bedrag op een totaalregel krijgt het label vlak ervoor (excl, incl of btw-bedrag),
  `bedragen_met_label`.

De andere punten:
- X4: kern moet voor beide firma's een ondernemingsnummer en een adres hebben, anders geen werk (nood voor Mehdi).
- X5: een werkverslag of dossier van een bouwagent telt als firma onbekend; dan geeft De Regisseur nooit een antwoord
  dat beide firma's noemt. De werkverslagen bewaren geen verslaginhoud of kenmerken meer, alleen vingerafdrukken en
  aantallen.
- X6: namen in hoofdletters worden ook binnen een zin weggehaald. OFFERTE_NAAR_AI blijft uit.
- X7: "aanverwante werken" is bouwtaal; "verwante firma" blijft verboden.
- X8: de offertedatum alleen met een label (Datum:, Offertedatum, opgemaakt op); zonder label onbekend en geen
  berekende geldigheid.
- X9: regressietests voor alles hierboven: 177 bouwtests, 55 regisseurtests.
