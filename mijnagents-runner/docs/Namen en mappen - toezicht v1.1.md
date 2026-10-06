# Namen en mappen: permanent toezicht

Versie 1.1, 06-10-2026. Vervangt v1.0 als actuele installatiehandleiding. V1.0 blijft als voorgeschiedenis staan.

Benamingenwacht en Mappenwacht draaien elk kwartier op de VM en delen één metadata-index. Het gezamenlijke overzicht staat op `https://mijnagents.globaal.be/naamstructuur`, via **Namen en mappen** op het bord. Bestaand bordbeheer ziet concrete bronidentiteiten, namen, paden, regels, voorstellen en status. De kaarten en openbare hartslag bevatten alleen neutrale werkstatus. Het woord privé in een mapnaam bepaalt geen rechten.

## Bestaande koppeling en bevestigd bereik

Alle drie roots én de dagelijkse H-A-regelbron gebruiken de reeds ingestelde **OMV-v2-Dropbox-koppeling**. Deze verbinding is op de VM gecontroleerd met accountmetadata, `get_metadata` en een begrensde recursieve `list_folder`-pagina per root. Er is geen nieuwe OAuth-toestemming, scope, token of leesrol aangevraagd.

| Bronbereik | Vastgestelde namespace | Verbinding |
|---|---|---|
| `/Work All` | accountroot van de bestaande OMV-v2-koppeling | `omv-v2` |
| `/Data uit Mehdi` | dezelfde accountroot | `omv-v2` |
| `/0 Chegini Mehdi/Prive met Claude` | afzonderlijke bestaande teamnamespace | `omv-v2` |
| H-A-afsprakenboek v1.7 onder Work All | dezelfde OMV-v2-accountroot | `omv-v2` |

De bevestigde namespace-identifiers staan expliciet in `werkwijze/naamstructuur-regels.json` en het live overzicht. Voor gedeelde namespaces gebruikt de Dropbox-header `namespace_id`, niet een willekeurige accountroot. Namen en paden gelden steeds binnen de genoemde verbinding en namespace.

De verbinding leest de bestaande configuratie `~/appportal/omv-v2-data/.env`. Benodigde **sleutelnamen**: `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_TOKEN_FILE`. Het daarin aangewezen JSON-tokenbestand bevat `DROPBOX_REFRESH_TOKEN`. Het vastgestelde hostbestand is `~/appportal/omv-v2-data/dropbox_tokens.json`. Een bestaand containerpad onder `/data/` wordt naar de reeds gekoppelde hostmap vertaald. De scanner schrijft nooit in deze configuratie of in het tokenbestand; een tijdelijk toegangstoken blijft alleen in procesgeheugen.

De stack-koppeling hoort bij een ander bestaand account en heeft alleen het voorgestelde Work All-bereik kunnen lezen. De privé-koppeling is een App-folderverbinding: authenticatie werkt, maar Dropbox antwoordt op een namespace-header `path root is not supported for sandbox app`. Zij is daarom geen bron voor deze drie roots. Er wordt niet stilzwijgend teruggevallen op een ander account als OMV-v2-configuratie of authenticatie ontbreekt.

## Inhoudelijke dekking

| Bron | Wat deze agents toetsen |
|---|---|
| Dropbox-bestanden en -folders in de drie roots | Uitwisselbaarheid van namen; voor expliciet herkende H-A-profielen de bevestigde naam- en structuurregels |
| H-A-projectmappen in bevestigde Standaard-/Light-fasen | A13 naam; A1 centrale communicatie; A3-A6 momentnamen; B1 verslagbestand |
| H-A-sales in bestaande Offerte-/B2B-roots | A14 dossierfiche en oude bronmapnamen; ontbrekende opnamebronnen worden niet zonder inhoudelijk bewijs als fout aangemerkt |
| Agenda | Bestaande Agendawacht en gedeelde nummerlezer op reeds geïndexeerde afspraken |
| Geregistreerde Fathom-/Plaud-gesprekken | Bestaande `benaming.benoem`, uitsluitend bij leesbare lokale gesprekmetadata |

Andere firma's hebben zonder bevestigd boek geen verzonnen structuurprofiel. Agenda en gesprekken krijgen geen nieuwe zelfstandige account- of archiefscan. Pipedrive-titels, Google-/Xelion-contacten, andere Dropbox-accounts, officiële adressen, dossierhouder en bestandsinhoud zijn niet zelfstandig gecontroleerd. Het overzicht vermeldt deze grenzen altijd. De firma bij een pad is een expliciete profielmapping; bij agenda en gesprek een herkenning, geen bewijs van dossierhouderschap.

## Regelbron

Bevestigde bron: **H-A vaste afspraken v1.7**, `/Work All/01. H-A WORK/_0 Claude reorganisatie/H-A vaste afspraken v1.7.md`. De machinevertaling bevat bronpad, verbinding, namespace, versie en SHA-256. V1.5 is gelezen als voorgeschiedenis. Volledige fasepaden voorkomen dat `0 Fathom`, numerieke opnamemappen of proefmappen als project worden bestempeld.

De bron wordt dagelijks gelezen en aan de bevestigde vingerafdruk getoetst. Wijziging of onleesbaarheid pauzeert H-A-toetsing; eerdere punten blijven open totdat een daadwerkelijke brontoets het herstel bevestigt. De proceswerkwijze staat op het bord, met versie 1.1. Een afwijkende bestaande bordtekst wordt door de installer niet overschreven. Firmacodes blijven uit het bestaande `kern`-register en de bestaande nummerlezer komen.

## Voortgang, schaal en bronhistoriek

De eerste basislijst wordt in pagina's opgebouwd: standaard acht pagina's per root per ronde, met maximaal 500 aangevraagde items per pagina. Daarna leest dezelfde cursor uitsluitend wijzigingen. Iedere pagina en cursor worden samen gecommit. Een ontbrekend of misvormd `has_more`-veld, namespacefout of geweigerde bron levert geen complete basis op.

Per controleagent worden maximaal 3000 vuile items verwerkt. De lokale agenda-/gespreksindex heeft eveneens een budget, checkpoint en expliciete backlog. Ontbrekende bestanden worden pas vastgesteld bij een volledige en bijgewerkte cloudmetadata-index. Online-only bestanden worden via cloudmetadata beoordeeld; een lokaal nulbytebestand is geen afwezigheidsbewijs.

De padindex op bronbereik en `pad_sleutel` ondersteunt exacte ouderzoekacties en begrensde kinderranges. Python `casefold()` normaliseert deze sleutel bij iedere metadata-invoer; dezelfde normalisatie geldt voor Unicodepaden zoals `ÉCLAIR` en `Straße`. Er wordt geen volledige index per item of dossier doorlopen. Alleen dossiers waarvoor een structurele toets geldt, laden hun kinderen. De planner gebruikt één gedeelde procesvergrendeling. Na een afgebroken ronde wordt de laatste gecommitte pagina hervat. Een ontbrekende hartslag wordt na 45 minuten zichtbaar en door de Agentnorm afgekeurd.

Dagelijks worden de ingestelde roots, bereikbaarheid, basisvolledigheid, deltapaginering en regelbron gecontroleerd. Dit is volledige-dekkingscontrole van de opgebouwde basis plus wijzigingen, geen dagelijkse nieuwe scan van miljoenen items.

Verandering van verbinding, namespace of rootpad vereist een **nieuwe scope-identiteit en nieuwe basis**. Oude cursors worden geweigerd. Oude items en bevindingen blijven als historisch bronbewijs beschikbaar; zij worden niet verwijderd en tellen niet mee in actuele open-punttellingen. Nieuwe OMV-v2-rootidentiteiten in de config maken deze scheiding expliciet.

## Installatie

Geen Postgres-migratie of nieuwe rechten nodig. De lokale SQLite-index krijgt bij eerste opening idempotent de kolom `pad_sleutel` en de index `(scope,pad_sleutel)`. Bestaande metadata worden in batches van 1000 teruggevuld, met behoud van originele paden, bronidentiteiten, cursors en bevindingen. Deze items worden opnieuw voor structuurcontrole gemarkeerd; een migratiemarkering voorkomt herhaalde volledige scans. Data staan in `~/appportal/mijnagents-data/naamstructuur/`: `index.sqlite3`, `overzicht.json` en proceslock. De bestaande compose-mount geeft de beheerpagina alleen dit lokale resultaat. Het bestaande `AGENTS_TOKEN` blijft uit `~/appportal/mijnagents-data/.env` komen.

`NAAMSTRUCTUUR_REGELS` kan een VM-configbestand kiezen. Dat bestand bevat uitsluitend bronverwijzingen en regels, geen credentials. Iedere root moet een bestaande selector en expliciete namespace hebben; onbekende verbindingen en geheimvelden worden geweigerd. `NAAMSTRUCTUUR_DATA` is optioneel; bij een andere locatie moet de beheerpagina dezelfde datamap blijven gebruiken.

Na pull van de gecontroleerde commit:

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

De installer bewaart de vorige crontab en behoudt alle andere regels. Alleen het eigen blok wordt weergegeven en vervangen; geen volledige crontab in uitvoer. Opnieuw installeren maakt geen dubbele planning, kaarten of werkwijzeversies.

## Grenzen en grendels

Deze agents hernoemen, verplaatsen en verwijderen geen bronnen. Zij wijzigen geen documenten en geven geen nieuwe leesrechten. Geen externe berichten of Bode-signalen en geen uitvoerbare parameters. Concrete voorstellen worden op het bord beoordeeld; Mehdi beslist over afzonderlijke uitvoering.

`tests/test_naamstructuur.py` toetst onder meer paginering, atomiciteit, hervatten, verbinding- en namespacewissel, selector/configfouten, in-geheugen-authenticatie zonder tokenbestandwijziging, idempotente punten, cloudmetadata, bronwijzigingen en indexgebruik met `EXPLAIN QUERY PLAN`. `mijnagents/test_naamstructuur.py` bewaakt beheerrechten, escaping, paginering en hartslagdetectie. Grendels draaien in CI; beheergrendels ook in de Docker-build. Testdata zijn verzonnen. Werkelijke voortgang en dekking worden uitsluitend door het live overzicht bewezen.
