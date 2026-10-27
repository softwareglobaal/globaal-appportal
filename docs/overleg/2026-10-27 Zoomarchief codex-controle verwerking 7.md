**Voor Mehdi — niet klaar.** Drie volgordes van rondes geven nog een onterechte of gemiste verliesmelding. `SEIN_AAN = False` houdt het groene sein uit, maar herstelt die meldingen niet. Daarom raad ik live kopiëren met dit herstel nog niet aan.

1. A1 en A2 beginnen vier seconden na elkaar. A1 rondt onder zijn eigen id af; daarna verschijnt een vervanger voor A2. Die wordt toch aan de al opgeloste groep van A1 toegewezen, waarna A2 onterecht als verloren geldt.
2. A1 en A2 worden allebei als verloren gemeld. Komt A1 later onder zijn eigen id terug, dan verdwijnen **beide** meldingen, hoewel A2 nog weg is. Als één verloren plaatshouder terugkeert en opnieuw verdwijnt, blijft een tweede verlies eveneens ongemeld.
3. Verschijnt hetzelfde voorlopige id eerst zonder soort en later met soort, dan ontstaan twee groepen voor één bestand. Zelfs met een bewezen vervanger meldt één groep alsnog verlies.

**Voor Claude en Shaniel**

52. **Hoog — [zoom_archief.py:492](/Users/mehdichegini/dev/_zoom-archief-verwerking/mijnagents-runner/zoom_archief.py:492).** De toewijzing neemt ook groepen zonder open tekort mee. Sluit die uit en test de reeks met A1, A2 en een latere vervanger.
53. **Hoog — [zoom_archief.py:510](/Users/mehdichegini/dev/_zoom-archief-verwerking/mijnagents-runner/zoom_archief.py:510) en [regel 682](/Users/mehdichegini/dev/_zoom-archief-verwerking/mijnagents-runner/zoom_archief.py:682).** `verloren` wordt op aantal en volgorde bijgewerkt, niet op het teruggekeerde id. Herstel de registratie per id; test beide terugkeerreeksen.
54. **Hoog — [zoom_archief.py:446](/Users/mehdichegini/dev/_zoom-archief-verwerking/mijnagents-runner/zoom_archief.py:446) en [regel 467](/Users/mehdichegini/dev/_zoom-archief-verwerking/mijnagents-runner/zoom_archief.py:467).** Veranderlijke soortgegevens maken een tweede groep voor hetzelfde id. Houd dat id bij zijn bestaande groep en test een soortwijziging tijdens verwerking.

Gedaan: commit `019b1f2` alleen lezend gecontroleerd; niets gewijzigd.  
Nagekeken: de drie reeksen in geheugen bevestigd; de 86 bestaande tests niet herhaald.  
Open: herstel en regressietests vóór live kopiëren.

BESLISSING: niet klaar