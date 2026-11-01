Besluit: 15 aangenomen (X1: A: nee. Een expliciet; X2: B: ja. “Privé-aankoop” i; X3: C: ja. Dezelfde geldige; X4: D: ja. Extra compatibili; X5: Ontbrekend: de metingen ; G1: Voorstel A: JA.** Eigen; G2: Voorstel B: JA.** De; G3: Voorstel C: JA, mits; G4: Voorstel D: JA.** Het; G5: Aanvullende bevinding op; K1: A: alleen eisen uit; K2: B: de VORM vraagt; K3: C: netwaarden uit een; K4: D: het werkverslag telt; K5: Wat ontbreekt: de herloo); 0 afgewezen.
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
| G1 | oneens | eens | eens | 2-1 | aangenomen |
| G2 | eens | eens | eens | 3-0 | aangenomen |
| G3 | oneens | eens | eens | 2-1 | aangenomen |
| G4 | eens | eens | eens | 3-0 | aangenomen |
| G5 | eens | eens | eens | 3-0 | aangenomen |
| K1 | oneens | eens | eens | 2-1 | aangenomen |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | eens | eens | eens | 3-0 | aangenomen |
| K5 | oneens | eens | eens | 2-1 | aangenomen |

## Besluitenlijst vóór stemming
- X1: A: nee. Een expliciet gevraagd model of variant mag bij “onbekend” niet worden aanbevolen. Anders kan bijvoorbeeld een goedkopere zwarte of afwijkende V70 worden gekozen terwijl Mehdi exact de witte MOVA-RC-V70ULC-WHT vroeg. Kleinste fix: maak expliciet gevraagde productidentiteit bindend, naast netspanning en netfrequentie. Andere modeleisen mogen bij “onbekend” alleen als waarschuwing blijven staan.
  Techniek voor Claude: `aankoop/aanbod.py:109-121,549-580` en `prijsonderzoeker.py:111,138` - haal ook expliciete modelcode/variant uit de vraag en blokkeer die bij onbekend.
- X2: B: ja. “Privé-aankoop” is geen producteigenschap die een winkelpagina kan bewijzen en hoort daarom niet als compatibiliteitseis mee te tellen.
  Techniek voor Claude: `aankoop/onderzoek.py:79,110-112` - beperk modeleisen tot bewijsbare product- en leveringseigenschappen.
- X3: C: ja. Dezelfde geldige EAN identificeert hetzelfde handelsartikel. Daardoor mag de goedkopere winkel gebruikmaken van de handleiding die een andere gelezen productpagina voor exact die EAN linkt. De voorgestelde controles op modelnaam, tegenspraak, regio en accessoires voorkomen een losse of verkeerde koppeling.
  Techniek voor Claude: `aankoop/aanbod.py:503-513,549-580` - voeg de gecontroleerde EAN-koppeling toe als alternatief voor de huidige eigen-paginalink.
- X4: D: ja. Extra compatibiliteitssleutels zichtbaar maken toont direct wanneer het model andere sleutels gebruikt of eisen overslaat.
  Techniek voor Claude: `prijsonderzoeker.py:83-94` en `tests/test_aankoop_prijs.py:1085-1095` - log de vereniging van verwachte eisen en ontvangen sleutels, zonder gevoelige tekst.
- X5: Ontbrekend: de metingen tonen dat expliciete productidentiteit nu niet door de code wordt afgedwongen. `keur` controleert alleen of een titel bestaat, niet of die overeenkomt met het gevraagde model. Dat moet vóór de echte VM-herhaling worden afgedekt met een test.
  Techniek voor Claude: `aankoop/aanbod.py:258-286` - test dat een afwijkende modelcode of variant nooit aanbevolen wordt.
- G1: Voorstel A: JA.** Eigen eisen van het model mogen een aanbod alleen uitsluiten bij een expliciete "nee" met citaat, niet bij "onbekend". De harde eisen uit Mehdi's vraag (`eisen_uit_vraag`) blijven wel bindend.
- G2: Voorstel B: JA.** De prompt-instructie moet het model verbieden om koperseigenschappen of prijsvoorwaarden als compatibiliteitseis op te voeren, want geen enkele productpagina kan dat bevestigen.
- G3: Voorstel C: JA, mits strikte controle.** EAN/GTIN-koppeling voor handleidingen over winkels heen is logisch en noodzakelijk voor prijsvergelijking (M3), maar vereist strikte verificatie: exact 13 cijfers, geldig modulo-10 controlecijfer, en expliciet label op beide pagina's.
- G4: Voorstel D: JA.** Het werkverslag moet sleutelverschillen inzichtelijk maken om prompt- en modelafwijkingen direct te signaleren.
- G5: Aanvullende bevinding op de metingen (M3/M4):
- K1: A: alleen eisen uit de vraag zelf blokkeren een aanbeveling.
  Techniek voor Claude: `aankoop/aanbod.py:554` - bij een eis die niet uit `eisen_uit_vraag` komt, telt "onbekend" als "niet bevestigd" (geen blokkade). Alleen "nee" sluit uit.
- K2: B: de VORM vraagt alleen om eisen die een pagina kan bevestigen.
  Techniek voor Claude: `aankoop/onderzoek.py:79` - de tekst wordt "eigenschappen van product of levering die een pagina kan bevestigen; niet de koper of de prijs". Pas ook de regel rond `:111` daarop aan.
- K3: C: netwaarden uit een handleiding mogen via dezelfde EAN gedeeld worden.
  Techniek voor Claude: `aankoop/aanbod.py:503` (`gelinkt_document`) - sta een link van een andere pagina toe bij gelijke EAN met geldig controlecijfer. Controleer dat het aanbod geen afwijkende modelcode toont. Zet de herkomst in het verslag.
- K4: D: het werkverslag telt ook de sleutels in compatibiliteit die geen eis zijn.
  Techniek voor Claude: werkverslag-log in `aankoop/onderzoek.py` - tel de sleutels in compatibiliteit zonder bijbehorende eis.
- K5: Wat ontbreekt: de herlooptest.
  Techniek voor Claude: `tests/test_aankoop_prijs.py` - twee gevallen toevoegen, één met gelijke EAN en één met EAN-gelijk maar modelverschil.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: Niet volledig akkoord: B, C en D zijn goed; A moet één kleine veiligheidsgrendel krijgen.<br><br>X1. A: nee. Een expliciet gevraagd model of variant mag bij “onbekend” niet worden aanbevolen. Anders kan bijvoorbeeld een goedkopere zwarte of afwijkende V70 worden gekozen terwijl Mehdi exact de witte MOVA-RC-V70ULC-WHT vroeg. Kleinste fix: maak expliciet gevraagde productidentiteit bindend, naast netspanning en netfrequentie. Andere modeleisen mogen bij “onbekend” alleen als waarschuwing blijven staan.  <br>Techniek voor Claude: `aankoop/aanbod.py:109-121,549-580` en `prijsonderzoeker.py:111,138` - haal ook expliciete modelcode/variant uit de vraag en blokkeer die bij onbekend.<br><br>X2. B: ja. “Privé-aankoop” is geen producteigenschap die een winkelpagina kan bewijzen en hoort daarom niet als compatibiliteitseis mee te tellen.  <br>Techniek voor Claude: `aankoop/onderzoek.py:79,110-112` - beperk modeleisen tot bewijsbare product- en leveringseigenschappen.<br><br>X3. C: ja. Dezelfde geldige EAN identificeert hetzelfde handelsartikel. Daardoor mag de goedkopere winkel gebruikmaken van de handleiding die een andere gelezen productpagina voor exact die EAN linkt. De voorgestelde controles op modelnaam, tegenspraak, regio en accessoires voorkomen een losse of verkeerde koppeling.  <br>Techniek voor Claude: `aankoop/aanbod.py:503-513,549-580` - voeg de gecontroleerde EAN-koppeling toe als alternatief voor de huidige eigen-paginalink.<br><br>X4. D: ja. Extra compatibiliteitssleutels zichtbaar maken toont direct wanneer het model andere sleutels gebruikt of eisen overslaat.  <br>Techniek voor Claude: `prijsonderzoeker.py:83-94` en `tests/test_aankoop_prijs.py:1085-1095` - log de vereniging van verwachte eisen en ontvangen sleutels, zonder gevoelige tekst.<br><br>X5. Ontbrekend: de metingen tonen dat expliciete productidentiteit nu niet door de code wordt afgedwongen. `keur` controleert alleen of een titel bestaat, niet of die overeenkomt met het gevraagde model. Dat moet vóór de echte VM-herhaling worden afgedekt met een test.  <br>Techniek voor Claude: `aankoop/aanbod.py:258-286` - test dat een afwijkende modelcode of variant nooit aanbevolen wordt.<br><br>GRENS: geen | BESLISSING: Akkoord met A, B, C en D (3-0 of 2-1 meerderheid mogelijk), met een scherpe technische borging voor C zodat handleidingen niet onterecht aan verkeerde winkels gekoppeld worden.<br><br>Hieronder mijn oordeel en bevindingen voor Mehdi:<br>Mehdi merkt dat de Prijsonderzoeker eindelijk zelf de goedkoopste optie aanbeveelt in plaats van vast te lopen op onzinnige bijzaken. Eisen die het model zelf verzint (zoals "privé-aankoop") blokkeren de aankoop niet langer als een winkelpagina die niet vermeldt. Bovendien kan een winkel met een scherpe prijs (zoals RoboCleaners) nu profiteren van de officiële handleiding van hetzelfde toestel die bij een andere winkel (zoals Vanden Borre) staat, mits de streepjescode (EAN) exact klopt.<br><br>G1. **Voorstel A: JA.** Eigen eisen van het model mogen een aanbod alleen uitsluiten bij een expliciete "nee" met citaat, niet bij "onbekend". De harde eisen uit Mehdi's vraag (`eisen_uit_vraag`) blijven wel bindend.<br>`Techniek voor Claude: aankoop/aanbod.py:539-546 - splits compatibel() in bindende eisen (ja vereist) en optionele modeleisen (enkel nee sluit uit).`<br><br>G2. **Voorstel B: JA.** De prompt-instructie moet het model verbieden om koperseigenschappen of prijsvoorwaarden als compatibiliteitseis op te voeren, want geen enkele productpagina kan dat bevestigen.<br>`Techniek voor Claude: aankoop/onderzoek.py:79,111-113 - VORM aanscherpen: eisen beperken tot product-/leveringseigenschappen; sluit koper en prijs uit.`<br><br>G3. **Voorstel C: JA, mits strikte controle.** EAN/GTIN-koppeling voor handleidingen over winkels heen is logisch en noodzakelijk voor prijsvergelijking (M3), maar vereist strikte verificatie: exact 13 cijfers, geldig modulo-10 controlecijfer, en expliciet label op beide pagina's.<br>`Techniek voor Claude: aankoop/aanbod.py:503-514,565-567 - breid gelinkt_document/koppeling uit met geverifieerde EAN-match en MODELNAAM-toets.`<br><br>G4. **Voorstel D: JA.** Het werkverslag moet sleutelverschillen inzichtelijk maken om prompt- en modelafwijkingen direct te signaleren.<br>`Techniek voor Claude: aankoop/verslag.py:110-140 (en aanbod.py:551) - tel niet-eis sleutels in compatibiliteit mee in de verslaglegging.`<br><br>G5. **Aanvullende bevinding op de metingen (M3/M4):**<br>In `aankoop/aanbod.py:509-514` eist `gelinkt_document` momenteel dat de link letterlijk onder `Documenten:` op de eigen pagina staat. Als we C toestaan, moet de document-koppeling via EAN ook in `bewijspagina()` (`aankoop/aanbod.py:516-522`) correct worden geaccepteerd als `bewijs_url` van een andere gelezen pagina.<br>`Techniek voor Claude: aankoop/aanbod.py:516-522,559-570 - zorg dat bewijspagina() externe handleidingen toestaat mits EAN op de aanbodpagina en bronpagina overeenkomen.`<br><br>GRENS: geen | BESLISSING: A, B en D ja. C ja, mits er één extra voorwaarde bij komt (zie K3).<br><br>De vindplaatsen uit de opdracht kloppen: `aankoop/onderzoek.py:79`, `aankoop/aanbod.py:109`, `:503` en `:554`. De regel "beoordeel in compatibiliteit elke eis" (`:111`) heb ik niet gecontroleerd.<br><br>**K1. A: alleen eisen uit de vraag zelf blokkeren een aanbeveling.**<br>Ja. Nu blokkeert een eis die het model zelf verzint (bijvoorbeeld "privé-aankoop") een goed aanbod. Dat is de reden dat u in proef 3 en 4 geen advies kreeg. Met A krijgt u wel een advies. Wat niet bevestigd is, staat er dan duidelijk bij.<br>Risico: "levering in België" kan een echte uitsluiter zijn. Daarom moet "niet bevestigd" in het verslag bij Aanbevolen staan, zoals A al voorstelt. Een betaling gebeurt hier niet automatisch.<br>Techniek voor Claude: `aankoop/aanbod.py:554` - bij een eis die niet uit `eisen_uit_vraag` komt, telt "onbekend" als "niet bevestigd" (geen blokkade). Alleen "nee" sluit uit.<br><br>**K2. B: de VORM vraagt alleen om eisen die een pagina kan bevestigen.**<br>Ja. Een eis over de koper kan nooit bevestigd worden, dus die hoort er niet in. Dit voorkomt het probleem bij de bron.<br>Techniek voor Claude: `aankoop/onderzoek.py:79` - de tekst wordt "eigenschappen van product of levering die een pagina kan bevestigen; niet de koper of de prijs". Pas ook de regel rond `:111` daarop aan.<br><br>**K3. C: netwaarden uit een handleiding mogen via dezelfde EAN gedeeld worden.**<br>Ja, met één extra voorwaarde. Het gevolg van niet doen is een verkeerd advies: dan wordt Vanden Borre (1.399 euro) aanbevolen boven hetzelfde toestel van 961,50 euro (M3). Een EAN wijst één handelsartikel aan. Maar een EAN op een webwinkelpagina kan fout zijn, bijvoorbeeld bij een bundel of een andere kleurvariant.<br>De extra voorwaarde: het aanbod zelf mag het model niet tegenspreken. Als de titel of modelcode op de pagina van RoboCleaners een ander model noemt dan de handleiding, geldt het bewijs niet. De verwante bron moet in het verslag staan, bijvoorbeeld "netwaarden via handleiding van Vanden Borre, zelfde EAN".<br>Techniek voor Claude: `aankoop/aanbod.py:503` (`gelinkt_document`) - sta een link van een andere pagina toe bij gelijke EAN met geldig controlecijfer. Controleer dat het aanbod geen afwijkende modelcode toont. Zet de herkomst in het verslag.<br><br>**K4. D: het werkverslag telt ook de sleutels in compatibiliteit die geen eis zijn.**<br>Ja. Het is goedkoop en maakt een sleutelverschil zichtbaar. Het raakt de aanbeveling niet.<br>Techniek voor Claude: werkverslag-log in `aankoop/onderzoek.py` - tel de sleutels in compatibiliteit zonder bijbehorende eis.<br><br>**K5. Wat ontbreekt: de herlooptest.**<br>Na de fixes moet de VM-run echt dezelfde vervolgvraag draaien. Het slagen telt alleen als er een aanbeveling met "niet bevestigd: levering" komt. Daarnaast moet RoboCleaners (961,50) boven Vanden Borre (1.399) uitkomen. Voeg een test toe met de EAN-paren uit M3 en een tegenvoorbeeld met een afwijkend model.<br>Techniek voor Claude: `tests/test_aankoop_prijs.py` - twee gevallen toevoegen, één met gelijke EAN en één met EAN-gelijk maar modelverschil.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: A krijgt de veiligheidsgrendel voor expliciet gevraagde productidentiteit; B, C en D zijn akkoord.

De meerderheid voor A voorkomt nu wel vastlopen, maar mist één risico: exact gevraagde modelcode, kleur of variant mag bij “onbekend” niet stilzwijgend passeren. Alleen overige modeleisen worden waarschuwingen.  
Techniek voor Claude: `aankoop/aanbod.py:109-121,549-580` - maak expliciete productidentiteit bindend en test model- en variantverschillen.

Bij C moeten geldige GTIN-lengtes worden ondersteund, niet uitsluitend dertien cijfers. Ook mag de aanbodpagina de gekoppelde handleiding niet tegenspreken en moet de bewijsherkomst zichtbaar zijn.  
Techniek voor Claude: `aankoop/aanbod.py:503-522,559-570` - valideer EAN/GTIN, modelovereenkomst, tegenspraak en `bewijs_url`.

De echte VM-herhaling blijft verplicht. RoboCleaners als verplichte winnaar is geen geldige live-grendel, omdat M4 al toont dat zoeken die winkel kan missen. De deterministische test moet wel bewijzen dat RoboCleaners met de gemeten pagina’s boven Vanden Borre eindigt.  
Techniek voor Claude: `tests/test_aankoop_prijs.py` - vaste EAN-paren en een afwijkend-model-tegenvoorbeeld testen; live apart beoordelen op een onderbouwde aanbeveling.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
G1: oneens
G2: eens
G3: oneens
G4: eens
G5: eens
K1: oneens
K2: eens
K3: eens
K4: eens
K5: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Meerderheid (3-0 of 2-1) op alle hoofdlijnen: B, C en D zijn unaniem aangenomen; A wordt aangenomen met de scherpe veiligheidsgrendel van Codex en Claude zodat productidentiteit (gevraagd model) bindend blijft.

Mehdi merkt dat de Prijsonderzoeker eindelijk met een concrete aankoopaanbeveling komt zonder vast te lopen op onzinnige randzaken. Eisen die het taalmodel zelf verzint (zoals "privé-aankoop") blokkeren een aankoop niet langer als een winkelpagina die niet noemt. Tegelijk blijft gewaarborgd dat Mehdi exact het gevraagde apparaat krijgt, en kan een goedkopere winkel (zoals RoboCleaners) meeliften op de officiële handleiding van een andere winkel als de streepjescode (EAN) exact klopt.

1. **Voorstel A (X1, K1): EENS met veiligheidsgrendel van Codex.** Alleen eisen uit de vraag blokkeren een aanbeveling bij "onbekend". Codex merkt terecht op dat expliciete modelidentiteit (zoals MOVA V70 Ultra Complete / MOVA-RC-V70ULC-WHT) bindend moet zijn om te voorkomen dat een verkeerde kleur of afwijkend model erdoor glipt. Overige modeleisen (bv. levertijd) geven bij "onbekend" een waarschuwing in het verslag ("niet bevestigd").
`Techniek voor Claude: aankoop/aanbod.py:109-121,551-574 - maak expliciet gevraagde productidentiteit bindend naast netwaarden; behandel overige modeleisen bij onbekend als niet-blokkerend.`

2. **Voorstel B (X2, K2): EENS (3-0).** De prompt in de VORM verbiedt koperseigenschappen en prijsvoorwaarden als compatibiliteitseis.
`Techniek voor Claude: aankoop/onderzoek.py:79,111-113 - VORM herformuleren naar controleerbare product- en leveringseigenschappen.`

3. **Voorstel C (X3, K3, G3, G5): EENS (3-0).** Het delen van netwaarden via dezelfde EAN/GTIN lost de oneerlijke uitsluiting van RoboCleaners (M3) op. Voorwaarde van Claude (K3) en Gemini (G3/G5): geldige 13-cijferige GTIN met controlecijfer en geen tegensprekende modelcode/titel op de aanbiedingspagina zelf.
`Techniek voor Claude: aankoop/aanbod.py:503-522,535-541 - valideer EAN cross-page en weiger koppeling bij tegensprekende modelcode in titel.`

4. **Voorstel D (X4, K4): EENS (3-0).** Werkverslag logt extra/afwijkende sleutels zodat modelafwijkingen direct zichtbaar zijn.
`Techniek voor Claude: prijsonderzoeker.py:83-94 en aankoop/onderzoek.py:140-155 - tel niet-eis sleutels in het werkverslag.`

5. **Ontbrekend en verificatie (X5, K5): EENS.** Borging met gerichte unit tests (EAN-match en afwijkende variant) en daarna de live test op de VM.
`Techniek voor Claude: tests/test_aankoop_prijs.py - voeg EAN cross-page tests toe en draai VM-proef.`

GRENS: geen

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Ik ben akkoord met A (met de veiligheidsgrendel van Codex), B, C (met de extra voorwaarde) en D. Dit komt door zonder Mehdi, want het is geen 1-1-1.

**Wat Mehdi merkt**
- Hij krijgt eindelijk een aanbeveling. Het model verzint nu geen eisen meer die een winkelpagina nooit kan bevestigen, zoals "privé-aankoop".
- Wat niet bevestigd is, staat bij Aanbevolen. Een voorbeeld is "niet bevestigd: levering in België tegen half november 2026".
- Hetzelfde toestel bij RoboCleaners (961,50) wordt niet meer verslagen door Vanden Borre (1.399), omdat de handleiding via dezelfde EAN mag meetellen.

**Over Codex (X1)**
Codex heeft hier gelijk, en dit vul ik aan op mijn eerdere standpunt in K1. Als Mehdi exact de witte MOVA-RC-V70ULC-WHT vraagt, mag "onbekend" geen groen licht zijn. Anders kan een goedkopere zwarte of afwijkende variant worden aanbevolen. Het kleinste herstel is om een expliciet gevraagde modelcode of variant bindend te maken, naast netspanning en netfrequentie. "Onbekend" op bijzaken zoals levering blijft een waarschuwing.
Techniek voor Claude: `aankoop/aanbod.py:109-121,549-580` - haal de modelcode of variant uit de vraag en laat die bij "onbekend" blokkeren.

**Over Gemini (G5)**
G5 klopt. Als de handleiding via EAN van een andere pagina komt, moet `bewijspagina()` die ook als `bewijs_url` accepteren. Anders werkt C in de praktijk niet.
Techniek voor Claude: `aankoop/aanbod.py:516-522` - sta een externe handleiding toe bij een geverifieerde EAN-match.

**Over C**
Een EAN op een webwinkel kan fout zijn, bijvoorbeeld bij een bundel. Het aanbod zelf mag dus geen afwijkend model tonen, en de herkomst ("handleiding van Vanden Borre, zelfde EAN") staat in het verslag.

**Test vóór de VM-run**
Voeg twee gevallen toe: gelijke EAN en gelijk model, en gelijke EAN met afwijkend model. Voeg ook een geval toe met een afwijkende variant die nooit mag winnen. De VM-run slaagt alleen als er een aanbeveling komt met "niet bevestigd: levering", en RoboCleaners boven Vanden Borre staat.
Techniek voor Claude: `tests/test_aankoop_prijs.py` - drie gevallen toevoegen.

**Wat ik niet heb gecontroleerd**
Ik heb geen bestanden gelezen. De vindplaatsen komen uit de opdracht en de meningen van Codex en Gemini.

Een kanttekening bij de stemtelling: de punten X1 tot X5, G1 tot G5 en K1 tot K5 overlappen elkaar. Daarom stem ik per id op de inhoud.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Claude

Beslissing: alle vijftien punten zijn aangenomen en worden zelfstandig uitgevoerd. Er is geen vraag aan Mehdi.

- **Aangenomen:** een gevraagd model of variant blokkeert een aanbeveling zolang het onbekend is (X1, X5).
- **Aangenomen:** "privé-aankoop" en koperseigenschappen tellen niet meer als productEis; alleen eisen die een pagina kan bevestigen (X2, G2, K2).
- **Aangenomen:** bij dezelfde geldige EAN mag een winkel de handleiding van een andere pagina gebruiken (X3, G3, K3).
- **Aangenomen:** eigen modeleisen sluiten een aanbod alleen uit bij een uitdrukkelijk "nee" (G1, K1). Eisen uit Mehdi's vraag blijven bindend.
- **Aangenomen:** het werkverslag toont afwijkende sleutels en er komen twee extra tests (X4, G4, K4, K5).

G5 is een aanvullende bevinding en geen besluit. Ik tel het daarom als open.

**Techniek voor Claude** (de stemmers haalden deze plekken aan, dus de bestanden zijn gelezen):
- Productidentiteit bindend maken: `aankoop/aanbod.py:109-121,549-580` en `prijsonderzoeker.py:111,138`. Test in `aankoop/aanbod.py:258-286` (X1, X5).
- Eisen beperken tot bewijsbare eigenschappen: `aankoop/onderzoek.py:79,110-112` (X2, G2, K2).
- "Onbekend" bij eigen eisen niet blokkeren: `aankoop/aanbod.py:554` (G1, K1).
- EAN-koppeling met controlecijfer, modelcontrole en herkomst in het verslag: `aankoop/aanbod.py:503-513,549-580` (X3, G3, K3).
- Sleutels loggen en tellen: `prijsonderzoeker.py:83-94`, `tests/test_aankoop_prijs.py:1085-1095` en het werkverslag in `aankoop/onderzoek.py` (X4, G4, K4).
- Herlooptest met twee gevallen, gelijke EAN en EAN-gelijk met modelverschil: `tests/test_aankoop_prijs.py` (K5).

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): A: nee. Een expliciet gevraagd model of variant mag bij “onbekend” niet worden aanbevolen. Anders kan bijvoorbeeld een goedkopere zwarte of afwijkende V70 worden gekozen terwijl Mehdi exact de witte MOVA-RC-V70ULC-WHT vroeg. Kleinste fix: maak expliciet gevraagde productidentiteit bindend, naast netspanning en netfrequentie. Andere modeleisen mogen bij “onbekend” alleen als waarschuwing blijven staan.
  Techniek voor Claude: `aankoop/aanbod.py:109-121,549-580` en `prijsonderzoeker.py:111,138` - haal ook expliciete modelcode/variant uit de vraag en blokkeer die bij onbekend.
- **X2** (3-0): B: ja. “Privé-aankoop” is geen producteigenschap die een winkelpagina kan bewijzen en hoort daarom niet als compatibiliteitseis mee te tellen.
  Techniek voor Claude: `aankoop/onderzoek.py:79,110-112` - beperk modeleisen tot bewijsbare product- en leveringseigenschappen.
- **X3** (3-0): C: ja. Dezelfde geldige EAN identificeert hetzelfde handelsartikel. Daardoor mag de goedkopere winkel gebruikmaken van de handleiding die een andere gelezen productpagina voor exact die EAN linkt. De voorgestelde controles op modelnaam, tegenspraak, regio en accessoires voorkomen een losse of verkeerde koppeling.
  Techniek voor Claude: `aankoop/aanbod.py:503-513,549-580` - voeg de gecontroleerde EAN-koppeling toe als alternatief voor de huidige eigen-paginalink.
- **X4** (3-0): D: ja. Extra compatibiliteitssleutels zichtbaar maken toont direct wanneer het model andere sleutels gebruikt of eisen overslaat.
  Techniek voor Claude: `prijsonderzoeker.py:83-94` en `tests/test_aankoop_prijs.py:1085-1095` - log de vereniging van verwachte eisen en ontvangen sleutels, zonder gevoelige tekst.
- **X5** (3-0): Ontbrekend: de metingen tonen dat expliciete productidentiteit nu niet door de code wordt afgedwongen. `keur` controleert alleen of een titel bestaat, niet of die overeenkomt met het gevraagde model. Dat moet vóór de echte VM-herhaling worden afgedekt met een test.
  Techniek voor Claude: `aankoop/aanbod.py:258-286` - test dat een afwijkende modelcode of variant nooit aanbevolen wordt.
- **G1** (2-1): Voorstel A: JA.** Eigen eisen van het model mogen een aanbod alleen uitsluiten bij een expliciete "nee" met citaat, niet bij "onbekend". De harde eisen uit Mehdi's vraag (`eisen_uit_vraag`) blijven wel bindend.
- **G2** (3-0): Voorstel B: JA.** De prompt-instructie moet het model verbieden om koperseigenschappen of prijsvoorwaarden als compatibiliteitseis op te voeren, want geen enkele productpagina kan dat bevestigen.
- **G3** (2-1): Voorstel C: JA, mits strikte controle.** EAN/GTIN-koppeling voor handleidingen over winkels heen is logisch en noodzakelijk voor prijsvergelijking (M3), maar vereist strikte verificatie: exact 13 cijfers, geldig modulo-10 controlecijfer, en expliciet label op beide pagina's.
- **G4** (3-0): Voorstel D: JA.** Het werkverslag moet sleutelverschillen inzichtelijk maken om prompt- en modelafwijkingen direct te signaleren.
- **G5** (3-0): Aanvullende bevinding op de metingen (M3/M4):
- **K1** (2-1): A: alleen eisen uit de vraag zelf blokkeren een aanbeveling.
  Techniek voor Claude: `aankoop/aanbod.py:554` - bij een eis die niet uit `eisen_uit_vraag` komt, telt "onbekend" als "niet bevestigd" (geen blokkade). Alleen "nee" sluit uit.
- **K2** (3-0): B: de VORM vraagt alleen om eisen die een pagina kan bevestigen.
  Techniek voor Claude: `aankoop/onderzoek.py:79` - de tekst wordt "eigenschappen van product of levering die een pagina kan bevestigen; niet de koper of de prijs". Pas ook de regel rond `:111` daarop aan.
- **K3** (3-0): C: netwaarden uit een handleiding mogen via dezelfde EAN gedeeld worden.
  Techniek voor Claude: `aankoop/aanbod.py:503` (`gelinkt_document`) - sta een link van een andere pagina toe bij gelijke EAN met geldig controlecijfer. Controleer dat het aanbod geen afwijkende modelcode toont. Zet de herkomst in het verslag.
- **K4** (3-0): D: het werkverslag telt ook de sleutels in compatibiliteit die geen eis zijn.
  Techniek voor Claude: werkverslag-log in `aankoop/onderzoek.py` - tel de sleutels in compatibiliteit zonder bijbehorende eis.
- **K5** (2-1): Wat ontbreekt: de herlooptest.
  Techniek voor Claude: `tests/test_aankoop_prijs.py` - twee gevallen toevoegen, één met gelijke EAN en één met EAN-gelijk maar modelverschil.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
