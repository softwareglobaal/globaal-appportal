**Niet klaar. Fase 1 mag niet live.** G2 en G3 blijven open met hoge ernst. H1 is gesloten. Daardoor blijven F4 en D6 open via G2, en F9 via G3. Activeer de nachtregel en werkwijze versie 3 nog niet.

**Voor Mehdi:** Bij een afspraak in een ongemeten ochtend kan het overzicht nog zeggen dat de auto niet op de plek is gezien. Na een gedeeltelijke Zoomlezing kan een onvolledige dag opnieuw “volledig” heten. Er is wel vooruitgang tegenover ronde 5: H1 is hersteld, dus het aantal open hoge punten daalt van drie naar twee. De stopregel *zonder vooruitgang* geldt hier niet.

**Voor Claude en Shaniel**

1. **G2, hoog.** [locatie/app.py:983](/Users/mehdichegini/dev/_dagvaststeller/locatie/app.py:983) kan een afgeleid parkeerstuk vanaf middernacht samenvoegen met een later bezoek dat meetpunten heeft. [locatie_wacht.py:280](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/locatie_wacht.py:280) mist dan het ochtendgat. Herstel de dekking aan de hand van werkelijke meettijden en test juist dit samengevoegde geval.
2. **G3, hoog.** Een Zoomronde kan na gedeeltelijke bronuitval toch slagen, terwijl een oude dagregel “volledig” blijft staan ([zoom_wacht.py:1437](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:1437)). [dagbundelaar.py:560](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:560) wist dan de bewaarde onzekerheid. Wis die pas na aantoonbaar volledige herlezing van die dag en voeg een tegenproef toe.
3. **H1 gesloten.** [dagbundelaar.py:452](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:452) maskeert nu ook de antwoordadressen van privéwachten; de gerichte test dekt ontvangersnamen.

Geen nieuwe zelfstandige blokkade van hoge of middelhoge ernst, dus geen nieuw I-punt. **Laag:** enkele verwijzingen naar ontwerp v1.2 zijn blijven staan. De actieve [Mac-sync](/Users/mehdichegini/bin/data_uit_mehdi_sync.sh:1) is bovendien nog de oude kopie zonder dagboekoverdracht; de [LaunchAgent](/Users/mehdichegini/Library/LaunchAgents/be.globaal.mijnagents.data-uit-mehdi.plist:9) gebruikt die kopie. Bij latere livegang moet de nieuwe sync ook worden geïnstalleerd en teruggelezen.

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: diff, bronpaden en gerichte pure controles; tests met tijdelijke mappen niet uitgevoerd.  
Open: G2 en G3 herstellen, daarna fase 1 opnieuw controleren.