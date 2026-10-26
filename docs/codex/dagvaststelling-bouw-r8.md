**Niet klaar. Fase 1 mag niet live.** De herziening herstelt het oordeel over de ongemeten ochtendafspraak, maar de Zoomtelling kan te vroeg volledig heten en een werkelijk bezoek kan uit “Niet gepland” verdwijnen.

**Voor Mehdi**

Een Zoomoverzicht kan een exact aantal tonen terwijl later alsnog een gesprek van die dag opduikt. Ook kan een bezoek in de namiddag ontbreken doordat een afgeleid parkeerstuk het ten onrechte aan een ochtendafspraak koppelt.

**Voor Claude en Shaniel**

1. **K1, hoog, Zoom.** De herkomstredenering klopt deels: [dagregels](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:1419) schrijft alleen afgelopen dagen. Maar `ok` betekent dat een bron antwoord gaf, niet dat alle opnames al beschikbaar waren. [Fathomlezers](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:616) kunnen `ok` geven zonder opname; een later gevonden gesprek maakt de telling alsnog een ondergrens via [dag_inhoud](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:1279), waarna [dagregels](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:1437) herziening toestaat. Een geheugenproef gaf eerst **0, volledig, definitief, alle bronnen ok** en daarna **1, ondergrens, definitief**. Latere uitval alleen weerlegt een eerdere lezing niet, maar de code bewijst de veronderstelde volledigheid niet. Vereis bewijs dat de bronnen voor die dag zijn uitgewerkt; toon anders een ondergrens.

2. **K2, hoog, locatie.** [De Locatiewacht](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/locatie_wacht.py:240) koppelt een samengevoegd parkeerstuk nog aan een ochtendafspraak en verwijdert het daardoor uit [bezoeken zonder afspraak](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/locatie_wacht.py:297). De nieuwe meetpuntcontrole noemt die ochtend terecht onbekend, maar [lees_locatie](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:436) kan het gemeten namiddagbezoek niet terughalen. De geheugenproef bevestigde die combinatie. Bepaal bezoeken zonder afspraak pas na het nieuwe oordeel, op grond van meting en werkelijk tijdstip.

**Status:** G2 open via K2; G3 open via K1; J1 gesloten; J2 gesloten; F4 open via K2; F9 open via K1; D6 open via beide. Laag: geen nieuwe bevinding.

De nachtregel en werkwijze versie 3 staan in de repo. De [geïnstalleerde Mac-sync](/Users/mehdichegini/bin/data_uit_mehdi_sync.sh:26), die de [LaunchAgent](/Users/mehdichegini/Library/LaunchAgents/be.globaal.mijnagents.data-uit-mehdi.plist:9) gebruikt, mist nog de dagboekoverdracht.

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: diff, broncode en twee geheugenproeven.  
Open: K1 en K2 herstellen, daarna live installatie en teruglezing controleren.