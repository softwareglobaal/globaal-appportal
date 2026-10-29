Besluit: 12 aangenomen (X1: ; X2: ; X3: 10 en v1.9 worden; X4: ; G1: De Namenwacht controleer; G2: Als iemand een codevoorb; G3: Verandert iemand later é; K1: Veilig pauzeren (Vraag 1; K2: Kop in codeblok of; K3: Versiesortering - ernst ; K4: Cache, dagelijkse force ; K5: Waar gaat de nood); 1 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | aangenomen |
| X5 | oneens | oneens | oneens | 0-3 | afgewezen |
| G1 | eens | eens | eens | 3-0 | aangenomen |
| G2 | eens | eens | eens | 3-0 | aangenomen |
| G3 | eens | eens | eens | 3-0 | aangenomen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | eens | eens | eens | 3-0 | aangenomen |
| K5 | eens | eens | eens | 3-0 | aangenomen |

## Afwijkingen in dit overleg
- Bezetting Codex: terugval op standaard voor ontbrekende velden: geen leesbare BEZETTING-regel (ook na de herstelbeurt); gebruikt gpt-5.6-luna · low. Voorstel: geen BEZETTING-regel gevonden.

## Besluitenlijst vóór stemming
- X1: Middel: hoofdstukkop in een codeblok wordt ten onrechte als echte kop gezien.
  Techniek voor Claude: `mijnagents-runner/koppelingen/naamstructuur.py:448-464` - parse fenced codeblokken en herken `## A. `-koppen alleen buiten codeblokken; voeg een regressietest toe.
- X2: Laag: hoofdstukgrenzen zijn voldoende voor de huidige bron, maar de parser is bewust smal.
  Techniek voor Claude: `naamstructuur.py:456-464` - eventueel expliciet testen/documenteren dat afwijkende kopopmaak pauzeert.
- X3: Laag: versies als v1.10 en v1.9 worden correct numeriek gesorteerd.
  Techniek voor Claude: `naamstructuur.py:478-500` - bestaande tests `test_oude_versie...` en `test_geen_of_alleen_oudere...` dekken dit af.
- X4: Laag: cache, dagelijkse force en herbeoordeling werken volgens ontwerp.
  Techniek voor Claude: `naamstructuur_ronde.py:44-46`, `naamstructuur.py:511-521`, `naamstructuur.py:676` - tests dekken cache, force en behoud van open bevindingen.
- X5: Middel: melding bij gewijzigd hoofdstuk A/B hoort primair bij Mehdi.
- G1: De Namenwacht controleert H-A-mappen weer zoals normaal. Omdat v1.10 voor de agents dezelfde regels bevat als v1.7, blokkeert hij niet meer onnodig.
- G2: Als iemand een codevoorbeeld in het boek plakt met `## B.`, kan de agent nu per ongeluk het verkeerde stuk tekst lezen of vastlopen.
- G3: Verandert iemand later écht iets aan de regels in hoofdstuk A of B, dan valt de agent jou niet meer lastig met technische vragen ("Welke versie geldt?"), maar gaat het direct naar Claude om de regels bij te werken.
- K1: Veilig pauzeren (Vraag 1) - ernst laag
  Techniek voor Claude: naamstructuur.py:503-521 en 531-532, geen aanpassing nodig.
- K2: Kop in codeblok of kop zonder letter (Vraag 2) - ernst middel
  Techniek voor Claude: naamstructuur.py:455-461 - geef elke `## `-kop buiten codeblokken (``` of ~~~) als hoofdstukgrens en neem alleen A en B mee. Voeg een test toe voor een changelog onder B.
- K3: Versiesortering - ernst laag
  Techniek voor Claude: naamstructuur.py:495-497, geen aanpassing nodig, hooguit een test voor v1.9 tegenover v1.10.
- K4: Cache, dagelijkse force en herbeoordeling - ernst laag
  Techniek voor Claude: naamstructuur.py:511-515 en naamstructuur_ronde.py:44-46. Controleer in de tests dat `r.nood` bij een herhaalde ronde niet elk kwartier een nieuwe melding maakt.
- K5: Waar gaat de nood heen (Vraag 3) - ernst middel
  Techniek voor Claude: naamstructuur_ronde.py:53-55 - stuur de nood naar `"claude-code"`. Neem de oude en nieuwe hash en de versie op, met als tekst "hoofdstuk A of B gewijzigd in v1.x, vertaling nakijken en pin bijwerken". Het dashboard (naamstructuur.html:28) toont de status al aan Mehdi.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: klaar met kanttekeningen. De hoofdreparatie is veilig en fail closed, maar er blijft één middelzwaar parseringsrisico dat nu niet door de tests wordt afgedekt.<br><br>X1. **Middel: hoofdstukkop in een codeblok wordt ten onrechte als echte kop gezien.**  <br>Als A of B een documentatievoorbeeld bevat met bijvoorbeeld `## C. voorbeeld` binnen een fenced codeblok, stopt `hoofdstukken()` daar alsnog. Daardoor kan de hash van A/B veranderen en pauzeert de Namenwacht onnodig. Andersom kan een voorbeeldkop een ontbrekend hoofdstuk maskeren.  <br>Techniek voor Claude: `mijnagents-runner/koppelingen/naamstructuur.py:448-464` - parse fenced codeblokken en herken `## A. `-koppen alleen buiten codeblokken; voeg een regressietest toe.<br><br>X2. **Laag: hoofdstukgrenzen zijn voldoende voor de huidige bron, maar de parser is bewust smal.**  <br>De functie herkent alleen exact `##` plus één hoofdletter, punt en spatie. Dat is fail closed bij afwijkende opmaak, dus veilig, maar een bronwijziging naar bijvoorbeeld `## A` wordt als ontbrekend gezien en pauzeert. Dat is acceptabel zolang de afspraakkoppen deze vorm verplichten.  <br>Techniek voor Claude: `naamstructuur.py:456-464` - eventueel expliciet testen/documenteren dat afwijkende kopopmaak pauzeert.<br><br>X3. **Laag: versies als v1.10 en v1.9 worden correct numeriek gesorteerd.**  <br>`tuple(int(...))` maakt v1.10 groter dan v1.9. De hoogste gevonden versie wordt gekozen; oudere bestanden of een ontbrekende vastgepinde versie leiden tot pauzeren. Dat is correct fail closed.  <br>Techniek voor Claude: `naamstructuur.py:478-500` - bestaande tests `test_oude_versie...` en `test_geen_of_alleen_oudere...` dekken dit af.<br><br>X4. **Laag: cache, dagelijkse force en herbeoordeling werken volgens ontwerp.**  <br>Binnen 24 uur wordt een ongewijzigde bron niet opnieuw gedownload. Een hogere versie krijgt een ander pad en wordt wel gelezen. De dagelijkse controle of gewijzigde regels forceert opnieuw lezen; een gewijzigde regelbron leidt via `geldig=False` tot pauzeren, terwijl bestaande bevindingen open blijven.  <br>Techniek voor Claude: `naamstructuur_ronde.py:44-46`, `naamstructuur.py:511-521`, `naamstructuur.py:676` - tests dekken cache, force en behoud van open bevindingen.<br><br>X5. **Middel: melding bij gewijzigd hoofdstuk A/B hoort primair bij Mehdi.**  <br>Mehdi is eigenaar van het afsprakenboek en heeft de inhoud al goedgekeurd. De melding “Welke versie geldt?” is daarom juist; Claude kan daarna technisch de vertaling en JSON-pin aanpassen, maar mag de inhoudelijke keuze niet zelf maken.<br><br>GRENS: geen | BESLISSING: Klaar met kanttekeningen (stemverhouding voorstel 3-0). De opzet van herstel T-0028 is inhoudelijk correct en fail-closed, maar mist bescherming tegen markdown-codeblokken en stuurt de noodmelding nog naar de verkeerde persoon.<br><br>### Voor Mehdi<br>- **G1:** De Namenwacht controleert H-A-mappen weer zoals normaal. Omdat v1.10 voor de agents dezelfde regels bevat als v1.7, blokkeert hij niet meer onnodig.<br>- **G2:** Als iemand een codevoorbeeld in het boek plakt met `## B.`, kan de agent nu per ongeluk het verkeerde stuk tekst lezen of vastlopen.<br>- **G3:** Verandert iemand later écht iets aan de regels in hoofdstuk A of B, dan valt de agent jou niet meer lastig met technische vragen ("Welke versie geldt?"), maar gaat het direct naar Claude om de regels bij te werken.<br><br>### Voor Claude en Shaniel<br>- **G1 (laag, 3-0):** Fail-closed en versiesortering kloppen. Numerieke tuple-sortering (`1.10 > 1.9`) en de 24-uurs cache/dagelijkse force werken veilig en correct.<br>  *Techniek voor Claude: [naamstructuur.py:488-515](file:///Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/koppelingen/naamstructuur.py#L488-L515) - Geen aanpassing nodig.*<br>- **G2 (middel, 3-0):** `hoofdstukken()` negeert codeblokken niet. `re.match(r"^## ([A-Z])\. ", regel)` matcht ook koppen binnen ` ``` ` fences. Voeg een eenvoudige toggle voor code fences toe.<br>  *Techniek voor Claude: [naamstructuur.py:455-464](file:///Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/koppelingen/naamstructuur.py#L455-L464) - Houd `in_codeblock` bij op regels die starten met ` ``` ` en sla kop-matching over.*<br>- **G3 (middel, 3-0):** Noodmelding bij inhoudelijke wijziging van A of B moet naar `claude-code`, niet naar `mehdi`. Mehdi keurt immers het markdown-document zelf al goed als regisseur; Claude moet de json-vertaling aanpassen.<br>  *Techniek voor Claude: [naamstructuur_ronde.py:53-57](file:///Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/naamstructuur_ronde.py#L53-L57) - Wijzig doel van noodmelding bij `bron.get("gevonden")` van `"mehdi"` naar `"claude-code"`.*<br><br>GRENS: geen | BESLISSING: Het herstel klopt en pauzeert nog veilig. Ik zie geen blokkerend gat. Wel vier kleine verbeteringen. De nood bij een echt gewijzigd hoofdstuk A of B moet naar Claude, niet naar Mehdi.<br><br>Ik heb de code gelezen, maar `git show` en de tests heb ik niet kunnen draaien (alleen lezen, geen Bash). De "17 groen" is dus niet door mij gecontroleerd.<br><br>**K1. Veilig pauzeren (Vraag 1) - ernst laag**<br>Mehdi merkt: de Namenwacht toetst H-A weer gewoon met v1.10. Staat er geen versie, alleen een oudere, een onleesbaar bestand of een bestand dat te groot is, dan pauzeert hij. Alleen een gelijke hash van A en B telt als geldig. Elke fout wordt "niet geldig", en daarna toetst `toets_index` geen H-A-mappen meer.<br>Techniek voor Claude: naamstructuur.py:503-521 en 531-532, geen aanpassing nodig.<br><br>**K2. Kop in codeblok of kop zonder letter (Vraag 2) - ernst middel**<br>Mehdi merkt: bij een volgende versie pauzeert de wacht soms onnodig, en dan komt er weer een vraag. De functie `hoofdstukken` kent geen codeblokken. Een `## C. `-regel in een codeblok knipt hoofdstuk B af. Een kop zonder letter erachter (bijvoorbeeld "## Wijzigingslog" onder B) wordt bij B gerekend. Dat geeft nooit een onveilige uitkomst, want de hash verandert dan en er komt een pauze. Het kost wel nodeloos pauzes.<br>Techniek voor Claude: naamstructuur.py:455-461 - geef elke `## `-kop buiten codeblokken (``` of ~~~) als hoofdstukgrens en neem alleen A en B mee. Voeg een test toe voor een changelog onder B.<br><br>**K3. Versiesortering - ernst laag**<br>Mehdi merkt: v1.10 wordt terecht hoger gezien dan v1.9, want de vergelijking gebruikt getallen. Alleen v1.10 en v1.10.0 zouden als verschillend gelden, en dat komt niet voor.<br>Techniek voor Claude: naamstructuur.py:495-497, geen aanpassing nodig, hooguit een test voor v1.9 tegenover v1.10.<br><br>**K4. Cache, dagelijkse force en herbeoordeling - ernst laag**<br>Mehdi merkt: een nieuwe versie wordt direct gezien. De map wordt bij elke ronde opnieuw gelezen. Een nieuwe versie geeft een ander pad, dus de cache van 24 uur geldt dan niet. Een wijziging in het pin of de hash forceert een nieuwe controle via `hercontrole_regels`. Een ongeldige stand wordt niet gecachet. Bij een gewijzigd hoofdstuk wordt het bestand daardoor elk kwartier opnieuw gedownload (maximaal 500 kB). Dat is geen veiligheidsprobleem.<br>Techniek voor Claude: naamstructuur.py:511-515 en naamstructuur_ronde.py:44-46. Controleer in de tests dat `r.nood` bij een herhaalde ronde niet elk kwartier een nieuwe melding maakt.<br><br>**K5. Waar gaat de nood heen (Vraag 3) - ernst middel**<br>Mehdi merkt: nu krijgt hij "Welke versie geldt?" en kan daar niets mee. Hij keurt het boek al goed, en de pin staat in code en JSON. Als A of B echt verandert, moet iemand de machinevertaling nakijken en de hash bijwerken. Dat is werk voor Claude. Mehdi hoeft alleen mee te kijken als Claude een echte tegenspraak in de regels vindt.<br>Techniek voor Claude: naamstructuur_ronde.py:53-55 - stuur de nood naar `"claude-code"`. Neem de oude en nieuwe hash en de versie op, met als tekst "hoofdstuk A of B gewijzigd in v1.x, vertaling nakijken en pin bijwerken". Het dashboard (naamstructuur.html:28) toont de status al aan Mehdi.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
Klaar met kanttekeningen. De herstelrichting is veilig en fail closed; de codeblokkwestie moet nog worden afgedekt. De noodmelding hoort volgens de meerderheid naar Claude.

X1. Middel: een `## A.`- of `## B.`-kop in een fenced codeblok wordt nu als echte hoofdstukkop gezien. Dat kan onnodige pauzes veroorzaken.  
Techniek voor Claude: `naamstructuur.py:448-464` - codeblokken met ``` en ~~~ negeren; regressietest toevoegen.

X2. Laag: afwijkende hoofdstukkoppen worden niet herkend. Dat pauzeert veilig, maar vraagt om een expliciete test of documentregel.  
Techniek voor Claude: `naamstructuur.py:456-464` - exacte kopvorm als broncontract testen.

X3. Laag: v1.10 wordt numeriek correct hoger gesorteerd dan v1.9.  
Techniek voor Claude: `naamstructuur.py:478-500` - geen fix; eventueel expliciete regressietest.

X4. Laag: cache, dagelijkse force en herbeoordeling gedragen zich veilig. Een nieuwe versie heeft een nieuw pad, gewijzigde regels worden opnieuw gecontroleerd en H-A blijft gepauzeerd zolang de bron ongeldig is.  
Techniek voor Claude: `naamstructuur.py:511-521`, `naamstructuur_ronde.py:44-46` - controleer nog dat herhaalde noden niet onnodig worden gedupliceerd.

X5. Middel: bij gewijzigde hoofdstukken A/B moet de nood naar Claude gaan. Mehdi heeft het afsprakenboek inhoudelijk al goedgekeurd; Claude moet vertaling, JSON-pin en hash technisch bijwerken.  
Techniek voor Claude: `naamstructuur_ronde.py:53-57` - wijzig `"mehdi"` naar `"claude-code"` en vermeld versie en gewijzigde hoofdstukken.

G1 en K1: eens. Geen versie, alleen oudere versie, onleesbaarheid of hashverschil pauzeert de toetsing veilig.  
G2 en K2: eens. Dit is hetzelfde middelzware codeblokrisico als X1.  
G3 en K5: eens. De meerderheid kiest voor Claude als ontvanger.  
K3: eens.  
K4: eens.

Stembesluit: 2-op-3 voor codeblokbescherming en noodmelding naar Claude. Er is geen 1-1-1-verdeeldheid.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: oneens
G1: eens
G2: eens
G3: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Klaar met kanttekeningen (stemverhouding 2-1 voor melding naar Claude, 3-0 voor codeblokken).

### Voor Mehdi
- De reparatie klopt: de Namenwacht hervat de H-A-toetsing direct veilig en zonder fouten.
- We voegen bescherming toe zodat codevoorbeelden met `## B.` in het afsprakenboek de controle niet laten crashen.
- Bij een inhoudelijke wijziging van hoofdstuk A of B gaat de technische melding direct naar Claude om de regels bij te werken, zodat jij geen onnodige technische vragen krijgt.

### Voor Claude en Shaniel
- Codeblokken (``` of ~~~) uitsluiten bij parseren van hoofdstukken A en B (`naamstructuur.py:448-464`).
- Noodmelding bij `bron.get("gevonden")` routeren naar `"claude-code"` in plaats van `"mehdi"` (`naamstructuur_ronde.py:53-57`).

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
X5: oneens
G1: eens
G2: eens
G3: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Het herstel is akkoord. De codeblok-fix (X1/G2/K2) en de nood naar Claude in plaats van Mehdi (G3/K5) zijn aangenomen. X5 is niet aangenomen.

Ik heb in deze ronde zelf geen bestanden gelezen en niets gedraaid. Mijn oordeel steunt op de drie meningen hierboven en op wat ik in ronde 0 al had gezien.

**Codeblokken (X1, G2, K2): eens, ernst middel**
Mehdi merkt: de Namenwacht pauzeert niet meer zonder reden als er een voorbeeld met `## C.` in het boek staat. Hij hoeft dan ook geen vraag meer te beantwoorden. Een pauze blijft de veilige uitkomst, dus dit is geen blokkerend gat.
Aanvulling op Codex en Gemini: K2 ziet meer dan de twee anderen. Een kop zonder letter, zoals "## Wijzigingslog" onder B, wordt nu bij B gerekend. Dat moet ook een grens worden. Houd bij het toggelen van codeblokken rekening met zowel ``` als ~~~. Een sluitende fence moet gelijk of langer zijn dan de openende.
Techniek voor Claude: naamstructuur.py:455-464 - fence-toggle toevoegen, elke `## `-kop buiten een codeblok als grens nemen, alleen A en B meenemen, plus tests voor codeblok en changelog onder B.

**Waar gaat de nood heen (X5, G3, K5): X5 oneens, G3 en K5 eens, ernst middel**
Mehdi merkt: hij krijgt geen vraag meer waar hij niets mee kan. Hij keurt het boek zelf al goed. Het nakijken van de machinevertaling en het bijwerken van de hash is werk voor Claude. Mehdi ziet de status nog wel op het dashboard.
Correctie op G3: de tekst "gaat direct naar Claude" is te kaal. Als Claude een echte tegenspraak in de regels vindt, gaat dat alsnog naar Mehdi. De melding moet ook de oude en nieuwe hash en de versie bevatten.
Techniek voor Claude: naamstructuur_ronde.py:53-57 - doel `claude-code` bij `bron.get("gevonden")`, tekst met versie en beide hashes.

**Veilig pauzeren en versiesortering (X2, X3, K1, K3): eens, ernst laag**
Mehdi merkt: de Namenwacht toetst H-A weer met v1.10. Hij pauzeert bij een ontbrekende, oudere of onleesbare bron. v1.10 telt terecht als hoger dan v1.9. Bij X2 is de smalle kopvorm acceptabel, want een afwijkende kop pauzeert.
Techniek voor Claude: naamstructuur.py:478-521 - geen aanpassing nodig. Eventueel een test voor v1.9 tegenover v1.10 en voor een afwijkende kopvorm.

**Cache, force en herbeoordeling (X4, K4): eens, ernst laag**
Mehdi merkt: een nieuwe versie wordt direct gezien. Een ongeldige stand wordt niet gecachet, dus een gewijzigd hoofdstuk wordt elk kwartier opnieuw gedownload (maximaal 500 kB). Dat is geen veiligheidsrisico. Wel moet de nood niet elk kwartier opnieuw ontstaan. Ik heb dat niet geverifieerd.
Techniek voor Claude: naamstructuur_ronde.py:44-46 en naamstructuur.py:511-521 - test dat een herhaalde ronde geen nieuwe nood maakt.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
X5: oneens
G1: eens
G2: eens
G3: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Claude

**Besluit: twaalf punten zijn aangenomen en worden zelfstandig uitgevoerd. Eén punt is afgewezen. Er is geen vraag aan Mehdi.**

Voor Mehdi:
- Alle drie de AI's waren het eens over alle aangenomen punten, dus 3-0.
- De Namenwacht controleert H-A-mappen weer normaal en blokkeert niet meer onnodig.
- Een codevoorbeeld met `## B.` in het boek kan de agent niet meer in de war brengen.
- Bij een echte regelwijziging in hoofdstuk A of B gaat de melding direct naar Claude.
- Verwijderen, versturen en ondertekenen blijven bij Mehdi. Daar is nu geen concrete handeling voor.

**Technische details (voor Claude/Shaniel)**

De deelnemers lazen de bronbestanden in `mijnagents-runner/koppelingen/`. De verwijzingen hieronder komen uit hun bevindingen.

Aangenomen, met aanpassing nodig:
- **X1**: `naamstructuur.py:448-464` - herken `## A. `-koppen alleen buiten fenced codeblokken en voeg een regressietest toe.
- **K2**: `naamstructuur.py:455-461` - gebruik elke `## `-kop buiten codeblokken (``` of ~~~) als hoofdstukgrens en neem alleen A en B mee. Voeg een test toe voor een changelog onder B.
- **K5**: `naamstructuur_ronde.py:53-57` - stuur de nood naar `"claude-code"`. Neem de oude en nieuwe hash en de versie op, met de tekst "hoofdstuk A of B gewijzigd in v1.x, vertaling nakijken en pin bijwerken". Het dashboard (`naamstructuur.html:28`) toont de status al.
- **G2**: wordt opgelost door de aanpassing bij X1 en K2.
- **G3**: wordt opgelost door K5.

Aangenomen, vooral bevestiging of testdekking:
- **X2**: `naamstructuur.py:456-464` - eventueel testen of documenteren dat een afwijkende kopopmaak pauzeert.
- **X3**: `naamstructuur.py:478-500` - de bestaande tests dekken versiesortering al af.
- **K3**: `naamstructuur.py:495-497` - geen aanpassing nodig, hooguit een test voor v1.9 tegenover v1.10.
- **X4**: `naamstructuur_ronde.py:44-46`, `naamstructuur.py:511-521` en `:676` - de tests dekken cache, force en behoud van open bevindingen.
- **K4**: `naamstructuur.py:511-515` en `naamstructuur_ronde.py:44-46` - controleer dat `r.nood` bij een herhaalde ronde niet elk kwartier een nieuwe melding maakt.
- **K1**: `naamstructuur.py:503-521` en `531-532` - veilig pauzeren, geen aanpassing nodig.
- **G1**: geen codewijziging. Dit volgt uit de bestaande werking, omdat v1.10 voor de agents dezelfde regels bevat als v1.7.

Afgewezen:
- **X5** (0-3): niet uitvoeren.

Open punten: geen.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-luna · low (terugval op standaard voor ontbrekende velden: geen leesbare BEZETTING-regel)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): Middel: hoofdstukkop in een codeblok wordt ten onrechte als echte kop gezien.
  Techniek voor Claude: `mijnagents-runner/koppelingen/naamstructuur.py:448-464` - parse fenced codeblokken en herken `## A. `-koppen alleen buiten codeblokken; voeg een regressietest toe.
- **X2** (3-0): Laag: hoofdstukgrenzen zijn voldoende voor de huidige bron, maar de parser is bewust smal.
  Techniek voor Claude: `naamstructuur.py:456-464` - eventueel expliciet testen/documenteren dat afwijkende kopopmaak pauzeert.
- **X3** (3-0): Laag: versies als v1.10 en v1.9 worden correct numeriek gesorteerd.
  Techniek voor Claude: `naamstructuur.py:478-500` - bestaande tests `test_oude_versie...` en `test_geen_of_alleen_oudere...` dekken dit af.
- **X4** (3-0): Laag: cache, dagelijkse force en herbeoordeling werken volgens ontwerp.
  Techniek voor Claude: `naamstructuur_ronde.py:44-46`, `naamstructuur.py:511-521`, `naamstructuur.py:676` - tests dekken cache, force en behoud van open bevindingen.
- **G1** (3-0): De Namenwacht controleert H-A-mappen weer zoals normaal. Omdat v1.10 voor de agents dezelfde regels bevat als v1.7, blokkeert hij niet meer onnodig.
- **G2** (3-0): Als iemand een codevoorbeeld in het boek plakt met `## B.`, kan de agent nu per ongeluk het verkeerde stuk tekst lezen of vastlopen.
- **G3** (3-0): Verandert iemand later écht iets aan de regels in hoofdstuk A of B, dan valt de agent jou niet meer lastig met technische vragen ("Welke versie geldt?"), maar gaat het direct naar Claude om de regels bij te werken.
- **K1** (3-0): Veilig pauzeren (Vraag 1) - ernst laag
  Techniek voor Claude: naamstructuur.py:503-521 en 531-532, geen aanpassing nodig.
- **K2** (3-0): Kop in codeblok of kop zonder letter (Vraag 2) - ernst middel
  Techniek voor Claude: naamstructuur.py:455-461 - geef elke `## `-kop buiten codeblokken (``` of ~~~) als hoofdstukgrens en neem alleen A en B mee. Voeg een test toe voor een changelog onder B.
- **K3** (3-0): Versiesortering - ernst laag
  Techniek voor Claude: naamstructuur.py:495-497, geen aanpassing nodig, hooguit een test voor v1.9 tegenover v1.10.
- **K4** (3-0): Cache, dagelijkse force en herbeoordeling - ernst laag
  Techniek voor Claude: naamstructuur.py:511-515 en naamstructuur_ronde.py:44-46. Controleer in de tests dat `r.nood` bij een herhaalde ronde niet elk kwartier een nieuwe melding maakt.
- **K5** (3-0): Waar gaat de nood heen (Vraag 3) - ernst middel
  Techniek voor Claude: naamstructuur_ronde.py:53-55 - stuur de nood naar `"claude-code"`. Neem de oude en nieuwe hash en de versie op, met als tekst "hoofdstuk A of B gewijzigd in v1.x, vertaling nakijken en pin bijwerken". Het dashboard (naamstructuur.html:28) toont de status al aan Mehdi.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
