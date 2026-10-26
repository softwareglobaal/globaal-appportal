**Niet klaar. Fase 1 mag niet live.** G2 en G3 blijven open. Daardoor blijven F4 open via G2, F9 via G3 en D6 via beide. Het negatieve locatiegeval uit ronde 6 is hersteld, maar het aantal open hoge punten is niet gedaald. De stopregel vraagt nu eerst een ontwerpronde over [G2 en G3 in v1.6](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:247).

**Voor Mehdi:** Een afspraak in een ongemeten ochtend kan nog de aanwijzing “auto ter plaatse” krijgen. Na een gedeeltelijke Zoomlezing kan een eerder volledig overzicht nog steeds volledig heten.

**Voor Claude en Shaniel**

1. **J1, hoog, G2/F4/D6.** [locatie/app.py:983](/Users/mehdichegini/dev/_dagvaststeller/locatie/app.py:983) kan een parkeerstuk vanaf middernacht met een later gemeten bezoek samenvoegen. [dagbundelaar.py:399](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:399) controleert meettijden alleen bij `niet_gezien`. Een proef zonder ochtendmeting gaf voor een ochtendafspraak nog `doorgegaan`. Toets ook “auto ter plaatse” aan echte meetpunten en test dit geval.
2. **G3, hoog, F9/D6.** Bij gedeeltelijke bronuitval kan [zoom_wacht.py:1437](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:1437) een opgepakte volledige dagregel laten staan. De ronde kan slagen; [dagbundelaar.py:575](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:575) registreert dan geen onzekerheid. Een proef gaf nul nieuwe dagregels en toch stand `volledig`. Bewaar de leesdekking van de actuele Zoomronde afzonderlijk.
3. **J2, middel.** [dagbundelaar.py:578](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:578) heft onzekerheid alleen op als de inhoudshash verandert. Een volledige herlezing met dezelfde inhoud blijft dus onbeperkt “ondergrens”. De [test](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/tests/test_dagbundelaar_vaststelling.py:395) verandert de inhoud kunstmatig. Gebruik een aantoonbare leesronde als herstelbewijs.

**Laag:** verwijzingen naar oudere ontwerpversies staan nog in de documentatie.

De nachtregel en werkwijze versie 3 staan in de repo. De [actieve Mac-sync](/Users/mehdichegini/bin/data_uit_mehdi_sync.sh:26) mist nog de dagboekoverdracht; de [LaunchAgent](/Users/mehdichegini/Library/LaunchAgents/be.globaal.mijnagents.data-uit-mehdi.plist:9) gebruikt die oude kopie. Live installatie en teruglezing zijn hiermee niet aangetoond.

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: diff, bronpaden en twee proeven zonder schrijven.  
Open: ontwerp G2/G3 herzien, herstellen en opnieuw controleren.