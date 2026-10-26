**Niet klaar. Fase 1 mag nog niet live:** de nachtcron en werkwijze kunnen nog niet op het bord worden geactiveerd. Dit oordeel geldt voor commit `bdf66ca`; de latere commit `c1196f5` veranderde de beoordeelde logica niet. Alle regelnummers hieronder horen bij `bdf66ca`.

**Status van ronde 2:** D1 gesloten (ochtendgrendel); D2 gesloten (kanaalstand uit hartslag); D5 open (privacy); D6 open (bewijs en locatie); D7 open (opnames); D8 open (verzonden mail); D9 open (versies); D10 gesloten voor het venster van veertien dagen. E1 open (Plaud); E2 gesloten (archiefagenda’s worden gelezen); E3 open (persoonskoppeling); E4 gesloten (leesfouten van inkomende mappen worden gemeld); E5 gesloten (volledige herberekening); E6 open (teruglezen).

**Voor Mehdi:** Het overzicht kan privénamen tonen, afspraken ten onrechte bevestigen en een eerdere versie verliezen. De nieuwe nachtregel botst ook met het bestaande beheer van de gesprekkenplanning.

**Voor Claude en Shaniel:**

1. **F1, hoog.** Een ongelezen privéagenda verschijnt met persoonsnaam (`dagbundelaar.py:299`; `koppelingen/dagvaststelling.py:297`). Het als privécommunicatie ingestelde postvak MCH toont ontvangers (`dagbundelaar.py:372`; `dagvaststelling.py:347`; `mailwachten.json:114`). Maskeer beide.
2. **F2, hoog.** Twijfelgevallen en overige verblijven schrijven een ongeschoonde plek of adres naar bord en Dropbox (`dagbundelaar.py:325`; `dagvaststelling.py:313`; `locatie_wacht.py:205`). Maskeer plekken die geen bevestigd werkproject zijn.
3. **F3, hoog.** Eén gedeelde voornaam of een plaatswoord kan een afspraak bevestigen (`dagvaststelling.py:129,169`). De runner vult `_personen` niet (`dagbundelaar.py:290`). Een synthetische tegenproef met twee verschillende personen gaf vals “bevestigd”. Koppel alleen aantoonbaar dezelfde persoon.
4. **F4, hoog.** Locatie vergelijkt alleen gewone agenda’s (`locatie_wacht.py:220`), terwijl de vaststelling archiefagenda’s leest en annuleringen uitsluit (`dagbundelaar.py:297,305`). Aanwijzingen kunnen ontbreken en bezoeken verdwijnen. Gebruik dezelfde gefilterde afsprakenlijst en controleer de locatiedekking.
5. **F5, hoog.** Bij onbekende Zoomstand verschijnt toch “0 chat” (`dagvaststelling.py:319-322`). Een actuele WhatsApp-hartslag bewijst bij latere aansluiting geen dekking voor alle veertien dagen (`dagbundelaar.py:441-443`). Toon onbekend per dag.
6. **F6, middel.** Zoom met een overlappende Plaud-opname wordt één gesprek, maar verliest de aanduiding “met opname” (`dagvaststelling.py:155-157,214-217`). De test verwacht die foutieve telling (`test_dagvaststelling.py:126`). Behoud het opnamebewijs.
7. **F7, middel.** Verzonden mail wordt bij 2.000 koppen zonder waarschuwing afgekapt; postvakken uit `antwoord_vanuit` ontbreken (`dagbundelaar.py:368-371,407`; `postvak.py:458-479`). Markeer het plafond en lees alle geconfigureerde afzenders.
8. **F8, hoog.** Na een bordfout kan bestand v2 naast staat v1 blijven staan; een latere revisie overschrijft dan archief v1. De terugleescontrole negeert bovendien het versieblok (`dagbundelaar.py:474-506`; `dagvaststelling.py:355-362`). Herstel de versie uit het bestand, bewaar archieven en vergelijk de volledige bordtekst.
9. **F9, hoog.** Het bestaande cronbeheer weigert de losse nachtregel (`planning/dagvaststelling.cron:9`; `planning/gesprekken_cron_zetten.py:152-165`). Een bezet slot en een mislukte Zoomronde worden niet afzonderlijk gemeld. Integreer de regel in het beheer en test beide foutpaden.
10. **F10, middel.** De Mac-sync kan “klaar” melden na mislukte rsync of ontvangstoverdracht (`planning/mac/data_uit_mehdi_sync.sh:7,30-45`). Laat de taak bij zo’n fout falen.

Gedaan: alleen gelezen; niets gewijzigd.  
Nagekeken: de pure dagvaststellingstest slaagt. Synthetische proeven bevestigen F3, F6 en F9; de tests missen onder meer privacy bij leesfout, herstel na bordfout en croninstallatie.  
Open: eerst privacy, bronkoppeling, dekking, versieherstel en cronbeheer corrigeren; daarna gerichte integratietests en een gecontroleerde liveproef.