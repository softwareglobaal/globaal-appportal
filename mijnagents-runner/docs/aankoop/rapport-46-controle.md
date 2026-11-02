**Nee, nog niet live zetten of de hele reeks opnieuw draaien.**

1. De opgegeven NL/BE-proef, de echte P07- en P09-citaten, D en X7 slagen in functieproeven. A/C en F zijn nog niet volledig hersteld.
2. **Hoog:** “Gratis binnen Nederland vanaf €50; verzendkosten naar België vanaf €9,95” levert toch een aanbeveling met €0 verzending op. De code wist ook het Belgische tarief als drempel ([aanbod.py:247](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:247)).
3. **Hoog:** “Ongeschikt voor DDF484” levert toch een aanbeveling van die accu op. “Geschikt” wordt herkend binnen “ongeschikt”, zonder dat de ontkenning wordt gezien ([aanbod.py:694](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:694)).
4. Ook “Gratis verzending naar België € 0,00” wordt ten onrechte geweigerd ([aanbod.py:248](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:248)). Alleen gelezen en in geheugen getest; niets gewijzigd of gepusht.