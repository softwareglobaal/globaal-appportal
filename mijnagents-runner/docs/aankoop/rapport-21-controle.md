**Niet klaar.** De gevraagde garantie voor livegang klopt nog niet.

1. **Punt 1, deels opgelost:** de proef zonder `init` schrijft geen merkteken. Tegenproef: bij een tijdslimiet vóór `init` slaat de prijsvraag de broncontrole over. [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:518) Controleer de bron bij elk einde.
2. **Punt 2, opgelost:** `klaar` vereist nu een abonnementsvenster én een melding over extra verbruik. Zonder die melding volgt `GeenAbonnement`. [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:533)
3. **Punt 3, opgelost voor `GeenAbonnement`:** de lus stopt vóór `opgepakt`. Nieuwe bevinding, **hoog**: bij een andere fout markeert de runner de vraag nog steeds als opgepakt, mogelijk zonder verslag. [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:170) Stop ook dan vóór `opgepakt`.

**Live: nee onder de gestelde voorwaarde.** Zelfs zonder token of merkteken kan een vraag met persoonsgegevens een verslag krijgen en als opgepakt worden gemarkeerd. [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:86)

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: laatste inhoudelijke commit, verwerkingsverslag en code; geen tests uitgevoerd.  
Open: broncontrole bij elk einde en bordvragen bij fouten laten staan.