# Namen en mappen: permanent toezicht

Versie 1.0, 05-10-2026.

Benamingenwacht en Mappenwacht draaien elk kwartier op de VM en gebruiken één metadata-index. Het gezamenlijke overzicht staat op `https://mijnagents.globaal.be/naamstructuur`, bereikbaar via **Namen en mappen** op het bord. Alleen bestaand bordbeheer ziet namen, paden, bronidentiteiten en voorstellen. De twee kaarten zijn beheerkaarten, op basis van het mandaat en de inhoud van het overzicht. Het woord privé in een mapnaam bepaalt geen toegang.

## Wat wordt gecontroleerd

| Bron | Bereik | Toets |
|---|---|---|
| Dropbox | `/Work All`, `/Data uit Mehdi`, afzonderlijk bevestigde teammap `/0 Chegini Mehdi/Prive met Claude` | Namen van bestanden en mappen: uitwisselbaarheid; voor herkende H-A-dossiers de bevestigde regels |
| H-A-projectmappen | onder `/Work All/01. H-A WORK`, rechtstreeks in bekende projectfasen | A13 dossiernaam; A1 centrale communicatie; A3-A6 momentnamen; B1 verslagbestand |
| H-A-salesmappen | de bestaande Offerte- en B2B-roots | A14 dossierfiche en oude bronmapnamen; afwezige bronmappen worden niet zonder bewijs als fout aangemerkt |
| Agenda | metadata die de bestaande Agendawacht op het bord heeft geïndexeerd | bestaande `lees_titel` en gedeelde nummerlezer, zonder nieuwe externe accountscan |
| Fathom/Plaud | geregistreerde gesprekken met leesbare lokale `gesprek.json` | bestaande `benaming.benoem`; een onleesbare bron staat als niet getoetst |

De projectfasen worden als volledige paden vastgelegd, geen algemene toets op een naam die met een cijfer begint. De fasepaden uit A13 zijn vergeleken met de bestaande directe Standaard- en Light-mappen op 05-10-2026. Daardoor zijn `0 Fathom`, numerieke opnames en proefmappen geen projectdossiers. Andere opslag-/archieffasen krijgen pas een projectprofiel nadat hun bronpad bevestigd is.

De firma bij een pad is uitsluitend een expliciete profielmapping, bij agenda of gesprek de herkende metadatafirma. Dit bewijst geen dossierhouder. Andere firma's krijgen alleen algemene bestandsnaamcontrole totdat hun structuurboek bevestigd is. Pipedrive-dealtitels, Google-/Xelion-contacten, andere accounts, officiële adressen en bestandsinhoud krijgen geen nieuwe zelfstandige scan. Die beperkingen staan altijd in het overzicht.

## Bronnen van de regels

De actuele bevestigde bron is **H-A vaste afspraken v1.7**, cloudpad `/Work All/01. H-A WORK/_0 Claude reorganisatie/H-A vaste afspraken v1.7.md`. V1.5 en het oude uittreksel zijn gelezen als voorgeschiedenis; A13 en A14 uit v1.7 bepalen de project- en salescontrole. `werkwijze/naamstructuur-regels.json` is de machinevertaling met pad, versie en SHA-256. Dit is geen nieuw firmaregister: codes blijven uit `kern.firma`, via de bestaande organisatiekoppeling en de bestaande nummerlezer.

Elke dag wordt het bronboek via Dropbox opgehaald en aan de bevestigde vingerafdruk getoetst. Bij wijziging of onleesbaarheid pauzeren H-A-toetsen; eerdere punten worden niet stilzwijgend als opgelost gemarkeerd. Werk dan de bronvertaling én gerichte tests bij. De werkwijze op het bord blijft de procesbron; het installatieprogramma overschrijft geen afwijkende bordtekst.

## Voortgang en dagelijkse dekking

De eerste basislijst is recursief, gepagineerd en begrensd op standaard acht pagina's van maximaal 500 items per root per ronde. Daarna wordt met dezelfde Dropbox-cursor alleen de delta gelezen. Metadata en cursor worden samen opgeslagen; bij een fout wordt uitsluitend de laatste geslaagde pagina hervat. Een nieuwe namespace of gewijzigd rootpad mag nooit een oude cursor gebruiken. Een ontbrekende teamnamespace blokkeert alleen dat bereik en verschijnt expliciet in het overzicht.

Per agent worden standaard maximaal 3000 vuile items per ronde verwerkt. De achterstand wordt per bereik getoond. Een gedeeld `flock` voorkomt overlappende indexschrijvers. Als een ronde nog loopt, hervat de volgende ronde. Een crash geeft via de gedeelde bordronde een foutstatus. De kaarten en de Agentnorm merken een ontbrekende hartslag na 45 minuten op.

Ontbrekende mappen of bestanden worden alleen vastgesteld als de gehele basislijst en alle ontvangen wijzigingspagina's van die root zijn verwerkt, zonder leesfout. De dagelijkse volledige-dekkingscontrole bevestigt de ingestelde roots, basisvolledigheid, deltapaginering, bereikbaarheid en regelbron. Het is geen nieuwe volledige scan van miljoenen items. Het cloudaccount bepaalt de leesrechten; lokale nulbytes worden niet als leeg of afwezig gelezen.

Een bevinding is uniek per agent, bronbereik, stabiele bronidentiteit en regel. Herhaalde controles werken hetzelfde punt bij. Hernoemen in de bron behoudt de identiteit; herstel sluit het punt. Een Dropbox-tombstone markeert alleen lokale metadata als niet meer aanwezig. De bron wordt nooit door deze agents verwijderd.

## Installatie op de VM

Er is geen Postgres-migratie en geen nieuwe leesrol nodig. De lokale SQLite wordt door de runner idempotent aangemaakt in `~/appportal/mijnagents-data/naamstructuur/index.sqlite3`; `overzicht.json` is de samenvatting die de bestaande compose-mount onder `/data` aan de beheerpagina beschikbaar maakt.

Bestaande sleutelnamen in `~/appportal/.env`: `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`. Bestaande tokennaam in `~/appportal/mijnagents-data/.env`: `AGENTS_TOKEN`. Geen waarden in documentatie of uitvoer.

Bevestig voor de overkoepelende teammap de accountnamespace via bestaande Dropbox-account-/teammetadata en zet uitsluitend de identifier als `NAAMSTRUCTUUR_OVERKOEPELEND_NS` in `~/appportal/.env`. Bij een andere servermapping kan een VM-configbestand het bereik aanpassen via `NAAMSTRUCTUUR_REGELS`. Het bronpad en de namespace worden beide zichtbaar gemaakt. Geen nieuwe token of extra leesrechten toekennen om een geblokkeerde map toch te lezen. `NAAMSTRUCTUUR_DATA` is optioneel; standaard hoort deze onder het bestaande datavolume en moet de beheerpagina dezelfde map blijven gebruiken.

Na pull van de geverifieerde commit:

```sh
cd ~/appportal
docker compose build app-mijnagents
docker compose up -d app-mijnagents
~/agents/.venv/bin/python mijnagents-runner/planning/naamstructuur_installeren.py
~/agents/.venv/bin/python mijnagents-runner/planning/naamstructuur_installeren.py --zet
~/agents/.venv/bin/python mijnagents-runner/benamingen_wacht.py
~/agents/.venv/bin/python mijnagents-runner/mappen_wacht.py
~/agents/.venv/bin/python mijnagents-runner/controle_agenten.py --agent benamingen-wacht --uitleg
~/agents/.venv/bin/python mijnagents-runner/controle_agenten.py --agent mappen-wacht --uitleg
```

De installer bewaart de vorige crontab en vervangt alleen zijn eigen gemarkeerde blok. Andere taken blijven staan. Bestaande losse planning van dezelfde runners wordt geweigerd voor handmatige beoordeling. Opnieuw installeren maakt geen dubbele kaarten, planning of werkwijzeversies.

## Grenzen en verificatie

Geen autonoom hernoemen, verplaatsen, verwijderen, documentwijzigingen of extern berichten versturen. Geen Bode-/Telegram-/WhatsApp-signalen en geen uitvoerbare voorstellen. Mehdi ziet concrete punten op het bord en beslist over afzonderlijke uitvoering.

Grendels: `tests/test_naamstructuur.py` voor paginering, atomiciteit, hervatten, accountroot, bronwijzigingen, online-only metadata, puntidentiteit en behoud van crontab; `mijnagents/test_naamstructuur.py` voor beheergrens, veilige weergave en paginering. Ze draaien in GitHub Actions, de dashboardgrendels ook in de Docker-build. Testdata zijn verzonnen. Werkelijk gescande roots, achterstand, hartslag en eventuele geblokkeerde bron zijn uitsluitend uit het live overzicht af te leiden.
