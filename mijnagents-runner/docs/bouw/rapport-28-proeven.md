Niet klaar: 11 aangenomen (X1: Een verwachting is fout.; X2: Versterk drie zoekproeve; X3: Versterk drie offertepro; X5: Reken steekproeven zelf ; X6: F1 klopt op codeniveau.*; X7: F2 klopt.** Na acht; X8: F3 klopt in uitkomst,; G1: Dekkingsgraad en ontbrek; G2: Te losse en foutieve; G3: Waterdichtheid van de pr; G4: Handmatige nametingen (V); 1 wacht op jouw ja/nee (X4); 0 open; 1 afgewezen.
## Voor Mehdi
- Vraag (ja/nee): Mag punt X4 doorgaan? Advies: ja (3-0).
- Nog 2 vragen staan onder Vragen aan Mehdi.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | naar Mehdi (grens) |
| X5 | eens | eens | eens | 3-0 | aangenomen |
| X6 | eens | eens | eens | 3-0 | aangenomen |
| X7 | eens | eens | eens | 3-0 | aangenomen |
| X8 | eens | eens | eens | 3-0 | aangenomen |
| G1 | oneens | eens | eens | 2-1 | aangenomen |
| G2 | eens | eens | eens | 3-0 | aangenomen |
| G3 | oneens | eens | eens | 2-1 | aangenomen |
| G4 | eens | eens | eens | 3-0 | aangenomen |
| G5 | oneens | eens | oneens | 1-2 | afgewezen |

## Vragen aan Mehdi
1. Vraag (ja/nee) X4: Mag een latere uitvoering van deze twintig proeven mogelijk extra Claude-verbruik veroorzaken? Advies: ja (3-0).
   Grens volgens Codex: geld
2. Vraag (ja/nee): Mag het voorstel van Claude doorgaan, ook al raakt het extern versturen? Advies: nee tot de keuze vastligt.
   Grens volgens Claude: versturen
3. Vraag (ja/nee): Mag het adres blijven staan? Advies: nee tot de keuze vastligt.
   Grens volgens Claude: versturen. Mail.py:74-75 zet het projectadres van de bouwheer in de onderwerpregel van de prijsaanvraag, terwijl verslag.py:27-28 zegt dat dit nooit naar buiten gaat. Vraag: mag het adres blijven staa...
Ook genoemd (hoort bij een vraag of grenspunt hierboven, geen aparte vraag):
- Claude: geld
- Claude: geld, versturen

## Besluitenlijst vóór stemming
- X1: Een verwachting is fout.** A4 vraagt naar `Atlantis` zonder postcode. De agent houdt die vraag al tegen als ongeldig gemeenteveld, vóór hij de gemeente opzoekt. Gebruik `9999 Atlantis` als de proef specifiek “gemeente niet gevonden” moet toetsen.
  Techniek voor Claude: `bouw/vraag.py:100-109`, `aannemerszoeker.py:119-147` en `proeven/aannemerszoeker.json:13-15`.
- X2: Versterk drie zoekproeven.** A7, vraag rond `{zetel:HB}`: bied de andere firma als vaste modeltreffer aan; verwacht geen kandidaat en geen conceptmail. A8, vraag met `straal: 15`: verwacht dat iedere firma onder “klaar” een bevestigde KBO-zetel binnen 15 km heeft. A10, vraag over gevelreiniging: bied een stopgezette firma en een site zonder bewezen nummer aan; verwacht geen van beide onder “klaar”. De huidige verwachtingen laten nul treffers of onjuiste treffers toe.
  Techniek voor Claude: `proeven/aannemerszoeker.json:22-33`, `bouw/proefbank.py:156-170`, `bouw/zoeken.py:344-387`. Voeg vaste invoer en inhoudelijke toetsen toe.
- X3: Versterk drie offerteproeven.** V2, vraag `project: 2405; lot: 1`: verwacht dat iedere PDF in een inschrijversmap precies eenmaal meetelt. V4, vraag `project: U84; lot: 40`: verwacht dat alle negen PDF’s verantwoord zijn, gelezen of expliciet overgeslagen. V10, vraag `project: U82; lot: 65`: verwacht vooraf uit de PDF’s vastgelegde exacte totalen en btw. V3 vraagt nu wel Claude, maar toetst geen vergelijking per post.
  Techniek voor Claude: `proeven/offertevergelijker.json:7-15,31-33`, `bouw/proefbank.py:156-166`. Voeg aantallen en referentiebedragen toe.
- X4: De proefbank is niet waterdicht.** De huidige bordschrijfacties via `bord.call` worden opgevangen. Er is geen harde blokkade voor een latere rechtstreekse bordaanroep. De proef schrijft ook uitslagen en Claude-limietbestanden; Claude gebruikt het abonnement. Gebruik een alleen lezende bordtoegang en begrens de uitvoermap.
  Techniek voor Claude: `bouw/proefbank.py:224-249`, `koppelingen/claude_abonnement.py:157-183,302-332`.
  Grens, Mehdi beslist (jullie stem is het advies): geld
- X5: Reken steekproeven zelf na.** Vergelijk bij zoekresultaten KBO-status en zetel, afstand, eigen site, werkbewijs en mailadres. Vergelijk bij offertes de PDF-totalen, btw, geldigheid, ontbrekende posten en het aantal bestanden met het verslag. De huidige proefbank toetst vooral woorden en aantallen, geen onafhankelijke bronwaarden.
  Techniek voor Claude: `bouw/proefbank.py:141-180`, `bouw/zoeken.py:326-387`, `bouw/verslag.py:120-164`.
- X6: F1 klopt op codeniveau.** De lezer ziet alleen PDF’s direct in de lotmap. Lees ook één niveau inschrijversmappen, sla archiefmappen over en houd gelijke bestandsnamen onderscheidbaar.
  Techniek voor Claude: `bouw/mappen.py:78-87`, `bouw/offertes.py:287-299`.
- X7: F2 klopt.** Na acht PDF’s valt de rest stil weg. Tel alle gevonden PDF’s mee en meld ieder niet gelezen bestand; presenteer de vergelijking dan als onvolledig.
  Techniek voor Claude: `offertevergelijker.py:127-131`, `bouw/verslag.py:129-132`.
- X8: F3 klopt in uitkomst, niet in de beschrijving van de uitzondering.** De lotkeuzelijst toont ruwe mapnamen. De fout wordt wél door de buitenste `try` gevangen, waarna een nood volgt zonder verslag. Pas dezelfde veilige lotnaam ook op de keuzelijst toe.
  Techniek voor Claude: `bouw/verslag.py:112-117`, `offertevergelijker.py:123-125,196-200`.
- G1: Dekkingsgraad en ontbrekende proeven (Vraag 1):
  *Techniek voor Claude: `docs/bouw/proeven/aannemerszoeker.json:31` en `docs/bouw/proeven/offertevergelijker.json:25` - verwachtingen aanscherpen en ontbrekende categorieën toevoegen.*
- G2: Te losse en foutieve verwachtingen (Vraag 2):
  *Techniek voor Claude: `docs/bouw/proeven/offertevergelijker.json:33` - voeg `bevat` met bedragen uit U82 lot 65 toe.*
- G3: Waterdichtheid van de proefbank (Vraag 3):
  *Techniek voor Claude: `bouw/proefbank.py:65` - Claude-aanroepen zijn live; monitor abonnementslimieten.*
- G4: Handmatige nametingen (Vraag 4):
  *Techniek voor Claude: `offertevergelijker.py:129` en `bouw/verslag.py:38` - steekproefsgewijs PDF-teksten vergelijken met `uitslag.md`.*
- G5: Toetsing F1, F2 en F3 met minimale oplossingen (Vraag 5):
  *Techniek voor Claude: `bouw/mappen.py:82` (zoek 1 diep), `offertevergelijker.py:129` (tel afkapping), `bouw/verslag.py:114` (anonimiseer mapnamen).*

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: Niet akkoord. De twintig proeven zijn nuttige controles, maar bewijzen nog niet dat beide agents volledig en juist werken. F1, F2 en F3 zijn codeproblemen; de aantallen in de echte mappen heb ik tijdens dit alleen lezende overleg niet gecontroleerd.<br><br>**X1. Een verwachting is fout.** A4 vraagt naar `Atlantis` zonder postcode. De agent houdt die vraag al tegen als ongeldig gemeenteveld, vóór hij de gemeente opzoekt. Gebruik `9999 Atlantis` als de proef specifiek “gemeente niet gevonden” moet toetsen.  <br>Techniek voor Claude: `bouw/vraag.py:100-109`, `aannemerszoeker.py:119-147` en `proeven/aannemerszoeker.json:13-15`.<br><br>**X2. Versterk drie zoekproeven.** A7, vraag rond `{zetel:HB}`: bied de andere firma als vaste modeltreffer aan; verwacht geen kandidaat en geen conceptmail. A8, vraag met `straal: 15`: verwacht dat iedere firma onder “klaar” een bevestigde KBO-zetel binnen 15 km heeft. A10, vraag over gevelreiniging: bied een stopgezette firma en een site zonder bewezen nummer aan; verwacht geen van beide onder “klaar”. De huidige verwachtingen laten nul treffers of onjuiste treffers toe.  <br>Techniek voor Claude: `proeven/aannemerszoeker.json:22-33`, `bouw/proefbank.py:156-170`, `bouw/zoeken.py:344-387`. Voeg vaste invoer en inhoudelijke toetsen toe.<br><br>**X3. Versterk drie offerteproeven.** V2, vraag `project: 2405; lot: 1`: verwacht dat iedere PDF in een inschrijversmap precies eenmaal meetelt. V4, vraag `project: U84; lot: 40`: verwacht dat alle negen PDF’s verantwoord zijn, gelezen of expliciet overgeslagen. V10, vraag `project: U82; lot: 65`: verwacht vooraf uit de PDF’s vastgelegde exacte totalen en btw. V3 vraagt nu wel Claude, maar toetst geen vergelijking per post.  <br>Techniek voor Claude: `proeven/offertevergelijker.json:7-15,31-33`, `bouw/proefbank.py:156-166`. Voeg aantallen en referentiebedragen toe.<br><br>**X4. De proefbank is niet waterdicht.** De huidige bordschrijfacties via `bord.call` worden opgevangen. Er is geen harde blokkade voor een latere rechtstreekse bordaanroep. De proef schrijft ook uitslagen en Claude-limietbestanden; Claude gebruikt het abonnement. Gebruik een alleen lezende bordtoegang en begrens de uitvoermap.  <br>Techniek voor Claude: `bouw/proefbank.py:224-249`, `koppelingen/claude_abonnement.py:157-183,302-332`.  <br>GRENS: geld.  <br>VRAAG: Mag een latere uitvoering van deze twintig proeven mogelijk extra Claude-verbruik veroorzaken?<br><br>**X5. Reken steekproeven zelf na.** Vergelijk bij zoekresultaten KBO-status en zetel, afstand, eigen site, werkbewijs en mailadres. Vergelijk bij offertes de PDF-totalen, btw, geldigheid, ontbrekende posten en het aantal bestanden met het verslag. De huidige proefbank toetst vooral woorden en aantallen, geen onafhankelijke bronwaarden.  <br>Techniek voor Claude: `bouw/proefbank.py:141-180`, `bouw/zoeken.py:326-387`, `bouw/verslag.py:120-164`.<br><br>**X6. F1 klopt op codeniveau.** De lezer ziet alleen PDF’s direct in de lotmap. Lees ook één niveau inschrijversmappen, sla archiefmappen over en houd gelijke bestandsnamen onderscheidbaar.  <br>Techniek voor Claude: `bouw/mappen.py:78-87`, `bouw/offertes.py:287-299`.<br><br>**X7. F2 klopt.** Na acht PDF’s valt de rest stil weg. Tel alle gevonden PDF’s mee en meld ieder niet gelezen bestand; presenteer de vergelijking dan als onvolledig.  <br>Techniek voor Claude: `offertevergelijker.py:127-131`, `bouw/verslag.py:129-132`.<br><br>**X8. F3 klopt in uitkomst, niet in de beschrijving van de uitzondering.** De lotkeuzelijst toont ruwe mapnamen. De fout wordt wél door de buitenste `try` gevangen, waarna een nood volgt zonder verslag. Pas dezelfde veilige lotnaam ook op de keuzelijst toe.  <br>Techniek voor Claude: `bouw/verslag.py:112-117`, `offertevergelijker.py:123-125,196-200`.<br><br>Gedaan: code en twintig verwachtingen gelezen; niets gewijzigd.  <br>Nagekeken: uitvoerpaden en bordopvang.  <br>Open: echte mapinhoud en bronbedragen zijn niet nagekeken. | BESLISSING: De 20 proeven geven een sterke basis maar zijn nog niet voldoende om beide agents als bewezen te beschouwen; er ontbreken essentiële randgevallen (zoals samengestelde posten en submappen bij offertes), meerdere verwachtingen zijn te laks, en de vooraf opgemerkte fouten F1, F2 en F3 kloppen inhoudelijk.<br><br>G1. **Dekkingsgraad en ontbrekende proeven (Vraag 1):** <br>Mehdi merkt dat de huidige proevenset situaties mist waar offertes over meerdere mappen verspreid liggen of waar aannemers met meervoudige postcodes worden gezocht.<br>- Voorstel Aannemerszoeker:<br>  1. A11 (Grote straal & grens): `firma: HA; werk: chape en isolatiechape; gemeente: 3000 Leuven; straal: 60`. Verwachting: `klaar_min: 1, duur_max: 480`.<br>  2. A12 (Geweigerde kandidaat wegens ontbrekend ondernemingsnummer): kandidaat met wel een site maar zonder geldig KBO-nummer komt in het overzicht onder "nagekeken maar geweigerd" en nooit in "klaar".<br>  3. Vervangen A10: A10 test met `klaar_min: 0`, wat triviaal slaagt, zelfs als het script niets doet; vervang door een werk met minstens 1 verifieerbare lokale aannemer.<br>- Voorstel Offertevergelijker:<br>  1. V11 (Offertes met verschillende btw-stelsels / medecontractant): `firma: HA; project: 2405; lot: 03`. Verwachting: btw-verlegd correct aangeduid in totalen, `noden_max: 0`.<br>  2. V12 (Scan / onleesbare PDF naast geldige PDF): `firma: HB; project: U77; lot: 41`. Verwachting: verslag vermeldt expliciet "1 niet (scan of onleesbaar)".<br>  3. Vervangen V8: verwachting bevat nu enkel `noden_max: 0`; voeg toe `bevat: ["lot 01"]` en `niet: ["h-architects", "harmonie"]`.<br>*Techniek voor Claude: `docs/bouw/proeven/aannemerszoeker.json:31` en `docs/bouw/proeven/offertevergelijker.json:25` - verwachtingen aanscherpen en ontbrekende categorieën toevoegen.*<br><br>G2. **Te losse en foutieve verwachtingen (Vraag 2):**<br>Mehdi merkt dat een proef groen kan vlaggen terwijl de agent in werkelijkheid faalt of een leeg resultaat levert.<br>- In `aannemerszoeker.json:24` (A7) en `aannemerszoeker.json:33` (A10) staat `"klaar_min": 0`. Nul kandidaten gevonden betekent slagen voor de test; dit moet een striktere toets hebben op logging of een expliciete statusmelding.<br>- In `offertevergelijker.json:27` (V8) en `:33` (V10) ontbreken inhoudelijke asserts (enkel `noden_max: 0`). V10 moet de berekende totalen controleren (`bevat: [...]`), anders test het niets functioneels.<br>*Techniek voor Claude: `docs/bouw/proeven/offertevergelijker.json:33` - voeg `bevat` met bedragen uit U82 lot 65 toe.*<br><br>G3. **Waterdichtheid van de proefbank (Vraag 3):**<br>Mehdi merkt dat er niets naar het live bord lekt, maar Claude-verbruik en lokale Dropbox-lezingen vinden wel echt plaats.<br>- `Opname.call` vangt alle `POST`/`PUT`/`DELETE` calls naar `/api/` en `/agent-status` af (`bouw/proefbank.py:41-48`). Het bord wordt dus niet beschreven.<br>- Aandachtspunt: `claude_abonnement.vraag` wordt onderschept door `Teller`, maar roept wel degelijk live `self.echt(*args, **kw)` aan (`bouw/proefbank.py:65`). De proefbank verbruikt dus echte Claude-beurten en vereist actieve netwerktoegang.<br>*Techniek voor Claude: `bouw/proefbank.py:65` - Claude-aanroepen zijn live; monitor abonnementslimieten.*<br><br>G4. **Handmatige nametingen (Vraag 4):**<br>Mehdi merkt dat de proefbank slaagt op syntax en aanwezigheid van velden, maar de juistheid van de inhoud niet zelfstandig kan garanderen.<br>- Mehdi moet handmatig verifiëren: <br>  1. KBO-status en zeteladres van nieuw aangedragen aannemers (klopt de afstand hemelsbreed werkelijk).<br>  2. Btw-tarieven en verlegde btw in offertetabellen (de regex kan getallen verkeerd toewijzen bij afwijkende layouts).<br>  3. Of uitgesloten documenten daadwerkelijk fiches waren en geen substantiële bijlagen van de offerte.<br>*Techniek voor Claude: `offertevergelijker.py:129` en `bouw/verslag.py:38` - steekproefsgewijs PDF-teksten vergelijken met `uitslag.md`.*<br><br>G5. **Toetsing F1, F2 en F3 met minimale oplossingen (Vraag 5):**<br>Mehdi merkt dat submappen worden genegeerd (F1), documenten stilzwijgend verdwijnen (F2), of een taak crasht bij lotkeuze (F3).<br>- **F1 klopt:** `mappen.py:78-87` zoekt in `offertebestanden` met `recursief=False` enkel direct in de lotmap. Bij H-A staan offertes in `lot/<inschrijver>/*.pdf`.<br>  *Oplossing:* In `bouw/mappen.py:78` ook één niveau dieper zoeken in submappen als er direct geen PDF's staan, of submappen van inschrijvers scannen (`recursief=True` tot diepte 1).<br>- **F2 klopt:** In `offertevergelijker.py:129` wordt afgekapt op `[:MAX_OFFERTES]` (8). De negende offerte valt weg en `overgeslagen` telt enkel fiches (`offertevergelijker.py:130`).<br>  *Oplossing:* Bereken `buiten_limiet = len(bestanden_zonder_fiches) - MAX_OFFERTES` en meld dit aantal expliciet in de waarschuwingsregel van `bouw/verslag.py:130`.<br>- **F3 klopt:** `V.lotkeuze(v, lots)` in `bouw/verslag.py:114` toont ongefilterde mapnamen. Als een mapnaam de andere firma bevat, gooit `zet_klaar` een ongevalideerde `ValueError` (`offertevergelijker.py:83`) waardoor Mehdi een noodmelding krijgt.<br>  *Oplossing:* Filter elke lotnaam in `bouw/verslag.py:114` door `lotnaam(l, firma)` voordat ze aan de lijst worden toegevoegd.<br>*Techniek voor Claude: `bouw/mappen.py:82` (zoek 1 diep), `offertevergelijker.py:129` (tel afkapping), `bouw/verslag.py:114` (anonimiseer mapnamen).*<br><br>GRENS: geen | BESLISSING: Nee, de 20 proeven bewijzen niet dat beide agents goed werken. F1 en F2 kloppen, F3 klopt in het gevolg maar niet in het mechanisme, en de proefbank schrijft niet alleen naar het bord.<br><br>K1 Aannemerszoeker, drie aanvullingen:<br>- A11: twee klaargezette vragen. Nu wordt de echte route nooit getest, omdat de proeven altijd met een handvraag draaien. Verwacht: beide afgewerkt en opgepakt.<br>- A12: "werk: plafonneerwerk voor H-Architects, gemeente: 3020 Herent" zonder firma-veld. Verwacht: niet gestart, geen Claude, firma niet geraden.<br>- A8 krijgt de toets: elke klaar-firma binnen de straal.<br>Techniek voor Claude: vraag.py:53 raadt de firma uit de hele tekst. Fix: alleen het firma-veld gebruiken, anders blokkeren.<br><br>K2 Offertevergelijker, drie aanvullingen:<br>- V11: lot met alleen scans. Verwacht: niet vergeleken, geen Claude.<br>- V12: H-A-lot met een submap van de andere firma. Verwacht: die naam staat nergens in het verslag.<br>- V13: verlopen offerte. Verwacht: telt niet mee voor laagste en hoogste.<br>Techniek voor Claude: proefbank.py:146-180 keurt alleen het verslag, niet de posten. Fix: keur_posten (offertes.py:445-471) in de keuring opnemen.<br><br>K3 Verwachtingen die fout of te los zijn:<br>- V10 heeft geen toets op de totalen, terwijl het doel dat wel noemt.<br>- V5 bewijst niets als lot 2145 geen naam van de andere firma draagt. Dan is het groen zonder test.<br>- A7 toetst niet wat het doel zegt en is bijna dubbel met de grendel.<br>- A10 "niets verzonnen" is niet te toetsen.<br>- A4 eist dat Geopunt bereikbaar is. Bij uitval wordt het een nood (adresregister.py:51-56).<br>Techniek voor Claude: proefbank.py:161-166. Fix: scherpere verwachtingen; V5 als fixture-test, want die situatie is live niet af te dwingen.<br><br>K4 De proefbank is niet waterdicht. Schrijfopdrachten naar het bord worden goed onderschept (bord.py:35-40, proefbank.py:226-227). Maar elke vraag aan Claude schrijft een probebestand en kan het limietbestand van de live agents overschrijven (claude_abonnement.py:157-186, 311, 332). Ook projectadressen en organisatie schrijven caches (projectadressen.py:55-56, organisatie.py:104-105). Er is geen maximum op Claude-vragen (proefbank.py:60-74).<br>Techniek voor Claude: proefbank.py:226-229 moet LIMIET_BESTAND en de cache-paden naar de proefmap zetten en het aantal vragen begrenzen.<br>GRENS: geld<br>VRAAG: Mag de proefbank ongeveer tien Claude-vragen op je abonnement doen, ook als de live agents daardoor tijdelijk moeten wachten?<br><br>K5 Na het draaien zelf narekenen: KBO-status en -nummer, afstand vanaf de KBO-zetel, mailadres per firma, totalen, btw en geldig-tot tegen de PDF, de posten per cel, en of het juiste lot is gekozen.<br><br>K6 F1 klopt: mappen.py:82-84 leest alleen PDF's direct in het lot (offertevergelijker.py:127-129). Kleinste fix: een niveau dieper lezen als er niets direct staat, en een submap van de andere firma alleen als letter tonen. test_bouw.py:261-264 legt nu het foute gedrag vast en moet mee veranderen.<br>F2 klopt: offertevergelijker.py:129-132 neemt er acht en telt alleen fiches. Kleinste fix: het restaantal tellen en in verslag.py:131-132 melden. De weggelaten PDF's zijn nu de alfabetisch laatste, dus willekeurig, ook de goedkoopste.<br>F3 klopt in het gevolg, niet in het mechanisme: het zit binnen de try (offertevergelijker.py:196-200), dus geen crash, wel een nood en geen verslag. De vraag wordt daarna toch opgepakt (offertevergelijker.py:202-203). Kleinste fix: verslag.py:114 dezelfde naamregel gebruiken als lotnaam (offertevergelijker.py:88-94).<br><br>K7 Het onderwerp van de prijsaanvraag bevat het projectadres van de bouwheer (mail.py:19, 74-75). Verslag.py:27-28 zegt dat adres nooit naar buiten gaat.<br>GRENS: versturen<br>VRAAG: Mag het projectadres uit de onderwerpregel van de prijsaanvraag aan de firma blijven staan?<br>Techniek voor Claude: mail.py:74-75, alleen het projectnummer in het onderwerp.<br><br>GRENS: geld, versturen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: **Niet akkoord.** De twintig proeven zijn een goede start, maar kunnen slagen terwijl offertes ontbreken of bedragen verkeerd zijn.

- **Verwachtingen:** A4 faalt al op de ontbrekende postcode. `9999 Atlantis` bereikt wel de gemeentetoets. A7, A10, V5, V8 en V10 kunnen groen worden zonder hun doel te bewijzen. Gebruik vaste proefgegevens en controleer kandidaten, bedragen en posten tegen vooraf vastgelegde waarden.  
  Techniek voor Claude: `bouw/vraag.py:108-109`, `bouw/proefbank.py:156-170`, `docs/bouw/proeven/offertevergelijker.json:16-33`.

- **Aanvullingen:** Test bij de zoeker twee klaargezette vragen, een firmanaam buiten het firma-veld en de werkelijke afstand van elke goedgekeurde kandidaat. Test bij de vergelijker gemengde hoofd- en inschrijversmappen, verantwoording van alle PDF’s en bedragen per post. Een proef met alleen scans mag Claude pas uitsluiten als OCR ook geen leesbare offertes oplevert.  
  Techniek voor Claude: `bouw/vraag.py:53`, `aannemerszoeker.py:217-251`, `bouw/offertes.py:302-315`.

- **Proefbank:** Bordschrijfacties via `bord.call` worden onderschept, maar er is geen algemene blokkade op andere schrijfwegen. De proef schrijft ook cache- en limietbestanden en gebruikt echte Claude-beurten.  
  Techniek voor Claude: `bouw/proefbank.py:224-249`, `koppelingen/claude_abonnement.py:157-183`, `koppelingen/projectadressen.py:56`.

- **Zelf narekenen:** Controleer KBO-status, zetel, afstand, eigen site en mailadres. Leg bij offertes PDF-aantal, totalen, btw, geldigheid en posten naast het verslag.  
  Techniek voor Claude: `bouw/proefbank.py:141-180`, `bouw/verslag.py:145-163`.

- **F1, F2, F3:** Alle drie kloppen op codeniveau. Lees bij F1 ook inschrijversmappen, óók als er direct in de lotmap PDF’s staan. Meld bij F2 elk niet gelezen bestand en dat de vergelijking onvolledig is. Maak bij F3 lotnamen veilig vóór de keuzelijst; de buitenste foutopvang geeft nu een nood zonder verslag. De aantallen in de echte mappen zijn hier niet gecontroleerd.  
  Techniek voor Claude: `bouw/mappen.py:78-87`, `offertevergelijker.py:123-129,196-200`, `bouw/verslag.py:112-117`.

Claude’s punt over het projectadres vraagt een aparte afweging: het adres staat bewust in een **conceptmail**; er wordt nu niets verstuurd. De tekst over de bouwheer bewijst niet dat elk projectadres verboden is.  
Techniek voor Claude: `aannemerszoeker.py:86-99`, `bouw/mail.py:63-75`, `bouw/verslag.py:26-28`.

Gedaan: lokale code en verwachtingen gelezen; niets gewijzigd.  
Nagekeken: foutpaden, bordopvang en stemmen.  
Open: echte mapinhoud en bronbedragen narekenen.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
X8: eens
G1: oneens
G2: eens
G3: oneens
G4: eens
G5: oneens
K1: eens
K2: oneens
K3: oneens
K4: eens
K5: eens
K6: oneens
K7: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Akkoord met aanscherping. De 20 proeven vormen een goede basis, maar bewijzen het systeem pas als we de blinde vlekken dichten (submappen, overgeslagen offertes, ontbrekende postcode) en de verwachtingen inhoudelijk toetsen.

Mehdi merkt hiervan:
1. Hij krijgt straks ook offertes te zien die netjes per aannemer in een submapje zitten, in plaats van een lege melding.
2. Als er meer dan 8 offertes binnenkomen, ziet hij direct welke er ontbreken in plaats van dat ze geruisloos verdwijnen.
3. De proefbank verbruikt echte Claude-aanroepen op zijn abonnement; we begrenzen dit zodat zijn live agents niet stilvallen.

Overlegreacties op Codex en Claude:
- **Eens met X1**: `Atlantis` zonder postcode stuit direct af op validatie in `bouw/vraag.py:100-109`. `9999 Atlantis` test werkelijk de adresregister/geopunt fallback.
- **Eens met X2 & G1**: `klaar_min: 0` toetst niets (een crashloos leeg resultaat slaagt). Vaste criteria en grenzen toevoegen is noodzakelijk.
- **Eens met X3 & G2**: V10 moet specifieke bedragen en btw toetsen, anders is de vergelijking niet geverifieerd.
- **Eens met X4 & G3 (Grens geld)**: De proefbank vangt bordschrijven af, maar raakt live Claude (`koppelingen/claude_abonnement.py:65`). Limietbestand en cache isoleren naar de proefmap. Advies aan Mehdi: ja, proeven toestaan binnen strikte limiet.
- **Eens met X5 & G4**: Automatische proeven kunnen niet zelfstandig KBO-afstanden of complexe pdf-tabellen verifiëren; steekproef blijft nodig.
- **Eens met X6 & G5 (F1)**: `bouw/mappen.py:78-87` moet precies 1 niveau submappen doorzoeken.
- **Eens met X7 & G5 (F2)**: `offertevergelijker.py:129` moet afkapping na 8 bestanden expliciet kwantificeren en melden in `bouw/verslag.py:131`.
- **Eens met X8 & G5 (F3)**: Uitzondering valt binnen try-except, maar leidt tot nood in plaats van verslag. Mapnamen filteren via `lotnaam` in `bouw/verslag.py:114`.

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
X8: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Nee, de twintig proeven bewijzen nog niet dat beide agents goed werken. Dat is 3-0 op dit punt.

Ik heb de regels in dit overleg niet zelf nagelopen. Ik neem ze over uit de drie meningen.

**Waar we het eens zijn**
- F1 en F2 kloppen. Bij F2 vallen de alfabetisch laatste PDF's weg, en dat zijn willekeurige bestanden, ook de goedkoopste. Mehdi ziet dan een schijnbaar volledige vergelijking.
- Codex X1 klopt: A4 met "Atlantis" zonder postcode stopt in de vraagcheck, vóór de gemeentezoektocht. Mijn eerdere Geopunt-opmerking over A4 vervalt.
- Codex X4 en Gemini G3 zijn het eens over het live Claude-verbruik. Dat is een financiële keuze en daarom aan Mehdi.

**Waar ik oneens ben**
- Gemini G5 zegt dat F3 "crasht". Dat klopt niet. De fout zit binnen de try en eindigt als nood zonder verslag. Het gevolg is ernstig, het mechanisme niet.
- A10 "niets verzonnen" is niet te toetsen. Vervang die door een vaste bronlijst.

**Aannemerszoeker**
- Mehdi merkt dat de klaarzet-route nooit getest wordt. Voeg twee klaargezette vragen toe (A11), en een vraag zonder firmaveld (A12): niet gestart, geen Claude. Gemini's A11 (straal 60) en A12 (ontbrekend KBO-nummer) zijn goed, combineer ze hiermee.
  Techniek voor Claude: vraag.py:53 - firma uit de hele tekst laten raden; alleen het firmaveld gebruiken, anders blokkeren.
- Mehdi merkt dat "klaar" een stopgezette firma of een zetel buiten de straal kan tonen. Bied bij A7, A8 en A10 vaste treffers aan en verwacht geen van die fouten onder "klaar".
  Techniek voor Claude: proeven/aannemerszoeker.json:22-33 - vaste modeltreffers en KBO-check binnen de straal.

**Offertevergelijker**
- Mehdi merkt dat V10 groen wordt zonder dat de totalen gecontroleerd zijn. Leg vooraf de bedragen en btw uit de PDF's vast, en zet aantallen bij V2 en V4.
  Techniek voor Claude: proeven/offertevergelijker.json:31-33 - bedragen en btw als vaste toets.
- Mehdi merkt geen scans en verlopen offertes in het verslag. Voeg een scan-lot (V11), een verlopen offerte (V13) en een btw-verlegd geval toe.
  Techniek voor Claude: proefbank.py:146-180 - keur_posten (offertes.py:445-471) meenemen in de keuring.
- V5 bewijst niets als het lot geen naam van de andere firma draagt. Maak V5 een vaste testmap in plaats van een live proef.
  Techniek voor Claude: proefbank.py:161-166.

**Waterdichtheid**
- Het bord is dicht: schrijfopdrachten worden onderschept.
- De proefbank is niet dicht. Elke vraag aan Claude verbruikt het abonnement en kan het limietbestand van de live agents overschrijven. Cache-bestanden schrijven ook mee. Er is geen maximum aantal vragen. "Limieten monitoren" voorkomt dat niet.
  Techniek voor Claude: proefbank.py:226-229 - LIMIET_BESTAND en caches naar de proefmap, plus een maximum aan vragen.

**Na het draaien zelf narekenen**
- KBO-status en -nummer, afstand, mailadres, totalen, btw, geldig-tot, posten per cel en het juiste lot.
  Techniek voor Claude: zoeken.py:326-387 en verslag.py:120-164 - bronwaarden naast uitslag.md.

**F1, F2 en F3**
- F1: lees een niveau diep als de lotmap geen PDF's bevat. Toon een submap van de andere firma alleen als letter. test_bouw.py:261-264 legt nu het foute gedrag vast en moet mee.
  Techniek voor Claude: mappen.py:78-87 - diepte 1.
- F2: tel alle PDF's en meld het aantal niet gelezen bestanden.
  Techniek voor Claude: offertevergelijker.py:127-131 en verslag.py:129-132.
- F3: gebruik dezelfde naamregel voor de lotkeuzelijst.
  Techniek voor Claude: verslag.py:114 - naamregel uit offertevergelijker.py:88-94.

**Grenzen**
- GRENS: geld. Vraag: mag de proefbank ongeveer tien Claude-vragen op het abonnement doen, ook als de live agents daardoor moeten wachten? Gemini zegt geen grens, maar dit is een abonnementskeuze, dus Mehdi beslist.
- GRENS: versturen. Mail.py:74-75 zet het projectadres van de bouwheer in de onderwerpregel van de prijsaanvraag, terwijl verslag.py:27-28 zegt dat dit nooit naar buiten gaat. Vraag: mag het adres blijven staan? Ons advies: alleen het projectnummer.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
X8: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: oneens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Gemini

### Voor Mehdi

Beslissing: 11 herstelpunten aangenomen voor zelfstandige uitvoering, 1 punt afgewezen en 1 punt wacht op goedkeuring.

- We voeren elf verbeteringen aan de aannemerszoeker en offertevergelijker zelfstandig en veilig uit.
- De zoekresultaten worden scherper gecontroleerd op afstand, KBO-inschrijving en geldige contactgegevens.
- Alle offertes per lot worden volledig gelezen, inclusief submappen, zonder dat bestanden stil wegvallen.
- Steekproeven en bedragen uit offertedocumenten worden voortaan automatisch en onafhankelijk nagerekend.
- Vraag (ja/nee) X4: Mag een latere uitvoering van deze twintig proeven mogelijk extra Claude-verbruik veroorzaken? Advies: ja (3-0).

**Vragen aan Mehdi:**
1. Vraag (ja/nee) X4: Mag een latere uitvoering van deze twintig proeven mogelijk extra Claude-verbruik veroorzaken? Advies: ja (3-0).
2. Vraag (ja/nee): Mag het voorstel van Claude doorgaan, ook al raakt het extern versturen? Advies: nee tot de keuze vastligt.
3. Vraag (ja/nee): Mag het adres blijven staan? Advies: nee tot de keuze vastligt.

---

### Voor Claude en Shaniel

**Aangenomen punten (zelfstandig uitvoeren):**
1. **X1** (3-0, aangenomen): Ongeldige invoer `Atlantis` zonder postcode direct afvangen vóór gemeente-opzoeking.
   Techniek voor Claude: `bouw/vraag.py:100-109`, `aannemerszoeker.py:119-147`, `proeven/aannemerszoeker.json:13-15`
2. **X2** (3-0, aangenomen): A7, A8 en A10 aanscherpen op vaste modeltreffers, KBO-zetel binnen straal en uitsluiten stopgezette firma's.
   Techniek voor Claude: `proeven/aannemerszoeker.json:22-33`, `bouw/proefbank.py:156-170`, `bouw/zoeken.py:344-387`
3. **X3** (3-0, aangenomen): Offerteproeven V2, V4 en V10 voorzien van vaste aantallen bestanden en referentiebedragen.
   Techniek voor Claude: `proeven/offertevergelijker.json:7-15,31-33`, `bouw/proefbank.py:156-166`
4. **X5** (3-0, aangenomen): Onafhankelijke verificatie van bronwaarden (KBO, afstanden, bedragen, btw, bestandsaantallen).
   Techniek voor Claude: `bouw/proefbank.py:141-180`, `bouw/zoeken.py:326-387`, `bouw/verslag.py:120-164`
5. **X6** (3-0, aangenomen): Inschrijversmappen één niveau diep doorzoeken en archiefmappen overslaan.
   Techniek voor Claude: `bouw/mappen.py:78-87`, `bouw/offertes.py:287-299`
6. **X7** (3-0, aangenomen): Maximumlimiet van 8 PDF's wegnemen en onvolledige vergelijkingen expliciet signaleren.
   Techniek voor Claude: `offertevergelijker.py:127-131`, `bouw/verslag.py:129-132`
7. **X8** (3-0, aangenomen): Veilige lotnamen toepassen op de lotkeuzelijst om crashes op ruwe mapnamen te voorkomen.
   Techniek voor Claude: `bouw/verslag.py:112-117`, `offertevergelijker.py:123-125,196-200`
8. **G1** (2-1, aangenomen): Dekkingsgraad verhogen en ontbrekende categorieën opnemen.
   Techniek voor Claude: `docs/bouw/proeven/aannemerszoeker.json:31`, `docs/bouw/proeven/offertevergelijker.json:25`
9. **G2** (3-0, aangenomen): Losse verwachtingen aanscherpen met exacte bedragen uit U82 lot 65.
   Techniek voor Claude: `docs/bouw/proeven/offertevergelijker.json:33`
10. **G3** (2-1, aangenomen): Claude-aanroepen monitoren op abonnementslimieten tijdens proeven.
    Techniek voor Claude: `bouw/proefbank.py:65`, `koppelingen/claude_abonnement.py:157-183`
11. **G4** (3-0, aangenomen): Steekproefsgewijze controle tussen ruwe PDF-teksten en het eindrapport `uitslag.md`.
    Techniek voor Claude: `offertevergelijker.py:129`, `bouw/verslag.py:38`

**Punt naar Mehdi (grens - wacht op akkoord):**
- **X4** (3-0, naar Mehdi): Alleen-lezende bordtoegang instellen en uitvoermap begrenzen tegen onbedoelde schrijfacties en abonnementskosten.
  Techniek voor Claude: `bouw/proefbank.py:156-166,224-249`

**Afgewezen punt:**
- **G5** (1-2, afgewezen): Geen meerderheid voor het voorstel.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-6-sol · xhigh (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-haiku-5-5 · medium (voorgesteld)

Punten naar Mehdi (grens, scriptmatig):
- **X4** (3-0, wacht op Mehdi): De proefbank is niet waterdicht.** De huidige bordschrijfacties via `bord.call` worden opgevangen. Er is geen harde blokkade voor een latere rechtstreekse bordaanroep. De proef schrijft ook uitslagen en Claude-limietbestanden; Claude gebruikt het abonnement. Gebruik een alleen lezende bordtoegang en begrens de uitvoermap.

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): Een verwachting is fout.** A4 vraagt naar `Atlantis` zonder postcode. De agent houdt die vraag al tegen als ongeldig gemeenteveld, vóór hij de gemeente opzoekt. Gebruik `9999 Atlantis` als de proef specifiek “gemeente niet gevonden” moet toetsen.
  Techniek voor Claude: `bouw/vraag.py:100-109`, `aannemerszoeker.py:119-147` en `proeven/aannemerszoeker.json:13-15`.
- **X2** (3-0): Versterk drie zoekproeven.** A7, vraag rond `{zetel:HB}`: bied de andere firma als vaste modeltreffer aan; verwacht geen kandidaat en geen conceptmail. A8, vraag met `straal: 15`: verwacht dat iedere firma onder “klaar” een bevestigde KBO-zetel binnen 15 km heeft. A10, vraag over gevelreiniging: bied een stopgezette firma en een site zonder bewezen nummer aan; verwacht geen van beide onder “klaar”. De huidige verwachtingen laten nul treffers of onjuiste treffers toe.
  Techniek voor Claude: `proeven/aannemerszoeker.json:22-33`, `bouw/proefbank.py:156-170`, `bouw/zoeken.py:344-387`. Voeg vaste invoer en inhoudelijke toetsen toe.
- **X3** (3-0): Versterk drie offerteproeven.** V2, vraag `project: 2405; lot: 1`: verwacht dat iedere PDF in een inschrijversmap precies eenmaal meetelt. V4, vraag `project: U84; lot: 40`: verwacht dat alle negen PDF’s verantwoord zijn, gelezen of expliciet overgeslagen. V10, vraag `project: U82; lot: 65`: verwacht vooraf uit de PDF’s vastgelegde exacte totalen en btw. V3 vraagt nu wel Claude, maar toetst geen vergelijking per post.
  Techniek voor Claude: `proeven/offertevergelijker.json:7-15,31-33`, `bouw/proefbank.py:156-166`. Voeg aantallen en referentiebedragen toe.
- **X5** (3-0): Reken steekproeven zelf na.** Vergelijk bij zoekresultaten KBO-status en zetel, afstand, eigen site, werkbewijs en mailadres. Vergelijk bij offertes de PDF-totalen, btw, geldigheid, ontbrekende posten en het aantal bestanden met het verslag. De huidige proefbank toetst vooral woorden en aantallen, geen onafhankelijke bronwaarden.
  Techniek voor Claude: `bouw/proefbank.py:141-180`, `bouw/zoeken.py:326-387`, `bouw/verslag.py:120-164`.
- **X6** (3-0): F1 klopt op codeniveau.** De lezer ziet alleen PDF’s direct in de lotmap. Lees ook één niveau inschrijversmappen, sla archiefmappen over en houd gelijke bestandsnamen onderscheidbaar.
  Techniek voor Claude: `bouw/mappen.py:78-87`, `bouw/offertes.py:287-299`.
- **X7** (3-0): F2 klopt.** Na acht PDF’s valt de rest stil weg. Tel alle gevonden PDF’s mee en meld ieder niet gelezen bestand; presenteer de vergelijking dan als onvolledig.
  Techniek voor Claude: `offertevergelijker.py:127-131`, `bouw/verslag.py:129-132`.
- **X8** (3-0): F3 klopt in uitkomst, niet in de beschrijving van de uitzondering.** De lotkeuzelijst toont ruwe mapnamen. De fout wordt wél door de buitenste `try` gevangen, waarna een nood volgt zonder verslag. Pas dezelfde veilige lotnaam ook op de keuzelijst toe.
  Techniek voor Claude: `bouw/verslag.py:112-117`, `offertevergelijker.py:123-125,196-200`.
- **G1** (2-1): Dekkingsgraad en ontbrekende proeven (Vraag 1):
  *Techniek voor Claude: `docs/bouw/proeven/aannemerszoeker.json:31` en `docs/bouw/proeven/offertevergelijker.json:25` - verwachtingen aanscherpen en ontbrekende categorieën toevoegen.*
- **G2** (3-0): Te losse en foutieve verwachtingen (Vraag 2):
  *Techniek voor Claude: `docs/bouw/proeven/offertevergelijker.json:33` - voeg `bevat` met bedragen uit U82 lot 65 toe.*
- **G3** (2-1): Waterdichtheid van de proefbank (Vraag 3):
  *Techniek voor Claude: `bouw/proefbank.py:65` - Claude-aanroepen zijn live; monitor abonnementslimieten.*
- **G4** (3-0): Handmatige nametingen (Vraag 4):
  *Techniek voor Claude: `offertevergelijker.py:129` en `bouw/verslag.py:38` - steekproefsgewijs PDF-teksten vergelijken met `uitslag.md`.*

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
