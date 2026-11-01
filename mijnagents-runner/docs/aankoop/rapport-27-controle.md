**Niet klaar.**

1. De twee concrete fouten uit controle 26 zijn hersteld: de herstarttijd op hoofdniveau wordt overgenomen, en de abonnementsproef controleert en bewaart de limietmeting. Zie [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:399) en [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:577).
2. **Hoog:** zonder bekende herstarttijd vervalt de blokkade na vijf uur, ook voor een zevendaagse limiet van 95%. Ik heb in het geheugen gereproduceerd dat een nieuwe vraag na zes uur weer mag starten. Een limietbestand van vóór deze commit zonder `gemeten_ts` wordt zelfs direct genegeerd. Zie [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:285).

**Live en één MOVA-vraag: nee.** Blokkeer eerst tot een herstart bewezen is en behandel oude limietbestanden veilig. Ik heb alleen gelezen en in het geheugen gecontroleerd; niets gewijzigd.