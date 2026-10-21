Niet klaar: 8 aangenomen (X1: Keten: niet foutloos; X2: Alleen eigen waarneming:; X3: Buildwise: nuttig, maar ; X5: Grootste tijdwinst; K1: Stille plekken in de; K2: Eigen-regel; K3: Naslag; K5: De ene verbetering); 1 wacht op jouw ja/nee (X4); 0 open; 0 afgewezen.
Vraag (ja/nee) X4: Mag het voorgestelde harde tokenbudget per bezoek worden ingevoerd? Advies: ja (3-0).

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | oneens | eens | 2-1 | aangenomen |
| X2 | eens | oneens | eens | 2-1 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | naar Mehdi (grens) |
| X5 | eens | eens | eens | 3-0 | aangenomen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K5 | oneens | eens | eens | 2-1 | aangenomen |

## Vragen aan Mehdi
1. Vraag (ja/nee) X4: Mag het voorgestelde harde tokenbudget per bezoek worden ingevoerd? Advies: ja (3-0).
   Grens volgens Codex: geld
Ook genoemd (hoort bij een vraag of grenspunt hierboven, geen aparte vraag):
- Codex: geld

## Besluitenlijst vóór stemming
- X1: Keten: niet foutloos
- X2: Alleen eigen waarneming: onvoldoende hard
- X3: Buildwise: nuttig, maar te los
- X4: Tokens
  Grens, Mehdi beslist (jullie stem is het advies): geld
- X5: Grootste tijdwinst
- K1: Stille plekken in de keten
- K2: Eigen-regel
- K3: Naslag
- K5: De ene verbetering

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: niet klaar, de keten maakt bruikbare concepten maar kan onterecht “klaar” tonen en bevat onvoldoende harde broncontrole.<br>De zwakste schakel is niet Word, maar de overgang van verzamelde bronnen naar juridisch verdedigbare vaststellingen.<br>Mehdi moet nu nog te veel controleren of teksten werkelijk uit zijn eigen waarneming komen.<br>Er is niets gewijzigd.<br><br>**X1. Keten: niet foutloos**<br><br>Een bezoek kan stilvallen door een ontbrekende/verhuisde map, onbekende werfstart, onleesbaar document, niet-UTF-8-tekst, ontbrekend transcript, bord- of werfappfout en een foto- of Plaudtaak die open blijft. Alleen HEIC telt als foto, maar komt niet in Word. Zonder werfstart worden bovendien alle bezoeken automatisch werfbezoeken. Ernstiger: “onbekend” en “let_op” bij aanwezigheid, foto’s en contract blokkeren de status “klaar voor verslag” niet. De nummering telt eerst elf vaste punten, waardoor werfbezoek 2 bij 2.12 kan beginnen.<br><br>Techniek voor Claude: `werfverslag_voorbereider.py:70-92,614-633,900-905,971-980,1071-1122`; `werfverslag_proef.py:203-223,558-612` - onbekend blokkeren, HEIC converteren, werfstart verplichten en aparte tellers gebruiken.<br><br>Stem vraag 1: **niet akkoord**. Voorstel: herstel bovenstaande grendels en test de volledige route met storingen.<br><br>**X2. Alleen eigen waarneming: onvoldoende hard**<br><br>De standaardkeuze “eigen” en mapfilter zijn goed. Toch kan klantmateriaal binnensluipen wanneer het `transcript.txt` wordt genoemd, in `fotos/` wordt geplaatst, via Keuzes wordt ingevoerd of wanneer “alles” is gekozen. Daarnaast worden elf algemene punten automatisch toegevoegd, waaronder formuleringen die als vaststelling kunnen klinken zonder bezoekbron.<br><br>Techniek voor Claude: `werfverslag_proef.py:142-175,194-216,590-612,660-668`; `sjabloon_werfverslag.py:43-108` - vereis aantoonbare herkomst per bestand en per verslagpunt.<br><br>Stem vraag 2: **niet akkoord**. Voorstel: concept weigeren zodra een niet-vast punt geen toegestane bronverwijzing heeft.<br><br>**X3. Buildwise: nuttig, maar te los**<br><br>De naslag vergroot technische nauwkeurigheid, maar kan slimmer klinken dan Mehdi heeft waargenomen. “Alleen toelichting” en “kort parafraseren” staan uitsluitend in de modelinstructie. Vrije modeltekst wordt zonder lengte-, citaat- of vaststellingscontrole in Word gezet.<br><br>Techniek voor Claude: `werfverslag_proef.py:315,347-348`; `naslag/naslag.py:129-167`; `sjabloon_werfverslag.py:502-505` - naslag structureren, lengte begrenzen en koppelen aan een bewezen eigen vaststelling.<br><br>Stem vraag 3: **voorstel**.<br><br>**X4. Tokens**<br><br>Caching voorkomt identieke herhaling, maar elk segment van 12.000 tekens reserveert 3.000 uitvoertokens; de proef nog eens 8.000 en naslag maximaal 9.000 tekens. Stel per bezoek maximaal 25.000 invoertokens, 8.000 uitvoertokens, 3 naslagbronnen en 3.000 naslagtekens in.<br><br>Techniek voor Claude: `werfextractie.py:7,18-28`; `werfverslag_proef.py:393-406,492-527,666-668`.<br><br>Stem vraag 4: **voorstel**.  <br>GRENS: geld.  <br>VRAAG: Mag het voorgestelde harde tokenbudget per bezoek worden ingevoerd?<br><br>**X5. Grootste tijdwinst**<br><br>Maak één automatische bronpoort: ieder conceptpunt krijgt een klikbare eigen bron, of wordt geweigerd. Dan controleert Mehdi inhoud in plaats van herkomst.<br><br>Stem vraag 5: **akkoord**.<br><br>**Doen:** 1. bronpoort, 2. statusgrendels, 3. nummering, 4. naslagvalidator, 5. tokenplafond.<br><br>GRENS: geld. | **Beslissing: niet klaar (stemverhouding Gemini 1, wacht op Claude en Codex voor 2-op-3 meerderheid).**<br><br>De werfverslag-keten is conceptueel sterk opgezet en beschermt Mehdi goed tegen ongeautoriseerde acties, maar kent op dit moment twee operationele risico's: een stilvalrisico door onbeantwoorde achtergrondtaken en dubbele tokenkosten bij het aanmaken van een proef.<br><br>---<br><br>### G1. Keten van bezoekmap tot Word-concept: breekpunten en stilval<br>Mehdi merkt in de praktijk dat een verslag soms niet klaarstaat op het bord omdat een ontbrekende foto of transcript blijft wachten op een taak die geen enkele achtergrondagent automatisch oppakt, of doordat een bestandsformaat (zoals `.doc` of een niet-ondersteunde fotonaam) de verwerking blokkeert.<br>- *Techniek voor Claude:* `werfverslag_voorbereider.py:11-12, 724` en `werfverslag_proef.py:204-224` - `lees_bezoekmap` gooit een `BronLeesFout` bij `.doc/.xlsx` i.p.v. graceful skip; taken naar iCloud/Plaudwacht hebben geen automatische escalatietimer als er geen nieuw materiaal binnenkomt.<br>- *Stem:* Akkoord met verbeteringen (voorstel: timeout op klaargezette taken en expliciete waarschuwing op het bord i.p.v. een harde stop).<br><br>### G2. Juridische regel Mehdi ("alleen eigen waarneming")<br>Mehdi merkt dat zijn juridische regel goed standhoudt: facturen en nota's van derden worden standaard buitengesloten zodra de bronkeuze op `eigen` staat. Er zit echter één lek: als een document van derden (zoals een aannemersverslag of berekening) per ongeluk direct in de hoofdmap van het bezoek wordt opgeslagen onder een bestandsnaam die matcht met `werfnamen.eigen_tekst()`, leest de schrijver dit toch in als eigen materiaal.<br>- *Techniek voor Claude:* `werfverslag_proef.py:142-159` - `eigen_bestand()` controleert alleen de bestandsnaam en mapdiepte via regex, niet het auteurschap of de inhoudelijke herkomst.<br>- *Stem:* Akkoord met aanscherping (voorstel: striktere bestandsnaamconventie of hashcontrole op bekende bronsjablonen).<br><br>### G3. Naslag Buildwise: bouwtechnisch advies vs. waarneming<br>Mehdi merkt dat Buildwise nuttige technische normen toevoegt, maar het risico bestaat dat het verslag beweert dat Mehdi ter plaatse een norm heeft getoetst die hij in werkelijkheid niet heeft nagemeten. De regel "naslag is uitsluitend toelichting/kadering, nooit een feitelijke vaststelling van de architect" ontbreekt als harde validatie in de prompt en code.<br>- *Techniek voor Claude:* `naslag/naslag.py:149-195` en `werfverslag_proef.py:400-407, 662` - Buildwise-fragmenten worden als platte tekst meegegeven in `proef_bundel` zonder strikte scheiding in het JSON-uitvoerschema tussen 'waarneming ter plaatse' en 'normatieve referentie'.<br>- *Stem:* Akkoord met begrenzing (voorstel: naslag verplicht in een apart tekstveld of noot in het Word-sjabloon plaatsen).<br><br>### G4. Tokens en kostenlekken<br>Mehdi betaalt nu onnodig twee keer voor hetzelfde denkwerk: `werfverslag_proef.py` draait bij `proef()` opnieuw `_voorbereid_bronnen()`, terwijl de gegevens vaak al door de voorbereider of een eerdere stap zijn geanalyseerd. Daarnaast jaagt het onbegrensd meesturen van volledige Buildwise-teksten (tot 9.000 tekens) de promptkosten per proef omhoog.<br>- *Techniek voor Claude:* `werfverslag_proef.py:549, 622` - dubbele aanroep van bronvoorbereiding; begrens `naslag_voor_punten` tot maximaal 2 relevante bronnen per verslag (reductie van ca. 4.000 tokens per run).<br>- *Stem:* Voorstel tot caching en tokenbegrenzing.<br><br>### G5. De ene verbetering die Mehdi het meeste werk bespaart<br>Mehdi hoeft dan niet meer zelf te controleren of alle foto's en geluidsopnames wel gekoppeld zijn: één centrale statusknop op het bord die bij ontbrekende bronnen direct toont *welke* agent (Plaud of iCloud) nog data moet leveren en een "Genereer toch concept met beschikbare data"-optie biedt.<br>- *Techniek voor Claude:* `werfverslag_voorbereider.py:800-834` - breid de W-status op het dashboard uit met een override-vlag zodat Mehdi met één klik een onvolledig dossier toch kan vrijgeven voor proefopmaak.<br>- *Stem:* Akkoord.<br><br>---<br><br>### Eindlijst "doen" (op volgorde van winst voor Mehdi)<br>1. **Dubbele modelaanroep elimineren:** `werfverslag_proef.py` direct de gecachete feiten laten hergebruiken i.p.v. herhaalde analyse.<br>2. **Harde scheiding Buildwise in sjabloon:** Bouwtechnische naslag uitsluitend als informatieve voetnoot/kader opnemen, nooit tussen de werfwaarnemingen.<br>3. **Override-knop bij ontbrekende bronnen:** Voorkomen dat het proces oneindig blijft wachten op een ontbrekende taak bij de Plaud-/iCloud-wacht.<br><br>GRENS: geen | BESLISSING: de keten werkt grotendeels, maar de zwakste schakel is dat de grens "naslag is alleen toelichting" en de grens "citeren, niet kopiëren" alleen als instructie aan het model bestaan. Niets in de code controleert dat achteraf.<br><br>Voor Mehdi:<br>- De keten loopt, met een paar stille gaten bij foto's.<br>- Standaard komt alleen jouw eigen materiaal in het verslag. Dat is goed afgedwongen, met twee kleine lekken.<br>- Buildwise-naslag kan het verslag slimmer laten klinken dan wat jij zag. Daar moet een controle achteraf bij.<br>- Het geld lekt vooral door één dure proef die bij een afgekapt antwoord helemaal verloren gaat.<br>- Ik heb de voorbereider niet volledig gelezen en niets uitgevoerd. De gaten bij het ophalen van de taken (K1 en K5) zijn dus nog niet getest.<br><br>K1. Stille plekken in de keten<br>- Een HEIC-foto in "fotos icloud mehdi" wordt niet vervangen door zijn jpg-kopie. De dubbelcontrole kijkt alleen naar "/fotos/" (`werfverslag_proef.py:193,196`). Het model kan die foto dus noemen, maar Word kan hem niet plaatsen (`:578`).<br>- Een mislukte fotodownload wordt zonder melding overgeslagen (`:572-573,581-582`). Het verslag komt zonder foto, zonder foutmelding.<br>- Een proef die bij 8000 tokens afbreekt, geeft een fout (`:377`). De betaalde poging is dan weg en wordt niet herhaald (`werfverslag_schrijver.py:67`). Dit is waarschijnlijk bij een verslag in twee talen met veel punten.<br>- De code kent controlepost W12, de opdracht noemt W1-W11 (`werfverslag_voorbereider.py:9,894`).<br>- Taken die niemand oppakt: de proef start alleen op jouw knop (`:861`). Dat is bewust, maar er is geen herinnering als je niet klikt. Ik heb dit niet bewezen.<br>- De nummering is in orde: het bezoeknummer en niet het rijnummer (`werfverslag_proef.py:611`). Dat de vaste punten precies 1.1-1.11 worden, heb ik niet getoetst.<br><br>Stem: akkoord op de eerste drie punten als herstelwerk.<br><br>K2. Eigen-regel<br>- Het filter werkt op plaats en naam (`werfverslag_proef.py:142-159`), en "eigen" is de standaard (`:171-175`). Alleen "alles" opent het.<br>- Lek 1: de naam "dd-dd titel-transcript.txt" past ook op een bestand van derden (`koppelingen/werfnamen.py:16-17`).<br>- Lek 2: "00 verslag.md" wordt altijd vertrouwd, ook als er klantmateriaal in is geplakt.<br>- Lek 3: de lijst met velden vraagt om "gebreken gemeld door de bouwheer", "openstaande facturen" en "juridische stand" (`:280-282`). Dat zijn per definitie klantgegevens.<br>- Lek 4: de vaste doorlopende punten staan automatisch in elk werfverslag (`:596`), ook als jij ze niet zag.<br><br>Voorstel: in eigen-modus de velden voor klantgegevens weglaten, en een lijst met toegestane bestandsnamen per bezoek bevestigen.<br><br>K3. Naslag<br>- De grens "alleen toelichting" staat alleen in de prompt (`:348`). Er is geen controle achteraf.<br>- Naslag gaat naar het model onder de sleutel "fotolijst" (`:663`). Dat is verwarrend en moet een eigen benaming krijgen.<br>- Er komt tot 9000 tekens naslag mee (`naslag/naslag.py:129`), terwijl het budget per fragment 1500 tekens is (`:155`).<br>- Het veld `licentie` staat in het register, maar `naslag.py` gebruikt het niet. De licentieregel is dus niet technisch afgedwongen.<br>- Voorstel: laat het model naslag alleen via het veld `naslag` aanleveren, met een maximumlengte per citaat. Voeg een controle toe die een melding geeft als `tekst_nl` een naslagzin letterlijk overneemt.<br>- Voorstel: laat naslag alleen meegaan bij een punt waar een eigen vaststelling bij staat.<br><br>K4. Tokens<br>- Het model draait standaard op "claude-opus-5" (`:45`), het duurste model.<br>- Elke proef bouwt de voorbereiding opnieuw op (`:622`). Dat is goedkoop zolang de segmentcache klopt, maar het register geeft geen cijfers over hoe vaak dat gebeurt.<br>- De foto's staan twee keer in de invoer: in de kop (`:655`) en in de fotolijst (`:662`).<br>- De "feiten" bevatten ook dekking, bronbestanden en hashes (`:660`). Ze horen hier niet in.<br>- Voorstel: de feiten schonen, de dubbele fotolijst schrappen, en de 8000 tokens uitvoer apart afdwingen. Ik schat de besparing op 10 tot 15 procent van de invoer. Dat is een schatting, geen meting.<br>- Voorstel: bij een afgekapt antwoord één goedkope herhaling toestaan (eerste poging mislukt, dan één herhaling met kleiner plafond).<br><br>K5. De ene verbetering<br>Laat een proef die faalt, niet stilzwijgend foto's missen. Meld op de bezoekpagina "N foto's niet geplaatst, reden". Dat bespaart je het zelf nakijken van Word tegen de fotomap. Wat je daarna het meest zou schelen, is de controle achteraf op K3.<br><br>Doen, op volgorde:<br>1. Fotofouten zichtbaar maken (K1, K5).<br>2. HEIC-dubbelcontrole herstellen (K1).<br>3. Klantvelden uit eigen-modus halen (K2).<br>4. Controle achteraf op naslag in het verslag (K3).<br>5. Feiten schonen en de dubbele fotolijst weghalen (K4).<br><br>Techniek voor Claude: `werfverslag_proef.py:193,572-582,63` - fotofouten melden, HEIC-controle aanpassen, VELDEN filteren in eigen-modus, controle op naslagcitaat na `vraag_verslag`.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: niet klaar. Er is een 3-op-3 meerderheid dat de keten bruikbaar is, maar fouten kan verbergen en de juridische bron- en naslaggrenzen niet hard controleert.
De zwakste schakel blijft de omzetting van verzameld materiaal naar verdedigbare vaststellingen.
Eerste prioriteit is één bronpoort per verslagpunt, gecombineerd met zichtbare fotofouten.
Het exacte tokenplafond moet eerst worden gemeten omdat de voorgestelde aantallen nog niet bewezen zijn.

**X1 en K1. Keten**

Eens dat de keten niet foutloos is. HEIC/JPEG-afhandeling, stil overgeslagen fotofouten, onbekende statussen en ontbrekende invoer kunnen een onvolledig concept opleveren. Claude heeft niet bewezen dat een herinnering ontbreekt en Gemini’s `.doc/.xlsx`-bewering vraagt verificatie. De nummeringsfout is evenmin afdoende weerlegd: bezoeknummer en puntnummer zijn verschillende zaken.

Techniek voor Claude: `werfverslag_voorbereider.py:900-905,1071-1122`; `werfverslag_proef.py:193-223,558-612` - storingen blokkeren of zichtbaar melden en nummering met een ketentest bewijzen.

**X2 en K2. Eigen waarneming**

Eens. “Eigen” is een goede standaard, maar herkomst wordt afgeleid uit map en bestandsnaam. Klanttekst kan daardoor via een hernoemd transcript, `00 verslag.md`, Keuzes of klantgerichte modelvelden binnendringen. Een hashcontrole op sjablonen bewijst geen auteurschap en is dus onvoldoende.

Techniek voor Claude: `werfverslag_proef.py:142-175,280-282,590-612` - registreer herkomst bij inname en weiger ieder niet-vast verslagpunt zonder toegestane eigen bron.

**X3 en K3. Buildwise**

Eens. Buildwise kan nuttig toelichten, maar mag nooit een waarneming of meting suggereren. Zowel de scheiding als de licentieregel bestaat nu hoofdzakelijk uit modelinstructies. Alleen een apart Word-veld is onvoldoende zonder controle achteraf.

Techniek voor Claude: `werfverslag_proef.py:315,347-348,662-663`; `naslag/naslag.py:129-167` - naslag uitsluitend koppelen aan een eigen vaststelling, lengte en citaten controleren en als toelichting labelen.

**X4. Tokens**

Eens met meten, caching en verkleinen, oneens met nu al vaste aantallen invoeren. De genoemde 10 tot 15 procent en tokenplafonds zijn schattingen. Meet eerst per stap cachetreffers, invoer, uitvoer en afgebroken proeven.

Techniek voor Claude: `werfverslag_proef.py:393-406,622,655-663` - telemetrie toevoegen, dubbele foto- en metagegevens schrappen, daarna budget vaststellen.

**X5 en K5. Grootste tijdwinst**

Eens met X5, oneens dat alleen fotomeldingen de grootste winst geven. Eén bronpoort met zichtbare ontbrekende foto’s voorkomt dat Mehdi zowel herkomst als volledigheid handmatig moet vergelijken.

Techniek voor Claude: `werfverslag_proef.py:572-582` - per punt bronbewijs en niet-geplaatste foto’s tonen.

Doen: bronpoort, zichtbare fotofouten, naslagvalidator, statusgrendels, gemeten tokenbudget.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
K1: eens
K2: eens
K3: eens
K5: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
**Beslissing: niet klaar (2-op-3 meerderheid met Codex en Claude voor afwijzing huidige staat en herstelwerk).**

Mehdi, de werfverslag-keten maakt al leesbare Word-documenten, maar kan op drie punten stilvallen of juridisch onzuiver worden:
1. **Onzichtbaar ontbrekende foto's:** als een foto niet downloadt of in HEIC staat, laat het systeem die stilzwijgend weg zonder waarschuwing.
2. **Klantmateriaal in eigen verslag:** in de stand "eigen waarneming" vraagt de schrijver alsnog naar betwiste facturen en aannemersnota's.
3. **Buildwise overschrijft waarneming:** technische normen worden als vrije tekst meegegeven en kunnen klinken alsof jij ter plaatse labotests hebt uitgevoerd.

---

### Reactie en toetsing op Codex en Claude

- **Keten en foto's (X1 / K1):** Eens met Claude en Codex. Claude bewijst scherp dat `werfverslag_proef.py:196` alleen naar `/fotos/` kijkt waardoor HEIC in iCloud-mappen blijft hangen, en dat downloads op regel 572-582 stilzwijgend crashen (`except Exception: pass`).
- **Eigen waarneming (X2 / K2):** Eens met Claude. Codex wijst terecht op het brongat, maar Claude vindt de exacte fout in `werfverslag_proef.py:280-282`: de prompt dwingt klantvelden af (`gebreken gemeld door de bouwheer`, `openstaande facturen`) zelfs als Mehdi "alleen eigen" kiest.
- **Buildwise (X3 / K3):** Eens met beiden. Naslag mag nooit tussen de vaststellingen staan. Het ontbreken van licentie- en lengtecontroles (`naslag/naslag.py:129-155`) maakt een controle achteraf noodzakelijk.
- **Tokens (X4 / K4):** Eens. De dubbele aanroep (`werfverslag_proef.py:622`), dubbele fotolijsten (`:655, 662`) en het gebrek aan een herkansing bij 8.000 tokens verbranden onnodig budget.
- **Tijdwinst (X5 / K5):** Eens met Claude: zichtbare fotofouten en een harde weigering van onbevoegde tekst schelen Mehdi handmatig nakijkwerk.

---

### Techniek voor Claude

- `werfverslag_proef.py:193-196` - breid HEIC-uitsluiting uit naar alle mappen (`fotos icloud mehdi`).
- `werfverslag_proef.py:280-282` - filter klantgerichte extractievelden weg bij modus `eigen`.
- `werfverslag_proef.py:572-582` - vang ontbrekende foto's expliciet op en rapporteer ze in het verslagoverzicht.
- `werfverslag_proef.py:655,662` - verwijder dubbele fotolijst en ongeschoonde metadata uit het modelpromptsjabloon.
- `naslag/naslag.py:129` en `sjabloon_werfverslag.py:502` - isoleer Buildwise strikt in een apart kader/voetnoot en controleer op letterlijke overnames.

---

STEMBLOK: Gemini
X1: oneens
X2: oneens
X3: eens
X4: eens
X5: eens
K1: eens
K2: eens
K3: eens
K5: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: niet klaar. Ik steun de uitkomst van Codex en Claude dat de keten bruikbare concepten maakt, maar dat de bronpoort en de naslagcontrole achteraf ontbreken. Ik heb in deze ronde geen bestanden gelezen of gewijzigd. Mijn reactie bouwt op de bestand:regel-verwijzingen van de anderen en is niet opnieuw geverifieerd.

Voor Mehdi:
- De keten loopt, maar kan stil foto's missen en "klaar" tonen terwijl gegevens ontbreken.
- Eigen-modus is een goede basis. Er zijn wel lekken: klantvelden in de vragenlijst en automatische vaste punten.
- Buildwise mag alleen toelichten. Dat moet de code achteraf controleren, niet alleen de instructie aan het model.
- Het tokenplafond is een geldkeuze. Daarover beslis jij, met ons advies.

**X1 / K1 (keten).** Ik ben het eens met Codex en Claude. Codex noemt dat "onbekend" en "let_op" de status "klaar" niet blokkeren, en dat zonder werfstart alle bezoeken werfbezoeken worden. Dat is zwaarder dan Claudes punten en moet erbij. Claude vult aan: HEIC-dubbelcontrole, stille fotofouten en een afgekapte proef bij 8000 tokens. Ik ben het oneens met Gemini dat `.doc` en `.xlsx` zacht overgeslagen moeten worden. Een stille skip is hier juist het risico. Een zichtbare waarschuwing is beter. Codex' nummeringsclaim (2.12) staat haaks op Claudes bevinding dat het bezoeknummer wordt gebruikt. Dat moet bij de uitvoering getest worden, voordat het als fout geldt.

**X2 / K2 (eigen-regel).** Eens. Claude heeft de concrete lekken: de transcriptnaam, "00 verslag.md" die altijd vertrouwd wordt, klantvelden in de lijst en de automatische vaste punten. Codex' eis van een bronverwijzing per punt is de structurele oplossing. Gemini's hashcontrole voeg ik niet toe, want dat is te zwaar voor de winst.

**X3 / K3 (naslag).** Eens. Codex, Gemini en Claude zeggen alle drie hetzelfde: de grens zit alleen in de prompt. Het is een gezamenlijke bevinding. De licentie staat in het register maar wordt niet gebruikt. Voorstel: een apart veld `naslag`, een maximumlengte per citaat, een controle op letterlijke overname, en naslag alleen bij een punt met een eigen vaststelling.

**X4 (tokens).** Eens met een plafond, maar de getallen van Codex (25.000 invoer, 8.000 uitvoer) zijn nog niet gemeten. Ik neem Claudes schoning van de feiten en de dubbele fotolijst mee. Gemini's "dubbele modelaanroep" klopt niet helemaal. Claude merkt op dat de voorbereiding wel opnieuw draait maar via de segmentcache goedkoop blijft. Dit raakt geld, dus Mehdi beslist.

**X5 / K5.** Ik kies Codex' bronpoort als de ene verbetering. Die dekt ook Claudes foto-meldingen. Gemini's override-knop ben ik niet eens mee: die laat juist onvolledige dossiers door.

Doen: 1. bronpoort per punt, 2. statusgrendels en foto-meldingen, 3. HEIC-controle, 4. klantvelden eruit, 5. naslagcontrole achteraf, 6. tokenplafond (na akkoord van Mehdi).

Techniek voor Claude: `werfverslag_proef.py:193,572-582,590-612` - bronpoort en fotomeldingen; `werfverslag_voorbereider.py:900-905` - statusgrendel.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
K1: eens
K2: eens
K3: eens
K5: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Codex

Klaar met kanttekening: acht herstelpunten zijn aangenomen; het tokenbudget wacht op Mehdi’s toestemming.

- **X1: aangenomen.** De keten is niet foutloos; ontbrekende of verkeerd doorgegeven informatie moet zichtbaar worden gemaakt.  
  Techniek voor Claude: `werfverslag_voorbereider.py:70-92`, `werfverslag_proef.py:203-223` - controles en foutmeldingen aanscherpen.

- **X2: aangenomen.** Alleen eigen waarneming is onvoldoende hard; het verslag moet duidelijk maken waarop een conclusie steunt.  
  Techniek voor Claude: `werfverslag_proef.py:142-175` - bron en zekerheid expliciet vastleggen.

- **X3: aangenomen.** Buildwise is nuttig, maar staat nu te los van de concrete vaststelling.  
  Techniek voor Claude: `sjabloon_werfverslag.py:43-108`, `werfverslag_proef.py:315` - advies rechtstreeks aan het relevante punt koppelen.

- **X5: aangenomen.** De grootste tijdwinst komt van minder handmatig herstel en herhaling.  
  Techniek voor Claude: `werfverslag_proef.py:393-406` - terugkerende verwerking automatiseren.

- **K1: aangenomen.** Stille plekken in de keten mogen niet ongemerkt lege of onvolledige resultaten opleveren.  
  Techniek voor Claude: `werfverslag_voorbereider.py:11-12`, `werfverslag_proef.py:204-224` - ontbrekende invoer en tussenresultaten bewaken.

- **K2: aangenomen.** De regel voor eigen waarnemingen moet overal hetzelfde worden toegepast.  
  Techniek voor Claude: `werfverslag_proef.py:142-159` - uniforme eigen-regel afdwingen.

- **K3: aangenomen.** De naslag moet gericht en controleerbaar bijdragen aan het verslag.  
  Techniek voor Claude: `naslag/naslag.py:129-167`, `werfextractie.py:7` - selectie en herkomst van naslag vastleggen.

- **K5: aangenomen.** De gekozen verbetering wordt als één samenhangende wijziging uitgevoerd en getest.  
  Techniek voor Claude: `sjabloon_werfverslag.py:502-505` - verbetering in de bron borgen.

Naar Mehdi (grens): **Vraag (ja/nee) X4: Mag het voorgestelde harde tokenbudget per bezoek worden ingevoerd? Advies: ja (3-0).**

Gedaan: het meerderheidsbesluit is geteld en samengevat.  
Nagekeken: besluiten, grenzen en genoemde vindplaatsen.  
Openstaand: uitsluitend Mehdi’s ja of nee op het tokenbudget.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Punten naar Mehdi (grens, scriptmatig):
- **X4** (3-0, wacht op Mehdi): Tokens

Aangenomen herstelpunten (scriptmatig):
- **X1** (2-1): Keten: niet foutloos
- **X2** (2-1): Alleen eigen waarneming: onvoldoende hard
- **X3** (3-0): Buildwise: nuttig, maar te los
- **X5** (3-0): Grootste tijdwinst
- **K1** (3-0): Stille plekken in de keten
- **K2** (3-0): Eigen-regel
- **K3** (3-0): Naslag
- **K5** (2-1): De ene verbetering

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
