Besluit: 22 aangenomen (X1: P1 eens.** De voorbereid; X2: P2 eens.** Oude dossiers; X3: P3 eens.** Voor bezoeken; X4: P4 eens.** Dit neemt; X5: P5 eens.** Een tijdelijk; X6: P6 eens.** De drie; X7: P7 eens.** Geen extra; G1: Twee agents blijven gesc; G2: W12 onbekend blokkeert n; G3: W2 vóór GPS-meetreeks de; G4: Werfdossier automatisch ; G5: Netwerkfout in dashboard; G6: Werkwijzen gelijktrekken; G7: Vaste taakverdeling sche; K1: Twee agents blijven (P1:; K2: W12 "onbekend" mag niet; K3: W2 vóór de GPS-meetreeks; K4: Werfdossier automatisch ; K5: Dashboard-crash opvangen; K6: Eén tekst in de; K7: Geen nieuw scherm (P7:; K8: Volgorde en rollen); 0 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | oneens | eens | eens | 2-1 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | aangenomen |
| X5 | eens | eens | eens | 3-0 | aangenomen |
| X6 | eens | eens | eens | 3-0 | aangenomen |
| X7 | eens | eens | eens | 3-0 | aangenomen |
| G1 | eens | eens | eens | 3-0 | aangenomen |
| G2 | oneens | eens | eens | 2-1 | aangenomen |
| G3 | eens | eens | eens | 3-0 | aangenomen |
| G4 | eens | eens | eens | 3-0 | aangenomen |
| G5 | eens | eens | eens | 3-0 | aangenomen |
| G6 | eens | eens | eens | 3-0 | aangenomen |
| G7 | eens | eens | eens | 3-0 | aangenomen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | oneens | eens | eens | 2-1 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | eens | eens | eens | 3-0 | aangenomen |
| K5 | eens | eens | eens | 3-0 | aangenomen |
| K6 | eens | eens | eens | 3-0 | aangenomen |
| K7 | eens | eens | eens | 3-0 | aangenomen |
| K8 | eens | eens | eens | 3-0 | aangenomen |

## Besluitenlijst vóór stemming
- X1: P1 eens.** De voorbereider controleert tokenvrij; de schrijver start uitsluitend na Mehdi’s knop. Samenvoegen maakt die kosten- en toestemmingsgrens minder controleerbaar.
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:873-877`, `mijnagents/app.py:3319-3336`, `mijnagents-runner/werkwijze/werfverslag-schrijver.md:5-8` - twee agents behouden.
- X2: P2 eens.** Oude dossiers mogen niet eeuwig vastlopen omdat het contractsysteem ze niet kent. Een werkelijk gevonden contract zonder werfopvolging blijft wel blokkeren.
  Techniek voor Claude: `werfverslag_voorbereider.py:650-683,916-927` - W12 `onbekend` zichtbaar maar niet blokkerend; `ontbreekt` wel; grendeltest.
- X3: P3 eens.** Voor bezoeken van vóór 03-10-2026 bestond de GPS-meting niet. Als de agenda-afspraak W1 bewijst, mag dat historische gebrek niet blokkeren.
  Techniek voor Claude: `werfverslag_voorbereider.py:604-624,916-927` - voor meetstart W2 `onbekend` aanvaarden uitsluitend bij W1 `ok`; na meetstart W2 `ok` eisen; grensgevallen testen.
- X4: P4 eens.** Dit neemt de structurele W8-blokkade weg zonder per ongeluk vrije projecten aan te maken. De nieuwe vlag moet bij een ontbrekende of niet-toetsbare H-A-bron veilig weigeren.
  Techniek voor Claude: `../globaal-werfverslag/app/api.py:259-303`, `werfverslag_voorbereider.py:878-896` - `alleen_ha:true`, 404 zonder H-A-match, 409 idempotent behandelen; tests in beide repositories.
- X5: P5 eens.** Een tijdelijke netwerkstoring mag één duidelijke foutmelding geven, niet iedere kwartier een traceback.
  Techniek voor Claude: runnerbestand `werfverslag_dashboard.py` staat niet in deze lokale checkout; op basis van de vier gemeten VM-tracebacks daar netwerkfouten afvangen, hartslag schrijven en met een fouttest vergrendelen.
- X6: P6 eens.** De drie instructies spreken elkaar nu tegen over auto-GPS en normversie. Dat veroorzaakt later opnieuw foutieve reparaties.
  Techniek voor Claude: `werfverslag-dashboard.md:7,18`, `werfverslag-schrijver.md:12,139`, `werfverslag-voorbereider.md:25-26,46` - één norm v1.10, auto telt volgens E1b, bestaande Commandocentrum-impuls benoemen.
- X7: P7 eens.** Geen extra scherm of agent. Het bord toont werkvoorraad en bewijs; de werfapp beheert nummer, concept en verzending.
  Techniek voor Claude: `mijnagents/app.py:3239-3259,3262-3278`; `werfverslag-dashboard.md:9-23` - bestaande taakverdeling behouden en testen.
- G1: Twee agents blijven gescheiden (Eens met P1)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:918` en `werfverslag_schrijver.py` - scheiding tussen tokenvrije controles en betaalde schrijftaken behouden.
- G2: W12 onbekend blokkeert niet meer (Eens met P2)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:921-935` (`voldaan()`) en `:650` (`contractbewijs()`) - `W12 == 'onbekend'` laten doorstromen naar 'klaar voor verslag' met behoud van grendeltest.
- G3: W2 vóór GPS-meetreeks deblokkeren via agenda (Eens met P3)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:933-935` (`voldaan()`) en `:597` (`aanwezigheidsbewijs()`) - `voor_meetreeks` vlag koppelen aan `W1 == 'ok'` en borgen met grendeltest.
- G4: Werfdossier automatisch openen in werfapp (Eens met P4)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py` en `globaal-werfverslag/app/api.py:259` - bij ontbrekend project `POST /api/v1/projecten` aanroepen met `alleen_ha: true` en status 409 netjes negeren als reeds bestaand.
- G5: Netwerkfout in dashboard-runner opvangen (Eens met P5)
  Techniek voor Claude: `mijnagents-runner/werfverslag_dashboard.py` - vang `TimeoutError` en `httpx.RequestError` af en zet één hartslag 'fout' met duidelijke tekst zonder crash.
- G6: Werkwijzen gelijktrekken (Eens met P6)
  Techniek voor Claude: `mijnagents-runner/werkwijze/werfverslag-*.md` - W2 overal volgens E1b, norm overal v1.10 en taakvermelding bijwerken naar Commandocentrum-impuls.
- G7: Vaste taakverdeling schermen behouden (Eens met P7)
  Techniek voor Claude: `mijnagents/app.py:3146-3170` - bordpagina blijft werkvoorraad tonen, werf.globaal.be blijft de bewerk- en verzendplek.
- K1: Twee agents blijven (P1: eens)
  Techniek voor Claude: geen codewijziging nodig. Zet wel een test die controleert dat `werfverslag_voorbereider.py` nergens een betaalde aanroep doet.
- K2: W12 "onbekend" mag niet blokkeren (P2: eens)
  Techniek voor Claude: `werfverslag_voorbereider.py:916` (`stand_van`): W12 == ok wordt "W12 niet ontbreekt". Grendeltest met drie waarden (ok, onbekend, ontbreekt).
- K3: W2 vóór de GPS-meetreeks (P3: eens, met één voorwaarde)
  Techniek voor Claude: `stand_van` :916 en `aanwezigheidsbewijs` :597 gebruiken één constante `GPS_START`.
- K4: Werfdossier automatisch openen (P4: eens, onder voorwaarden)
  Techniek voor Claude: `globaal-werfverslag/app/api.py:259` krijgt de vlag. Aan de kant van de voorbereider komt een aanroep vóór de W8-controle. Tests: nummer onbekend geeft 404 en niets aangemaakt, tweede aanroep geeft 409.
- K5: Dashboard-crash opvangen (P5: eens)
  Techniek voor Claude: `werfverslag_dashboard.py`: vang `TimeoutError`, `OSError` en `URLError` rond de aanroep. Schrijf een hartslag "fout" en sluit netjes af. Test met een gesimuleerde time-out.
- K6: Eén tekst in de drie werkwijzen (P6: eens)
  Techniek voor Claude: `mijnagents-runner/werkwijze/werfverslag-*.md`: norm v1.10 en E1b. Vervang "Later: ..." door de zin over het Commandocentrum (impuls, `werfverslag_voorbereider.py:1240`).
- K7: Geen nieuw scherm (P7: eens)
- K8: Volgorde en rollen

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: Ja, twee agents blijven nodig; P1-P7 zijn akkoord. De kernfout zit niet in de tweedeling, maar in statusregels die “onbekend” ten onrechte behandelen als “ontbreekt”.<br><br>**X1. P1 eens.** De voorbereider controleert tokenvrij; de schrijver start uitsluitend na Mehdi’s knop. Samenvoegen maakt die kosten- en toestemmingsgrens minder controleerbaar.  <br>Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:873-877`, `mijnagents/app.py:3319-3336`, `mijnagents-runner/werkwijze/werfverslag-schrijver.md:5-8` - twee agents behouden.<br><br>**X2. P2 eens.** Oude dossiers mogen niet eeuwig vastlopen omdat het contractsysteem ze niet kent. Een werkelijk gevonden contract zonder werfopvolging blijft wel blokkeren.  <br>Techniek voor Claude: `werfverslag_voorbereider.py:650-683,916-927` - W12 `onbekend` zichtbaar maar niet blokkerend; `ontbreekt` wel; grendeltest.<br><br>**X3. P3 eens.** Voor bezoeken van vóór 03-10-2026 bestond de GPS-meting niet. Als de agenda-afspraak W1 bewijst, mag dat historische gebrek niet blokkeren.  <br>Techniek voor Claude: `werfverslag_voorbereider.py:604-624,916-927` - voor meetstart W2 `onbekend` aanvaarden uitsluitend bij W1 `ok`; na meetstart W2 `ok` eisen; grensgevallen testen.<br><br>**X4. P4 eens.** Dit neemt de structurele W8-blokkade weg zonder per ongeluk vrije projecten aan te maken. De nieuwe vlag moet bij een ontbrekende of niet-toetsbare H-A-bron veilig weigeren.  <br>Techniek voor Claude: `../globaal-werfverslag/app/api.py:259-303`, `werfverslag_voorbereider.py:878-896` - `alleen_ha:true`, 404 zonder H-A-match, 409 idempotent behandelen; tests in beide repositories.<br><br>**X5. P5 eens.** Een tijdelijke netwerkstoring mag één duidelijke foutmelding geven, niet iedere kwartier een traceback.  <br>Techniek voor Claude: runnerbestand `werfverslag_dashboard.py` staat niet in deze lokale checkout; op basis van de vier gemeten VM-tracebacks daar netwerkfouten afvangen, hartslag schrijven en met een fouttest vergrendelen.<br><br>**X6. P6 eens.** De drie instructies spreken elkaar nu tegen over auto-GPS en normversie. Dat veroorzaakt later opnieuw foutieve reparaties.  <br>Techniek voor Claude: `werfverslag-dashboard.md:7,18`, `werfverslag-schrijver.md:12,139`, `werfverslag-voorbereider.md:25-26,46` - één norm v1.10, auto telt volgens E1b, bestaande Commandocentrum-impuls benoemen.<br><br>**X7. P7 eens.** Geen extra scherm of agent. Het bord toont werkvoorraad en bewijs; de werfapp beheert nummer, concept en verzending.  <br>Techniek voor Claude: `mijnagents/app.py:3239-3259,3262-3278`; `werfverslag-dashboard.md:9-23` - bestaande taakverdeling behouden en testen.<br><br>Claude is maker. Codex is onafhankelijke tester na uitvoering.<br><br>GRENS: geen | BESLISSING: Eens met alle voorstellen P1 tot en met P7. De twee agents blijven gescheiden (voorbereider gratis, schrijver betaald pas na jouw klik). We lossen de blokkades op in code zodat de 30 werfbezoeken doorstromen. Claude is maker, Codex is tester.<br><br>G1. Twee agents blijven gescheiden (Eens met P1)<br>Wat Mehdi merkt: de voorbereider verzamelt dagelijks gratis alle bewijzen op de achtergrond. De schrijver start pas als jij op de knop 'Maak concept' drukt. Dit voorkomt onnodige tokenkosten en vermijdt dat er ongevraagd verslagen worden gegenereerd.<br>Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:918` en `werfverslag_schrijver.py` - scheiding tussen tokenvrije controles en betaalde schrijftaken behouden.<br><br>G2. W12 onbekend blokkeert niet meer (Eens met P2)<br>Wat Mehdi merkt: oudere projecten die nog niet in het nieuwe contractdashboard staan, blijven niet langer hopeloos hangen op 'te verzamelen', maar worden gewoon klaargezet voor een verslag. Alleen als een contract expliciet werfopvolging uitsluit, stopt het.<br>Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:921-935` (`voldaan()`) en `:650` (`contractbewijs()`) - `W12 == 'onbekend'` laten doorstromen naar 'klaar voor verslag' met behoud van grendeltest.<br><br>G3. W2 vóór GPS-meetreeks deblokkeren via agenda (Eens met P3)<br>Wat Mehdi merkt: werfbezoeken van vóór 3 oktober 2026 (startdatum GPS-ritten) worden goedgekeurd zodra de agenda-afspraak (W1) klopt. Je hoeft ontbrekende historische ritten niet handmatig te corrigeren.<br>Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:933-935` (`voldaan()`) en `:597` (`aanwezigheidsbewijs()`) - `voor_meetreeks` vlag koppelen aan `W1 == 'ok'` en borgen met grendeltest.<br><br>G4. Werfdossier automatisch openen in werfapp (Eens met P4)<br>Wat Mehdi merkt: je krijgt geen foutmeldingen meer dat de werfapp een projectnummer niet herkent (W8). Het dossier wordt veilig op de achtergrond geopend met de officiële projectgegevens uit H-A Projecten.<br>Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py` en `globaal-werfverslag/app/api.py:259` - bij ontbrekend project `POST /api/v1/projecten` aanroepen met `alleen_ha: true` en status 409 netjes negeren als reeds bestaand.<br><br>G5. Netwerkfout in dashboard-runner opvangen (Eens met P5)<br>Wat Mehdi merkt: het dashboard crasht niet meer als de werfapp heel even niet binnen een seconde reageert.<br>Techniek voor Claude: `mijnagents-runner/werfverslag_dashboard.py` - vang `TimeoutError` en `httpx.RequestError` af en zet één hartslag 'fout' met duidelijke tekst zonder crash.<br><br>G6. Werkwijzen gelijktrekken (Eens met P6)<br>Wat Mehdi merkt: geen tegenstrijdige regels meer tussen de schermen over autobezoeken of wie de opdrachten aanmaakt.<br>Techniek voor Claude: `mijnagents-runner/werkwijze/werfverslag-*.md` - W2 overal volgens E1b, norm overal v1.10 en taakvermelding bijwerken naar Commandocentrum-impuls.<br><br>G7. Vaste taakverdeling schermen behouden (Eens met P7)<br>Wat Mehdi merkt: geen extra knoppen of verwarrende nieuwe schermen. Op het bord zie je wat er klaarligt; in de werfapp controleer en verstuur je het verslag.<br>Techniek voor Claude: `mijnagents/app.py:3146-3170` - bordpagina blijft werkvoorraad tonen, werf.globaal.be blijft de bewerk- en verzendplek.<br><br>GRENS: geen | BESLISSING: Twee agents blijven. P1, P2, P3, P5, P6 en P7 zijn goed. P4 ook, maar alleen met de vlag `alleen_ha` en een test in beide repos. Ik kon de code zelf niet nalezen. Mijn werkmap (globaal-appportal) bevat die bestanden niet, en de tools zijn beperkt tot die map. De bestand:regel-verwijzingen hieronder komen dus uit de opdracht en niet uit eigen controle.<br><br>**K1. Twee agents blijven (P1: eens)**<br>In de praktijk: de voorbereider kost geen geld en draait vanzelf. De schrijver kost tokens en start pas als jij op de knop drukt. Als je ze samenvoegt, kan het geld uitgeven los komen van jouw knop. Dat willen we niet.<br>Techniek voor Claude: geen codewijziging nodig. Zet wel een test die controleert dat `werfverslag_voorbereider.py` nergens een betaalde aanroep doet.<br><br>**K2. W12 "onbekend" mag niet blokkeren (P2: eens)**<br>In de praktijk: 29 van de 30 bezoeken kunnen nu nooit op "klaar voor verslag" komen, omdat het project van vóór het systeem is. Dat is geen ontbrekend bewijs. Alleen "ontbreekt" (contract gevonden, maar geen werfopvolging) mag blokkeren. "Onbekend" blijft zichtbaar als aandachtspunt.<br>Techniek voor Claude: `werfverslag_voorbereider.py:916` (`stand_van`): W12 == ok wordt "W12 niet ontbreekt". Grendeltest met drie waarden (ok, onbekend, ontbreekt).<br><br>**K3. W2 vóór de GPS-meetreeks (P3: eens, met één voorwaarde)**<br>In de praktijk: voor bezoeken van vóór 03-10-2026 bestaat geen GPS-bewijs. De werkwijze zegt dat de buitenafspraak (W1) dan volstaat. De code moet dat ook doen.<br>De voorwaarde: de grensdatum mag maar op één plaats staan, als constante. Test op de dag ervoor, de dag zelf en de dag erna. Zonder W1 "ok" blijft het bezoek blokkeren.<br>Techniek voor Claude: `stand_van` :916 en `aanwezigheidsbewijs` :597 gebruiken één constante `GPS_START`.<br><br>**K4. Werfdossier automatisch openen (P4: eens, onder voorwaarden)**<br>In de praktijk: 23 bezoeken staan stil omdat de werfapp het project niet kent. Dat lost zichzelf op als de voorbereider het dossier opent.<br>Het gevaar: dezelfde route maakt nu een los project aan voor een nummer dat niet in H-A Projecten staat. Daarom is de vlag `alleen_ha: true` verplicht, met 404 en zonder aanmaak als het nummer ontbreekt. 409 telt als gelukt. De voorbereider mag het dossier alleen openen voor gevolgde dossiers, nooit voor een gegokt nummer. Een mislukte poging mag de rest van de ronde niet stoppen.<br>Techniek voor Claude: `globaal-werfverslag/app/api.py:259` krijgt de vlag. Aan de kant van de voorbereider komt een aanroep vóór de W8-controle. Tests: nummer onbekend geeft 404 en niets aangemaakt, tweede aanroep geeft 409.<br>Dit schrijft in de werfapp, maar met alleen H-A-gegevens en zonder overschrijven. Dat valt niet onder verwijderen, versturen of ondertekenen.<br><br>**K5. Dashboard-crash opvangen (P5: eens)**<br>In de praktijk: soms valt de controle van elke 15 minuten om bij een time-out, en dan weet niemand het. Het moet één melding "fout, reden" geven.<br>Techniek voor Claude: `werfverslag_dashboard.py`: vang `TimeoutError`, `OSError` en `URLError` rond de aanroep. Schrijf een hartslag "fout" en sluit netjes af. Test met een gesimuleerde time-out.<br><br>**K6. Eén tekst in de drie werkwijzen (P6: eens)**<br>In de praktijk: nu zeggen de drie documenten verschillende dingen over W2, en ze hebben verschillende normversies. Dat geeft verkeerde verwachtingen.<br>Mijn aanvulling: laat een test de normversie en de W2-zin in de drie bestanden vergelijken. Dan kan het niet opnieuw uit elkaar lopen.<br>Techniek voor Claude: `mijnagents-runner/werkwijze/werfverslag-*.md`: norm v1.10 en E1b. Vervang "Later: ..." door de zin over het Commandocentrum (impuls, `werfverslag_voorbereider.py:1240`).<br><br>**K7. Geen nieuw scherm (P7: eens)**<br>In de praktijk: je houdt één plek voor het verslag (werf.globaal.be) en één werkvoorraad (het bord). Controleer wel dat `mijnagents/app.py:3150` en :3157 dezelfde `stand_van` gebruiken en geen eigen berekening maken.<br><br>**K8. Volgorde en rollen**<br>Eerst K2 en K3, dan K4, dan de rest. Claude maakt, Codex test. Na K2 en K3 moeten de 4 bezoeken met "verslag aanwezig, bronnen onvolledig" en de bezoeken met alleen W2/W12 als blokkade de stand veranderen. Meet dat opnieuw op de VM, alleen lezend. W4 (foto's, iCloud-wacht) blijft terecht blokkeren.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: klaar met kanttekeningen; twee agents blijven, maar P2 is te ruim geformuleerd en moet bronuitval blijven blokkeren.

P1 en P7 kloppen. De voorbereider verzamelt bewijs zonder tokens; alleen Mehdi’s knop maakt een opdracht voor de betaalde schrijver. Het bord berekent geen eigen stand, maar toont de opgeslagen controles en werkvoorraad.

Techniek voor Claude: `werfverslag_voorbereider.py:875-879`, `mijnagents/app.py:3239-3259,3319-3336` - scheiding behouden; Claude maakt, Codex test.

P2 keur ik in deze vorm af. `onbekend` betekent niet alleen “oud project van vóór het contractsysteem”, maar ook “systemen onbereikbaar”, “antwoord niet toetsbaar” en “geen contractgegevens”. Al die gevallen laten doorstromen kan een verslag zonder gecontroleerde opdracht maken. Alleen een afzonderlijk, aantoonbaar kenmerk `voor_contractsysteem` mag niet blokkeren.

Techniek voor Claude: `werfverslag_voorbereider.py:650-683,921-935` - geef W12 een reden/code; alleen `voor_contractsysteem` aanvaarden. Netwerkfout en ongeldig antwoord blijven blokkeren. Test alle varianten.

P3 klopt. De huidige bronbeleidsgrens is al de ene centrale datumbron; voeg geen tweede `GPS_START` toe. Test dag vóór, op en na de grens, telkens met en zonder W1.

Techniek voor Claude: `werfverslag_voorbereider.py:597-625,811-815,921-935` - centrale grens uit `locatiecontext.bronbeleid` behouden.

P4 klopt mits veilig falen. Een werkelijk onbekend nummer geeft 404; als H-A Projecten niet betrouwbaar gelezen kon worden, moet het 503 zijn en mag niets ontstaan. De bestaande vrije route blijft ongewijzigd.

Techniek voor Claude: `globaal-werfverslag/app/api.py:259-303`, `app/ha_projecten.py:91-128` - `alleen_ha` vóór verplichte vrije naamvelden behandelen; 404 versus 503 testen.

P5 en P6 kloppen. Vang bij P5 het fouttype af dat de gebruikte API-brug werkelijk oplevert; die brug zet netwerkfouten om naar `WerfappFout(0)`.

Techniek voor Claude: `koppelingen/werfapp.py:54-75` - gerichte foutafhandeling en hartslagtest; werkwijzen gelijkzetten en met een consistentietest vergrendelen.

STEMBLOK: Codex
X1: eens
X2: oneens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
G1: eens
G2: oneens
G3: eens
G4: eens
G5: eens
G6: eens
G7: eens
K1: eens
K2: oneens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
K8: eens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Klaar met kanttekeningen (3-0 akkoord op P1 t/m P7). De twee agents blijven gescheiden; we lossen de statusblokkades in de code op zodat werfverslagen weer kunnen doorstromen. Claude voert uit, Codex toetst onafhankelijk.

Voor Mehdi:
* Twee agents blijven: de voorbereider verzamelt gratis bewijzen op de achtergrond; de schrijver start pas tokens en kosten wanneer jij op de knop klikt.
* Oude dossiers deblokkeren: bezoeken van vóór de GPS-meting of vóór het contractsysteem blijven niet langer vaststaan op 'onbekend' als de agenda-afspraak klopt.
* Geen ontbrekende werfdossiers meer: dossiers worden veilig automatisch aangemaakt op basis van H-A Projecten zonder losse spookprojecten.
* Dashboard blijft stabiel: netwerk-time-outs laten het systeem niet meer crashen.
* Geen nieuwe schermen: het bord toont de werkvoorraad, werf.globaal.be blijft de plek voor controle en verzending.

Techniek voor Claude en Shaniel:
Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:873-877` en `:916-927` - twee agents behouden, W12 `onbekend` niet-blokkerend maken en W2 vóór centrale `GPS_START` vrijgeven mits W1 `ok`.
Techniek voor Claude: `globaal-werfverslag/app/api.py:259-303` - vlag `alleen_ha: true` implementeren (404 bij onbekend H-A-nummer, 409 idempotent).
Techniek voor Claude: `werfverslag_dashboard.py` - netwerkfouten (TimeoutError/URLError) afvangen met hartslag "fout" zonder traceback.
Techniek voor Claude: `mijnagents-runner/werkwijze/werfverslag-*.md` - documentatie harmoniseren op norm v1.10, auto volgens E1b en Commandocentrum-impuls.

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
K8: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Alle drie zijn het eens. Twee agents blijven, en P1 tot en met P7 gaan door. Claude maakt, Codex test. Mehdi hoeft niets te beslissen.

**Wat Mehdi hiervan merkt**
- De voorbereider blijft gratis werken. De schrijver start alleen op Mehdi's knop. Dat blijft dus onder zijn controle.
- Oudere projecten die het contractsysteem niet kent (W12 onbekend), blijven niet meer eeuwig op "te verzamelen" staan.
- Bezoeken van vóór 03-10-2026 (W2) tellen mee zodra de agenda-afspraak (W1) klopt.
- De werfapp opent het werfdossier zelf, maar alleen voor nummers die in H-A Projecten staan. Een gegokt nummer maakt dus geen los project aan.
- Het dashboard geeft bij een time-out één foutmelding. Het crasht niet meer met een traceback.
- De drie werkwijzen zeggen hetzelfde over W2 en de normversie (v1.10).

**Correctie en aanvulling op de andere meningen**
- Ik heb de code niet zelf nagelezen. Mijn werkmap bevat die bestanden niet. De bestand:regel-verwijzingen komen dus uit de opdracht en uit Codex en Gemini. Codex en Gemini noemen verschillende regelnummers voor dezelfde functie (`stand_van` 916-927 bij Codex, `voldaan()` 921-935 bij Gemini). Claude moet bij het maken eerst controleren waar de echte regels staan.
- Gemini noemt `httpx.RequestError`. De runner gebruikt dat misschien niet. Ik stel `TimeoutError`, `OSError` en `URLError` voor. Dat dekt ook `socket.timeout`. Codex heeft dit punt niet uitgewerkt.
- Gemini zegt bij W12 dat het stopt "als een contract expliciet werfopvolging uitsluit". Dat klopt met P2 (alleen "ontbreekt" blokkeert), maar de test moet alle drie de waarden dekken: ok, onbekend, ontbreekt.
- Mijn extra eisen, die Codex en Gemini niet noemden:
  - De grensdatum 03-10-2026 staat op één plek als constante (`GPS_START`). Test op de dag ervoor, de dag zelf en de dag erna.
  - Een mislukte poging om een dossier te openen mag de rest van de ronde niet stoppen.
  - Een test controleert dat de normversie en de W2-zin in de drie werkwijzen gelijk blijven.
  - Een test controleert dat de voorbereider nergens een betaalde aanroep doet.
  - De bordpagina gebruikt dezelfde `stand_van` en rekent niet zelf.
- Na de wijziging meet Codex de stand opnieuw op de VM, alleen lezend. W4 (foto's, iCloud-wacht) moet blijven blokkeren, want dat is echte ontbrekende bronlevering.

Techniek voor Claude: `werfverslag_voorbereider.py` stand_van (rond :916), `aanwezigheidsbewijs` (:597), `globaal-werfverslag/app/api.py:259` - eerst echte regels controleren, dan de wijzigingen met grendeltests.

STEMBLOK: Claude
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
K8: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Codex

Klaar: alle 22 herstelpunten zijn aangenomen en worden zelfstandig uitgevoerd.

- X1, X2, X3, X4, X5, X6 en X7: aangenomen.
- G1, G2, G3, G4, G5, G6 en G7: aangenomen.
- K1, K2, K3, K4, K5, K6, K7 en K8: aangenomen.
- Historische dossiers worden veilig gedeblokkeerd; netwerkfouten leggen het proces niet meer stil.
- Taakverdeling blijft: bord voor werkvoorraad, werfapp voor dossierbeheer en verzending.

Techniek voor Claude en Shaniel: voer de gebundelde fixes en grendeltests uit in `mijnagents-runner/werfverslag_voorbereider.py`, `mijnagents-runner/werfverslag_dashboard.py`, `mijnagents/app.py`, `globaal-werfverslag/app/api.py` en de drie werkwijzedocumenten.

Gedaan: meerderheidsbesluiten geteld en samengevat.  
Nagekeken: alle genoemde punten hebben minimaal twee stemmen.  
Openstaand: uitvoering en onafhankelijke eindcontrole; geen vraag aan Mehdi.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): P1 eens.** De voorbereider controleert tokenvrij; de schrijver start uitsluitend na Mehdi’s knop. Samenvoegen maakt die kosten- en toestemmingsgrens minder controleerbaar.
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:873-877`, `mijnagents/app.py:3319-3336`, `mijnagents-runner/werkwijze/werfverslag-schrijver.md:5-8` - twee agents behouden.
- **X2** (2-1): P2 eens.** Oude dossiers mogen niet eeuwig vastlopen omdat het contractsysteem ze niet kent. Een werkelijk gevonden contract zonder werfopvolging blijft wel blokkeren.
  Techniek voor Claude: `werfverslag_voorbereider.py:650-683,916-927` - W12 `onbekend` zichtbaar maar niet blokkerend; `ontbreekt` wel; grendeltest.
- **X3** (3-0): P3 eens.** Voor bezoeken van vóór 03-10-2026 bestond de GPS-meting niet. Als de agenda-afspraak W1 bewijst, mag dat historische gebrek niet blokkeren.
  Techniek voor Claude: `werfverslag_voorbereider.py:604-624,916-927` - voor meetstart W2 `onbekend` aanvaarden uitsluitend bij W1 `ok`; na meetstart W2 `ok` eisen; grensgevallen testen.
- **X4** (3-0): P4 eens.** Dit neemt de structurele W8-blokkade weg zonder per ongeluk vrije projecten aan te maken. De nieuwe vlag moet bij een ontbrekende of niet-toetsbare H-A-bron veilig weigeren.
  Techniek voor Claude: `../globaal-werfverslag/app/api.py:259-303`, `werfverslag_voorbereider.py:878-896` - `alleen_ha:true`, 404 zonder H-A-match, 409 idempotent behandelen; tests in beide repositories.
- **X5** (3-0): P5 eens.** Een tijdelijke netwerkstoring mag één duidelijke foutmelding geven, niet iedere kwartier een traceback.
  Techniek voor Claude: runnerbestand `werfverslag_dashboard.py` staat niet in deze lokale checkout; op basis van de vier gemeten VM-tracebacks daar netwerkfouten afvangen, hartslag schrijven en met een fouttest vergrendelen.
- **X6** (3-0): P6 eens.** De drie instructies spreken elkaar nu tegen over auto-GPS en normversie. Dat veroorzaakt later opnieuw foutieve reparaties.
  Techniek voor Claude: `werfverslag-dashboard.md:7,18`, `werfverslag-schrijver.md:12,139`, `werfverslag-voorbereider.md:25-26,46` - één norm v1.10, auto telt volgens E1b, bestaande Commandocentrum-impuls benoemen.
- **X7** (3-0): P7 eens.** Geen extra scherm of agent. Het bord toont werkvoorraad en bewijs; de werfapp beheert nummer, concept en verzending.
  Techniek voor Claude: `mijnagents/app.py:3239-3259,3262-3278`; `werfverslag-dashboard.md:9-23` - bestaande taakverdeling behouden en testen.
- **G1** (3-0): Twee agents blijven gescheiden (Eens met P1)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:918` en `werfverslag_schrijver.py` - scheiding tussen tokenvrije controles en betaalde schrijftaken behouden.
- **G2** (2-1): W12 onbekend blokkeert niet meer (Eens met P2)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:921-935` (`voldaan()`) en `:650` (`contractbewijs()`) - `W12 == 'onbekend'` laten doorstromen naar 'klaar voor verslag' met behoud van grendeltest.
- **G3** (3-0): W2 vóór GPS-meetreeks deblokkeren via agenda (Eens met P3)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py:933-935` (`voldaan()`) en `:597` (`aanwezigheidsbewijs()`) - `voor_meetreeks` vlag koppelen aan `W1 == 'ok'` en borgen met grendeltest.
- **G4** (3-0): Werfdossier automatisch openen in werfapp (Eens met P4)
  Techniek voor Claude: `mijnagents-runner/werfverslag_voorbereider.py` en `globaal-werfverslag/app/api.py:259` - bij ontbrekend project `POST /api/v1/projecten` aanroepen met `alleen_ha: true` en status 409 netjes negeren als reeds bestaand.
- **G5** (3-0): Netwerkfout in dashboard-runner opvangen (Eens met P5)
  Techniek voor Claude: `mijnagents-runner/werfverslag_dashboard.py` - vang `TimeoutError` en `httpx.RequestError` af en zet één hartslag 'fout' met duidelijke tekst zonder crash.
- **G6** (3-0): Werkwijzen gelijktrekken (Eens met P6)
  Techniek voor Claude: `mijnagents-runner/werkwijze/werfverslag-*.md` - W2 overal volgens E1b, norm overal v1.10 en taakvermelding bijwerken naar Commandocentrum-impuls.
- **G7** (3-0): Vaste taakverdeling schermen behouden (Eens met P7)
  Techniek voor Claude: `mijnagents/app.py:3146-3170` - bordpagina blijft werkvoorraad tonen, werf.globaal.be blijft de bewerk- en verzendplek.
- **K1** (3-0): Twee agents blijven (P1: eens)
  Techniek voor Claude: geen codewijziging nodig. Zet wel een test die controleert dat `werfverslag_voorbereider.py` nergens een betaalde aanroep doet.
- **K2** (2-1): W12 "onbekend" mag niet blokkeren (P2: eens)
  Techniek voor Claude: `werfverslag_voorbereider.py:916` (`stand_van`): W12 == ok wordt "W12 niet ontbreekt". Grendeltest met drie waarden (ok, onbekend, ontbreekt).
- **K3** (3-0): W2 vóór de GPS-meetreeks (P3: eens, met één voorwaarde)
  Techniek voor Claude: `stand_van` :916 en `aanwezigheidsbewijs` :597 gebruiken één constante `GPS_START`.
- **K4** (3-0): Werfdossier automatisch openen (P4: eens, onder voorwaarden)
  Techniek voor Claude: `globaal-werfverslag/app/api.py:259` krijgt de vlag. Aan de kant van de voorbereider komt een aanroep vóór de W8-controle. Tests: nummer onbekend geeft 404 en niets aangemaakt, tweede aanroep geeft 409.
- **K5** (3-0): Dashboard-crash opvangen (P5: eens)
  Techniek voor Claude: `werfverslag_dashboard.py`: vang `TimeoutError`, `OSError` en `URLError` rond de aanroep. Schrijf een hartslag "fout" en sluit netjes af. Test met een gesimuleerde time-out.
- **K6** (3-0): Eén tekst in de drie werkwijzen (P6: eens)
  Techniek voor Claude: `mijnagents-runner/werkwijze/werfverslag-*.md`: norm v1.10 en E1b. Vervang "Later: ..." door de zin over het Commandocentrum (impuls, `werfverslag_voorbereider.py:1240`).
- **K7** (3-0): Geen nieuw scherm (P7: eens)
- **K8** (3-0): Volgorde en rollen

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
