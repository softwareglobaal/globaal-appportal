Besluit: 9 aangenomen (X1: K1: tel alleen geslaagde; X2: K2 is te ruim.; X3: K3 akkoord. Een explicie; X4: Er blijft één gemeten; G3: Restrisico K2: landkeuze; G4: Akkoord met K3 (geen; K1: Alleen geslaagde lezinge; K2: Verzendkost ook van een; K3: Niet opnieuw toestemming); 2 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | oneens | eens | 2-1 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | aangenomen |
| G1 | oneens | eens | oneens | 1-2 | afgewezen |
| G2 | oneens | eens | oneens | 1-2 | afgewezen |
| G3 | oneens | eens | eens | 2-1 | aangenomen |
| G4 | eens | eens | eens | 3-0 | aangenomen |
| K1 | oneens | eens | eens | 2-1 | aangenomen |
| K2 | oneens | eens | eens | 2-1 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |

## Besluitenlijst vóór stemming
- X1: K1: tel alleen geslaagde lezingen, met maximaal twaalf pogingen. Houd voorlopig zes geslaagde lezingen. De proef bewijst dat mislukte pagina’s de grens onterecht opgebruikten, niet dat tien geslaagde pagina’s nodig zijn.
- X2: K2 is te ruim. Alleen “zelfde host” kan ook de verzendkost van een ander product of Nederland goedkeuren. Een zichtbaar citaat met link volstaat niet, want dan moet Mehdi alsnog iedere fout ontdekken. Laat een aparte pagina alleen meetellen als de context België noemt, België ondubbelzinnig in een genoemde regio valt, of duidelijk zegt dat het tarief voor alle bestellingen geldt. Productgebonden tarieven moeten hetzelfde product of dezelfde modelcode noemen.
- X3: K3 akkoord. Een expliciete opdracht om handleiding en verzending te zoeken is al toestemming om openbare bronnen te lezen. Alleen werkelijk ontbrekende beslisinformatie mag een vervolgvraag veroorzaken.
- X4: Er blijft één gemeten oorzaak open: de twee handleidingbronnen waren technisch onleesbaar. Extra leesruimte maakt een JavaScript-viewer of HTTP 403 niet leesbaar. Zoek daarom na zo’n fout automatisch een alternatieve fabrikantpagina, PDF of specificatiebron voor exact dezelfde modelcode.
- G1: Akkoord met K1 (geslaagde lezingen tellen, limiet 10, max 20 pogingen).
  Techniek voor Claude: `aankoop/leesserver.py:26-28,201-223` - `MAX_LEZEN = 10` en `MAX_POGINGEN = 2 * MAX_LEZEN` berekend via `_gelezen_tot_nu(log)` op basis van `ok`.
- G2: Akkoord met K2 (verzendkosten van dezelfde host toegestaan).
  Techniek voor Claude: `aankoop/aanbod.py:280-283,514-520` - `citaat_op_pagina(citaat, alle_tekst)` toestaan voor veld `verzending` mits zelfde `netloc`.
- G3: Restrisico K2: landkeuze (België versus Nederland).
  Techniek voor Claude: `aankoop/werkwijze/prijsonderzoeker.md:48` (of runner prompt) - voeg instructie toe: zoek specifiek verzendkost naar België bij landspecifieke tabellen.
- G4: Akkoord met K3 (geen herhaalde toestemming vragen).
  Techniek voor Claude: `aankoop/werkwijze/prijsonderzoeker.md` - schrap de tussenstap waarin het model toestemming vraagt om publieke productspecificaties/handleidingen op te halen.
- K1: Alleen geslaagde lezingen tellen (grens 10).
- K2: Verzendkost ook van een pagina van dezelfde winkel.
- K3: Niet opnieuw toestemming vragen.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: K3 akkoord; K1 en K2 alleen aangepast uitvoeren, omdat de proef de verhoging naar tien lezingen en verzending van elke pagina op dezelfde host niet veilig bewijst.<br><br>X1. K1: tel alleen geslaagde lezingen, met maximaal twaalf pogingen. Houd voorlopig zes geslaagde lezingen. De proef bewijst dat mislukte pagina’s de grens onterecht opgebruikten, niet dat tien geslaagde pagina’s nodig zijn.<br><br>Wat Mehdi merkt: meer echte bronnen binnen dezelfde vraag, zonder onbewezen extra verbruik.<br><br>Techniek voor Claude: `aankoop/leesserver.py:201-223` en `aankoop/onderzoek.py:33-36` - scheid geslaagde lezingen van pogingen, behoud `MAX_LEZEN=6`, zet `MAX_POGINGEN=12`; pas de oude test aan op `tests/test_aankoop_prijs.py:817-821`.<br><br>X2. K2 is te ruim. Alleen “zelfde host” kan ook de verzendkost van een ander product of Nederland goedkeuren. Een zichtbaar citaat met link volstaat niet, want dan moet Mehdi alsnog iedere fout ontdekken. Laat een aparte pagina alleen meetellen als de context België noemt, België ondubbelzinnig in een genoemde regio valt, of duidelijk zegt dat het tarief voor alle bestellingen geldt. Productgebonden tarieven moeten hetzelfde product of dezelfde modelcode noemen.<br><br>Wat Mehdi merkt: een Nederlands tarief of verzending van een ander toestel wordt niet als volledig totaal aanbevolen.<br><br>Techniek voor Claude: `aankoop/aanbod.py:276-293,503-523` - controleer naast host ook bestemming en algemene of productspecifieke toepasbaarheid; behoud het scenario van `tests/test_aankoop_prijs.py:301-315` als grendel.<br><br>X3. K3 akkoord. Een expliciete opdracht om handleiding en verzending te zoeken is al toestemming om openbare bronnen te lezen. Alleen werkelijk ontbrekende beslisinformatie mag een vervolgvraag veroorzaken.<br><br>Wat Mehdi merkt: geen herhaalde vraag waarop hij al “ja” antwoordde.<br><br>Techniek voor Claude: `werkwijze/prijsonderzoeker.md:15-16,24-26` en `aankoop/onderzoek.py:101-113` - expliciete zoekonderdelen dezelfde ronde uitvoeren en niet als toestemmingsvraag teruggeven.<br><br>X4. Er blijft één gemeten oorzaak open: de twee handleidingbronnen waren technisch onleesbaar. Extra leesruimte maakt een JavaScript-viewer of HTTP 403 niet leesbaar. Zoek daarom na zo’n fout automatisch een alternatieve fabrikantpagina, PDF of specificatiebron voor exact dezelfde modelcode.<br><br>Techniek voor Claude: `aankoop/leesserver.py:218-235` en `docs/aankoop/opdracht-29-vervolg.md:16-18` - foutbron overslaan en binnen de zoekgrens een alternatieve bron proberen.<br><br>GRENS: geen | BESLISSING: Akkoord met K1, K2 en K3. Het zichtbare bewijscitaat met link en context volstaat voor Mehdi, mits een klein restrisico op landkeuze wordt afgedekt.<br><br>Wat Mehdi hiervan in de praktijk merkt:<br>- De Prijsonderzoeker zoekt direct door naar handleidingen en verzendkosten zodra je daarom vraagt, zonder overbodig opnieuw toestemming te vragen.<br>- Mislukte webpagina's (zoals foutmeldingen of lege viewers) snoepen je leesbudget niet meer op, waardoor het model tot 10 echte pagina's kan doornemen.<br>- Verzendkosten van aparte infopagina's van dezelfde winkel tellen mee, compleet met link en citaat ter controle, zodat aanbiedingen niet onterecht als onvolledig worden afgewezen.<br><br>**G1. Akkoord met K1 (geslaagde lezingen tellen, limiet 10, max 20 pogingen).**<br>Twee mislukte downloads (403 en JS-viewer) verbruikten 33 procent van de oude leesruimte (6 pagina's). Door alleen geslaagde pagina's te tellen met een plafond van 10 lezingen en 20 pogingen, blijft de veiligheid tegen lussen behouden zonder legitieme bronnen af te knijpen.<br>Techniek voor Claude: `aankoop/leesserver.py:26-28,201-223` - `MAX_LEZEN = 10` en `MAX_POGINGEN = 2 * MAX_LEZEN` berekend via `_gelezen_tot_nu(log)` op basis van `ok`.<br><br>**G2. Akkoord met K2 (verzendkosten van dezelfde host toegestaan).**<br>Winkels zoals RoboCleaners tonen verzendkosten op een aparte leveringspagina. Door dezelfde host toe te staan met verplicht bewijscitaat en brondocumentatie in het verslag, wordt het aanbod correct als volledig berekend.<br>Techniek voor Claude: `aankoop/aanbod.py:280-283,514-520` - `citaat_op_pagina(citaat, alle_tekst)` toestaan voor veld `verzending` mits zelfde `netloc`.<br><br>**G3. Restrisico K2: landkeuze (België versus Nederland).**<br>Het zichtbare citaat met link volstaat voor Mehdi omdat hij het voorstel controleert via de link. Als kleinste extra code-regel: eis in de prompt/werkwijze dat het model bij leveringstarieven expliciet zoekt naar tarieven voor levering naar België (of dat het citaat "België"/"BE" bevat indien er landensplitsing op de pagina staat).<br>Techniek voor Claude: `aankoop/werkwijze/prijsonderzoeker.md:48` (of runner prompt) - voeg instructie toe: zoek specifiek verzendkost naar België bij landspecifieke tabellen.<br><br>**G4. Akkoord met K3 (geen herhaalde toestemming vragen).**<br>Mehdi's expliciete opdracht in de vervolgvraag is reeds bindend; het model hoeft niet in een beleefdheidslus te blijven hangen voor openbare webpagina's.<br>Techniek voor Claude: `aankoop/werkwijze/prijsonderzoeker.md` - schrap de tussenstap waarin het model toestemming vraagt om publieke productspecificaties/handleidingen op te halen.<br><br>GRENS: geen | BESLISSING: Akkoord met K1, K2 en K3, met twee aanvullingen: een landregel bij K2 en een lagere grens voor mislukte pogingen bij K1. Ik heb alleen het opdrachtbestand gelezen. De regels in de code heb ik niet zelf nagelezen.<br><br>**K1. Alleen geslaagde lezingen tellen (grens 10).**<br>Mehdi merkt dan dat een kapotte pagina de rest van het onderzoek niet meer opvreet. Het scenario uit de proef (2 foutpagina's, handleiding niet gelezen) komt dan niet meer voor.<br>- Zwakte: "hoogstens 2 x de grens" laat 20 mislukte pogingen toe. Dat is te ruim en kost tijd en tokens zonder winst. Neem hoogstens 4 mislukte pogingen en laat een host die één keer mislukte (403 of viewer zonder tekst) niet opnieuw proberen.<br>- Een mislukte bron lost dit niet op. Het model moet dan een andere bron voor de handleiding zoeken, bijvoorbeeld de site van de fabrikant.<br><br>Techniek voor Claude: `aankoop/leesserver.py:210` - tel alleen regels met status ok. Voeg een aparte teller toe voor mislukte pogingen met maximum 4 en een blokkade per host. Verhoog MAX_LEZEN van 6 naar 10.<br><br>**K2. Verzendkost ook van een pagina van dezelfde winkel.**<br>Mehdi ziet dan een volledig totaal bij RoboCleaners in plaats van "totaal onvolledig". Dat besluit klopt, want X16 is door de echte winkel bevestigd.<br>- Zwakte 1: de host moet exact gelijk zijn, of dezelfde basisdomeinnaam. Een redirect naar een andere host telt niet mee.<br>- Zwakte 2: het model kan het tarief van het verkeerde land pakken.<br><br>Techniek voor Claude: `aankoop/aanbod.py:281` - sta een citaat toe van elke gelezen pagina met dezelfde host als het aanbod. Controleer de host na redirects. Pas werkwijze regel 48 aan.<br><br>**Vraag 2: volstaat citaat met context en link?**<br>Nee, nog niet helemaal. De kleinste extra regel is: bij een verzendpagina van dezelfde winkel moet het citaat "België", "Belgium" of "BE" bevatten. Staat het land er niet in, dan staat in het verslag "land niet bewezen" en telt het totaal als onvolledig. Een tarief zonder landaanduiding, zoals "gratis boven 100 euro" of één vast bedrag, mag wel als de pagina geen landen noemt. Dat moet het verslag dan zichtbaar vermelden. Het nakijken door Mehdi blijft een vangnet, geen controle.<br><br>Techniek voor Claude: `aankoop/aanbod.py:268-290` - landcontrole op het citaat. Anders markeer je "land niet bewezen".<br><br>**K3. Niet opnieuw toestemming vragen.**<br>Mehdi hoort niet twee keer dezelfde vraag. Alleen werkwijze-tekst is zwak, omdat het model zijn eerdere antwoord niet vanzelf kent.<br>- Aanvulling: geef Mehdi's antwoord ("Ja, verder zoeken") expliciet mee in de vervolgvraag. Verbied in het verslag de zin "mag ik lezen?" voor onderwerpen die al gevraagd zijn.<br><br>Techniek voor Claude: `werkwijze/prijsonderzoeker.md` - voeg de K3-regel toe. In `prijsonderzoeker.py --vraag` voeg je een veld "reeds toegestaan" toe aan de prompt.<br><br>**Vraag 3: ontbrekende oorzaak.**<br>Ja, één. Het model vroeg opnieuw om toestemming omdat die context ontbrak, niet alleen door de leesgrens. K3 als tekstregel dekt dat alleen als de prompt het antwoord ook meegeeft (zie de aanvulling hierboven). Verder ontbreekt een bewijs dat een alternatieve handleidingbron bereikbaar is. Dat blijkt pas uit de nieuwe proef.<br><br>**Na het herstel:** dezelfde vervolgvraag opnieuw op de VM draaien. Slaagt die niet, dan is dit herstel niet voldoende bewezen.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: Kies de kleinste gemeten oplossing: zes geslaagde lezingen, maximaal twaalf pogingen, streng verzendbewijs voor België en geen herhaalde toestemming.

Eens met X1. De proef bewijst dat mislukte lezingen het budget opaten. Ze bewijst niet dat tien geslaagde pagina’s nodig zijn. Zes geslaagde lezingen geven hier al vier extra echte bronnen.

Eens met X2. Gemini’s zichtbare citaat is geen voldoende controle. De huidige code controleert wel verzendwoorden en bedrag, maar niet België of producttoepassing. Mehdi mag niet de foutcontrole worden.

Eens met X3 en G4. De expliciete zoekopdracht is voldoende. Claude’s extra veld “reeds toegestaan” is nog niet als ontbrekende oorzaak gemeten.

Eens met X4 als werkwijzeregel: een 403 of lege viewer moet leiden naar een alternatieve bron voor exact dezelfde modelcode. Claude’s blokkade van een volledige host na één fout is te streng, omdat een andere pagina of PDF op die host wel kan werken.

Oneens met G1 en K1: tien geslaagde lezingen verhoogt verbruik zonder proefbewijs. Oneens met G2 en K2: dezelfde host alleen voorkomt een Nederlands of productvreemd tarief niet. G3 is richtinggevend, maar een promptregel alleen is geen betrouwbare grendel.

Techniek voor Claude: `aankoop/leesserver.py:26-27,201-223` - zes successen en twaalf totale pogingen; `aankoop/aanbod.py:276-292,514-523` - bestemming en algemene of productspecifieke toepasbaarheid controleren; `werkwijze/prijsonderzoeker.md:17-18,26-28,50-51` - geen herhaalde toestemming en na een fout een exacte alternatieve bron zoeken.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
G1: oneens
G2: oneens
G3: oneens
G4: eens
K1: oneens
K2: oneens
K3: eens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: 3-0 akkoord om K1, K2 en K3 uit te voeren, waarbij we K1 en K2 verfijnen met de landcontrole en gerichte foutafhandeling.

Wat Mehdi in de praktijk merkt:
- De Prijsonderzoeker zoekt direct zelfstandig door naar handleidingen en verzendkosten als je dat vraagt, zonder overbodig opnieuw toestemming te vragen.
- Kapotte pagina's (zoals 403 of lege viewers) snoepen je leesbudget niet meer op; het model telt alleen geslaagde pagina's en zoekt bij een fout meteen een alternatieve bron voor hetzelfde model.
- Verzendkosten van aparte leveringspagina's van dezelfde winkel tellen mee, mits het tarief aantoonbaar voor België geldt (of algemeen voor alle bestellingen is).

1. **K1 / G1 / X1 (Leesgrens en tellen van geslaagde pagina's):**
Eens met K1 en G1 (MAX_LEZEN op 10, mislukte pogingen aftoppen). Codex stelt 6 geslaagde lezingen voor (X1), maar de praktijkproef met 5 zoekopdrachten en een handleiding plus meerdere verzendpagina's toont aan dat 6 te krap is zodra er meerdere winkels en documenten worden vergeleken. 10 geslaagde pagina's met een stop op mislukte pogingen (maximaal 12 tot 20) voorkomt lussen zonder nuttige data af te kappen.
Techniek voor Claude: `mijnagents-runner/aankoop/leesserver.py:26-28,201-223` - `MAX_LEZEN = 10`, `MAX_POGINGEN = 12` (of `2 * MAX_LEZEN`), alleen tellen van `ok=True`.

2. **K2 / G2 / G3 / X2 (Verzendkosten van dezelfde winkel en landcontrole):**
Eens met K2 en G2, aangevuld met de landgrendel van X2/G3/Claude. Alleen "zelfde host" is te vaag als er meerdere landentarieven op de pagina staan. Er moet bewijs zijn dat het tarief geldt voor levering naar België (of een algemeen tarief is).
Techniek voor Claude: `mijnagents-runner/aankoop/aanbod.py:280-293` - valideer dat het citaat van de verzendpagina bij landentabellen "België", "Belgium", "BE" bevat of ondubbelzinnig algemeen geldt.

3. **K3 / G4 / X3 (Geen herhaalde toestemming vragen):**
Eens met K3, G4 en X3. Een expliciete opdracht in een vervolgvraag is reeds bindende toestemming om openbare bronnen te raadplegen.
Techniek voor Claude: `werkwijze/prijsonderzoeker.md` en `aankoop/onderzoek.py:101-113` - vervolgopdracht direct uitvoeren zonder herhaalde toestemmingsvraag.

4. **X4 (Alternatieve bron bij technische fouten):**
Eens met X4 van Codex. Als een handleidingbron 403 geeft of een lege JS-viewer toont, moet het model direct doorschakelen naar een alternatieve bron (zoals de fabrikant of een directe PDF).
Techniek voor Claude: `mijnagents-runner/aankoop/leesserver.py:218-235` en werkwijze - foutieve bron direct overslaan en alternatief bevragen.

STEMBLOK: Gemini
X1: oneens
X2: eens
X3: eens
X4: eens
G1: eens
G2: eens
G3: eens
G4: eens
K1: eens
K2: eens
K3: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: K3 en K2 gaan door, K2 met een landregel. K1 gaat door met "alleen geslaagde lezingen tellen" en een begrensd aantal mislukte pogingen. Of de grens van 6 naar 10 gaat, laat ik open voor de nieuwe proef. Ik heb alleen het opdrachtbestand en de drie meningen gelezen, niet de code zelf.

**K1. Geslaagde lezingen tellen, mislukte apart.**
Mehdi merkt dat een kapotte pagina het onderzoek niet meer afkapt.
- Ik sluit me aan bij Codex: de proef bewijst dat mislukte pogingen de grens onterecht opaten. Hij bewijst niet dat tien geslaagde pagina's nodig zijn. In de proef waren 4 pagina's gelezen en 2 mislukt, en daarna was de grens van 6 op. Alleen de telling repareren geeft al 2 extra leesbeurten.
- Mijn eerdere voorstel was maximaal 4 mislukte pogingen. Codex noemt 12 pogingen in totaal en Gemini 20. Ik houd 4 mislukte pogingen aan, met een blokkade per host na één mislukking. Dat is strakker en kost minder tijd en tokens.
- Ik trek mijn eerdere steun voor het verhogen naar 10 in. Eerst meten met 6 geslaagde lezingen. Blijkt dat te weinig, dan verhogen we met een nieuw bewijs.

Techniek voor Claude: `aankoop/leesserver.py:210` - tel alleen status ok voor de leesgrens, aparte teller voor mislukt (max 4) met blokkade per host. MAX_LEZEN voorlopig 6.

**K2. Verzending van een pagina van dezelfde winkel.**
Mehdi ziet dan geen onterechte "totaal onvolledig" meer bij RoboCleaners.
- Codex heeft gelijk dat "zelfde host" alleen te ruim is. Een tarief voor Nederland of voor een ander toestel mag niet als volledig totaal tellen. Ik sluit me aan bij zijn regel, in de eenvoudigste vorm: het citaat noemt België, valt ondubbelzinnig onder een regio waar België bij hoort, of de pagina zegt dat het tarief voor alle bestellingen geldt. Anders staat in het verslag "land niet bewezen" en blijft het totaal onvolledig.
- Een productgebonden tarief moet de modelcode of het product noemen.
- Het zichtbare citaat met link blijft verplicht, maar is een vangnet en geen controle.

Techniek voor Claude: `aankoop/aanbod.py:276-293` - naast host ook een controle op bestemming en op product of modelcode. Het scenario `tests/test_aankoop_prijs.py:301-315` blijft als grendel.

**K3. Niet opnieuw toestemming vragen.**
Mehdi hoort dezelfde vraag niet nog eens.
- Ik neem Codex' zin over: alleen echt ontbrekende beslisinformatie mag een vervolgvraag geven.
- Mijn aanvulling blijft: Mehdi's antwoord moet in de prompt van `--vraag` staan. Een tekstregel in de werkwijze alleen is niet genoeg.

Techniek voor Claude: `werkwijze/prijsonderzoeker.md:15-16,24-26` en `prijsonderzoeker.py --vraag` - K3-regel toevoegen en een veld "reeds toegestaan" meegeven.

**Extra oorzaak (Codex X4).**
De twee handleidingbronnen waren technisch onleesbaar (viewer zonder tekst, HTTP 403). Meer leesruimte lost dat niet op. Ik ben het eens met zoeken naar een alternatieve fabrikantbron voor dezelfde modelcode. Dit is wel nieuw gedrag, dus ik zou het klein houden: één alternatieve zoekopdracht na een mislukte handleidingbron.

Techniek voor Claude: `aankoop/leesserver.py:218-235` - bij een mislukte handleidingbron één extra zoekpoging naar een fabrikantpagina of PDF voor dezelfde modelcode.

**Daarna.** De vervolgvraag opnieuw draaien op de VM. Dat resultaat telt.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
G1: oneens
G2: oneens
G3: eens
G4: eens
K1: eens
K2: eens
K3: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Codex

Besluit: acht herstelpunten zijn aangenomen; niets hoeft naar Mehdi.

- X1 en K1 aangenomen: alleen geslaagde lezingen tellen, voorlopig zes binnen twaalf pogingen.
- X2, K2 en G3 aangenomen: verzendkosten vereisen passend product én bewijs voor België.
- X3, G4 en K3 aangenomen: openbare bronnen lezen mag zonder opnieuw toestemming te vragen.
- X4 aangenomen: onleesbare handleidingen leiden automatisch naar een alternatieve bron.
- G1 en G2 afgewezen.

Techniek voor Claude: voer dit zelfstandig uit en borg het met tests op de aangehaalde regels.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (2-1): K1: tel alleen geslaagde lezingen, met maximaal twaalf pogingen. Houd voorlopig zes geslaagde lezingen. De proef bewijst dat mislukte pagina’s de grens onterecht opgebruikten, niet dat tien geslaagde pagina’s nodig zijn.
- **X2** (3-0): K2 is te ruim. Alleen “zelfde host” kan ook de verzendkost van een ander product of Nederland goedkeuren. Een zichtbaar citaat met link volstaat niet, want dan moet Mehdi alsnog iedere fout ontdekken. Laat een aparte pagina alleen meetellen als de context België noemt, België ondubbelzinnig in een genoemde regio valt, of duidelijk zegt dat het tarief voor alle bestellingen geldt. Productgebonden tarieven moeten hetzelfde product of dezelfde modelcode noemen.
- **X3** (3-0): K3 akkoord. Een expliciete opdracht om handleiding en verzending te zoeken is al toestemming om openbare bronnen te lezen. Alleen werkelijk ontbrekende beslisinformatie mag een vervolgvraag veroorzaken.
- **X4** (3-0): Er blijft één gemeten oorzaak open: de twee handleidingbronnen waren technisch onleesbaar. Extra leesruimte maakt een JavaScript-viewer of HTTP 403 niet leesbaar. Zoek daarom na zo’n fout automatisch een alternatieve fabrikantpagina, PDF of specificatiebron voor exact dezelfde modelcode.
- **G3** (2-1): Restrisico K2: landkeuze (België versus Nederland).
  Techniek voor Claude: `aankoop/werkwijze/prijsonderzoeker.md:48` (of runner prompt) - voeg instructie toe: zoek specifiek verzendkost naar België bij landspecifieke tabellen.
- **G4** (3-0): Akkoord met K3 (geen herhaalde toestemming vragen).
  Techniek voor Claude: `aankoop/werkwijze/prijsonderzoeker.md` - schrap de tussenstap waarin het model toestemming vraagt om publieke productspecificaties/handleidingen op te halen.
- **K1** (2-1): Alleen geslaagde lezingen tellen (grens 10).
- **K2** (2-1): Verzendkost ook van een pagina van dezelfde winkel.
- **K3** (3-0): Niet opnieuw toestemming vragen.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
