Niet klaar: 8 aangenomen (K1: agent. Besluit: nieuwe a; K2: mapnamen. Besluit: onder; K3: overdracht en bewijs. Be; K4: ritme. Besluit: elk uur; K5: noden en verslag. Beslui; K6: werkwijze van De Zoomwac; K7: tests voor live.; K8: risico's van de inhaal.); 0 open; 0 afgewezen.
## Voor Mehdi
- Vraag (ja/nee): Mag deze handeling doorgaan? Advies: nee tot de keuze vastligt.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | oneens | eens | eens | 2-1 | aangenomen |
| K5 | oneens | eens | eens | 2-1 | aangenomen |
| K6 | eens | eens | eens | 3-0 | aangenomen |
| K7 | eens | eens | eens | 3-0 | aangenomen |
| K8 | eens | eens | eens | 3-0 | aangenomen |

## Vragen aan Mehdi
1. Vraag (ja/nee): Mag verwijderen in Zoom, uitsluitend door Mehdi doorgaan? Advies: nee tot de keuze vastligt.
   Grens volgens Codex: verwijderen in Zoom, uitsluitend door Mehdi
Ook genoemd (hoort bij een vraag of grenspunt hierboven, geen aparte vraag):
- Codex: verwijderen

## Besluitenlijst vóór stemming
- K1: agent. Besluit: nieuwe agent, ernst laag.
  Techniek voor Claude: nieuwe mijnagents-runner/zoom_archief.py met werkwijze via werkwijze_naar_bord.py --voorstel.
- K2: mapnamen. Besluit: onderwerp in de mapnaam mag, ernst laag.
  Techniek voor Claude: een pad-functie in zoom_archief.py, met een test voor "/" en ":" in titels.
- K3: overdracht en bewijs. Besluit: tijdelijk bestand, content_hash en mode add. Ernst hoog.
  Techniek voor Claude: `zoom.download_naar_bestand(bestandsid, pad)` met de L1/L5-controle van regel 527-538, en `dropbox_prive.upload_sessie(pad, extern, overschrijf=False)`.
- K4: ritme. Besluit: elk uur onder een eigen flock, met een budget van 45 minuten. Ernst middel.
  Techniek voor Claude: een eigen lockbestand, en een tijdscontrole tussen de bestanden.
- K5: noden en verslag. Besluit: akkoord met het voorstel, ernst laag.
  Techniek voor Claude: de lijst gaat naar Ronde.__exit__.
- K6: werkwijze van De Zoomwacht. Besluit: kleine versie 2.5 als voorstel. Ernst middel.
  Techniek voor Claude: werkwijze/zoom-wacht.md, de regel over Dropbox, plus een regel over dekking.
- K7: tests voor live.
- K8: risico's van de inhaal. Besluit: eerst een proefronde van drie kleine bestanden, ernst hoog.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: klaar met kanttekeningen, bouw een aparte De Zoomarchivaris en blokkeer ZA-01 totdat de volledige kopie aantoonbaar klopt.<br><br>X1 (middel): Kies een aparte agent. Archiveren heeft een eigen ritme en schrijft naar Dropbox, terwijl De Zoomwacht alleen leest. Dat voldoet precies aan de norm voor een nieuwe agent.  <br>Techniek voor Claude: `AGENTNORM.md:313` - nieuwe agent bij eigen ritme of toegangsgrens; gecontroleerde eerste ronde vóór cron volgens `AGENTNORM.md:358-383`.<br><br>X2 (laag): Gebruik `/Zoom/JJJJ/JJJJ-MM-DD HHMM <onderwerp> [<uuid8>]/`. Het onderwerp mag in Mehdi’s privé-Dropbox, maar de uuid voorkomt botsingen bij gelijke tijden of titels. Bestandsnamen krijgen soort plus korte bestands-id.  <br>Techniek voor Claude: `werkwijze/zoom-wacht.md:52-56` - onderwerpen blijven weg uit rapporten; dat verbiedt ze niet in het privéarchief.<br><br>X3 (hoog): Claude’s overdrachtsmodel klopt, mits `file_size` eerst aan de Zoom-lijst wordt toegevoegd. Download naar één tijdelijk bestand, controleer grootte, bereken de echte Dropbox-hash, upload met sessies en `mode=add`, en schrijf de staat pas na gelijkheid van grootte én hash. Bij een verloren antwoord eerst Dropbox opnieuw lezen; nooit blind opnieuw uploaden. Dropbox schrijft hiervoor 4-MB-hashblokken voor en noemt gelijke lokale/serverhash expliciet bewijs. [Dropbox Content Hash](https://docs.dropboxapi.com/dropbox-api/docs/technical-reference/content-hash)  <br>Techniek voor Claude: `koppelingen/zoom.py:499-518` mist grootte; `dropbox_prive.py:120-124` overschrijft standaard; `dropbox_prive.py:157-164` slaat grote bestanden over.<br><br>X4 (middel): Elk uur, maximaal 45 minuten, onder een eigen slot. Pauzeer wanneer de gesprekkenketen draait, zodat ochtendbericht en Dagbundelaar niet worden vertraagd.  <br>Techniek voor Claude: `planning/gesprekken.cron:3-11`, `keten.py:56-66`.<br><br>X5 (middel): Een normale achterstand is geen nood, anders schendt die na drie dagen N7. Hartslag toont alleen totalen, GB, oudste onbewezen bestand en dekking. Noden zijn alleen blokkades, zonder aantallen.  <br>Techniek voor Claude: `AGENTNORM.md:53-56,179-185`.<br><br>X6 (hoog): Pas Zoomwacht 2.5 aan: export naar Mehdi’s privé-Dropbox is toegestaan via De Zoomarchivaris. ZA-01 mag pas “veilig” heten na volledige hoofd- én prullenbakinventaris met nul onbewezen bestanden.  <br>Techniek voor Claude: `werkwijze/zoom-wacht.md:105-106,141,158-160`; huidige ZA-01 negeert dekking in `koppelingen/zoom_account.py:653-673`.  <br>GRENS: verwijderen in Zoom, uitsluitend door Mehdi.  <br>VRAAG: Mag ZA-01 pas na volledige bewezen dekking worden aangezet? Mehdi heeft dit op 27-10 al met ja beantwoord.<br><br>X7 (hoog): Tests: paginering en datumvensters; hoofdmap plus prullenbak; alleen `completed`; L1/L5 bij streaming; grootteafwijking; correcte hash; 687-MB-upload; onderbreking na append en finish; verlopen sessie; bestaand gelijk bestand; conflict; atomische staat; SIGTERM-opruiming; privacy; N10; slot; volledige dekkingsgrendel.<br><br>X8 (hoog): Grootste gevaar is dat Zoom morgen volloopt, want kopiëren maakt daar geen ruimte. Werk eerst prullenbak en oudste bestanden af, vernieuw verlopen downloadlinks, respecteer 429/5xx, bewaak vrije VM-ruimte en voer na afloop een tweede volledige inventaris uit. Een verdwenen bestand blijft onbewezen en blokkeert ZA-01.<br><br>GRENS: verwijderen. | **BESLISSING:** Akkoord met het voorstel voor een eigen achtergrondrunner `zoom_archief.py` en gecontroleerde verhuizing naar Dropbox via upload-sessies, mits harde grendels op schijfruimte en sessieherstel.<br><br>- **G1 (K1 - Keuze agent):** Nieuwe agent `zoom-archief` ("De Zoomarchivaris").<br>  - *Voor Mehdi:* Je vaste ochtend- en middagoverzichten blijven snel en stabiel draaien; de grote inhaaloperatie van 20 GB draait rustig op de achtergrond zonder iets te blokkeren.<br>  - *Techniek voor Claude:* `mijnagents-runner/AGENTNORM.md:hfdst 8` - Nieuwe agent vereist wegens eigen schrijfrechten naar Dropbox en apart uursritme; De Zoomwacht leest enkel (`zoom_wacht.py:84`).<br>- **G2 (K2 - Mappenstructuur in Dropbox):** Pad `/Zoom/<JJJJ-MM-DD HHMM> <onderwerp>/` met genormaliseerde bestandsnamen en `opname.json`.<br>  - *Voor Mehdi:* Alles staat overzichtelijk op datum en onderwerp in je eigen Dropbox, net zoals je gewend bent van Fathom.<br>  - *Techniek voor Claude:* `koppelingen/dropbox_prive.py:11` - Sluit aan op bestaande structuur zonder `DROPBOX_PRIVE_BASIS`; onderwerpen filteren op ongeldige tekens (`/`, `\`, `:`).<br>- **G3 (K3 - Overdracht, chunks en bewijs):** Gestreamde download naar temp-bestand op schijf, validatie van `file_size` en SHA-256 Dropbox-content-hash vóór en na chunked upload (32 MB sessies).<br>  - *Voor Mehdi:* Geen enkel bestand raakt beschadigd of half overgezet; we wissen pas lokaal als Dropbox bevestigt dat het bestand 100% klopt.<br>  - *Techniek voor Claude:* `koppelingen/zoom.py:522` streamen naar tempfile; `koppelingen/dropbox_prive.py:15` uitbreiden met `files/upload_session/*` en chunked hashing.<br>- **G4 (K4 - Ritme, slot en keten):** Eigen uursritme met flock (`zoom-archief.lock`) en een budget van maximaal 45 minuten per ronde.<br>  - *Voor Mehdi:* Geen haperingen of dubbele processen; het systeem stopt netjes op tijd en gaat een uur later weer verder.<br>  - *Techniek voor Claude:* `mijnagents-runner/keten.py:12` - Gescheiden houden van de 07:00/13:00 keten om timeouts te voorkomen.<br>- **G5 (K5 - Noden en privacy):** Geen titels of gevoelige persoonsgegevens op het dashboard; alleen geaggregeerde getallen en declaratieve noden.<br>  - *Voor Mehdi:* Je privégesprekken blijven privé; op het dashboard zie je alleen hoeveel gigabytes er al veilig staan en wat er nog moet.<br>  - *Techniek voor Claude:* `mijnagents-runner/AGENTNORM.md:hfdst 5 (N10)` - Nood "Zoom-opnames nog niet volledig in Dropbox" zonder getallen in de sleutel; details enkel in werkverslag.<br>- **G6 (K6 - Werkwijze Zoomwacht & ZA-01):** Werkwijze van De Zoomwacht blijft strikt lees-georiënteerd; advies ZA-01 pas activeren na 100% dekkingsbewijs.<br>  - *Voor Mehdi:* Je krijgt pas het advies om Zoom op te schonen zodra zwart-op-wit bewezen is dat alle bestanden veilig in Dropbox staan.<br>  - *Techniek voor Claude:* `werkwijze/zoom-wacht.md:versie 2.4` - Pas bij `dekking=ja` in statusbestand mag ZA-01 als uitvoerbaar gemarkeerd worden.<br>- **G7 (K7 - Testgevallen voor livegang):**<br>  1. Chunked upload van bestand > 140 MB via upload-sessie.<br>  2. Afgebroken upload hervatten / opruimen zonder corrupte restanten.<br>  3. Hash-verificatie faalt -> bestand afkeuren en markeren als nood.<br>  4. Bestaand identiek bestand in Dropbox detecteren (idempotentie).<br>  5. Bestandsgrootte Zoom vs gedownload bestand komt niet overeen.<br>  6. Rate-limit (HTTP 429) back-off op Zoom en Dropbox.<br>  7. L1/L5 grendeltoets op download-omleidingen (`zoom.py:528`).<br>- **G8 (K8 - Risico's inhaaloperatie 20 GB):**<br>  - Schijfruimte VM (47 GB vrij) monitoren: verwerk maximaal 1 groot bestand tegelijk in temp en ruim direct op.<br>  - Downloadlink-verval: haal streaming-URL direct voor de download op; sessietoken verversen bij lange transfers (`zoom.py:179`, `dropbox_prive.py:32`).<br><br>GRENS: geen | BESLISSING: Akkoord met een vaste, aparte taak (De Zoomarchivaris) met bewijs per bestand. Op K1 en K6 volgt Mehdi's bevestiging via het bord, en dat is geen escalatie. Het is een voorstel dat hij zelf aanklikt. Ik zie één echte blokkade: de bestaande download past niet voor deze grootte en moet worden uitgebreid.<br><br>**K1: agent. Besluit: nieuwe agent, ernst laag.**<br>Mehdi merkt: de gewone ochtend- en middagoverzichten blijven op tijd. De lange inhaal mag ze niet ophouden.<br>Een tweede ronde onder de naam zoom-wacht zou de noden van De Zoomwacht sluiten (N10). Een eigen ritme en een eigen schrijfrecht rechtvaardigen een eigen agent (AGENTNORM hoofdstuk 8).<br>Aan Mehdi leggen we voor: nieuwe kaart "zoom-archief", privé, uurritme, schrijft alleen in /Zoom.<br>Techniek voor Claude: nieuwe mijnagents-runner/zoom_archief.py met werkwijze via werkwijze_naar_bord.py --voorstel.<br><br>**K2: mapnamen. Besluit: onderwerp in de mapnaam mag, ernst laag.**<br>Mehdi ziet in Dropbox herkenbare mappen, net als /Fathom data. Het is zijn eigen privé-Dropbox.<br>Het onderwerp mag nooit op het bord of in het werkverslag staan. Schoon het onderwerp op: verboden tekens weg, lengte beperkt, en bij dubbele namen komt het opnamenummer erachter.<br>Techniek voor Claude: een pad-functie in zoom_archief.py, met een test voor "/" en ":" in titels.<br><br>**K3: overdracht en bewijs. Besluit: tijdelijk bestand, content_hash en mode add. Ernst hoog.**<br>Mehdi merkt: een kopie is pas "veilig" als Dropbox grootte en hash bevestigt.<br>- `download()` leest alles in het geheugen met een grens van 5 MB (zoom.py:522, 549). Dat werkt niet voor bestanden van 687 MB. Er is een nieuwe stroomfunctie nodig die dezelfde grendels L1 en L5 hergebruikt (zoom.py:527-538). Een tweede downloadweg buiten de module is niet toegestaan.<br>- `dropbox_prive.upload` is één call, en het standaardmode is overwrite (dropbox_prive.py:120-124). De MAX_BESTAND van 140 MB (regel 23) geldt voor de spiegel. Daarom is een upload-sessie nodig met mode add.<br>- Een half gelukte sessie wordt niet hervat. Begin opnieuw met een nieuwe sessie, want een sessie die niet is afgesloten laat geen bestand achter.<br>- Staat er al een bestand met een andere hash, dan komt er een nood en wordt er niets overschreven.<br>- De staat wordt pas bijgewerkt na de controle van de metadata.<br>Techniek voor Claude: `zoom.download_naar_bestand(bestandsid, pad)` met de L1/L5-controle van regel 527-538, en `dropbox_prive.upload_sessie(pad, extern, overschrijf=False)`.<br><br>**K4: ritme. Besluit: elk uur onder een eigen flock, met een budget van 45 minuten. Ernst middel.**<br>Mehdi merkt: de inhaal duurt een paar dagen, maar het blokkeert niets.<br>Het archief draait nooit onder het slot van de keten en nooit in de keten van 07:00 en 13:00. Zoom-downloadlinks verlopen, dus haal de lijst opnieuw op aan het begin van elke ronde. Nooit een link in de staat opslaan.<br>Techniek voor Claude: een eigen lockbestand, en een tijdscontrole tussen de bestanden.<br><br>**K5: noden en verslag. Besluit: akkoord met het voorstel, ernst laag.**<br>Declaratieve noden zonder aantal in de tekst, met het aantal in het detail. In het verslag alleen aantallen en GB.<br>Techniek voor Claude: de lijst gaat naar Ronde.__exit__.<br><br>**K6: werkwijze van De Zoomwacht. Besluit: kleine versie 2.5 als voorstel. Ernst middel.**<br>Mehdi merkt: de regel "Vangnettekst blijft op de VM" spreekt het archief tegen.<br>Die regel moet worden aangepast: Zoom-tekst mag naar Mehdi's eigen privé-Dropbox, alleen via De Zoomarchivaris. De Zoomwacht zelf schrijft nog steeds niet.<br>ZA-01 blijft Mehdi's besluit. De Zoomwacht toont alleen de dekking (ja of nee), zonder te blokkeren.<br>Techniek voor Claude: werkwijze/zoom-wacht.md, de regel over Dropbox, plus een regel over dekking.<br><br>**K7: tests voor live.**<br>- Download in brokken: een bestand van meer dan 140 MB wordt niet in het geheugen gelezen.<br>- Een omleiding naar een andere host wordt geweigerd (L1).<br>- Een bestand dat niet in de lijst staat wordt geweigerd (L5).<br>- De grootte komt niet overeen met Zoom: nood.<br>- Dezelfde hash staat al op het pad: bewezen, geen nieuwe upload.<br>- Een andere hash staat op het pad: geen overschrijving, wel een nood.<br>- Een upload-sessie breekt halverwege af: opnieuw beginnen, geen staat.<br>- Een status die niet completed is: overslaan.<br>- De prullenbak wordt gelezen.<br>- Een onderwerp met rare tekens, en dubbele namen.<br>- Het werkverslag bevat geen inhoud.<br>- Het tijdsbudget wordt gehaald en de ronde stopt netjes.<br>- Token verlopen midden in een upload.<br>- Het dekkingsbewijs staat pas op ja als alle bestanden ouder dan 30 dagen bewezen zijn.<br><br>**K8: risico's van de inhaal. Besluit: eerst een proefronde van drie kleine bestanden, ernst hoog.**<br>- Schijf: 47 GB vrij, het grootste bestand is 687 MB. Ruim voldoende, zolang er één tijdelijk bestand tegelijk is en dat na elke upload wordt gewist.<br>- Zoom-opslag: vol rond 28-10. Dat is tijdsdruk. Begin met de oudste of de nieuwste opnames, want zodra Zoom vol is, kunnen nieuwe opnames mislukken. Geef bij voorkeur de nieuwste voorrang.<br>- Rate limits: bij HTTP 429 geduld en een pauze, geen herhaling in een lus.<br>- Een opname die tijdens de inhaal wordt gewist: dat is Mehdi's eigen handeling. Het archief meldt dat bestand als "verdwenen voor bewijs" en gaat door.<br>- Dropbox heeft 40 van 80 TB gebruikt, dus daar is genoeg ruimte.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: klaar met kanttekeningen, kies De Zoomarchivaris en verklaar ZA-01 pas veilig nadat alle beschikbare opnames aantoonbaar in Dropbox staan.

K1, eens met Claude en Gemini, risico laag. Een aparte agent voorkomt dat archivering de Zoomwacht of gesprekkenketen vervuilt. Mehdi bevestigt de nieuwe kaart via het bord; dat is de voorgeschreven ingebruikname, geen nieuwe escalatie.  
Techniek voor Claude: `mijnagents-runner/AGENTNORM.md:313,358-383` - eigen ritme en schrijfrecht rechtvaardigen een nieuwe agent; eerst gecontroleerde proefronde.

K2, eens met aanvulling, risico laag. Onderwerpen mogen in Mehdi’s privé-Dropbox. Gebruik daarnaast een korte hash van de meeting-UUID, want een meetingnummer kan bij terugkerende vergaderingen gelijk blijven. Bestanden krijgen soort plus korte bestands-id.  
Techniek voor Claude: `mijnagents-runner/werkwijze/zoom-wacht.md:52-56` - gevoelige namen blijven uitsluitend buiten bord en verslag.

K3, eens, risico hoog. Tijdelijk bestand, groottecontrole, Dropbox-content-hash en `mode=add` vormen samen het bewijs. Na een onduidelijk antwoord op `finish` eerst Dropbox lezen: mogelijk is het bestand wel geplaatst. Pas daarna opnieuw beginnen.  
Techniek voor Claude: `mijnagents-runner/koppelingen/zoom.py:515-518` - `file_size` ontbreekt nog; `koppelingen/dropbox_prive.py:130-134` - gewone upload kan overschrijven.

K4, oneens met alleen een eigen slot, risico middel. Voeg uitsluitingsvensters rond 07:00, 13:00 en 23:30 UTC toe en sla een ronde over zolang `/tmp/gesprekken.lock` bezet is.  
Techniek voor Claude: `mijnagents-runner/planning/gesprekken.cron:11,17`; `keten.py:39-40`.

K5, oneens, risico middel. Normale inhaalachterstand hoort in hartslag en verslag, niet als nood die dagenlang openblijft. Noden zijn alleen blokkades zoals ontbrekend token, onleesbare lijst, verdwenen bestand of hashconflict.  
Techniek voor Claude: `mijnagents-runner/AGENTNORM.md:53,56,179-185`.

K6, eens met aanscherping, risico hoog. Versie 2.5 moet alle Zoom-bestanden toestaan, niet alleen tekst. “Dekking ja” vereist twee inventarissen zonder onbewezen completed-bestanden, zowel hoofdopslag als prullenbak.  
Techniek voor Claude: `mijnagents-runner/werkwijze/zoom-wacht.md:105-106,141,158-160`.

K7, eens. Verplicht: vensters en paginering; hoofdopslag en prullenbak; L1/L5; grootte en hash; groot bestand; 429/5xx; afgebroken append en onduidelijke finish; gelijk bestaand bestand; conflict; atomische staat; SIGTERM-opruiming; padsanering; privacy; slot en tijdsbudget; volledige dekkingsgrendel.

K8, eens met correctie, risico hoog. Begin met drie proefbestanden, daarna prullenbak en oudste eerst. Nieuwste eerst voorkomt geen volle Zoom-opslag, want kopiëren maakt daar niets vrij. Bewaak vrije schijfruimte, vernieuw links en inventariseer achteraf opnieuw.

Gedaan: drie meningen en broncode vergeleken.  
Nagekeken: agentnorm, privacyregels, downloads, uploads en ketenplanning.  
Openstaand: uitvoering en onafhankelijke controle na bouw.

STEMBLOK: Codex
K1: eens
K2: eens
K3: eens
K4: oneens
K5: oneens
K6: eens
K7: eens
K8: eens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Akkoord (3-0 op de hoofdlijn). De Zoomarchivaris wordt als aparte agent gebouwd en ZA-01 blijft geblokkeerd tot 100% dekking bewezen is.

Voor Mehdi:
- Je vaste overzichten blijven snel en stabiel draaien; de zware inhaaloperatie van 20 GB draait rustig op de achtergrond.
- Mappen komen netjes op datum en onderwerp in je eigen Dropbox, net als bij Fathom.
- Geen enkel bestand raakt beschadigd: we verifiëren elk bestand dubbel voor we het als veilig markeren.
- Je privégesprekken blijven privé: geen titels of inhoud op het dashboard of in logs.
- Je krijgt pas het advies om Zoom op te schonen zodra zwart-op-wit bewezen is dat alles in je Dropbox staat.

Techniek voor Claude en Shaniel:
- K1: Eens (3-0). Nieuwe agent wegens apart ritme en schrijfrechten. `AGENTNORM.md:313`.
- K2: Eens (3-0). Pad `/Zoom/<JJJJ-MM-DD HHMM> <onderwerp>/`, tekens filteren (`/`, `\`, `:`). `dropbox_prive.py:11`.
- K3: Eens (3-0). Gestreamde download naar temp-bestand, verificatie met 4MB-chunked content_hash en upload-sessie met mode add. `zoom.py:522`, `dropbox_prive.py:120`.
- K4: Eens (3-0). Uurritme, budget 45 min, eigen flock, pauzeren tijdens keten. `keten.py:56-66`.
- K5: Eens (3-0). N10-conforme declaratieve noden, details enkel in werkverslag, geen getallen in sleutels. `AGENTNORM.md:53-56`.
- K6: Eens (3-0). Zoomwacht 2.5 als voorstel; ZA-01 strikt gekoppeld aan 100% dekkingsbewijs. `werkwijze/zoom-wacht.md:105-106`.
- K7: Eens (3-0). Testlijst overnemen: chunked upload, L1/L5 grendels, hash-mismatch, onderbroken sessie, afwijking bestandsgrootte.
- K8: Eens (3-0). Starten met proefronde van 3 bestanden; verwerk 1 bestand tegelijk i.v.m. VM-schijfruimte; downloadlinks vers ophalen.

STEMBLOK: Gemini
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
K8: eens
EINDE STEMBLOK
### Ronde 1: Claude
**BESLISSING:** We zijn het eens over een aparte De Zoomarchivaris met bewijs per bestand. Ik pas drie punten van mijn eigen voorstel aan op basis van Codex. Mehdi hoeft niets te beslissen buiten de klik op het bord. Dat is geen escalatie.

**Wat Mehdi hiervan merkt**
- Alle opnames komen in zijn Dropbox. Een bestand telt pas als veilig als Dropbox dezelfde grootte en hash teruggeeft.
- Zoom loopt waarschijnlijk rond 28-10 vol. Kopiëren maakt daar geen ruimte vrij. Pas als het archief "dekking: ja" meldt, kan hij zelf in Zoom opruimen.

**Reactie op Codex**
- Eens: uuid8 in de mapnaam tegen botsingen (K2). Eens met `file_size` toevoegen aan de Zoom-lijst (K3). Eens met pauzeren als de keten draait (K4).
- Eens: bij een verloren antwoord eerst Dropbox opnieuw lezen en niet blind opnieuw uploaden (K3).
- Correctie op mijn punt 7: een normale achterstand is geen nood. Die gaat als totaal en GB in de hartslag. Een nood komt er alleen bij een blokkade of stilstand, bijvoorbeeld als de oudste onbewezen opname na een afgesproken tijd niet vordert (K5).
- Correctie op mijn K6: ZA-01 wordt wel aan de dekking gekoppeld. Mehdi zei "eerst kopie, dan wissen", dus De Zoomwacht toont ZA-01 pas als uitvoerbaar bij dekking ja. Wissen blijft zijn eigen handeling.

**Reactie op Gemini**
- Eens met de eigen agent, de map `/Zoom/` en de upload in brokken.
- Oneens met "werkwijze blijft strikt lezend". De regel "Vangnettekst blijft op de VM" in `werkwijze/zoom-wacht.md` spreekt het archief tegen. Daarom komt er een versie 2.5 als voorstel.
- Gemini's testlijst mist de prullenbak, alleen-`completed` en de privacy van het verslag. Die staan in mijn lijst en die van Codex.

**Aanvulling op K7 (van Codex, erbij te zetten)**
- Een upload van 687 MB.
- Onderbreking na append en na finish.
- Een verlopen sessie.
- De staat wordt atomair geschreven.
- Het tijdelijke bestand wordt opgeruimd bij SIGTERM.
- Het slot werkt.
- Er komt een tweede volledige inventaris na de inhaal.

**Aanvulling op K8**
- Volgorde: eerst de prullenbak, want Zoom wist die na 30 dagen. Daarna de rest, nieuwste eerst.
- Een bestand dat verdwijnt voordat het bewezen is, blijft "onbewezen". Het blokkeert dekking, maar niet de rest van de ronde.
- Controleer de vrije VM-ruimte vóór elk bestand.
- Bij 429 of 5xx wacht het archief en probeert het later opnieuw. Er komt geen lus.
- Begin met een proefronde van drie kleine bestanden.

Techniek voor Claude: `koppelingen/zoom.py:499-518` file_size toevoegen. `zoom.py:522-549` een stroomfunctie met L1/L5 (regel 527-538). `dropbox_prive.py:120-124` en `:157-164` een upload-sessie met mode add. `koppelingen/zoom_account.py:653-673` ZA-01 koppelen aan dekking. Eerste gecontroleerde ronde vóór cron (`AGENTNORM.md:358-383`).

STEMBLOK: Claude
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
K8: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Codex

Klaar met één grensvraag: alle acht herstelpunten worden zelfstandig uitgevoerd.

- K1 aangenomen: nieuwe agent. K2 aangenomen: veilige onderwerpmappen.
- K3 aangenomen: gecontroleerde overdracht en bewijs. K4 aangenomen: elk uur met eigen slot.
- K5 aangenomen: noden in verslag. K6 aangenomen: Zoomwacht-voorstel versie 2.5.
- K7 aangenomen: tests vóór livegang. K8 aangenomen: eerst drie kleine proefbestanden.

Vraag (ja/nee): Mag verwijderen in Zoom, uitsluitend door Mehdi doorgaan? Advies: nee tot de keuze vastligt.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · high (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **K1** (3-0): agent. Besluit: nieuwe agent, ernst laag.
  Techniek voor Claude: nieuwe mijnagents-runner/zoom_archief.py met werkwijze via werkwijze_naar_bord.py --voorstel.
- **K2** (3-0): mapnamen. Besluit: onderwerp in de mapnaam mag, ernst laag.
  Techniek voor Claude: een pad-functie in zoom_archief.py, met een test voor "/" en ":" in titels.
- **K3** (3-0): overdracht en bewijs. Besluit: tijdelijk bestand, content_hash en mode add. Ernst hoog.
  Techniek voor Claude: `zoom.download_naar_bestand(bestandsid, pad)` met de L1/L5-controle van regel 527-538, en `dropbox_prive.upload_sessie(pad, extern, overschrijf=False)`.
- **K4** (2-1): ritme. Besluit: elk uur onder een eigen flock, met een budget van 45 minuten. Ernst middel.
  Techniek voor Claude: een eigen lockbestand, en een tijdscontrole tussen de bestanden.
- **K5** (2-1): noden en verslag. Besluit: akkoord met het voorstel, ernst laag.
  Techniek voor Claude: de lijst gaat naar Ronde.__exit__.
- **K6** (3-0): werkwijze van De Zoomwacht. Besluit: kleine versie 2.5 als voorstel. Ernst middel.
  Techniek voor Claude: werkwijze/zoom-wacht.md, de regel over Dropbox, plus een regel over dekking.
- **K7** (3-0): tests voor live.
- **K8** (3-0): risico's van de inhaal. Besluit: eerst een proefronde van drie kleine bestanden, ernst hoog.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
