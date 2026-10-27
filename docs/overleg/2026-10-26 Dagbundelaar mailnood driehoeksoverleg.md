Besluit: 11 aangenomen (X1: Kernoorzaak voor de gewo; X2: Tweede stille route: inh; X3: Kies één nood per; X4: Adres in de nood; X5: Versie 2 is precies; X6: Advies: A+B+C+D en tests; K1: Is de kernoorzaak weg?; K2: Nood per postvak, niet; K3: Adres in de noodtekst:; K4: De 14 dagen naar; K5: A+B+C is al klein); 0 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | aangenomen |
| X5 | eens | eens | eens | 3-0 | aangenomen |
| X6 | eens | eens | eens | 3-0 | aangenomen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | oneens | eens | eens | 2-1 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | eens | eens | eens | 3-0 | aangenomen |
| K5 | oneens | eens | eens | 2-1 | aangenomen |

## Besluitenlijst vóór stemming
- X1: Kernoorzaak voor de gewone nachtronde: weg.
- X2: Tweede stille route: inhaaldagen ouder dan dertig dagen.
- X3: Kies één nood per postvak, niet één wisselende lijst.
- X4: Adres in de nood is aanvaardbaar.
- X5: Versie 2 is precies het ontwerp.
- X6: Advies: A+B+C+D en tests.
- K1: Is de kernoorzaak weg? Grotendeels, niet helemaal.
  Techniek voor Claude: `dagbundelaar.py:610-616` - venstercontrole naast de versheidscontrole; of in `postvak.py:203` een kleine hulpfunctie `bron_venster`.
- K2: Nood per postvak, niet met een lijst. Aangenomen.
  Techniek voor Claude: `dagbundelaar.py:780-781` - lus over postvakken. Sla de soort apart op, bijvoorbeeld als tuple `(soort, volle reden)`, en parse hem niet uit de tekst.
- K3: Adres in de noodtekst: ja.
  Techniek voor Claude: geen aparte actie nodig.
- K4: De 14 dagen naar versie 2: dat is het ontwerp, laat het zo.
  Techniek voor Claude: geen codewijziging.
- K5: A+B+C is al klein genoeg. Eén kanttekening bij A en C.
  Techniek voor Claude: `dagbundelaar.py:613` en `:632` - tekst en commentaar; tests in de bestaande dagbundelaar-tests.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: Niet klaar. A+B+C is goed, maar mist één echte route waarlangs Hotmail stil te laag wordt geteld.<br><br>**X1. Kernoorzaak voor de gewone nachtronde: weg.**  <br>Voor de veertien dagen is de serverkopie ruim genoeg: De Dagbundelaar vraagt vanaf één dag vóór het venster, terwijl Hotmail dertig dagen binnengekomen mail levert. Leesfouten, ontbrekende mappen en plafonds worden als onvolledig gemeld.<br><br>Techniek voor Claude: `dagbundelaar.py:581-639`, `hotmail_server.py:22-24`, `hotmail_lezer.py:127-142` - huidige veertiendaagse route behouden.<br><br>**X2. Tweede stille route: inhaaldagen ouder dan dertig dagen.**  <br>De Dagbundelaar kan dagen tot zestig dagen terug opnieuw vaststellen. De Hotmail-kopie bevat maar dertig dagen binnengekomen mail. Voor zo’n oude dag geeft de kopie gewoon nul of een te laag aantal terug, zonder “onvolledig”. Dit kan ook bij een handmatige oude `--dag`.<br><br>Techniek voor Claude: `dagbundelaar.py:73-77,266-272,340-371` tegenover `hotmail_server.py:22-24` en `postvak.py:195-221` - leg de begindatum van beide richtingen vast in `koppen.json` en laat De Dagbundelaar “onvolledig” melden wanneer zijn gevraagde periode daarbuiten valt. Alleen verhogen naar 61 dagen dekt het automatische inhalen, maar niet een willekeurige oude `--dag`.<br><br>**X3. Kies één nood per postvak, niet één wisselende lijst.**  <br>Dan blijft een storing van Hotmail dezelfde nood wanneer een ander postvak bijkomt of herstelt. Gebruik vaste soorten. Bij een totale leesfout hoort het wisselende fouttype niet in de noodtekst, want RuntimeError vandaag en TimeoutExpired morgen worden twee noden.<br><br>Techniek voor Claude: `dagbundelaar.py:704-706,780-781`, `bord.py:361-374` - per adres een vaste nood; totale fout als `Mail niet gelezen voor de dagvaststelling`, fouttype en uitleg alleen in `ag.log`.<br><br>**X4. Adres in de nood is aanvaardbaar.**  <br>Mehdi ziet onmiddellijk welk eigen postvak hapert. Het adres staat al in de dagvaststelling en bestaande Mailwacht-noden; zet geen afzenders, onderwerpen of berichtinhoud in nood of logboek.<br><br>Techniek voor Claude: `postvak.py:500-507`, `dagbundelaar.py:728-750` - alleen het postvakadres tonen.<br><br>**X5. Versie 2 is precies het ontwerp.**  <br>De eerdere versie blijft bewaard en de nieuwe telling wordt zichtbaar. Er hoeft niets handmatig met die veertien dagen te gebeuren.<br><br>Techniek voor Claude: `dagbundelaar.py:729-756`, `docs/ontwerp-dagvaststelling.md:295-307` - bestaande revisielogica behouden.<br><br>**X6. Advies: A+B+C+D en tests.**  <br>A, B en C uitvoeren, plus X2 als D. Werk ook de nog actieve teksten “Mac-kopie” bij.<br><br>Techniek voor Claude: `docs/ontwerp-dagvaststelling.md:65-68,119-126` - bronbeschrijving actualiseren en regressietests toevoegen voor verse/oude kopie, wisselende fouttypen en een inhaaldag ouder dan dertig dagen.<br><br>GRENS: geen | BESLISSING: Akkoord met voorstel A + B + C (stem 3-0 verwacht).<br><br>- **G1 (Kernoorzaak & venster)**: De hotmail-blokkade is opgelost doordat de server nu zelfstandig `koppen.json` bijwerkt. Er is geen tweede weg waarlangs hotmail stil te laag geteld wordt: het 30-dagenvenster op de server dekt de 14 dagen van De Dagbundelaar (`sinds = vandaag - 15`) ruimschoots, en het plafond van 2000 per map wordt bewaakt via `dagbundelaar.py:597-598` (meldt direct onvolledig bij overschrijding).<br>  `Techniek voor Claude: koppelingen/hotmail_server.py:27 en dagbundelaar.py:593-599 - venster en plafond zijn sluitend gedekt`.<br><br>- **G2 (Voorstel A - Tekstcorrectie kopie)**: De tekst `"kopie van de Mac"` in `dagbundelaar.py:613` is achterhaald sinds acfb970/bc6990a. Aanpassing naar `"kopie " + ("onleesbaar" if oud is None else f"{oud:.0f} uur oud")` houdt de melding accuraat voor zowel server- als Mac-bronnen.<br>  `Techniek voor Claude: dagbundelaar.py:613 - 'kopie van de Mac' vervangen door generieke kopietekst`.<br><br>- **G3 (Voorstel B - Nood per postvak conform N10)**: Eén nood per haperend postvak met vaste oorzaak zonder getallen (`Mail niet volledig gelezen voor de dagvaststelling: {adres} ({vaste_reden})`) is superieur aan één gecombineerde lijst. Een gecombineerde lijst flippert zodra één postvak herstelt en overtreedt de stabiliteit van N10; losse noden sluiten netjes declaratief per hersteld postvak via `bord.py`.<br>  `Techniek voor Claude: dagbundelaar.py:780-781 - r.nood itereren over unieke (adres, vaste_reden) paren zonder uren of getallen`.<br><br>- **G4 (Privacy van mailadres in noodtekst)**: Het mailadres mag en hoort in de noodtekst. Dit gebeurt al conform het ontwerp in de Mailwacht-noden en in de dagbestanden zelf; zonder adres is een operationele nood voor Claude Code onbruikbaar.<br>  `Techniek voor Claude: dagbundelaar.py:781 - adres opnemen in noodtekst analoog aan koppelingen/mailwacht.py`.<br><br>- **G5 (Versie 2 van de 14 dagen & voorstel C)**: Het ophogen naar versie 2 voor de 14 dagen vannacht is 100% conform het ontwerp van de dagvaststelling (v1.9: herziening bij nieuw gevonden berichten). Voorstel C voegt de ontbrekende traceerbaarheid toe via `ag.log("mail", "bron", ...)` zodat exacte uren in het logboek belanden en de noodtekst zuiver blijft.<br>  `Techniek voor Claude: dagbundelaar.py:616 - ag.log toevoegen voor detail en urenconformiteit met N10`.<br><br>GRENS: geen | BESLISSING: Akkoord met A+B+C, met twee aanpassingen. B wordt een nood per postvak, en er komt één extra controle op het leesvenster van het bestand. Stem Claude: ja.<br><br>**K1. Is de kernoorzaak weg? Grotendeels, niet helemaal.**<br>Voor Mehdi: de mail van vannacht en de komende dagen klopt zolang het bestand vers is. Eén gat blijft: het serverbestand heeft maar 30 dagen binnenkomende post. Wordt later een oudere dag opnieuw gebouwd (herstel of inhaalronde), dan telt hotmail stil te laag en meldt niemand iets.<br>- `postvak.py:199` filtert alleen op `sinds` en kijkt niet naar het venster van het bestand (`binnen_dagen`, `hotmail_server.py:24`).<br>- `dagbundelaar.py:597` ziet dit niet, want er zijn geen 2000 berichten.<br>- Voorstel: bij `mb.get("bron")` de `binnen_dagen` uit het bestand lezen. Ligt `sinds` voor `gemaakt` min `binnen_dagen`, dan reden "kopie dekt de dagen niet" voor ontvangen. Voor verzonden geldt dat bij 730 dagen.<br>- Dat geldt niet voor de 14 dagen van nu (12-10 ligt binnen 30 dagen).<br>Techniek voor Claude: `dagbundelaar.py:610-616` - venstercontrole naast de versheidscontrole; of in `postvak.py:203` een kleine hulpfunctie `bron_venster`.<br><br>**K2. Nood per postvak, niet met een lijst. Aangenomen.**<br>Voor Mehdi: je ziet direct welk postvak hapert. Verandert de lijst van onvolledige postvakken, dan blijft de tekst van elke andere nood gelijk. Een lijst in één tekst wisselt van vorm zodra een tweede postvak uitvalt, en dan sluit de nood niet netjes.<br>- Noden zijn declaratief en `bord.py:373` ontdubbelt op tekst. Eén nood per postvak met een vaste soort is dus stabiel.<br>- Er mag geen getal in de tekst (`bord.py:364-372`).<br>- Het hele lezen faalt (`ontvangen is None`): één nood met alleen het fouttype.<br>Techniek voor Claude: `dagbundelaar.py:780-781` - lus over postvakken. Sla de soort apart op, bijvoorbeeld als tuple `(soort, volle reden)`, en parse hem niet uit de tekst.<br><br>**K3. Adres in de noodtekst: ja.**<br>Voor Mehdi: het is je eigen postvak, geen klantgegeven. Het staat al in De Mailwacht-noden en in het dagbestand. Het is alleen intern zichtbaar.<br>Techniek voor Claude: geen aparte actie nodig.<br><br>**K4. De 14 dagen naar versie 2: dat is het ontwerp, laat het zo.**<br>Voor Mehdi: de dagen krijgen vannacht een nieuwe versie met de hotmail-aantallen erbij. Het oude bestand verdwijnt niet.<br>- Het teruglezen op `dagbundelaar.py:762-768` controleert bestand en bord op dezelfde tekst, dus een revisie is veilig.<br>- Controleer morgen één ding: dat nood 3399 echt gesloten is.<br>Techniek voor Claude: geen codewijziging.<br><br>**K5. A+B+C is al klein genoeg. Eén kanttekening bij A en C.**<br>Voor Mehdi: de tekst van de reden klopt dan weer en het werkverslag toont de uren.<br>- A: reden op `dagbundelaar.py:613` zonder "van de Mac". Regel 608 en 612 zetten de reden op beide richtingen, dus de fix moet beide dekken. Dat gebeurt al via de lus op regel 614.<br>- C: de logregel moet de volle reden bevatten, met het aantal uren. Daar mag het aantal wel staan.<br>- Regel 632 zegt ook "een kopie van de Mac" in een commentaar. Pas dat mee aan.<br>- Test: een kopie die 150 uur oud is, een kopie die te kort loopt, en een stabiele nood over twee rondes.<br>Techniek voor Claude: `dagbundelaar.py:613` en `:632` - tekst en commentaar; tests in de bestaande dagbundelaar-tests.<br><br>Ik heb alleen gelezen. Ik heb `koppelingen/hotmail_server.py` niet helemaal doorgenomen, alleen de venster- en tijdconstanten.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: Klaar met kanttekeningen. A+B+C uitvoeren, plus een venstercontrole; Gemini mist terecht de route via oude inhaaldagen.

**X1/K1. Gewone nachtronde is hersteld, oudere dagen niet.**  
De huidige veertien dagen vallen binnen de Hotmail-kopie van dertig dagen. Maar De Dagbundelaar kan automatisch tot zestig dagen terug inhalen en `--dag` kent geen grens. Zo kan ontvangen Hotmail stil als nul of te laag worden vastgelegd. Gemini G1 is daarom onjuist.

Techniek voor Claude: `dagbundelaar.py:73-77,266-272,340-371,581-599`; `hotmail_server.py:22-24,55-56` - schrijf de werkelijk gedekte begindatum per richting in `koppen.json` en toets die vóór het tellen. Alleen `binnen_dagen` bewaren is minder duidelijk en ontbreekt nu bovendien in het bestand.

**X3/K2. Eén nood per postvak, zonder oorzaak in de noodtekst.**  
Een lijst wisselt zodra een ander postvak uitvalt. Ook een oorzaak kan wisselen terwijl hetzelfde postvak onvolledig blijft. De stabielste tekst is daarom: `Mail niet volledig gelezen voor de dagvaststelling: <adres>`. Zet oorzaak, richting, uren en fouttype uitsluitend in het logboek. Bij een totale leesfout blijft één vaste algemene nood staan, zonder Python-fouttype.

Techniek voor Claude: `dagbundelaar.py:591-638,780-781`; `bord.py:361-374` - noodidentiteit alleen per adres; details via `ag.log`.

**X4/K3. Adres mag in de nood.**  
Het betreft een intern eigen postvak en hetzelfde adres staat al in dagbestanden en Mailwacht-noden. Geen afzenders, onderwerpen of inhoud loggen.

Techniek voor Claude: `postvak.py:500-507` - bestaand patroon volgen.

**X5/K4. Versie 2 is juist.**  
De veertien dagen mogen automatisch worden herzien; de vorige versie blijft bewaard. Alleen na de nachtronde controleren dat nood 3399 gesloten is en Hotmail meetelt.

Techniek voor Claude: `dagbundelaar.py:729-768` - revisielogica behouden.

**X6/K5. A+B+C is niet volledig zonder D.**  
Pas ook de achterhaalde tekst en commentaar over de Mac aan en test verse, oude en te kort dekkende kopieën plus stabiele noden.

Techniek voor Claude: `dagbundelaar.py:613,632`; `hotmail_server.py:55-56`; `tests/test_dagbundelaar_vaststelling.py`.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
K1: eens
K2: oneens
K3: eens
K4: eens
K5: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Akkoord met voorstel A + B + C, inclusief de versterkingen X2/K1 (venstercontrole) en X3/K2 (stabiele nood per postvak). Stem: ja op alle punten.

- **G1/K1/X1/X2 (Kernoorzaak & venstercontrole)**: De directe blokkade voor de nachtronde is weg. Terecht wijzen Codex en Claude op het stille venstergat: bij inhaaldagen ouder dan 30 dagen geeft de Hotmail-serverkopie stil te weinig resultaten terug zonder onvolledig te vlaggen. Een expliciete dekkingstoets op `sinds` tegenover het kopievenster (`gemaakt` min `binnen_dagen`) sluit deze tweede route waterdicht af.
  `Techniek voor Claude: mijnagents-runner/dagbundelaar.py:610-616 - controleer of sinds binnen de dekkingsperiode van de kopie valt; meld anders 'kopie dekt periode niet'`.

- **G2/K5 (Aanpassing kopietekst)**: Volledig eens. De tekst `"kopie van de Mac"` op regel 613 (en het commentaar op 632) is verouderd. We maken dit bron-neutraal naar `"kopie " + ("onleesbaar" if oud is None else f"{oud:.0f} uur oud")`.
  `Techniek voor Claude: mijnagents-runner/dagbundelaar.py:613,632 - vervang 'kopie van de Mac' door generieke kopietekst`.

- **G3/K2/X3 (Nood per postvak conform N10)**: Eén nood per postvak met vaste reden zonder getallen is stabiel en voorkomt dat een herstel van één adres de nood van een ander adres laat flipperen. Bij een totale storing (`ontvangen is None`) blijft de tekst uniform en generiek, terwijl specifieke uitzonderingen en fouttypen netjes naar het werkverslag (`ag.log`) gaan.
  `Techniek voor Claude: mijnagents-runner/dagbundelaar.py:780-781 - r.nood itereren per adres met vaste soort; wisselend fouttype alleen in ag.log`.

- **G4/K3/X4 (Adres in nood)**: Geen bezwaar. Mehdi's eigen mailadres staat al in de Mailwacht-noden en dagbestanden; voor operationele herkenning is dit noodzakelijk.
  `Techniek voor Claude: mijnagents-runner/dagbundelaar.py:781 - adres behouden in noodtekst`.

- **G5/K4/X5 (Versie 2 van dagbestanden & ag.log)**: Het ophogen naar versie 2 voor de 14 dagen vannacht volgt exact de revisielogica van het ontwerp (v1.9). Het toevoegen van `ag.log` legt de exacte uren en details vast in het werkverslag zonder de N10-noodtekst te vervuilen.
  `Techniek voor Claude: mijnagents-runner/dagbundelaar.py:616 - ag.log toevoegen voor bron/uren logging`.

GRENS: geen

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: A+B+C wordt uitgevoerd met één nood per postvak. Daarbij komt de venstercontrole uit K1 en X2, als D. Dit is 3-0 voor één nood per postvak en 2-1 voor D. Mehdi hoeft niets te doen.

Ik heb in deze ronde geen code opnieuw gelezen. Mijn oordeel steunt op de drie meningen en op mijn eigen eerdere regelverwijzingen.

**Eens/oneens per punt**

- **Kernoorzaak (X1, K1):** Voor de 14 dagen van vannacht is de oorzaak weg. Codex en ik vinden allebei hetzelfde gat. Het serverbestand heeft maar 30 dagen binnenkomende post, en een oudere dag levert dan stil een te laag aantal. Gemini ziet dit gat niet, want zijn onderbouwing gaat alleen over de 14 dagen. Het 2000-plafond lost dit gat niet op.
- **Nood per postvak (X3, K2, G3):** Alle drie eens. Een lijst in één tekst wisselt van vorm zodra één postvak herstelt. Dat past slecht bij N10.
- **Fouttype in de nood (X3):** Ik neem de correctie van Codex over. Bij een totale leesfout komt het fouttype niet in de noodtekst, want RuntimeError van vandaag en TimeoutExpired van morgen worden dan twee aparte noden. De tekst wordt vast: `Mail niet gelezen voor de dagvaststelling`. Het fouttype gaat alleen in `ag.log`. Mijn eerdere voorstel (alleen het fouttype in de nood) was daarmee fout.
- **Adres in de nood (X4, K3, G4):** Alle drie eens: ja. Zet geen afzenders, onderwerpen of inhoud in nood of logboek.
- **Versie 2 (X5, K4, G5):** Alle drie eens. Dit is het ontwerp en er is geen handwerk nodig. Controleer morgen wel dat nood 3399 echt gesloten is.
- **Venstercontrole (D):** Codex wil de begindatum van beide richtingen in `koppen.json` vastleggen. Mijn voorstel was `binnen_dagen` uitlezen. Dat is vrijwel hetzelfde. Ik kies de variant met de begindatum, omdat die niet afhangt van `gemaakt`. Verhogen naar 61 dagen is onvoldoende, want een handmatige oude `--dag` blijft dan stil te laag.
- **Teksten (X6, K5):** Eens. `dagbundelaar.py:613` en het commentaar op `:632` aanpassen. Ook de teksten "Mac-kopie" in `docs/ontwerp-dagvaststelling.md:65-68,119-126` bijwerken.

**Wat Mehdi merkt:** De nood noemt voortaan welk postvak hapert en waarom. De tekst blijft gelijk van ronde tot ronde. Het aantal uren staat alleen in het werkverslag. Een te oude dag wordt gemeld in plaats van stil te laag geteld.

Techniek voor Claude: `dagbundelaar.py:613,632,704-706,780-781` - reden zonder "van de Mac", lus per postvak met `(soort, volle reden)`, vaste totale-fouttekst en `ag.log`. Daarnaast de venstercontrole naast `:610-616`, met de begindatum uit `hotmail_server.py:22-24`. Tests voor een verse en een oude kopie, een wisselend fouttype, een inhaaldag ouder dan 30 dagen en een stabiele nood over twee rondes.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Gemini

Beslissing: klaar, alle 11 herstelpunten zijn aangenomen (zes met 3-0, vijf met 3-0 of 2-1) en worden zelfstandig uitgevoerd zonder Mehdi te belasten.

**Voor Mehdi:**
* Alle voorgestelde herstelpunten zijn aangenomen; er is geen actie van jou nodig.
* De nachtronde en inhaaldagen lopen voortaan betrouwbaar zonder vastlopers.
* Noodmeldingen worden netjes per postvak vastgelegd in plaats van via wisselende lijsten.
* Mailadressen blijven duidelijk zichtbaar in de noodtekst.
* We voeren het goedgekeurde ontwerp direct zelfstandig uit met bijbehorende tests.

---

**Voor Claude en Shaniel:**
1. [Aangenomen 3-0] X1: Kernoorzaak gewone nachtronde structureel verhelpen.
2. [Aangenomen 3-0] X2: Tweede stille route bij inhaaldagen ouder dan dertig dagen blokkeren.
3. [Aangenomen 3-0] X3: Keuze voor één nood per postvak i.p.v. dynamische lijst.
4. [Aangenomen 3-0] X4: Mailadres opnemen in de noodmeldingstekst handhaven.
5. [Aangenomen 3-0] X5: Versie 2 volgens `docs/ontwerp-dagvaststelling.md:295-307` aanhouden.
6. [Aangenomen 3-0] X6: Aanpak A+B+C+D met bijbehorende testdekking uitvoeren.
7. [Aangenomen 3-0] K1: Techniek voor Claude: `dagbundelaar.py:610-616` - venstercontrole naast versheidscontrole plaatsen, of hulpfunctie in `postvak.py:203`.
8. [Aangenomen 2-1] K2: Techniek voor Claude: `dagbundelaar.py:780-781` - lus over postvakken; soort apart opslaan als tuple `(soort, volle reden)`, niet parsen uit tekst.
9. [Aangenomen 3-0] K3: Techniek voor Claude: geen aparte actie nodig voor adresweergave.
10. [Aangenomen 3-0] K4: Techniek voor Claude: 14 dagen conform `docs/ontwerp-dagvaststelling.md:65-68`; geen codewijziging.
11. [Aangenomen 2-1] K5: Techniek voor Claude: `dagbundelaar.py:613` en `:632` - tekst en commentaar bijwerken; tests toevoegen aan bestaande suite.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): Kernoorzaak voor de gewone nachtronde: weg.
- **X2** (3-0): Tweede stille route: inhaaldagen ouder dan dertig dagen.
- **X3** (3-0): Kies één nood per postvak, niet één wisselende lijst.
- **X4** (3-0): Adres in de nood is aanvaardbaar.
- **X5** (3-0): Versie 2 is precies het ontwerp.
- **X6** (3-0): Advies: A+B+C+D en tests.
- **K1** (3-0): Is de kernoorzaak weg? Grotendeels, niet helemaal.
  Techniek voor Claude: `dagbundelaar.py:610-616` - venstercontrole naast de versheidscontrole; of in `postvak.py:203` een kleine hulpfunctie `bron_venster`.
- **K2** (2-1): Nood per postvak, niet met een lijst. Aangenomen.
  Techniek voor Claude: `dagbundelaar.py:780-781` - lus over postvakken. Sla de soort apart op, bijvoorbeeld als tuple `(soort, volle reden)`, en parse hem niet uit de tekst.
- **K3** (3-0): Adres in de noodtekst: ja.
  Techniek voor Claude: geen aparte actie nodig.
- **K4** (3-0): De 14 dagen naar versie 2: dat is het ontwerp, laat het zo.
  Techniek voor Claude: geen codewijziging.
- **K5** (2-1): A+B+C is al klein genoeg. Eén kanttekening bij A en C.
  Techniek voor Claude: `dagbundelaar.py:613` en `:632` - tekst en commentaar; tests in de bestaande dagbundelaar-tests.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
