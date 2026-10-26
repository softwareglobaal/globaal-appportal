**Niet klaar. Fase 1 mag niet live.** Een afspraak kan nog “auto niet gezien” krijgen terwijl de tracker op dat uur niets mat. Na herhaalde mislukte Zoomnachten kan een onvolledige dag weer “volledig” heten. Ook kunnen namen van mailontvangers via antwoordadressen van een privéwacht op het bord en in Dropbox belanden. Activeer daarom de nachtregel, werkwijze versie 3 en de Mac-sync nog niet.

**Voor Claude en Shaniel**

G1 **gesloten**, G2 **open**, G3 **open**, G4 **gesloten**, G5 **gesloten**, G6 **gesloten**, G7 **gesloten**. Van de oudere punten blijven **F4, F9 en D6 open**. **F3, F5, F7, F8, F10, D8, D9 en E3 zijn gesloten**.

1. **G2, hoog.** Bij een vorige parkeerstand en een eerste, verre meting pas om 17:00 maakt [locatie/app.py:969](/Users/mehdichegini/dev/_dagvaststeller/locatie/app.py:969) geen gat voor de ochtend. Omdat er wel één geldige meting is, kan [dagbundelaar.py:386](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:386) een afspraak om 10:00 als “niet gezien” laten staan. Maak ontbrekende meetdekking aan het dagbegin expliciet onbekend en test dit geval.
2. **G3, hoog.** [dagbundelaar.py:523](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:523) verlaagt de Zoomstand na een mislukte nacht alleen voor *gisteren*. Mislukt Zoom twee nachten na elkaar, dan kan de eerste dag bij de tweede herberekening weer de bewaarde stand “volledig” krijgen. Bewaar de onzekerheid per dag tot Zoom die dag aantoonbaar opnieuw las; test twee opeenvolgende mislukkingen.
3. **H1, hoog, nieuw.** De privéwacht heeft vier antwoordadressen in [mailwachten.json:114](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/werkwijze/mailwachten.json:114). [dagbundelaar.py:446](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:446) maskeert alleen zijn postvakken, terwijl [dagvaststelling.py:392](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/koppelingen/dagvaststelling.py:392) ontvangers van de antwoordadressen toont. Een synthetische proef bevestigt het lekpad. Neem die adressen op in het privémasker en voeg een tegenproef toe.

**Laag:** G7 is hersteld; enkele kopteksten verwijzen nog naar ontwerp v1.2.

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: de pure test en gerichte G2-, G4- en F9-tests slagen; de tegenproeven bevestigen G2 en H1. Tests met tijdelijke mappen konden in deze leessandbox niet draaien.  
Open: G2, G3 en H1. Het aantal blokkades daalde tegenover ronde 4 van zes naar drie.