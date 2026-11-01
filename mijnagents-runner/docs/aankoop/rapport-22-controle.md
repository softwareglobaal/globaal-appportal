**Niet klaar. Live: nee.**

1. Punt 1 van controle 21 is opgelost: de broncontrole geldt nu ook na een deadline. Punt 3 is alleen opgelost wanneer de code een uitzondering geeft. [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:518), [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:170)
2. Zonder token gaat geen vraag naar het model. Zonder merkteken kan dat **wel met een token**: `--proef-abonnement` doet bewust een korte modelvraag om het merkteken te maken. Een gewone prijsvraag vereist beide. [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:493), [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:552)
3. **Hoog:** als het modelonderzoek `stop="fout"` teruggeeft, krijgt de bordvraag een verslag zonder antwoord en wordt ze toch als opgepakt gemarkeerd. Laat die fout vóór `opgepakt` stoppen en test dit retourpad. [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:103), [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:174)

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: commit `d69d2fc`, onderkant van het verwerkingsverslag, code en tests; geen tests uitgevoerd.  
Open: foutretour moet de bordvraag laten staan; niets gepusht.