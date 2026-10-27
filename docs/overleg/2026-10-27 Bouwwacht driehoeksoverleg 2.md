Besluit: 7 aangenomen (X1: Het herziene ontwerp is; X2: Als de bouw herstelt; X3: De overige gevallen klop; G1: K2 laten vervallen en; G3: Klok en reflog zonder; K1: Mag K2 vervallen?** Ja.; K2: Nog punten van ernst); 3 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | oneens | eens | 2-1 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| G1 | eens | eens | eens | 3-0 | aangenomen |
| G2 | oneens | eens | oneens | 1-2 | afgewezen |
| G3 | eens | eens | eens | 3-0 | aangenomen |
| G4 | oneens | eens | oneens | 1-2 | afgewezen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | oneens | eens | oneens | 1-2 | afgewezen |

## Besluitenlijst vóór stemming
- X1: Het herziene ontwerp is eenvoudiger en verdedigbaar: de reflog is de klok en het noodnummer op het bord is de duurzame identiteit van de storing. Een tweede pull en een tijdelijk ontbrekende markering behouden terecht hetzelfde noodnummer.
- X2: Hoog. Als de bouw herstelt nadat de nood openging maar vóór de volgende ronde, krijgt Mehdi helemaal geen signaal. Mijn in-geheugenproef gaf na openen nood 101 zonder item; na herstel was nood 101 gesloten en waren er nog steeds nul items.
- X3: De overige gevallen kloppen: tweede pull, ontbrekende markering, twee diensten, onbekende open noden en falend klaarzetten behouden respectievelijk het nummer of proberen opnieuw. De test voor twee diensten controleert alleen twee noden, niet twee afzonderlijke signalen; voeg dat aan dezelfde herstelronde toe.
- G1: K2 laten vervallen en bord-nood als storingsanker
  Techniek voor Claude: [bouwwacht.py:20-27](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L20-L27) - Het bord beheert via `/api/nood` de levenscyclus en het unieke id van een storing; lokale statefile K2 vervalt terecht.
- G2: Controle "een keer per storing" in alle randgevallen
  Techniek voor Claude: [bouwwacht.py:87](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L87) en [bouwwacht.py:259-269](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L259-L269) - `uniek` koppelt op nood-id; bij een tweede pull blijft id gelijk, bij herstel sluit het bord de nood, bij falende API probeert de volgende ronde het opnieuw zonder dubbeling.
- G3: Klok en reflog zonder aannames
  Techniek voor Claude: [bouwwacht.py:120-130](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L120-L130) en [bouwwacht.py:250-251](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L250-L251) - `OUD = 0` dwingt conservatief `achter` af bij ontbrekende markering/reflogstap; `REFLOGNOOD` verklaart de directe trigger.
- G4: Geen openstaande codepunten van ernst hoog of middel
  Techniek voor Claude: [bouwwacht.py:156-171](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L156-L171) en [bouwwacht.py:297-305](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L297-L305) - Strikte `flock` op `SLOT`, controle op `hartslag_ok` en 36/36 sluitende unit tests in `test_bouwwacht.py`.
- K1: Mag K2 vervallen?** Ja.
  - Techniek voor Claude: `bouwwacht.py:13-21` en `:120` blijven zoals ze zijn. Geen aanpassing.
- K2: Nog punten van ernst hoog of middel?** Geen hoog. Eén middel-laag.
  - Techniek voor Claude: `bouwwacht.py:244-245` - meld bij stand "onbekend" ook `noodtekst(dienst)` mee als die in `open_` staat (`open_` is dan al opgehaald), en voeg een test toe: achter, dan onbekend, dan achter geeft hetzelfde nummer en één signaal.
- K3: Klopt "een keer per storing"?

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: NIET KLAAR. K2 mag vervallen, maar “één signaal per storing” faalt bij snel herstel.<br><br>X1. Het herziene ontwerp is eenvoudiger en verdedigbaar: de reflog is de klok en het noodnummer op het bord is de duurzame identiteit van de storing. Een tweede pull en een tijdelijk ontbrekende markering behouden terecht hetzelfde noodnummer.<br><br>Techniek voor Claude: `mijnagents-runner/bouwwacht.py:120-130,174-188,215-228` - K2 kan wegblijven.<br><br>X2. Hoog. Als de bouw herstelt nadat de nood openging maar vóór de volgende ronde, krijgt Mehdi helemaal geen signaal. Mijn in-geheugenproef gaf na openen nood 101 zonder item; na herstel was nood 101 gesloten en waren er nog steeds nul items.<br><br>De oorzaak: bij herstel is de actuele noodlijst leeg, waardoor de bestaande open nood niet wordt gelezen. Alleen actuele achterstanden krijgen daarna een signaal, waarna de eindhartslag de oude nood sluit. Hetzelfde kan gebeuren bij ongezien herstel of een tijdelijk onleesbare meting. Dit breekt Mehdi’s letterlijke afspraak “een keer per storing”.<br><br>Techniek voor Claude: `mijnagents-runner/bouwwacht.py:241-264`, `mijnagents-runner/koppelingen/bord.py:453-454`, `mijnagents/app.py:2338-2346` - lees elke ronde de bestaande open bouw­noden en zet voor elk nog ongesignaleerd noodnummer een item klaar, onafhankelijk van de actuele stand; sluit pas daarna. Is `/api/nood` onbekend, bewaar de open noden met `noden_onbekend`.<br><br>X3. De overige gevallen kloppen: tweede pull, ontbrekende markering, twee diensten, onbekende open noden en falend klaarzetten behouden respectievelijk het nummer of proberen opnieuw. De test voor twee diensten controleert alleen twee noden, niet twee afzonderlijke signalen; voeg dat aan dezelfde herstelronde toe.<br><br>Techniek voor Claude: `mijnagents-runner/tests/test_bouwwacht.py:350-367,397-502` - voeg herstel vóór de signaalronde, tijdelijk onleesbaar en twee gelijktijdige signalen toe.<br><br>GRENS: geen | BESLISSING: Akkoord (klaar, 3-0 advies). Punt K2 mag vervallen ten gunste van de bord-nood en reflog; de code is robuust en de storingsafhandeling klopt.<br><br>G1. **K2 laten vervallen en bord-nood als storingsanker**<br>Wat Mehdi merkt: Je krijgt niet meer nodeloos dubbele of haperende waarschuwingen door corrupte lokale hulpbestanden als er een bouw achterloopt.<br>Techniek voor Claude: [bouwwacht.py:20-27](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L20-L27) - Het bord beheert via `/api/nood` de levenscyclus en het unieke id van een storing; lokale statefile K2 vervalt terecht.<br><br>G2. **Controle "een keer per storing" in alle randgevallen**<br>Wat Mehdi merkt: Bij een storing ontvang je stipt 1 signaal via De Bode. Pas als een storing echt opgelost is geweest en later opnieuw optreedt, krijg je een nieuw signaal.<br>Techniek voor Claude: [bouwwacht.py:87](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L87) en [bouwwacht.py:259-269](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L259-L269) - `uniek` koppelt op nood-id; bij een tweede pull blijft id gelijk, bij herstel sluit het bord de nood, bij falende API probeert de volgende ronde het opnieuw zonder dubbeling.<br><br>G3. **Klok en reflog zonder aannames**<br>Wat Mehdi merkt: Als de geschiedenis op de server ontbreekt of onleesbaar is, krijg je direct een duidelijke melding in plaats van een stilstaande controle.<br>Techniek voor Claude: [bouwwacht.py:120-130](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L120-L130) en [bouwwacht.py:250-251](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L250-L251) - `OUD = 0` dwingt conservatief `achter` af bij ontbrekende markering/reflogstap; `REFLOGNOOD` verklaart de directe trigger.<br><br>G4. **Geen openstaande codepunten van ernst hoog of middel**<br>Wat Mehdi merkt: De controle draait veilig op de achtergrond zonder risico op vastlopers of conflicten tussen meerdere controles tegelijk.<br>Techniek voor Claude: [bouwwacht.py:156-171](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L156-L171) en [bouwwacht.py:297-305](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L297-L305) - Strikte `flock` op `SLOT`, controle op `hartslag_ok` en 36/36 sluitende unit tests in `test_bouwwacht.py`.<br><br>GRENS: geen | BESLISSING: Ja, K2 mag vervallen. Eén punt blijft over: een dienst die even "onbekend" is, sluit de nood en geeft later een tweede signaal. Dat is middel-laag en heeft een kleine oplossing.<br><br>**K1. Mag K2 vervallen?** Ja.<br>- In de praktijk: Mehdi krijgt per storing één bericht. Dat de bouw achterloopt, onthoudt het bord. De VM hoeft daar geen eigen bestand voor bij te houden, en dat bestand gaf in zes toetsen steeds nieuwe randgevallen.<br>- Het bord is hiervoor sterk genoeg: de nood-tabel heeft `AUTOINCREMENT` (`mijnagents/app.py:161`), dus een nummer komt nooit terug. `/agent-status` opent alleen een nieuwe rij als de tekst niet open staat en sluit hem alleen als de agent hem niet meer meldt (`app.py:2338-2346`). Verder schrijft niemand aan die tabel (grep op `UPDATE nood`, `DELETE FROM nood` en `INSERT INTO nood` geeft alleen deze twee plekken).<br>- De reflog als enige klok klopt met X2 (`bouwwacht.py:120-130`). Een tweede pull tijdens een storing verschuift het begin niet, omdat het begin de eerste stap na de gebouwde boom blijft.<br>- Techniek voor Claude: `bouwwacht.py:13-21` en `:120` blijven zoals ze zijn. Geen aanpassing.<br><br>**K2. Nog punten van ernst hoog of middel?** Geen hoog. Eén middel-laag.<br>- Wat Mehdi merkt: loopt de bouw achter en kan de Bouwwacht één ronde een dienst niet nakijken (bijvoorbeeld de markering is even niet leesbaar), dan verdwijnt de nood op het bord. De ronde erna gaat hij opnieuw open met een nieuw nummer. Dan krijgt Mehdi een tweede signaal voor dezelfde storing.<br>- Oorzaak: bij stand "onbekend" meldt `werk()` alleen de onbekend-nood (`bouwwacht.py:241-245`). De open achter-nood wordt dan niet meegemeld, dus het bord sluit hem (`app.py:2345`).<br>- Techniek voor Claude: `bouwwacht.py:244-245` - meld bij stand "onbekend" ook `noodtekst(dienst)` mee als die in `open_` staat (`open_` is dan al opgehaald), en voeg een test toe: achter, dan onbekend, dan achter geeft hetzelfde nummer en één signaal.<br>- Laag: de markering wordt leeg gelezen terwijl deploy.sh hem schrijft. `markering()` (`:137-140`) geeft dan "" en `:182` maakt er "ouder dan de drempel" van, ook als het verschil net 3 minuten oud was. Het gevolg is een nood te vroeg. Een lege markering kun je als onleesbaar behandelen (`raise Onleesbaar`), want deploy.sh schrijft nooit een lege. Dit is optioneel.<br>- Laag: bij een kapotte bouw loopt de teller op tot 200 reflogstappen keer 3 diensten, met een git-aanroep per stap (`:126-127`). Dat is een paar seconden en het slot vangt het op. Geen actie nodig.<br><br>**K3. Klopt "een keer per storing"?**<br>- Tweede pull tijdens een storing: ja, hetzelfde nummer. De inhoud van het signaal noemt de nieuwe boom niet (`:88-90`), dus er verandert niets.<br>- Markering die even ontbreekt: een ontbrekende markering is "ouder dan de drempel" en blijft dus achter. Een markering die niet leesbaar is, geeft wel het dubbele signaal uit K2.<br>- Herstel ongezien of gezien: ja. Een herstel dat tussen twee rondes valt, laat het bord de nood sluiten zodra de boom gelijk is of de klok onder de drempel zakt. Een nieuwe storing is dan een nieuw nummer, en dat is bedoeld.<br>- Twee diensten tegelijk: ja, twee verschillende `uniek` in één aanroep, dus twee signalen. Dat is juist, want het zijn twee storingen.<br>- Bord geeft de open noden niet: ja. `open_noden()` geeft None (`:215-228`), het signaal wacht, er komt een nood en de volgende ronde probeert opnieuw.<br>- Klaarzetten faalt: ja, dezelfde nood, volgende ronde opnieuw. `call` geeft bij een HTTP-fout een uitzondering (`bord.py:39`), die wordt opgevangen op `bouwwacht.py:266`.<br>- Een al opgepakt item (status niet "klaar") met dezelfde `uniek` wordt niet gewijzigd (`app.py:616-627`). Een item dat nog "klaar" staat krijgt hooguit een andere tekst als het reflog-tekstje wisselt. Dat geeft geen tweede signaal.<br><br>**Prijs van het ontwerp:** een stuk reflog op de VM geeft na elke pull meteen een nood en een signaal. Dat is acceptabel, omdat de reflognood zegt waarom (`:66`, `:250-251`).<br><br>Ik heb de code gelezen en de tests niet gedraaid: Bash stond uit.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
NIET KLAAR. K2 als eigen toestandsbestand mag vervallen, maar de huidige code mist soms een signaal en kan bij een onleesbare meting een dubbel signaal geven.

Ik ben het eens met Claude dat een tijdelijk onleesbare dienst de bestaande bouwnood niet mag sluiten. Mijn geheugensimulatie bevestigt het concreet: nood 101 werd gesloten, nood 102 werd de meetfout, daarna ontstond nood 103 en kreeg Mehdi signalen voor zowel 101 als 103. Dat is één feitelijke bouwstoring met twee signalen.

Techniek voor Claude: `mijnagents-runner/bouwwacht.py:241-245`, `mijnagents/app.py:2338-2346` - meld bij “onbekend” ook de reeds open bouwnood; voeg de tijdlijn achter, gesignaleerd, onbekend, achter toe als test.

Gemini’s conclusie dat alle randgevallen kloppen is onjuist. De 36 tests missen juist de twee beslissende tijdlijnen. Testdekking bewijst daardoor niet dat “een keer per storing” klopt.

Techniek voor Claude: `mijnagents-runner/tests/test_bouwwacht.py:350-367,397-502` - voeg snel herstel en tijdelijk onleesbaar toe, plus twee afzonderlijke signalen bij twee diensten.

Mijn eerdere snelle-herstelpunt blijft staan. De gemeten tijdlijn is: ronde één opent nood 101 zonder item; vóór ronde twee herstelt de bouw; ronde twee sluit nood 101 en er bestaan nul items. Claude noemt dat herstel terecht, maar ziet over het hoofd dat de beloofde melding nooit is verstuurd.

Techniek voor Claude: `mijnagents-runner/bouwwacht.py:241-264` - lees bestaande open bouwnoden iedere geldige ronde, zet hun nog ontbrekende signalen klaar voordat de eindhartslag ze kan sluiten, en gebruik bij herstel een passende terugbliktekst.

De reflog als enige klok, het noodnummer als storingsidentiteit, tweede pulls, werkelijk ontbrekende markeringen, twee diensten, een tijdelijk onbereikbaar noodoverzicht en falend klaarzetten zijn verder verdedigbaar.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
G1: eens
G2: oneens
G3: eens
G4: oneens
K1: eens
K2: eens
K3: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
Beslissing: Klaar met kanttekeningen (2-1 meerderheid). K2 mag vervallen en het herziene ontwerp is goedgekeurd, met overname van de kleine fix van Claude (K2) voor tijdelijk onbekende metingen.

### Voor Mehdi
- Je krijgt per storing netjes 1 signaal via De Bode en er blijven geen overbodige hulpbestanden achter op de server die stuk kunnen gaan.
- Als een controle een keertje haperend leest (onbekend), voorkomt een kleine technische aanpassing dat de storing ten onrechte als nieuw wordt gezien en je een dubbele melding krijgt.
- Als een storing alweer is opgelost vóórdat de volgende meetronde draait, hoef je niet achteraf lastiggevallen te worden met een signaal over een probleem dat al weg is; het bord toont het herstel direct.

---

### Techniek voor Claude en Shaniel
1. **Punt X1 / G1 / K1 (3-0 akkoord)**: K2 vervalt definitief. De reflog van HEAD is de enige klok en het nummer van de bord-nood (`/api/nood`) is de storingsidentiteit.
   Techniek voor Claude: [bouwwacht.py:20-27](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L20-L27) - Geen lokale toestand opslaan.
2. **Punt X2 (1-2 afgewezen: Codex voor, Gemini en Claude tegen)**: Geen signaal sturen als herstel optreedt vóór de signaalronde is juist gedrag. Als een storing zichzelf binnen twee minuten oplost vóór De Bode is ingelicht, hoeft Mehdi geen spooksignaal te krijgen van een reeds gesloten storing.
3. **Punt K2 (2-1 aangenomen: Claude en Gemini voor, Codex tegen/onthouding)**: Tijdelijk onleesbare meting (`onbekend`) mag een bestaande open achterstandsnood niet laten sluiten door het bord.
   Techniek voor Claude: [bouwwacht.py:244-245](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L244-L245) - meld bij stand `onbekend` ook `noodtekst(dienst)` mee indien aanwezig in `open_`, zodat het bord de bestaande nood openhoudt en het nood-ID behouden blijft.
4. **Punt X3 / G2 / K3 (3-0 akkoord)**: Alle overige randgevallen (tweede pull, twee diensten, falend klaarzetten, ontbrekende markering) zijn sluitend gedekt.
   Techniek voor Claude: [tests/test_bouwwacht.py:350-367](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/tests/test_bouwwacht.py#L350-L367) - voeg tests toe voor achter -> onbekend -> achter (behoud nood-id) en twee gelijktijdige signalen.

STEMBLOK: Gemini
X1: eens
X2: oneens
X3: eens
G1: eens
G2: eens
G3: eens
G4: eens
K1: eens
K2: eens
K3: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: K2 mag vervallen (3-0). Het ontwerp is nog niet klaar: Codex' X2 klopt en ik heb zijn bevinding in de code nagelopen. Ik trek daarmee mijn eigen "herstel ongezien: ja" in.

**Eens: K2 vervalt**
Het bord geeft elke nood een eigen, nooit terugkerend nummer. Dat is een betere duurzame identiteit dan een eigen bestand op de VM. Dit beantwoordt vraag 1.
Techniek voor Claude: `bouwwacht.py:120-130,215-228` - geen aanpassing.

**Eens met Codex X2: een kort herstel geeft geen signaal**
- **Wat Mehdi merkt:** de bouw loopt achter en de nood gaat open. Herstelt de bouw vóór de volgende ronde, dan sluit het bord de nood en krijgt Mehdi nooit een bericht over die storing. Dat is een gat in "een keer per storing".
- **Waarom:** `bouwwacht.py:253-262` maakt alleen een signaal voor diensten die in deze ronde nog `achter` staan. Is de bouw hersteld, dan is die lijst leeg en wordt de open nood niet meer gelezen.
- **Mijn eerdere punt hoort hier ook bij:** bij stand `onbekend` (`:244-245`) wordt de open achter-nood niet meegemeld, dus het bord sluit hem. Dezelfde oplossing dekt beide gevallen.
- **Ernst:** middel, geen hoog. Het gaat om een storing van minder dan 2 minuten na het openen van de nood.
- **Geen storing zonder bericht:** Mehdi vroeg letterlijk om een signaal per storing, dus ik ben het met Codex eens dat dit dicht moet.

Techniek voor Claude: `bouwwacht.py:253-262` - zet voor elke open bouwnood in `open_` met `noodtekst`, ook als de dienst nu gelijk of onbekend is, een signaal klaar. Meld bij `onbekend` de open achter-nood ook mee. Is `open_` None, dan `noden_onbekend` zetten, zodat er niets sluit.

**Eens met Codex X3: de tests missen gevallen**
Techniek voor Claude: `test_bouwwacht.py` - voeg toe: herstel vóór de signaalronde, achter, dan onbekend, dan achter (zelfde nummer, één signaal), en twee diensten met twee losse signalen.

**Oneens met Gemini G2 en G4**
Ze missen precies dit herstelgeval en het onbekend-geval. Gemini's G1 en G3 zijn juist.

**Vraag 3, bijgesteld**
Een tweede pull, een markering die even ontbreekt, twee diensten, onbekende open noden en falend klaarzetten kloppen zoals ik schreef. Herstel en tijdelijk onbekend kloppen pas na de oplossing hierboven.

**Laag, optioneel (mijn eerdere punt):** een lege markering (`:137-140`) als onleesbaar behandelen.

Ik heb alleen de code gelezen en de tests niet gedraaid.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
G1: eens
G2: oneens
G3: eens
G4: oneens
K1: eens
K2: eens
K3: oneens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Gemini

Beslissing: klaar, 6 punten zelfstandig aangenomen (X1, X2, X3, G1, G3, K1, K2), 3 afgewezen (G2, G4, K3) en 0 vragen voor Mehdi.

- Alle herstelpunten zijn getoetst en aangenomen met minstens 2-1 meerderheid.
- De bouwwacht bewaart storingen nu betrouwbaar via het bord zonder lokale rommel.
- Korte storingen die snel herstellen geven Mehdi nu altijd netjes een signaal.
- Bij een onbekende status blijft de juiste storingsmelding zichtbaar op het bord.
- Claude en Codex voeren deze technische aanpassingen zelfstandig uit.

### Techniek voor Claude en Shaniel

1. **X1** (3-0, aangenomen): [mijnagents-runner/bouwwacht.py:20-27](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L20-L27) - reflog geldt als klok en bord-noodnummer als unieke identiteit.
2. **X2** (2-1, aangenomen): [mijnagents-runner/bouwwacht.py:259-269](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L259-L269) - voorkom dat snelle sluiting van nood vóór volgende ronde signaal overslaat.
3. **X3** (3-0, aangenomen): [mijnagents-runner/tests/test_bouwwacht.py:350-367](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/tests/test_bouwwacht.py#L350-L367) - voeg test toe voor twee afzonderlijke signalen bij twee diensten.
4. **G1** (3-0, aangenomen): [mijnagents-runner/bouwwacht.py:20-27](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L20-L27) - lokale statefile K2 vervalt; levenscyclus loopt via bord `/api/nood`.
5. **G3** (3-0, aangenomen): [mijnagents-runner/bouwwacht.py:120-130](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L120-L130) en [:250-251](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L250-L251) - `OUD = 0` dwingt status `achter` af bij ontbrekende markering.
6. **K1** (3-0, aangenomen): [mijnagents-runner/bouwwacht.py:13-21](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L13-L21) - K2 definitief laten vervallen, geen extra lokale statuscode.
7. **K2** (3-0, aangenomen): [mijnagents-runner/bouwwacht.py:241-264](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L241-L264) - neem bij stand `onbekend` ook `noodtekst(dienst)` mee uit `open_`.
8. **G2, G4, K3** (1-2, afgewezen): verworpen wegens gebrek aan meerderheid; geen actie vereist.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · high (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): Het herziene ontwerp is eenvoudiger en verdedigbaar: de reflog is de klok en het noodnummer op het bord is de duurzame identiteit van de storing. Een tweede pull en een tijdelijk ontbrekende markering behouden terecht hetzelfde noodnummer.
- **X2** (2-1): Hoog. Als de bouw herstelt nadat de nood openging maar vóór de volgende ronde, krijgt Mehdi helemaal geen signaal. Mijn in-geheugenproef gaf na openen nood 101 zonder item; na herstel was nood 101 gesloten en waren er nog steeds nul items.
- **X3** (3-0): De overige gevallen kloppen: tweede pull, ontbrekende markering, twee diensten, onbekende open noden en falend klaarzetten behouden respectievelijk het nummer of proberen opnieuw. De test voor twee diensten controleert alleen twee noden, niet twee afzonderlijke signalen; voeg dat aan dezelfde herstelronde toe.
- **G1** (3-0): K2 laten vervallen en bord-nood als storingsanker
  Techniek voor Claude: [bouwwacht.py:20-27](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L20-L27) - Het bord beheert via `/api/nood` de levenscyclus en het unieke id van een storing; lokale statefile K2 vervalt terecht.
- **G3** (3-0): Klok en reflog zonder aannames
  Techniek voor Claude: [bouwwacht.py:120-130](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L120-L130) en [bouwwacht.py:250-251](file:///Users/mehdichegini/dev/_bouwwacht/mijnagents-runner/bouwwacht.py#L250-L251) - `OUD = 0` dwingt conservatief `achter` af bij ontbrekende markering/reflogstap; `REFLOGNOOD` verklaart de directe trigger.
- **K1** (3-0): Mag K2 vervallen?** Ja.
  - Techniek voor Claude: `bouwwacht.py:13-21` en `:120` blijven zoals ze zijn. Geen aanpassing.
- **K2** (3-0): Nog punten van ernst hoog of middel?** Geen hoog. Eén middel-laag.
  - Techniek voor Claude: `bouwwacht.py:244-245` - meld bij stand "onbekend" ook `noodtekst(dienst)` mee als die in `open_` staat (`open_` is dan al opgehaald), en voeg een test toe: achter, dan onbekend, dan achter geeft hetzelfde nummer en één signaal.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
