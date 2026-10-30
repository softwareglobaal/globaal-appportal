Niet klaar. H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; geen stuk van de ene noemt de andere of laat een band vermoeden.

X1 hoog, `bouw/zoeken.py:154`: een projectadres op een gelezen site geldt nog als vestigingsadres. Tegenproef: een firma met zetel in Brugge maar een project in Leuven kwam in `goed` op 0 km. Mehdi voorkomt een verkeerde keuze alleen door zelf het vestigingsadres te controleren.

X2 hoog, `bouw/offertes.py:99`: bij exclusief, btw en inclusief op één regel neemt `_laatste_bedrag` 12.100 als exclusief in plaats van 10.000. Dit kan de rangschikking verkeerd maken. Mehdi moet de originele PDF-totalen nakijken.

X3 hoog, `bouw/vraag.py:88`: `dakwerken voor jan peeters` levert geen privacyfout op en gaat naar het model. Alleen de naam vooraf uit de vraag laten houdt dit tegen.

X4 middel, `bouw/scheiding.py:63`: `laad_kern()` accepteert twee firmarijen ook als ondernemingsnummer en adres leeg zijn. De runner werkt dan zonder die kenmerken te kunnen blokkeren. Mehdi kan verzending nog stoppen door elk concept te lezen.

X5 hoog, `regisseur.py:132`: de firmagrendel registreert alleen `agent_ronde` en `klaargezet`. `agent_verslag` en het automatisch geladen agentdossier kunnen rondes van verschillende firma’s aan het model geven; regel 1415 grendelt dan niets. Mehdi voorkomt dit alleen door het bordverslag rechtstreeks te lezen.

X6 laag, `bouw/offertes.py:156`: `redigeer()` laat `JAN PEETERS` inline staan. `OFFERTE_NAAR_AI=False` voorkomt dit nu; Mehdi moet toestemming blijven weigeren tot de redactie sluitend is.

X7 laag, `bouw/scheiding.py:37`: gewone bouwtaal “aanverwante werken” wordt door `verwant` geblokkeerd. Mehdi kan alleen herformuleren en opnieuw starten.

X8 middel, `bouw/offertes.py:66`: de eerste datum in het document wordt als offertedatum gebruikt. Een oude projectdatum vóór de offertedatum maakt de geldigheid fout. Mehdi moet datum en vervaldag in de PDF nakijken.

X9 laag, `tests/test_bouw.py:380`: regressietests ontbreken voor X1 tot X8; daarom blijven alle 159 tests groen. Alleen handmatig testen vangt dit nu.

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: volledige diff, controle 4 en 159 Bouw-tests groen.  
Open: herstel; N1 tot N14 zijn pas na de live eerste rondes bewijsbaar.