Niet klaar: 16 aangenomen (X1: Kies De Aannemerszoeker ; X2: Verplicht: firma, vak/we; X3: Maak één afzonderlijke m; X4: Accepteer firma plus pro; X6: Tests moeten kruisvermel; X7: Vandaag: beide runners, ; G2: De Aannemerszoeker funct; G3: Strikte mailscheiding en; G4: De Offertevergelijker fu; G5: Privacy en gegevensbesch; G6: Testbatterij (wat Mehdi ; G7: Volgorde van oplevering ; K2: De Aannemerszoeker; K3: De mail; K5: Grenzen en gegevens; K6: Tests); 3 wacht op jouw ja/nee (X5, K1, K7); 0 open; 2 afgewezen.
## Voor Mehdi
- Vraag (ja/nee): Mag punt X5 doorgaan? Advies: ja (3-0).
- Nog 3 vragen staan onder Vragen aan Mehdi.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | aangenomen |
| X5 | eens | eens | eens | 3-0 | naar Mehdi (grens) |
| X6 | eens | eens | eens | 3-0 | aangenomen |
| X7 | eens | eens | eens | 3-0 | aangenomen |
| G1 | oneens | eens | oneens | 1-2 | afgewezen |
| G2 | eens | eens | eens | 3-0 | aangenomen |
| G3 | eens | eens | oneens | 2-1 | aangenomen |
| G4 | eens | eens | oneens | 2-1 | aangenomen |
| G5 | eens | eens | eens | 3-0 | aangenomen |
| G6 | eens | eens | eens | 3-0 | aangenomen |
| G7 | oneens | eens | eens | 2-1 | aangenomen |
| K1 | oneens | eens | oneens | 1-2 | naar Mehdi (grens) |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | eens | eens | oneens | 2-1 | aangenomen |
| K4 | oneens | eens | oneens | 1-2 | afgewezen |
| K5 | oneens | eens | eens | 2-1 | aangenomen |
| K6 | eens | eens | eens | 3-0 | aangenomen |
| K7 | oneens | eens | eens | 2-1 | naar Mehdi (grens) |

## Vragen aan Mehdi
1. Vraag (ja/nee) X5: Mag De Offertevergelijker lokaal uitgelezen offerte-inhoud, nadat bouwheernaam, adres en contactgegevens zijn verwijderd, naar het reeds ingestelde AI-model sturen? Advies: ja (3-0).
   Grens volgens Codex: extern versturen van geredigeerde offerte-inhoud naar het AI-model
2. Vraag (ja/nee) K1: Mag de lege afdeling `harmoniebouw` van het bord worden verwijderd, in plaats van alleen hernoemd naar `bouw`? Advies: nee (1-2).
   Grens volgens Claude: verwijderen van de afdeling `harmoniebouw` op het bord
3. Vraag (ja/nee) K7: Mag er een betaalde bedrijvengids-API voor aannemers worden afgesloten? Advies: ja (2-1).
   Grens volgens Claude: een betaalde bedrijvengids-API zou geld kosten. Mijn advies is niet doen; het web en de KBO volstaan voor de eerste versie
4. Vraag (ja/nee): Mag het voorstel van Claude doorgaan, ook al raakt het geld en verwijderen? Advies: nee tot de keuze vastligt.
   Grens volgens Claude: verwijderen (afdeling `harmoniebouw`) en geld (bedrijvengids-API)
Ook genoemd (hoort bij een vraag of grenspunt hierboven, geen aparte vraag):
- Codex: extern versturen

## Besluitenlijst vóór stemming
- X1: Kies De Aannemerszoeker en De Offertevergelijker, niet vier firma-agents. Hun mandaten verschillen; de firma is per ronde verplicht en bepaalt alle bronnen, sjablonen en uitvoer. Gebruik `harmoniebouw` niet voor gedeeld werk en laat die lege afdeling voorlopig ongemoeid. Een wc-pomp hoort bij Bouw zodra projectoffertes worden vergeleken, maar bij De Prijsonderzoeker voor een losse marktaankoop.
  Techniek voor Claude: `AGENTNORM.md:312-316`, `docs/bouw/opdracht-1-ontwerp.md:19-24,43` - zonder geldige HARC/HARM direct stoppen.
- X2: Verplicht: firma, vak/werk, omvang, gemeente of postcode, gebied, timing en optioneel project. Zoek eerst uitsluitend in bronnen van die firma, daarna op het web. Lever per kandidaat bewijs, contact van de gelezen site, KBO-status, gebied en eerdere samenwerking; onbewezen of buiten gebied apart. Bewaar later alleen firmacode, `partij_id`, vak, regio, bewijs en controledatum, nooit gekopieerde bedrijfsgegevens.
  Techniek voor Claude: `aankoop/onderzoek.py:82-112`, `organisatie.py:55-61`, `pipedrive.py:21-27` - Harmonie Bouw ontbreekt in Pipedrive en kern levert nu onvoldoende afzendergegevens. Gebruik officiële [KBO Public Search](https://economie.fgov.be/nl/themas/ondernemingen/kruispuntbank-van/diensten-voor-iedereen/raadpleging-en-opzoeking-van/kruispuntbank-van) en [checkinhoudingsplicht](https://www.socialsecurity.be/site_nl/employer/applics/30bis/index.htm); bij onbereikbaarheid “niet gecontroleerd”, nooit groen.
- X3: Maak één afzonderlijke mail per kandidaat. H-Architects vermeldt project/lot, werkomschrijving, plannen of meetstaat, plaatsbezoek, prijsbasis, geldigheid en termijn. Harmonie Bouw vraagt prijs exclusief btw per post, beschikbaarheid, uitvoeringstermijn, verzekering en uitsluitingen. Alleen tekst op het bord, geen postvakconcept.
  Techniek voor Claude: `bouw/scheiding.py:50-71` - vaste firmagegevens uit kern, model schrijft alleen de werkomschrijving, daarna volledige uitvoer blokkeren bij elk vreemd kenmerk.
- X4: Accepteer firma plus project/lot/map of expliciete PDF’s. Lees lokaal met pypdf; een lege pagina stopt als “OCR nodig”. Code controleert totalen en btw, vergelijkt hoeveelheden, eenheden, inclusies, uitsluitingen, voorwaarden, termijn en documentbasis; ontbrekend is nooit nul. V1 levert een bordverslag met verschillen en risico’s, geen gunning.
  Techniek voor Claude: `bronnen.py:198-207`, `docs/bouw/opdracht-1-ontwerp.md:56-59` - `scheiding.py:5-10` botst met Mehdi’s letterlijke regel: Harmonie Bouw mag ook als inschrijver niet genoemd worden in H-Architects-uitvoer; gebruik “Inschrijver B”.
- X5: Nooit contacteren, versturen, aanvaarden, tekenen, overschrijven of verplaatsen. Mehdi kiest leverancier en offerte. Zoekvragen bevatten geen bouwheer; offerte-inhoud wordt lokaal geredigeerd en scans blijven in V1 geblokkeerd.
  Grens, Mehdi beslist (jullie stem is het advies): extern versturen van geredigeerde offerte-inhoud naar het AI-model
- X6: Tests moeten kruisvermelding, ongelezen websites, onbewezen gebied, ontbrekende posten, btw-normalisatie, rekenfouten, ramingen en scans blokkeren. Project 2145 ventilatie is het gouden resultaat; 2405 bewaakt offertebasis en kortingen.
  Techniek voor Claude: `docs/bouw/opdracht-1-ontwerp.md:47-59,104-109` - voeg ook een vergelijking met de andere firma als geanonimiseerde inschrijver toe.
- X7: Vandaag: beide runners, werkwijzen, firmagrendel, webbewijs, lokale PDF-extractie, bordverslagen, Regisseur-koppeling en tests. Later: kernrelatie-register, automatische inhoudingsplicht, OCR, postvakconcepten en opvolging. Bewijs met dezelfde zoekvraag eenmaal per firma zonder contact, plus 2145 als vergelijking.
  Techniek voor Claude: `regisseur.py:79-96,120-122`, `AGENTNORM.md:352-383` - pas actief na gecontroleerde eerste ronde.
- G1: Indeling afdeling Bouw (wat Mehdi merkt):** Mehdi ziet op het bord één overzichtelijke afdeling `bouw` met twee agents. Per vraag kiest hij verplicht de firma (H-Architects of Harmonie Bouw). De lege afdeling `harmoniebouw` wordt gedeactiveerd om verwarring te voorkomen. Productvergelijkingen (zoals een losse wc-pomp) horen bij De Prijsonderzoeker; aannemersoffertes met plaatsing bij De Offertevergelijker.
- G2: De Aannemerszoeker functies (wat Mehdi merkt):** De agent zoekt eerst in eigen historiek (eerdere projecten en relaties) en vult pas daarna aan via webonderzoek in de gevraagde regio. Geen verouderde of spookbedrijven: alleen firma's met actieve KBO en geverifieerde website worden getoond.
- G3: Strikte mailscheiding en concepten (wat Mehdi merkt):** Mails worden nooit automatisch verzonden en blijven concepten in het verslag op het bord. Een harde codefilter blokkeert elke tekst waarin namen, contactgegevens of banden tussen H-Architects en Harmonie Bouw voorkomen.
- G4: De Offertevergelijker functies (wat Mehdi merkt):** Offertes worden objectief naast elkaar gezet met herberekening van btw en stelposten. Ontbrekende posten worden expliciet gemarkeerd als ontbrekend (nooit als 0 euro). Het verslag adviseert feitelijk zonder voorkeur voor Harmonie Bouw.
- G5: Privacy en gegevensbescherming (wat Mehdi merkt):** Namen en privégegevens van particuliere bouwheren gaan nooit naar externe zoekmachines of AI-prompts; alleen het vakgebied en de werklocatie (gemeente).
- G6: Testbatterij (wat Mehdi merkt):** Fouten worden opgevangen vóór ingebruikname via geautomatiseerde tests (verboden kruisverwijzingen, ontbrekende posten, ongeldige btw).
- G7: Volgorde van oplevering (wat Mehdi merkt):** Vandaag leveren we de twee werkende agents met verslaglegging op het bord en Dropbox-opslag; geavanceerde KBO-checks en automatische postvakkoppelingen volgen later.
- K1: Indeling
  Grens, Mehdi beslist (jullie stem is het advies): verwijderen van de afdeling `harmoniebouw` op het bord
- K2: De Aannemerszoeker
  Techniek voor Claude: `aankoop/onderzoek.py` hergebruiken (grendel "alleen gelezen pagina's"); `koppelingen/organisatie.py` voor kern.firma.
- K3: De mail
  Techniek voor Claude: `bouw/scheiding.py` als grendel, aanroepen vlak voor het wegschrijven en in elke test.
- K4: De Offertevergelijker
  Techniek voor Claude: `koppelingen/bronnen.py` (`lijst`, `download`, `pdf_tekst`); schrijven via een aparte, beperkte uploadfunctie die weigert te overschrijven.
- K5: Grenzen en gegevens
- K6: Tests
- K7: Volgorde
  Grens, Mehdi beslist (jullie stem is het advies): een betaalde bedrijvengids-API zou geld kosten. Mijn advies is niet doen; het web en de KBO volstaan voor de eerste versie

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: Klaar met kanttekeningen: bouw twee functie-agents in `bouw`, met verplichte firma en harde scheiding; offerte-inhoud naar een extern AI-model vereist Mehdi’s ja.<br><br>X1. Kies De Aannemerszoeker en De Offertevergelijker, niet vier firma-agents. Hun mandaten verschillen; de firma is per ronde verplicht en bepaalt alle bronnen, sjablonen en uitvoer. Gebruik `harmoniebouw` niet voor gedeeld werk en laat die lege afdeling voorlopig ongemoeid. Een wc-pomp hoort bij Bouw zodra projectoffertes worden vergeleken, maar bij De Prijsonderzoeker voor een losse marktaankoop.  <br>Techniek voor Claude: `AGENTNORM.md:312-316`, `docs/bouw/opdracht-1-ontwerp.md:19-24,43` - zonder geldige HARC/HARM direct stoppen.<br><br>X2. Verplicht: firma, vak/werk, omvang, gemeente of postcode, gebied, timing en optioneel project. Zoek eerst uitsluitend in bronnen van die firma, daarna op het web. Lever per kandidaat bewijs, contact van de gelezen site, KBO-status, gebied en eerdere samenwerking; onbewezen of buiten gebied apart. Bewaar later alleen firmacode, `partij_id`, vak, regio, bewijs en controledatum, nooit gekopieerde bedrijfsgegevens.  <br>Techniek voor Claude: `aankoop/onderzoek.py:82-112`, `organisatie.py:55-61`, `pipedrive.py:21-27` - Harmonie Bouw ontbreekt in Pipedrive en kern levert nu onvoldoende afzendergegevens. Gebruik officiële [KBO Public Search](https://economie.fgov.be/nl/themas/ondernemingen/kruispuntbank-van/diensten-voor-iedereen/raadpleging-en-opzoeking-van/kruispuntbank-van) en [checkinhoudingsplicht](https://www.socialsecurity.be/site_nl/employer/applics/30bis/index.htm); bij onbereikbaarheid “niet gecontroleerd”, nooit groen.<br><br>X3. Maak één afzonderlijke mail per kandidaat. H-Architects vermeldt project/lot, werkomschrijving, plannen of meetstaat, plaatsbezoek, prijsbasis, geldigheid en termijn. Harmonie Bouw vraagt prijs exclusief btw per post, beschikbaarheid, uitvoeringstermijn, verzekering en uitsluitingen. Alleen tekst op het bord, geen postvakconcept.  <br>Techniek voor Claude: `bouw/scheiding.py:50-71` - vaste firmagegevens uit kern, model schrijft alleen de werkomschrijving, daarna volledige uitvoer blokkeren bij elk vreemd kenmerk.<br><br>X4. Accepteer firma plus project/lot/map of expliciete PDF’s. Lees lokaal met pypdf; een lege pagina stopt als “OCR nodig”. Code controleert totalen en btw, vergelijkt hoeveelheden, eenheden, inclusies, uitsluitingen, voorwaarden, termijn en documentbasis; ontbrekend is nooit nul. V1 levert een bordverslag met verschillen en risico’s, geen gunning.  <br>Techniek voor Claude: `bronnen.py:198-207`, `docs/bouw/opdracht-1-ontwerp.md:56-59` - `scheiding.py:5-10` botst met Mehdi’s letterlijke regel: Harmonie Bouw mag ook als inschrijver niet genoemd worden in H-Architects-uitvoer; gebruik “Inschrijver B”.<br><br>X5. Nooit contacteren, versturen, aanvaarden, tekenen, overschrijven of verplaatsen. Mehdi kiest leverancier en offerte. Zoekvragen bevatten geen bouwheer; offerte-inhoud wordt lokaal geredigeerd en scans blijven in V1 geblokkeerd.  <br>GRENS: extern versturen van geredigeerde offerte-inhoud naar het AI-model.  <br>VRAAG: Mag De Offertevergelijker lokaal uitgelezen offerte-inhoud, nadat bouwheernaam, adres en contactgegevens zijn verwijderd, naar het reeds ingestelde AI-model sturen?<br><br>X6. Tests moeten kruisvermelding, ongelezen websites, onbewezen gebied, ontbrekende posten, btw-normalisatie, rekenfouten, ramingen en scans blokkeren. Project 2145 ventilatie is het gouden resultaat; 2405 bewaakt offertebasis en kortingen.  <br>Techniek voor Claude: `docs/bouw/opdracht-1-ontwerp.md:47-59,104-109` - voeg ook een vergelijking met de andere firma als geanonimiseerde inschrijver toe.<br><br>X7. Vandaag: beide runners, werkwijzen, firmagrendel, webbewijs, lokale PDF-extractie, bordverslagen, Regisseur-koppeling en tests. Later: kernrelatie-register, automatische inhoudingsplicht, OCR, postvakconcepten en opvolging. Bewijs met dezelfde zoekvraag eenmaal per firma zonder contact, plus 2145 als vergelijking.  <br>Techniek voor Claude: `regisseur.py:79-96,120-122`, `AGENTNORM.md:352-383` - pas actief na gecontroleerde eerste ronde.<br><br>GRENS: extern versturen. | BESLISSING: KLAAR MET KANTTEKENINGEN (2-op-3 akkoord vereist). We richten afdeling `bouw` in met twee strikt gescheiden agents conform `AGENTNORM.md`: De Aannemerszoeker en De Offertevergelijker.<br><br>* **G1. Indeling afdeling Bouw (wat Mehdi merkt):** Mehdi ziet op het bord één overzichtelijke afdeling `bouw` met twee agents. Per vraag kiest hij verplicht de firma (H-Architects of Harmonie Bouw). De lege afdeling `harmoniebouw` wordt gedeactiveerd om verwarring te voorkomen. Productvergelijkingen (zoals een losse wc-pomp) horen bij De Prijsonderzoeker; aannemersoffertes met plaatsing bij De Offertevergelijker.<br>  `Techniek voor Claude: AGENTNORM.md:H8 - Voeg bouw toe aan regisseur.py en deactiveer afdeling harmoniebouw op het bord.`<br><br>* **G2. De Aannemerszoeker functies (wat Mehdi merkt):** De agent zoekt eerst in eigen historiek (eerdere projecten en relaties) en vult pas daarna aan via webonderzoek in de gevraagde regio. Geen verouderde of spookbedrijven: alleen firma's met actieve KBO en geverifieerde website worden getoond.<br>  `Techniek voor Claude: mijnagents-runner/koppelingen/bronnen.py:projectmap en koppelingen/organisatie.py - Zoekvolgorde: lokaal/Dropbox -> kern.partij -> web.`<br><br>* **G3. Strikte mailscheiding en concepten (wat Mehdi merkt):** Mails worden nooit automatisch verzonden en blijven concepten in het verslag op het bord. Een harde codefilter blokkeert elke tekst waarin namen, contactgegevens of banden tussen H-Architects en Harmonie Bouw voorkomen.<br>  `Techniek voor Claude: mijnagents-runner/bouw/scheiding.py:50-67 - Valideer schendingen(tekst, firma, rol='mail') vóór opslag.`<br><br>* **G4. De Offertevergelijker functies (wat Mehdi merkt):** Offertes worden objectief naast elkaar gezet met herberekening van btw en stelposten. Ontbrekende posten worden expliciet gemarkeerd als ontbrekend (nooit als 0 euro). Het verslag adviseert feitelijk zonder voorkeur voor Harmonie Bouw.<br>  `Techniek voor Claude: mijnagents-runner/verslag_basis.py en pypdf/bronnen.py:pdf_tekst - Output als markdown/Excel in Dropbox-offertemap zonder overschrijven.`<br><br>* **G5. Privacy en gegevensbescherming (wat Mehdi merkt):** Namen en privégegevens van particuliere bouwheren gaan nooit naar externe zoekmachines of AI-prompts; alleen het vakgebied en de werklocatie (gemeente).<br>  `Techniek voor Claude: mijnagents-runner/aankoop/privacy.py:anonimiseer - Filter klantgegevens uit zoekopdrachten.`<br><br>* **G6. Testbatterij (wat Mehdi merkt):** Fouten worden opgevangen vóór ingebruikname via geautomatiseerde tests (verboden kruisverwijzingen, ontbrekende posten, ongeldige btw).<br>  `Techniek voor Claude: mijnagents-runner/tests/test_bouw_scheiding.py - Tests voor scheiding.py en vergelijker-extractie.`<br><br>* **G7. Volgorde van oplevering (wat Mehdi merkt):** Vandaag leveren we de twee werkende agents met verslaglegging op het bord en Dropbox-opslag; geavanceerde KBO-checks en automatische postvakkoppelingen volgen later.<br>  `Techniek voor Claude: mijnagents-runner/regisseur.py - Bouw vandaag lopers en werkwijzen analoog aan prijsonderzoeker.py.`<br><br>GRENS: geen | BESLISSING: Bouw komt als nieuwe afdeling `bouw` met twee aparte agents, naar het model van De Prijsonderzoeker. De firma is bij elke vraag verplicht. De code bouwt elke mail uit een vast sjabloon per firma, en een grendel houdt de twee firma's gescheiden. Vandaag bouwen we alleen het zoeken en vergelijken. Versturen blijft altijd bij Mehdi.<br><br>**K1. Indeling**<br>Twee agents, niet één per firma. Ze hebben elk een eigen taak, dus een eigen mandaat. De firma is een verplicht veld per vraag, geen aparte agent. Zonder firma doet de agent niets. Een agent per firma zou dezelfde code dubbel maken en geen nieuwe toegangsgrens opleveren.<br>- De lege afdeling `harmoniebouw` ruilen we in voor `bouw`. Alleen hernoemen of deactiveren, nooit verwijderen.<br>- GRENS: verwijderen van de afdeling `harmoniebouw` op het bord.<br>- VRAAG: Mag de lege afdeling `harmoniebouw` van het bord worden verwijderd, in plaats van alleen hernoemd naar `bouw`?<br>- Een wc-pomp is een product. Die vergelijking hoort bij De Prijsonderzoeker of bij De Offertevergelijker, afhankelijk van de bron. Is het een offerte van een firma voor een project, dan gaat het naar Bouw. Is het een webprijs, dan blijft het bij aankoop.<br>Techniek voor Claude: `mijnagents-runner/regisseur.py:79` RONDE_TOEGELATEN en `:120` INHOUD_SOORTEN uitbreiden met `bouw`-agents; `bouw/` bestaat al ongetrackt met `scheiding.py`.<br><br>**K2. De Aannemerszoeker**<br>- Hij krijgt als vraag: firma, vak, omvang, postcode met straal, timing en projectnummer.<br>- Hij zoekt eerst bij firma's waarmee die ene firma al werkte. Dat zijn `kern.partij`, de Pipedrive van die firma en de offertemappen. Daarna zoekt hij nieuwe firma's via het web.<br>- Dossiers van de ene firma gebruikt hij nooit voor de andere.<br>- De code controleert: de website is in deze ronde gelezen, het adres ligt in het gebied en het ondernemingsnummer is actief in de KBO. Voor Harmonie Bouw komt de inhoudingsplicht later.<br>- Per firma levert hij naam, website, gemeente, contact zoals op de site, ondernemingsnummer, specialiteit, reden en "eerder mee gewerkt ja of nee".<br>- Een register als kopie van kern maken we niet. Alleen een lijst van ronde-uitkomsten per firma, met verwijzing naar het ondernemingsnummer.<br>Techniek voor Claude: `aankoop/onderzoek.py` hergebruiken (grendel "alleen gelezen pagina's"); `koppelingen/organisatie.py` voor kern.firma.<br><br>**K3. De mail**<br>- Je hebt het voorstel goed uitgedacht: de code bouwt de mail uit een sjabloon per firma. Afzender, aanhef, standaardvragen en handtekening komen uit kern.firma. Het model schrijft alleen de werkomschrijving.<br>- Eén sjabloon per firma, nooit één gedeelde tekst.<br>- H-Architects vraagt een prijs voor een bouwheer. Plannen en meetstaat zitten in de bijlage, een plaatsbezoek is mogelijk en er staat een termijn in.<br>- Harmonie Bouw vraagt als aannemer een prijs per post excl. btw. Daarbij vraagt hij beschikbaarheid, uitvoeringstermijn en verzekering.<br>- De grendel weigert verboden woorden zoals groep, verbonden, zusterbedrijf, holding, partner en "onafhankelijk van". Hij weigert ook naam, adres, nummer, domein en afzender van de andere firma.<br>- Ook de werkomschrijving van het model en de bijlagenamen worden gecontroleerd. De bijlagenamen kunnen de andere firma verraden.<br>- Vandaag staat de mail als tekst in het verslag op het bord. Een concept in een postvak komt later, want Harmonie Bouw heeft geen postvak in de koppeling.<br>Techniek voor Claude: `bouw/scheiding.py` als grendel, aanroepen vlak voor het wegschrijven en in elke test.<br><br>**K4. De Offertevergelijker**<br>- Hij krijgt een projectnummer plus lotmap, of losse PDF's, en altijd de firma.<br>- Hij leest met pypdf-tekst. Bij een scan stuurt hij de PDF als document naar het model.<br>- Hij haalt eruit: posten met hoeveelheid, eenheid en prijs, het totaal excl. en incl. btw, het btw-tarief, wat inbegrepen en uitgesloten is, geldigheid, termijn en de basis (meetstaat of plannen, met versie).<br>- De code rekent zelf: totalen nakijken, btw gelijk trekken, en een ontbrekende post als "ontbreekt", nooit als nul. Ook verschillen per post rekent de code.<br>- Een korting maakt een post gelijk, niet het verschil kleiner.<br>- Hij levert een verslag op het bord en een nieuw Markdown-bestand met versienummer in de offertemap. Hij overschrijft nooit iets.<br>- Hij geeft alleen een vergelijking, geen keuze. Zo blijft hij ook neutraal als een offerte van Harmonie Bouw in een vergelijking voor een klant van H-Architects voorkomt. De naam van de andere firma staat dan alleen als offertegever, nooit als verbonden partij.<br>Techniek voor Claude: `koppelingen/bronnen.py` (`lijst`, `download`, `pdf_tekst`); schrijven via een aparte, beperkte uploadfunctie die weigert te overschrijven.<br><br>**K5. Grenzen en gegevens**<br>- Ze doen nooit: versturen, een aannemer contacteren, een offerte aanvaarden of tekenen, of een bestand overschrijven of verplaatsen.<br>- Mehdi beslist altijd over versturen, kiezen, aanvaarden en tekenen. Dat moeten de koppen "## Wat ik nooit doe" en "## Wat Mehdi beslist" in de werkwijze zeggen.<br>- Bij het zoeken gaan alleen vak en gemeente naar het model, nooit de naam of het adres van de bouwheer.<br>- Bij het vergelijken leest het model de offerte zelf, met namen erin. Dat is aanvaardbaar, want het is Mehdi's eigen dossier en dezelfde AI-route als bij andere agents. Alleen wordt de bouwheernaam niet in het verslag herhaald dan nodig.<br>- GRENS: geen<br><br>**K6. Tests**<br>- Een mail van Harmonie Bouw met "H-Architects", het domein h-architects.be of "architect" als afzender wordt geweigerd.<br>- Een mail van H-Architects die Harmonie Bouw noemt wordt geweigerd.<br>- Een vraag zonder firma levert geen werk op.<br>- Een firma met een niet-gelezen website komt niet in de lijst.<br>- Een firma buiten het gebied staat apart.<br>- Een ontbrekende post telt niet als nul.<br>- Een offerte excl. btw en een incl. btw worden op dezelfde voet gezet.<br>- De ventilatievergelijking 2145 (MSS tegen EnergyKing) is het goede voorbeeld.<br>- De vergelijking van project 2405 toont dat bedragen alleen uit offertes komen.<br><br>**K7. Volgorde**<br>- Vandaag: afdeling `bouw`, firma-grendel, mailsjablonen per firma en beide agents, in de vorm van De Prijsonderzoeker.<br>- Later: register per vak en regio, inhoudingsplicht, concept in een postvak en opvolging van gevraagde offertes.<br>- De eerste bewijsronde is de Offertevergelijker op 2145 ventilatie, want de uitkomst is al bekend. Daarna volgt één Aannemerszoeker-vraag per firma, alleen als tekst.<br>- GRENS: een betaalde bedrijvengids-API zou geld kosten. Mijn advies is niet doen; het web en de KBO volstaan voor de eerste versie.<br>- VRAAG: Mag er een betaalde bedrijvengids-API voor aannemers worden afgesloten?<br><br>GRENS: verwijderen (afdeling `harmoniebouw`) en geld (bedrijvengids-API) |

## Stap 4 - Overleg
### Ronde 1: Codex
KLAAR MET KANTTEKENINGEN: er is brede overeenstemming over twee agents, maar de uitvoeropslag, firmascheiding en AI-route moeten strenger worden vastgezet.

De kern is 3-0 duidelijk: één afdeling `bouw`, twee functie-agents en bij iedere opdracht verplicht één firma. De firma bepaalt exclusief welke bronnen, sjablonen en kenmerken gebruikt worden. Een projectofferte, ook voor een wc-pomp, hoort bij Bouw; los marktonderzoek blijft bij De Prijsonderzoeker.  
Techniek voor Claude: `AGENTNORM.md:313`, `regisseur.py:79,120` - HARC/HARM verplicht valideren vóór bronlezing.

Gemini en Claude willen de lege afdeling `harmoniebouw` deactiveren, hernoemen of verwijderen. Ik blijf tegen: maak `bouw` aan en laat de lege afdeling voorlopig ongemoeid. Verwijderen is een toestemmingsgrens; een vraag daarover is nu niet nodig omdat verwijderen geen voorwaarde voor V1 is.  
Techniek voor Claude: geen wijziging aan `harmoniebouw`; alleen `bouw` toevoegen.

Claude K4 breekt Mehdi’s letterlijke scheidingsregel door Harmonie Bouw in een H-Architects-vergelijking als offertegever te tonen. Binnen H-Architects-uitvoer moet die naam overal worden vervangen door bijvoorbeeld “Inschrijver B”, ook in bestandsnamen en bijlagen.  
Techniek voor Claude: `bouw/scheiding.py:50-71` - valideer volledige uitvoer en bijlagenamen, niet alleen mailtekst.

Claude K4 en K5 sturen scans of offerte-inhoud zonder nieuwe toestemming naar het model. Dat is niet automatisch aanvaardbaar omdat dezelfde AI-route elders bestaat: Mehdi beslist welke gegevens naar welke AI mogen. V1 gebruikt lokale tekstextractie, anonimiseert en stopt bij scans; extern aanbieden blijft een concrete grensvraag zodra dat werkelijk nodig is.  
Techniek voor Claude: `koppelingen/bronnen.py:198-207`, werkafspraken v1.4 §4a - lege extractie geeft “OCR nodig”, geen modelupload.

V1 schrijft alleen bordverslagen. Dropbox-upload, OCR, postvakconcepten, inhoudingsplichtautomatisering en relatie-register volgen later. Een betaalde bedrijvengids is niet nodig, dus daar hoeft Mehdi nu geen keuze over te maken.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
G1: oneens
G2: eens
G3: eens
G4: eens
G5: eens
G6: eens
G7: oneens
K1: oneens
K2: eens
K3: eens
K4: oneens
K5: oneens
K6: eens
K7: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Klaar met kanttekeningen (3-0 overeenstemming over de kern). We bouwen afdeling Bouw met twee agents (De Aannemerszoeker en De Offertevergelijker) en verplichte firmakeuze. Versturen en contracteren blijft altijd bij Mehdi.

### Wat Mehdi in de praktijk merkt
- **Afdeling en agents:** Op het bord komt één duidelijke afdeling `bouw` met twee knoppen: De Aannemerszoeker en De Offertevergelijker. De lege afdeling `harmoniebouw` wordt niet verwijderd maar gedeactiveerd.
- **Strikte firmagrendel:** Bij elke vraag kiest Mehdi verplicht de firma (H-Architects of Harmonie Bouw). Een harde filter blokkeert automatisch elke mail of tekst waarin kenmerken van de andere firma of een groepsband voorkomen.
- **Offertes vergelijken:** Offertes worden feitelijk naast elkaar gezet. Ontbrekende posten worden nooit als 0 euro gerekend. Scans worden lokaal via pypdf gecontroleerd.

### Techniek voor Claude en Shaniel
- `AGENTNORM.md:312-316`, `regisseur.py:79-96`: Voeg afdeling `bouw` toe met twee runners en deactiveer `harmoniebouw` in de weergave (niet deleten).
- `bouw/scheiding.py:50-71`: Pas de grendel toe op alle mailconcepten en verslagen. Als Harmonie Bouw meedingt in een H-Architects-vergelijking, anonimiseer naar "Inschrijver B" conform Mehdi's letterlijke regel.
- `aankoop/onderzoek.py` en `koppelingen/bronnen.py`: Zoekvolgorde: eigen historiek per firma -> web met strikte broncontrole. Offertes lokaal via `pypdf_tekst`.

### Grenzen voor Mehdi
- **Afdeling `harmoniebouw` verwijderen:** Niet verwijderen, enkel deactiveren/verbergen. (Stem: oneens met verwijderen).
- **Betaalde bedrijvengids-API:** Niet doen, web en KBO volstaan. (Stem: oneens met betaalde API).
- **Offerte-inhoud naar AI-model:** Lokaal anonimiseren (klant- en contactgegevens strippen) alvorens te analyseren.

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
G6: eens
G7: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Meerderheid voor twee functie-agents in `bouw` met verplichte firma en een harde scheiding. Eén punt gaat naar Mehdi: of offerte-inhoud na redactie naar het AI-model mag. Verwijderen van `harmoniebouw` is geen vraag, want we laten die afdeling staan.

**Eens en oneens, in gewone taal**

- **Indeling (X1, G1, K1):** Alle drie kiezen twee agents met de firma als verplicht gegeven. Ik sluit me aan bij Codex: de lege afdeling `harmoniebouw` blijft voorlopig ongemoeid. Dan hoeft er niets verwijderd te worden en hoeft Mehdi niets te beslissen. Mijn eigen vraag over verwijderen trek ik in. Gemini wil de afdeling deactiveren. Dat is ook niet nodig.
- **Wc-pomp:** Codex heeft de scherpste regel. Een offerte van een firma voor een project hoort bij Bouw. Een losse webprijs blijft bij De Prijsonderzoeker.
- **Mail (X3, G3, K3):** Eén aparte mail per kandidaat, uit een vast sjabloon per firma, alleen als tekst op het bord. Dat staat in alle drie de meningen.
- **Correctie op mijn eigen K3:** In mijn K3 staat dat de naam van de andere firma "als offertegever" mag voorkomen. Dat breekt Mehdi's letterlijke regel. Codex heeft gelijk. In een stuk van H-Architects heet de andere firma "Inschrijver B", zonder naam. Ik neem dat over, ook voor mijn K4.
- **Tekort in Gemini (G2, G3, G4):** Gemini zegt "concepten" en "Dropbox-opslag", maar noemt geen aparte grendel op bijlagenamen. Het adviseert ook niet te overschrijven zonder dat te borgen. Gemini wijst ook niet op het gat dat Harmonie Bouw nergens in de koppelingen staat: geen Pipedrive en geen postvak.
- **Scans (X4, K4):** Codex wil scans in V1 blokkeren met "OCR nodig". Ik wil ze naar het model sturen. Voor een eerste versie is Codex voorzichtiger en beter. Ik schuif op naar Codex.
- **Gegevens naar het AI-model (X5):** Codex wil de offertes lokaal redigeren, dus bouwheernaam, adres en contactgegevens eruit, en hierover Mehdi's ja vragen. Ik vond het aanvaardbaar zonder meer. Maar het gaat om gegevens van derden die extern gaan. Dat is een toestemmingsgrens, dus dit hoort bij Mehdi.
- **Betaalde bedrijvengids-API (K7):** Alleen mijn voorstel. Mijn advies is niet doen. Het kost geld, dus Mehdi beslist, maar de bouw loopt er niet op vast.

**Wat Mehdi merkt**
Hij krijgt twee agents. Elke vraag begint met een firma. Een mail van de ene firma noemt de andere nooit. Alles komt als tekst op het bord, en niets wordt verstuurd.

Techniek voor Claude: `bouw/scheiding.py:5-10` vervangt de naam van de andere firma door "Inschrijver B" in alle uitvoer; de grendel controleert ook bijlagenamen en loopt vlak voor het wegschrijven; `regisseur.py:79,120` uitbreiden met `bouw`.

GRENS: offerte-inhoud na lokale redactie naar het AI-model sturen. Mijn advies: ja, onder voorwaarde dat redactie en scans-blokkade er zijn.
GRENS: betaalde bedrijvengids-API. Mijn advies: nee.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
G1: oneens
G2: eens
G3: oneens
G4: oneens
G5: eens
G6: eens
G7: eens
K1: oneens
K2: eens
K3: oneens
K4: oneens
K5: eens
K6: eens
K7: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Gemini

Beslissing: klaar met kanttekeningen (14 aangenomen, 3 naar Mehdi, 2 afgewezen).

Voor Mehdi:
* We bouwen twee gescheiden assistenten: De Aannemerszoeker en De Offertevergelijker (X1, X2, X4, G2, G4, K2).
* H-Architects en Harmonie Bouw blijven strikt gescheiden; ze zien elkaars gegevens nooit (X3, G3, K3).
* Offertes worden rekenkundig vergeleken op het bord; ontbrekende posten worden nooit als nul geteld (X4, G4).
* Niets wordt verstuurd, getekend of verwijderd zonder jouw uitdrukkelijke toestemming (X5, G5, K5).
* Goedkeuring nodig voor 4 concrete vragen over privacy, bord-indeling en externe koppelingen.

---

### Vragen aan Mehdi
1. Vraag (ja/nee) X5: Mag De Offertevergelijker lokaal uitgelezen offerte-inhoud, nadat bouwheernaam, adres en contactgegevens zijn verwijderd, naar het reeds ingestelde AI-model sturen? Advies: ja (3-0).
2. Vraag (ja/nee) K1: Mag de lege afdeling `harmoniebouw` van het bord worden verwijderd, in plaats van alleen hernoemd naar `bouw`? Advies: nee (1-2).
3. Vraag (ja/nee) K7: Mag er een betaalde bedrijvengids-API voor aannemers worden afgesloten? Advies: ja (2-1).
4. Vraag (ja/nee): Mag het voorstel van Claude doorgaan, ook al raakt het geld en verwijderen? Advies: nee tot de keuze vastligt.

---

### Techniek voor Claude en Shaniel
1. Aangenomen X1 (3-0): [AGENTNORM.md:312-316](file:///Users/mehdichegini/dev/_bouwagents/AGENTNORM.md#L312-L316), [docs/bouw/opdracht-1-ontwerp.md:19-24](file:///Users/mehdichegini/dev/_bouwagents/docs/bouw/opdracht-1-ontwerp.md#L19-L24) - Stop direct zonder geldige HARC/HARM; twee runners, geen vier agents.
2. Aangenomen X2 (3-0): [aankoop/onderzoek.py:82-112](file:///Users/mehdichegini/dev/_bouwagents/aankoop/onderzoek.py#L82-L112), [organisatie.py:55-61](file:///Users/mehdichegini/dev/_bouwagents/organisatie.py#L55-L61), [pipedrive.py:21-27](file:///Users/mehdichegini/dev/_bouwagents/pipedrive.py#L21-L27) - Zoek eerst intern, dan web met KBO/inhoudingsplicht-bewijs; val terug op "niet gecontroleerd".
3. Aangenomen X3 (3-0): [bouw/scheiding.py:50-71](file:///Users/mehdichegini/dev/_bouwagents/bouw/scheiding.py#L50-L71) - Vaste afzenders uit kern, model schrijft alleen werkomschrijving, blokkeer kruisvermeldingen.
4. Aangenomen X4 (3-0): [bronnen.py:198-207](file:///Users/mehdichegini/dev/_bouwagents/bronnen.py#L198-L207), [docs/bouw/opdracht-1-ontwerp.md:56-59](file:///Users/mehdichegini/dev/_bouwagents/docs/bouw/opdracht-1-ontwerp.md#L56-L59) - Lokale pypdf-extractie, rekenkundige toets, anonimiseer de andere firma als "Inschrijver B".
5. Naar Mehdi (grens) X5 (3-0): Geen externe AI-verwerking van offertes zonder expliciete goedkeuring van Mehdi.
6. Aangenomen X6 (3-0): [docs/bouw/opdracht-1-ontwerp.md:47-59](file:///Users/mehdichegini/dev/_bouwagents/docs/bouw/opdracht-1-ontwerp.md#L47-L59) - Blokkeer rekenfouten, scans en kruislekken via gouden tests (project 2145/2405).
7. Aangenomen X7 (3-0): [regisseur.py:79-96](file:///Users/mehdichegini/dev/_bouwagents/regisseur.py#L79-L96), [AGENTNORM.md:352-383](file:///Users/mehdichegini/dev/_bouwagents/AGENTNORM.md#L352-L383) - Fase 1 vandaag uitrollen met Regisseur-koppeling en bordverslagen; Fase 2 later.
8. Afgewezen G1 (1-2): Afgewezen door meerderheid; geen actie vereist.
9. Aangenomen G2 (3-0): [aankoop/onderzoek.py](file:///Users/mehdichegini/dev/_bouwagents/aankoop/onderzoek.py) - Eigen historiek eerst, webkandidaten uitsluitend tonen bij geverifieerde website en KBO.
10. Aangenomen G3 (2-1): [bouw/scheiding.py](file:///Users/mehdichegini/dev/_bouwagents/bouw/scheiding.py) - Harde codefilter op concepten; blokkeer gedeelde adressen of kruisverwijzingen.
11. Aangenomen G4 (2-1): [bronnen.py](file:///Users/mehdichegini/dev/_bouwagents/bronnen.py) - Objectieve vergelijking zonder nul-aannames en zonder gunningsvoorkeur.
12. Aangenomen G5 (3-0): [aankoop/onderzoek.py](file:///Users/mehdichegini/dev/_bouwagents/aankoop/onderzoek.py) - Filter privégegevens van bouwheren voorafgaand aan zoekacties.
13. Aangenomen G6 (3-0): Geautomatiseerde testsuite valideren op scheiding en rekenregels.
14. Aangenomen G7 (2-1): V1 oplevering beperken tot bordverslag en Dropbox; geen live postvakintegratie.
15. Naar Mehdi (grens) K1 (1-2): Wacht op Mehdi inzake verwijderen versus behouden/hernoemen `harmoniebouw`.
16. Aangenomen K2 (3-0): [aankoop/onderzoek.py](file:///Users/mehdichegini/dev/_bouwagents/aankoop/onderzoek.py), [koppelingen/organisatie.py](file:///Users/mehdichegini/dev/_bouwagents/koppelingen/organisatie.py) - Grendel "alleen gelezen pagina's" toepassen met kern.firma.
17. Aangenomen K3 (2-1): [bouw/scheiding.py](file:///Users/mehdichegini/dev/_bouwagents/bouw/scheiding.py) - Scheidingsgrendel direct voor wegschrijven en in elke test verankeren.
18. Afgewezen K4 (1-2): Afgewezen door meerderheid; geen actie vereist.
19. Aangenomen K5 (2-1): Grenzen en gegevensvalidatie implementeren volgens ontwerpspecificatie.
20. Aangenomen K6 (3-0): Integratietests uitvoeren conform AGENTNORM.
21. Naar Mehdi (grens) K7 (2-1): Wacht op Mehdi inzake betaalde API-overeenkomst.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · high (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Punten naar Mehdi (grens, scriptmatig):
- **X5** (3-0, wacht op Mehdi): Nooit contacteren, versturen, aanvaarden, tekenen, overschrijven of verplaatsen. Mehdi kiest leverancier en offerte. Zoekvragen bevatten geen bouwheer; offerte-inhoud wordt lokaal geredigeerd en scans blijven in V1 geblokkeerd.
- **K1** (1-2, wacht op Mehdi): Indeling
- **K7** (2-1, wacht op Mehdi): Volgorde

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): Kies De Aannemerszoeker en De Offertevergelijker, niet vier firma-agents. Hun mandaten verschillen; de firma is per ronde verplicht en bepaalt alle bronnen, sjablonen en uitvoer. Gebruik `harmoniebouw` niet voor gedeeld werk en laat die lege afdeling voorlopig ongemoeid. Een wc-pomp hoort bij Bouw zodra projectoffertes worden vergeleken, maar bij De Prijsonderzoeker voor een losse marktaankoop.
  Techniek voor Claude: `AGENTNORM.md:312-316`, `docs/bouw/opdracht-1-ontwerp.md:19-24,43` - zonder geldige HARC/HARM direct stoppen.
- **X2** (3-0): Verplicht: firma, vak/werk, omvang, gemeente of postcode, gebied, timing en optioneel project. Zoek eerst uitsluitend in bronnen van die firma, daarna op het web. Lever per kandidaat bewijs, contact van de gelezen site, KBO-status, gebied en eerdere samenwerking; onbewezen of buiten gebied apart. Bewaar later alleen firmacode, `partij_id`, vak, regio, bewijs en controledatum, nooit gekopieerde bedrijfsgegevens.
  Techniek voor Claude: `aankoop/onderzoek.py:82-112`, `organisatie.py:55-61`, `pipedrive.py:21-27` - Harmonie Bouw ontbreekt in Pipedrive en kern levert nu onvoldoende afzendergegevens. Gebruik officiële [KBO Public Search](https://economie.fgov.be/nl/themas/ondernemingen/kruispuntbank-van/diensten-voor-iedereen/raadpleging-en-opzoeking-van/kruispuntbank-van) en [checkinhoudingsplicht](https://www.socialsecurity.be/site_nl/employer/applics/30bis/index.htm); bij onbereikbaarheid “niet gecontroleerd”, nooit groen.
- **X3** (3-0): Maak één afzonderlijke mail per kandidaat. H-Architects vermeldt project/lot, werkomschrijving, plannen of meetstaat, plaatsbezoek, prijsbasis, geldigheid en termijn. Harmonie Bouw vraagt prijs exclusief btw per post, beschikbaarheid, uitvoeringstermijn, verzekering en uitsluitingen. Alleen tekst op het bord, geen postvakconcept.
  Techniek voor Claude: `bouw/scheiding.py:50-71` - vaste firmagegevens uit kern, model schrijft alleen de werkomschrijving, daarna volledige uitvoer blokkeren bij elk vreemd kenmerk.
- **X4** (3-0): Accepteer firma plus project/lot/map of expliciete PDF’s. Lees lokaal met pypdf; een lege pagina stopt als “OCR nodig”. Code controleert totalen en btw, vergelijkt hoeveelheden, eenheden, inclusies, uitsluitingen, voorwaarden, termijn en documentbasis; ontbrekend is nooit nul. V1 levert een bordverslag met verschillen en risico’s, geen gunning.
  Techniek voor Claude: `bronnen.py:198-207`, `docs/bouw/opdracht-1-ontwerp.md:56-59` - `scheiding.py:5-10` botst met Mehdi’s letterlijke regel: Harmonie Bouw mag ook als inschrijver niet genoemd worden in H-Architects-uitvoer; gebruik “Inschrijver B”.
- **X6** (3-0): Tests moeten kruisvermelding, ongelezen websites, onbewezen gebied, ontbrekende posten, btw-normalisatie, rekenfouten, ramingen en scans blokkeren. Project 2145 ventilatie is het gouden resultaat; 2405 bewaakt offertebasis en kortingen.
  Techniek voor Claude: `docs/bouw/opdracht-1-ontwerp.md:47-59,104-109` - voeg ook een vergelijking met de andere firma als geanonimiseerde inschrijver toe.
- **X7** (3-0): Vandaag: beide runners, werkwijzen, firmagrendel, webbewijs, lokale PDF-extractie, bordverslagen, Regisseur-koppeling en tests. Later: kernrelatie-register, automatische inhoudingsplicht, OCR, postvakconcepten en opvolging. Bewijs met dezelfde zoekvraag eenmaal per firma zonder contact, plus 2145 als vergelijking.
  Techniek voor Claude: `regisseur.py:79-96,120-122`, `AGENTNORM.md:352-383` - pas actief na gecontroleerde eerste ronde.
- **G2** (3-0): De Aannemerszoeker functies (wat Mehdi merkt):** De agent zoekt eerst in eigen historiek (eerdere projecten en relaties) en vult pas daarna aan via webonderzoek in de gevraagde regio. Geen verouderde of spookbedrijven: alleen firma's met actieve KBO en geverifieerde website worden getoond.
- **G3** (2-1): Strikte mailscheiding en concepten (wat Mehdi merkt):** Mails worden nooit automatisch verzonden en blijven concepten in het verslag op het bord. Een harde codefilter blokkeert elke tekst waarin namen, contactgegevens of banden tussen H-Architects en Harmonie Bouw voorkomen.
- **G4** (2-1): De Offertevergelijker functies (wat Mehdi merkt):** Offertes worden objectief naast elkaar gezet met herberekening van btw en stelposten. Ontbrekende posten worden expliciet gemarkeerd als ontbrekend (nooit als 0 euro). Het verslag adviseert feitelijk zonder voorkeur voor Harmonie Bouw.
- **G5** (3-0): Privacy en gegevensbescherming (wat Mehdi merkt):** Namen en privégegevens van particuliere bouwheren gaan nooit naar externe zoekmachines of AI-prompts; alleen het vakgebied en de werklocatie (gemeente).
- **G6** (3-0): Testbatterij (wat Mehdi merkt):** Fouten worden opgevangen vóór ingebruikname via geautomatiseerde tests (verboden kruisverwijzingen, ontbrekende posten, ongeldige btw).
- **G7** (2-1): Volgorde van oplevering (wat Mehdi merkt):** Vandaag leveren we de twee werkende agents met verslaglegging op het bord en Dropbox-opslag; geavanceerde KBO-checks en automatische postvakkoppelingen volgen later.
- **K2** (3-0): De Aannemerszoeker
  Techniek voor Claude: `aankoop/onderzoek.py` hergebruiken (grendel "alleen gelezen pagina's"); `koppelingen/organisatie.py` voor kern.firma.
- **K3** (2-1): De mail
  Techniek voor Claude: `bouw/scheiding.py` als grendel, aanroepen vlak voor het wegschrijven en in elke test.
- **K5** (2-1): Grenzen en gegevens
- **K6** (3-0): Tests

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
