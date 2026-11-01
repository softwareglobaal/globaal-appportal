**Niet klaar. Live: nee.** Punt 3 van controle 22 is opgelost: bij `fout`, `limiet` en geen leesbaar antwoord komt er geen verslag en blijft de bordvraag staan. [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:112)

**Hoog, voor Claude en Shaniel:** bij `plafond` (tijd, beurten of zoekgrens) kan een al leesbaar JSON-antwoord alsnog een verslag worden en wordt de bordvraag als opgepakt gemarkeerd. Laat ook dit pad de vraag staan en test het met leesbare JSON. [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:524) · [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:130)

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: commit `4411846`, het slot van het verwerkingsverslag, code en tests; tests niet uitgevoerd.  
Open: het `plafond`-pad herstellen; niets gepusht.