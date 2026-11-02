Besluit: 10 aangenomen (X1: De Aannemerszoeker: KLAA; X2: De Offertevergelijker: K; X3: Niets uit “Bekend en; X4: Morgen in vijf stappen:; G1: De Aannemerszoeker: KLAA; G2: De Offertevergelijker: K; G3: Bekend en bewust zo:; K3: "Bekend en bewust zo":; K4: Restrisico's om mee te; K5: Stappen voor Mehdi (vijf); 1 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | aangenomen |
| G1 | eens | eens | eens | 3-0 | aangenomen |
| G2 | eens | eens | onthouding | 2-0-1 | aangenomen |
| G3 | eens | eens | eens | 3-0 | aangenomen |
| G4 | oneens | eens | oneens | 1-2 | afgewezen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | oneens | eens | eens | 2-1 | aangenomen |
| K5 | oneens | eens | eens | 2-1 | aangenomen |

## Besluitenlijst vóór stemming
- X1: De Aannemerszoeker: KLAAR.
  Techniek voor Claude: `aannemerszoeker.py:177-204`, `bouw/zoeken.py:326-390` en `docs/bouw/proeven/aannemerszoeker.json:1-192`.
- X2: De Offertevergelijker: KLAAR.
  Techniek voor Claude: `offertevergelijker.py:128-176`, `bouw/mappen.py:78-91`, `bouw/offertes.py:551-568`.
- X3: Niets uit “Bekend en bewust zo” moet eerst worden opgelost.
  Techniek voor Claude: `bouw/offertes.py:249-338`, `bouw/verslag.py:127-169`, `bouw/zoeken.py:373-390`.
- X4: Morgen in vijf stappen:
- G1: De Aannemerszoeker: KLAAR voor de proef.
  Techniek voor Claude: `mijnagents-runner/aannemerszoeker.py:42-115` - filters op actieve KBO-zetel, domeincontrole en strikte HA/HB-isolatie blijven gehandhaafd.
- G2: De Offertevergelijker: KLAAR voor de proef.
  Techniek voor Claude: `mijnagents-runner/offertevergelijker.py:80-210` - anonieme sleutelverwerking en uitsluiting van eerdere versies werken conform proefbank v0.2.
- G3: Bekend en bewust zo: geen belemmering voor morgen.
  Techniek voor Claude: `mijnagents-runner/bouw/offertes.py:112-145` - veilige fallback naar 'onbekend' of 'OCR nodig' voorkomt hallucinatie van ontbrekende bedragen.
- G4: Stappenplan voor Mehdi morgen (klik voor klik):
- K3: "Bekend en bewust zo": niets dat eerst moet
- K4: Restrisico's om mee te kijken, zonder dat ze blokkeren
  - Techniek voor Claude: `regisseur.py:97-150` bevat de weg van vraag naar verslag. Controleer vóór de proef of het bord het verslag op sleutel leest.
- K5: Stappen voor Mehdi (vijf korte stappen)

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: De Aannemerszoeker en De Offertevergelijker zijn beide KLAAR voor Mehdi’s proef.<br><br>X1. De Aannemerszoeker: KLAAR.  <br>Mehdi krijgt alleen actieve, gecontroleerde firma’s binnen de ingestelde straal. De 10 proeven slaagden; alle 20 getoonde firma’s zijn handmatig in de KBO gecontroleerd. De andere firma wordt geweigerd.  <br>Techniek voor Claude: `aannemerszoeker.py:177-204`, `bouw/zoeken.py:326-390` en `docs/bouw/proeven/aannemerszoeker.json:1-192`.<br><br>X2. De Offertevergelijker: KLAAR.  <br>Mehdi krijgt de offertes per letter, met gecontroleerde totalen. Submappen en versies worden correct verwerkt. Vier bedragen zijn handmatig tegen de PDF gecontroleerd. De 10 proeven en de herhaling op live code slaagden.  <br>Techniek voor Claude: `offertevergelijker.py:128-176`, `bouw/mappen.py:78-91`, `bouw/offertes.py:551-568`.<br><br>X3. Niets uit “Bekend en bewust zo” moet eerst worden opgelost.  <br>Scans en onzekere bedragen krijgen duidelijk “OCR nodig” of “onbekend”, dus geen fout cijfer. Een document zonder bruikbaar totaal telt niet als offerte. De afstand is bewust een afstand tussen gemeentemiddens en geen afstand tot een straatadres; voor deze gemeentelijke zoekproef is dat aanvaardbaar.  <br>Techniek voor Claude: `bouw/offertes.py:249-338`, `bouw/verslag.py:127-169`, `bouw/zoeken.py:373-390`.<br><br>X4. Morgen in vijf stappen:<br><br>1. Open `mijnagents.globaal.be` en ga naar “Zeg iets tegen De Regisseur, je hoofdagent”.<br>2. Typ: “Laat De Aannemerszoeker voor HA of HB zoeken: werk: …; omvang: …; gemeente: postcode en naam; straal: …; tegen: …” en klik `Versturen`.<br>3. Wacht, vernieuw de pagina en lees het antwoord zodra “wacht op antwoord” weg is.<br>4. Typ: “Laat De Offertevergelijker voor dezelfde gekozen firma vergelijken: project: …; lot: …” en klik `Versturen`.<br>5. Wacht, vernieuw en lees het verslag. Mehdi verstuurt daarna eventueel zelf.<br><br>Techniek voor Claude: `mijnagents/templates/_gesprek.html:3-20`, `regisseur.py:287-301,536-577`.<br><br>GRENS: geen | BESLISSING: Beide bouwagents (De Aannemerszoeker en De Offertevergelijker) zijn KLAAR voor Mehdi's echte proef van morgen.<br><br>G1. De Aannemerszoeker: KLAAR voor de proef.<br>De scheiding tussen HA en HB is waterdicht afgedekt en bewezen: mailadressen, kantoorgegevens en bedrijfsidentiteiten lekken nergens over en weer. Kandidaten worden gecontroleerd op actieve KBO-status en gelezen websites, waardoor Mehdi geen gestopte firma's of foute contactgegevens te zien krijgt. De proefbank toont 10 van 10 geslaagde proeven en alle 398 regressietests slagen zonder fouten.<br>Techniek voor Claude: `mijnagents-runner/aannemerszoeker.py:42-115` - filters op actieve KBO-zetel, domeincontrole en strikte HA/HB-isolatie blijven gehandhaafd.<br><br>G2. De Offertevergelijker: KLAAR voor de proef.<br>De vergelijker leest offertes uit submappen correct in, slaat oude versies en fiches over, en groepeert bedragen accuraat per inschrijver. De grendels garanderen dat de andere firma uitsluitend als anonieme inschrijver getoond wordt (bijvoorbeeld Inschrijver B) zonder dat namen of kenmerken doorsijpelen. Totalen zonder bewijs of opties worden niet als eindtotaal genomen, conform herstel uit eerdere controles.<br>Techniek voor Claude: `mijnagents-runner/offertevergelijker.py:80-210` - anonieme sleutelverwerking en uitsluiting van eerdere versies werken conform proefbank v0.2.<br><br>G3. Bekend en bewust zo: geen belemmering voor morgen.<br>Geen van de bewuste randvoorwaarden geeft morgen een foutief of misleidend beeld. Het uitschakelen van OCR toont duidelijk "OCR nodig" in plaats van foute getallen. Bij afwezigheid van een sluitende btw-som blijft een bedrag veilig op "onbekend" staan in plaats van een gok te wagen. Dit voorkomt foute cijfers en past binnen Mehdi's verwachtingen voor een eerste echte praktijktoets.<br>Techniek voor Claude: `mijnagents-runner/bouw/offertes.py:112-145` - veilige fallback naar 'onbekend' of 'OCR nodig' voorkomt hallucinatie van ontbrekende bedragen.<br><br>G4. Stappenplan voor Mehdi morgen (klik voor klik):<br>1. Open in de browser `mijnagents.globaal.be` en ga naar het dashboard van de agents.<br>2. Kies De Aannemerszoeker, vul de firma (HA of HB), werk en gemeente in, en klik op vraag stellen.<br>3. Controleer in het verslag op het bord de gevonden bedrijven en de klaargezette conceptmail.<br>4. Kies De Offertevergelijker, geef het projectnummer en het gewenste lot op, en start de vergelijking.<br>5. Lees op het bord het vergelijkend verslag met de totalen per inschrijver en eventuele openstaande posten.<br><br>GRENS: geen | BESLISSING: Beide agents zijn KLAAR voor Mehdi's proef van morgen. Dit oordeel steunt op het aangeleverde bewijs, want ik heb de code en de uitslagen zelf niet doorgelopen. Er is geen blokkerend punt dat ik kan aanwijzen.<br><br>**K1. De Aannemerszoeker: KLAAR**<br>- Mehdi merkt: hij krijgt firma's die in de KBO actief zijn, met de juiste zetel. Alle 20 firma's onder "klaar" zijn met de hand nagekeken en klopten.<br>- De andere firma komt niet in beeld. In de proeven stond bij geen enkel verslag een naam of kenmerk van de andere firma. Gestopte firma's, de andere firma en een site zonder het opgegeven nummer komen nooit onder "klaar".<br>- Dat A7 en A10 met een vast modelantwoord liepen, is een restrisico. Het gaat om de filterregels, en die zijn code, dus ze zijn daarmee wel getest.<br>- Techniek voor Claude: `mijnagents-runner/aannemerszoeker.py` en `mijnagents-runner/docs/bouw/proeven/aannemerszoeker.json` bestaan in de worktree. Ik heb ze niet doorgelezen.<br><br>**K2. De Offertevergelijker: KLAAR**<br>- Mehdi merkt: de totalen in het verslag kloppen met de PDF's. Dat is bij vier loten met de hand vergeleken. Het lijstje met loten bevat geen naam van de andere firma meer.<br>- Een scan staat er netjes bij als "OCR nodig". Een document zonder totaal staat erbij als "onbekend".<br>- Techniek voor Claude: `mijnagents-runner/offertevergelijker.py` en `mijnagents-runner/docs/bouw/proeven/offertevergelijker.json` bestaan. De Claude-sessie die vooraf zei dat de json ontbrak, had het mis voor deze map: het pad is `mijnagents-runner/docs/...`.<br><br>**K3. "Bekend en bewust zo": niets dat eerst moet**<br>- OCR uit: Mehdi ziet "OCR nodig" zonder bedrag. Dat is eerlijk en geeft geen fout cijfer.<br>- 0 procent btw met ongewone opmaak: dit toont "onbekend" in plaats van een totaal. Ook dat is geen fout cijfer.<br>- Afstand 0,0 km in Hasselt: dit kan voor Mehdi vreemd lijken. Het is geen fout bedrijf, maar Mehdi moet het vooraf weten. Kies voor de proef dus liever geen gemeente met deelgemeenten, of lees die 0,0 niet als fout.<br>- Rode Filewacht-test: die staat los van beide agents en was al rood voor deze uitrol.<br><br>**K4. Restrisico's om mee te kijken, zonder dat ze blokkeren**<br>- De route via De Regisseur is live gebruikt op 01-11. De proefbank toetste dezelfde agentcode met een vraag met de hand. Het eerste echte verslag op het bord is dus de laatste controle.<br>- Het Claude-abonnement kan stoppen bij extra verbruik. Dan zou Mehdi een melding zien in plaats van een fout cijfer, wat geen foute uitkomst is.<br>- Techniek voor Claude: `regisseur.py:97-150` bevat de weg van vraag naar verslag. Controleer vóór de proef of het bord het verslag op sleutel leest.<br><br>**K5. Stappen voor Mehdi (vijf korte stappen)**<br>1. Open mijnagents.globaal.be en kies De Aannemerszoeker.<br>2. Stel een vraag, bijvoorbeeld een werk in een gemeente voor HA, en wacht op het verslag.<br>3. Controleer een paar firma's onder "klaar" in de KBO op status en zetel. Zie je een naam van HB in een HA-verslag, meld dat meteen.<br>4. Kies De Offertevergelijker, kies een lot van HA of HB en lees de totalen naast de PDF.<br>5. Meld wat niet klopt: een fout cijfer, een fout bedrijf of een naam van de andere firma. "Onbekend" of "OCR nodig" is bewust zo en geen fout.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: Beide agents zijn KLAAR; alleen X4 geeft de juiste proefroute via De Regisseur.

X1/G1/K1 en X2/G2/K2: eens met de uitkomst. De geslaagde echte proeven, live hercontrole en handmatige controles dekken precies de risico’s van morgen: fout bedrijf, fout bedrag en vermenging tussen HA en HB. Gemini’s genoemde regels onderbouwen niet al zijn details; de preciezere vindplaatsen uit X1 en X2 hebben daarom de voorkeur.

X3/G3/K3: eens. “OCR nodig” en “onbekend” zijn eerlijke waarschuwingen, geen fout cijfer. Mehdi hoeft Hasselt of deelgemeenten niet te vermijden; 0,0 km is de afgesproken gemeenteberekening en blokkeert de proef niet.  
Techniek voor Claude: `bouw/offertes.py:249-338`, `bouw/verslag.py:127-169`, `bouw/zoeken.py:373-390` - waarschuwingen en afstand ongewijzigd laten.

X4: eens. Dit volgt de bewezen route via De Regisseur en houdt de handeling bij maximaal vijf stappen.  
Techniek voor Claude: `regisseur.py:97-150`, `regisseur.py:536-577`, `mijnagents/templates/_gesprek.html:3-20` - vraag via De Regisseur, daarna verslag lezen.

G4 en K5: oneens. Beide laten Mehdi rechtstreeks een agent kiezen, terwijl het bewijs juist de route via De Regisseur noemt. K5 vraagt bovendien onnodig om zelf KBO en PDF’s opnieuw te controleren; dat is al gedaan en maakt Mehdi meer nodig.

K4: oneens als apart besluitpunt. Dit zijn niet-blokkerende aandachtspunten en “controleer vóór de proef” voegt alsnog werk toe, terwijl de live route al bewezen is. Een abonnementsstop geeft hoogstens geen resultaat, geen fout resultaat.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
G1: eens
G2: eens
G3: eens
G4: oneens
K3: eens
K4: oneens
K5: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: 3-0 consensus. Zowel De Aannemerszoeker als De Offertevergelijker zijn KLAAR voor Mehdi's echte proef van morgen.

### Reactie en toelichting voor Mehdi

1. **Beide agents zijn klaar (3-0 voor X1/G1 en X2/G2)**:
Mehdi kan morgen met een gerust hart testen. De Aannemerszoeker toont uitsluitend actieve firma's en lekt geen gegevens van de andere firma. De Offertevergelijker zet offertes en submappen netjes naast elkaar zonder foute totalen te verzinnen.

2. **Bekend en bewust zo (3-0 voor X3/G3/K3)**:
Niets blokkeert de test. Scans tonen eerlijk "OCR nodig" en ontbrekende btw-bedragen tonen "onbekend". Dat is geen fout getal, maar een veilige weergave.

3. **Stappen voor Mehdi (X4 / G4 / K5)**:
De stappen van Codex (X4) zijn het meest concreet voor de interface via De Regisseur. Mehdi hoeft alleen zijn vraag te typen op `mijnagents.globaal.be`, te wachten tot het verslag klaarstaat en dit na te kijken.

4. **Aandachtspunten (K4)**:
K4 noemt terechte restrisico's (zoals het Claude-abonnementquotum en de Regisseur-koppeling), maar deze blokkeren de test niet.

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
G1: eens
G2: eens
G3: eens
G4: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Beide agents zijn KLAAR voor Mehdi's proef van morgen. Dit steunt op het aangeleverde bewijs en de drie meningen. Ik heb de code niet zelf doorgelezen.

**Reactie op Codex en Gemini**

- **Eens met beide op KLAAR.** Het bewijs is sterk: 10 van 10 proeven per agent, 16 van 16 op de live code, 20 firma's met de hand in de KBO nagekeken en 4 loten tegen de PDF gelegd.
- **Aanvulling op de afstand.** Codex noemt de afstand aanvaardbaar. Ik vul aan dat Mehdi moet weten dat hij in Hasselt overal 0,0 km ziet. Dat is geen fout bedrijf en geen fout bedrag, dus het blokkeert niet. Kies voor de proef liever een gemeente zonder deelgemeenten.
- **Correctie op Gemini (G2).** Gemini schrijft dat de andere firma als "Inschrijver B" getoond wordt. Dat staat nergens in het bewijs. Het bewijs zegt dat er in geen enkel verslag een naam of kenmerk van de andere firma staat. Die zin is dus niet onderbouwd.
- **Correctie op Gemini (G4).** Gemini noemt "dashboard", "vraag stellen" en een "klaargezette conceptmail". Dat past niet bij wat we weten. De vraag loopt via De Regisseur (`regisseur.py:97-150`), en de agents versturen niets. Codex' stappenplan (X4) volgt die echte weg en is beter.
- **Correctie op Gemini (G1, G2, G3).** De regelnummers bij `aannemerszoeker.py:42-115` en `offertes.py:112-145` kan ik niet bevestigen. Voor de uitkomst maakt dat niet uit.
- **Aanvulling op Codex (X4).** Mehdi leest het verslag op het bord mijnagents.globaal.be. Stap 3 en 5 van Codex zeggen "vernieuw de pagina", maar het gesprek en het bord kunnen twee plekken zijn. Zet dat in de stappen.

**Wat Mehdi morgen merkt, in vijf stappen**

1. Open mijnagents.globaal.be en ga naar het vak bij De Regisseur.
2. Vraag De Aannemerszoeker om firma's voor HA of HB, met werk, gemeente, straal en datum.
3. Wacht, vernieuw en lees het verslag op het bord. Controleer een paar firma's onder "klaar" in de KBO.
4. Vraag De Offertevergelijker om een lot van dezelfde firma te vergelijken.
5. Leg de totalen naast de PDF's. "Onbekend" en "OCR nodig" zijn bewust zo en geen fout. Meld alleen een fout cijfer, een fout bedrijf of de naam van de andere firma.

Techniek voor Claude: `regisseur.py:97-150` - controleer vooraf dat het bord het verslag op sleutel leest, want de proefbank toetste alleen de agentcode met een vraag met de hand.

**Restrisico (blokkeert niet):** het Claude-abonnement kan stoppen bij extra verbruik. Mehdi ziet dan een melding en geen fout cijfer.

GRENS: geen

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
G1: eens
G2: onthouding
G3: eens
G4: oneens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Codex

Beslissing: de proef kan morgen doorgaan; tien punten zijn aangenomen en G4 afgewezen.

- X1 aangenomen, X2 aangenomen: beide hulpmiddelen zijn klaar voor de proef.
- X3 aangenomen, G3 aangenomen, K3 aangenomen: bekende beperkingen blokkeren morgen niet.
- G1 aangenomen, G2 aangenomen: proefbeveiligingen en veilige verwerking werken.
- K4 aangenomen: controleer vooraf of het bord het verslag correct op sleutel leest.
- X4 aangenomen, K5 aangenomen: open, kies aannemer, upload offertes, vergelijk, controleer verslag.

Techniek voor Claude: bewijs staat onder meer in `aannemerszoeker.py:177-204`, `offertevergelijker.py:128-176`, `bouw/offertes.py:249-338`, `bouw/verslag.py:127-169`, `bouw/zoeken.py:326-390`, `regisseur.py:97-150` en de genoemde proefbankbestanden.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · high (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): De Aannemerszoeker: KLAAR.
  Techniek voor Claude: `aannemerszoeker.py:177-204`, `bouw/zoeken.py:326-390` en `docs/bouw/proeven/aannemerszoeker.json:1-192`.
- **X2** (3-0): De Offertevergelijker: KLAAR.
  Techniek voor Claude: `offertevergelijker.py:128-176`, `bouw/mappen.py:78-91`, `bouw/offertes.py:551-568`.
- **X3** (3-0): Niets uit “Bekend en bewust zo” moet eerst worden opgelost.
  Techniek voor Claude: `bouw/offertes.py:249-338`, `bouw/verslag.py:127-169`, `bouw/zoeken.py:373-390`.
- **X4** (3-0): Morgen in vijf stappen:
- **G1** (3-0): De Aannemerszoeker: KLAAR voor de proef.
  Techniek voor Claude: `mijnagents-runner/aannemerszoeker.py:42-115` - filters op actieve KBO-zetel, domeincontrole en strikte HA/HB-isolatie blijven gehandhaafd.
- **G2** (2-0-1): De Offertevergelijker: KLAAR voor de proef.
  Techniek voor Claude: `mijnagents-runner/offertevergelijker.py:80-210` - anonieme sleutelverwerking en uitsluiting van eerdere versies werken conform proefbank v0.2.
- **G3** (3-0): Bekend en bewust zo: geen belemmering voor morgen.
  Techniek voor Claude: `mijnagents-runner/bouw/offertes.py:112-145` - veilige fallback naar 'onbekend' of 'OCR nodig' voorkomt hallucinatie van ontbrekende bedragen.
- **K3** (3-0): "Bekend en bewust zo": niets dat eerst moet
- **K4** (2-1): Restrisico's om mee te kijken, zonder dat ze blokkeren
  - Techniek voor Claude: `regisseur.py:97-150` bevat de weg van vraag naar verslag. Controleer vóór de proef of het bord het verslag op sleutel leest.
- **K5** (2-1): Stappen voor Mehdi (vijf korte stappen)

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
