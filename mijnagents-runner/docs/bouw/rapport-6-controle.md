Niet klaar. H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; geen stuk van de ene noemt de andere of laat een band vermoeden. Controle 5 is niet volledig opgelost.

### Voor Claude en Shaniel

X1 hoog, `bouw/vraag.py:107`: `gemeente: 3000 Jan Peeters` geeft geen privacyfout en gaat naar het model. Mehdi houdt dit alleen tegen door zelf vooraf de naam te verwijderen.

X2 hoog, `bouw/zoeken.py:198`: iedere gelezen pagina met 100 tekens geldt als firmapagina. Een nieuwsartikel zonder kandidaatnaam of activiteit leverde met geldige KBO en zetel toch `goed` op. Mehdi moet elke link openen om de verkeerde keuze te zien.

X3 hoog, `regisseur.py:1281`: het automatische dossier laadt zonder firmasleutel het laatste Bouw-verslag. Bij een vraag voor de andere firma kan het model daardoor het verkeerde verslag gebruiken; een antwoord zonder herkenbare firmanaam passeert de eindgrendel. Mehdi voorkomt dit alleen door het keyed bordverslag rechtstreeks te lezen.

X4 hoog, `bouw/offertes.py:30`: de herkenning begrijpt geen context of ontkenning. “Medecontractant is niet van toepassing” werd `btw verlegd` en maakte 12.100 inclusief ook 12.100 exclusief. “Offerte vervangt eerdere raming” werd als raming uitgesloten. Mehdi moet de originele PDF en rangschikking controleren.

X5 middel, `bouw/scheiding.py:18`: schrijfwijzen als `H.B. BV`, `H A Architects`, `5 Gerzenstraat` en `Gerzenstr. 5` passeren. Daardoor kan de andere firma nog als kandidaat, inschrijver of bestandsnaam verschijnen. Mehdi ziet dit op het bord of vóór hij een mail kopieert.

X6 laag, `bouw/offertes.py:179`: `redigeer()` laat in “Jan Peeters, Voorbeeldlaan 7” de naam staan. `OFFERTE_NAAR_AI=False` blokkeert dit nu; Mehdi’s blijvende weigering voorkomt verzending.

X7 laag, `bouw/scheiding.py:39`: gewone teksten met “eigen aannemer”, “vaste aannemer” of “partner van de fabrikant” worden geblokkeerd. Mehdi kan alleen herformuleren.

X8 laag, `tests/test_bouw.py:439`: tests ontbreken voor X1 tot X7; de X5-test controleert alleen het eindantwoord, niet het vooraf geladen dossier.

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: volledige diff; 177 Bouw-tests groen; Dropbox-vorm klopt met het officiële [API-schema](https://dropbox.github.io/dropbox-sdk-js/global.html).  
Open: herstel X1 tot X8; N1 tot N14 zijn pas na de eerste live rondes bewijsbaar.