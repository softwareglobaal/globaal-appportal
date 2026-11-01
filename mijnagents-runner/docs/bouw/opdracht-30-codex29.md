# Controle 30: de vier punten van controle 29

Lees docs/bouw/rapport-29-herstel-proefbank.md en `git diff HEAD~1 -- mijnagents-runner` op tak bouw-proefbank. Wijzig
niets. Noem nooit de namen van de twee firma's samen.

Hersteld, elk met een test (395 goed):
- 5: een kale regel na een totaal telt alleen als ze niets anders draagt dan een bedrag en euro, incl, btw, totaal
  (`alleen_bedrag`); "Optie 1.210,00 EUR" en "Transport incl. BTW 50,00 EUR" tellen niet.
- 6: alleen gekende afkortingen beletten een zinseinde, geen woorden van een of twee letters meer.
- 8: twee verschillende submappen zijn nooit versies van elkaar; alleen de lotmap zelf en een submap kunnen een kopie delen.
- Afscherming: ook `urlopen(url, data)` met een gewone URL naar het bord is een POST en wordt geweigerd.

Klopt dit, en breekt het iets wat in controle 29 correct was? Kort, Nederlands, `bestand:regel`. Eindig met precies een
regel: AKKOORD of NIET AKKOORD.
