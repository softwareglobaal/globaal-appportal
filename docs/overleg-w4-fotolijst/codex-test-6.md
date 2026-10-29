Niet akkoord met live zetten. De eerdere fouten met gemengde lijsten, BOM en afwijkende regels zijn verholpen, maar ik vond nog een onterechte `ok`.

1. **Hoog:** [werfverslag_voorbereider.py](/Users/user2025/dev/_wt-w4/mijnagents-runner/werfverslag_voorbereider.py:645) ziet `.HEIC` en `.heic` als verschillende tabelnamen, terwijl de JPG-controle beide aan dezelfde foto koppelt. Mijn leesproef voegde voor één foto een tweede rij toe, om 12:33 of op 450 m. W4 gaf toch `ok`. Wijs zulke dubbele namen af en leg beide gevallen vast in tests.

Gedaan: alleen gelezen en getest; niets gewijzigd of gepusht.  
Nagekeken: 99 tests en 14 subtests geslaagd; 2 integratietests konden door het schrijfverbod geen tijdelijke map maken. De VM-ronde heb ik niet herhaald.  
NIET AKKOORD: een tegenstrijdige tweede rij voor dezelfde foto kan W4 nog ten onrechte goedkeuren.