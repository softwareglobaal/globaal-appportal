**Niet klaar.** De harde regel is: geen stuk van de ene firma noemt de andere of laat een verband vermoeden. Die scheiding is nog niet sluitend. Ook kunnen een onbewezen KBO-status en verkeerd gelezen offertebedragen bovenaan in een resultaat terechtkomen.

### Voor Claude en Shaniel

- **X1 hoog — [bouw/verslag.py:20](mijnagents-runner/bouw/verslag.py:20):** Een onvolledige HA-vraag krijgt letterlijk het voorbeeld `firma: HB`; [aannemerszoeker.py:99](mijnagents-runner/aannemerszoeker.py:99) zet dit zonder firmatoets klaar. Maak het voorbeeld firmaneutraal en toets ook foutverslagen.
- **X2 hoog — [bouw/scheiding.py:17](mijnagents-runner/bouw/scheiding.py:17):** De codes `HA` en `HB` ontbreken als kenmerken; `kruis()` op regel 61 controleert ook geen bandwoorden of persoonsnaam. Een kandidaat of bestandsnaam `HB` passeert. Breid de toets uit.
- **X3 middel — [bouw/scheiding.py:27](mijnagents-runner/bouw/scheiding.py:27):** Gewone tekst als “ventilatie groep D” en “onafhankelijke ophanging” wordt geweigerd. Begrens deze patronen; test beide formuleringen.
- **X4 hoog — [bouw/zoeken.py:56](mijnagents-runner/bouw/zoeken.py:56):** De volledige werkwijze, met beide firmanamen, gaat naar het externe model. Bouw de modelinstructie per gekozen firma op.
- **X5 hoog — [aannemerszoeker.py:101](mijnagents-runner/aannemerszoeker.py:101):** De privacytoets slaat `gemeente` over; een werfadres daarin gaat op regel 120 naar het model. Een losse bouwheernaam in `werk` wordt evenmin herkend. Valideer alle uitgaande velden.
- **X6 hoog — [bouw/zoeken.py:84](mijnagents-runner/bouw/zoeken.py:84):** “Niet actief” geeft `True`; een nagemaakte KBO-URL ook. Via regel 118 kan zelfs een website zonder gelezen tekst bovenaan staan. Controleer host, nummer, status en broninhoud exact.
- **X7 hoog — [regisseur.py:1318](mijnagents-runner/regisseur.py:1318):** De Regisseur heeft een vaste firma-identiteit, terwijl `klaargezet_lees()` op regel 575 verslagen van beide firma’s zonder firmaveld ophaalt. Maak vraag, lezing en antwoord firmagebonden.
- **X8 middel — [bouw/offertes.py:25](mijnagents-runner/bouw/offertes.py:25):** `1,234.56` wordt `4.56`; een latere regel “Subtotaal excl. btw” overschrijft het totaal (regel 83). Herstel bedragparse en totaalkeuze.
- **X9 middel — [bouw/offertes.py:251](mijnagents-runner/bouw/offertes.py:251):** Opties vallen buiten de som maar komen wel in de vergelijking per post; zonder totaal vervalt de somcontrole. Houd opties apart en eis een bevestigd totaal.
- **X10 middel — [bouw/offertes.py:126](mijnagents-runner/bouw/offertes.py:126):** `redigeer()` laat “Werf: Voorbeeldstraat 1” en een losse bouwheernaam staan. Houd `OFFERTE_NAAR_AI` uit tot dit met tests is afgedicht.
- **X11 middel — [offertevergelijker.py:161](mijnagents-runner/offertevergelijker.py:161):** Zestien downloads kunnen elk 120 seconden duren; de Regisseur wacht maximaal 600 seconden. Voeg een rondedeadline toe.
- **X12 middel — [bouw/eigen.py:31](mijnagents-runner/bouw/eigen.py:31):** Dropbox-resultaten stoppen na 100; `has_more` en `cursor` worden genegeerd. Daardoor kunnen mappen ontbreken. Implementeer vervolgpaginering.
- **X13 middel — [aannemerszoeker.py:120](mijnagents-runner/aannemerszoeker.py:120):** De gedeelde ronde leest lessen en collega’s voor N13/N14, maar geeft die kennis niet aan het zoekmodel. Voeg een per firma gefilterde versie toe.
- **X14 middel — [docs/bouw/uitrol.sh:14](mijnagents-runner/docs/bouw/uitrol.sh:14):** `git checkout --` kan parallel werk aan beide runners overschrijven. Controleer de werkboom vóór de uitrol en gebruik een geïsoleerde werkmap.
- **X15 middel — [tests/test_bouw.py:110](mijnagents-runner/tests/test_bouw.py:110):** Tests ontbreken voor de bovenstaande KBO-, privacy-, scheidings-, bedrag- en tijdsgrenzen. Voeg gerichte regressietoetsen toe.

Gedaan: alleen gelezen; niets gewijzigd.  
Nagekeken: 84 bestaande tests groen; modulo 97 en SQL-filtering kloppen. De Dropbox-JSON-vorm klopt volgens de [Dropbox-documentatie](https://dropbox.github.io/dropbox-sdk-js/global.html).  
Open: herstel en tests; N4/N11 en de eerste live ronde zijn in deze leescontrole niet verifieerbaar.