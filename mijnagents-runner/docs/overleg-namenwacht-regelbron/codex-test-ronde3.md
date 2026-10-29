1. **OK** — Beide gevraagde tests slagen: 20/20 en 27/27. De nieuwe kopgevallen staan in [test_regelbron_en_ha_voorrang.py](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py:313).

2. **FOUT** — In een gesimuleerde v1.11 op basis van de echte v1.10 voegde ik na hoofdstuk C `## > B. Het verslag` en een nieuwe B6-regel toe. De vingerafdruk bleef gelijk aan de pin en de bron kreeg `geldig=True`. [hoofdstukken()](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/koppelingen/naamstructuur.py:469) slaat de controle op zo’n verdachte regel over zodra die als ATX-kop wordt herkend. Controleer die regel ook binnen die tak.

3. **OK** — De ongewijzigde echte v1.10 geeft exact de [pin](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/werkwijze/naamstructuur-regels.json:24) en krijgt `geldig=True`; zij pauzeert dus niet ten onrechte.

**NIET AKKOORD.**