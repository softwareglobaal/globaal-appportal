**Niet klaar.** Deze versie mag niet live: ook zonder token kan de agent open bordvragen als opgepakt markeren, zonder verslag. [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:163)

Voor Claude en Shaniel:

1. **Hoog:** zonder passend merkteken start geen prijsvraag, maar een proef zonder `init` kan toch een merkteken voor dit token schrijven. De abonnementsbron is dan niet bewezen. [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:570)
2. **Hoog:** een latere prijsvraag zonder abonnementsvensters kan als `klaar` eindigen. Dat schendt overleg 19, punt K2. [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:518)
3. **Hoog:** bij een geblokkeerde bordvraag loopt de runner door naar `opgepakt`. Laat die vraag in de wachtrij staan. [prijsonderzoeker.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:171)

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: diff, tests en merge `595fd50`; geen tests uitgevoerd.  
Open: deze drie fouten herstellen vóór livegang.