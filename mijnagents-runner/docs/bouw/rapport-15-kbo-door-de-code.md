NIET AKKOORD

1. **Hoog:** code-uitkomst `None` valt terug op modelbewijs. Tegenproef werd daardoor toch actief en kreeg een zetel. [bouw/zoeken.py:319](mijnagents-runner/bouw/zoeken.py:319), [bouw/zoeken.py:334](mijnagents-runner/bouw/zoeken.py:334)
2. **Middel:** na `OSError` wordt hetzelfde ondernemingsnummer opnieuw opgevraagd. Tegenproef: 2 oproepen. [bouw/zoeken.py:186](mijnagents-runner/bouw/zoeken.py:186), [bouw/zoeken.py:192](mijnagents-runner/bouw/zoeken.py:192)
3. **Middel:** de vestigingsoproep kan ná de deadline starten. Tegenproef bevestigd; elke oproep kan 30 seconden duren. [bouw/zoeken.py:174](mijnagents-runner/bouw/zoeken.py:174), [kern_adres.py:60](mijnagents-runner/bouw/kern_adres.py:60)
4. **Middel:** het model krijgt nog `kbo_url` en “web en de KBO”, ondanks “lees die niet”. [bouw/zoeken.py:43](mijnagents-runner/bouw/zoeken.py:43), [bouw/zoeken.py:92](mijnagents-runner/bouw/zoeken.py:92)

258 tests groen; niets gewijzigd.