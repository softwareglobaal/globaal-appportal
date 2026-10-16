# Verwerking ontwerpronde 5: levensloop van .herstel

Door Claude, 16-10-2026. Codex: optie A, met één herstelovergang per cronronde; nog niet klaar. Vier nieuwe punten van
ernst middel (BU-23 tot BU-26). Claude raadt eveneens A aan. Volgens de stopregel beslist Mehdi vóór er gebouwd wordt.

## Nameting

| Punt | Oordeel | Nameting |
|---|---|---|
| BU-23 middel | gelijk | `git rev-parse` staat vóór de behandeling van `.herstel`; een Git-fout laat een ongezonde kandidaat staan |
| BU-24 middel | gelijk | `terug` zet `:latest` op de vorige image; faalt compose, dan draait de kandidaat door; hervatten markeert hem later als gebouwd terwijl `:latest` naar de vorige wijst |
| BU-25 middel | gelijk | `draait()` maakt van een inspectiefout een leeg ID; dan lijkt er geen container en kan de terugrolimage ontbreken |
| BU-26 middel | gelijk (race) | `compose up` leest de werkboom; een pull tijdens de ronde kan een latere compose-configuratie toepassen. Gemeten op de VM: de lokale wijzigingen in `docker-compose.override.yml` raken `app-mijnagents` niet; wel geeft `docker compose config --hash app-mijnagents` nu `84e3962b…` en draagt de container `536c85a9…` (gemaakt 14-10 21:50, compose 5.1.4). De oorzaak (rekenwijze of echte configuratie) is niet vastgesteld |

## Ontwerp A, zoals Claude het zou bouwen na een ja

1. Een open `.herstel` blokkeert elke bouw. Per cronronde hooguit één overgang: herstellen óf uitrollen, nooit beide.
2. `.herstel` wordt alleen geschreven als er geen open herstel is, en nooit overschreven. Inhoud:
   `VORIGE-ID KANDIDAAT-ID revisie poging`. Een oude markering met drie velden wordt behandeld als "kandidaat
   onbekend"; een onleesbare markering verdwijnt niet vanzelf (blokkeren en melden).
3. `.herstel` wordt behandeld vóór het lezen van HEAD (BU-23).
4. De markering verdwijnt pas bij een volledig kloppende eindtoestand: het draaiende ID gezond, `:latest` op dat ID,
   `.built` en `.built_id` passend en met succes geschreven (BU-21, BU-24). Voltooien eist precies het KANDIDAAT-ID,
   niet alleen het label (BU-22).
5. `afbreken` gebruikt `VORIGE` als hersteldoel, kijkt de tag na en laat de markering staan zolang dat niet lukt
   (BU-19, BU-20).
6. Een inspectiefout is iets anders dan een ontbrekende container: bij een fout stopt de ronde (BU-25).
7. De compose-confighash van `app-mijnagents` wordt bij het begin en vlak voor de wissel bepaald; verschilt hij, dan
   geen wissel (BU-26). Een pull op de VM gebeurt onder het slot:
   `flock ~/appportal/mijnagents-data/.deploy.lock git -C ~/appportal pull --ff-only`.
8. Handmatige vrijgave na een blijvend mislukt herstel, als één procedure in de kop van het script: `.pauze`, bord met
   de hand in orde brengen, `.herstel` en eventueel `.mislukt` weg, `.built` op de revisie die draait, pauze opheffen.
9. Tests minstens: gewone wissel; onderbreking voor en na de tag; gezonde kandidaat met verkeerde `:latest`; gezonde
   vorige image met half geschreven metadata; mislukte terugzetting met nieuwere HEAD zonder bouw en daarna geslaagd
   herstel; halve tagfout waarbij terugtaggen faalt; Git-fout met open markering; oud of ongeldig markerformaat;
   inspectiefout bij een gezond bord; de eerste uitrol zonder vorige image als uitdrukkelijke uitzondering.

Gevolg van A: is de vorige image blijvend kapot, dan wacht ook een herstelde revisie op een mens (zichtbaar in het log,
met de procedure uit punt 8). De eis uit CX10 (geen blijvende blokkade door een tijdelijke storing) blijft gelden:
elke ronde probeert het herstel opnieuw.

Optie B (twee markeringen, nieuwere revisie mag bouwen als het herstel faalt) houdt meer toestanden en combinaties;
Codex en Claude raden haar af.

## Voor de bewaakte uitrol, los van de keuze

Omdat de confighash afwijkt: bij de eerste wissel de omgevingsnamen (geen waarden), mounts, poorten en netwerken van de
container voor en na vergelijken, naast `/gezondheid`, het aantal agents (tegen de logregel van de kopie), `.built`,
`.built_id`, `:vorige` en een verse agenthartslag.
