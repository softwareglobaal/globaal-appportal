**Niet klaar.** De herstellingen verbeteren de eerste uitrol, maar vier punten van ernst middel blijven open. Volgens werkafspraken v1.3 houden die de merge en bewaakte uitrol tegen.

1. **BU-10 — middel — [mijnagents/deploy.sh:204](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:204).** Stel dat `.built` al de nieuwe revisie noemt, `.herstel` is achtergebleven en de oude image weer gezond draait. Het script verwijdert `.herstel`, laat `.built` op nieuw staan en stopt bij regel 222. Latere rondes slaan de uitrol over. **Fix:** herstel in deze tak ook `.built` naar de vorige revisie, of maak haar ongeldig als die revisie onbekend is; controleer de `:latest`-tag en test deze toestand.

2. **BU-11 — middel — [mijnagents/deploy.sh:93](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:93), [mijnagents/test_bord_deploy.py:560](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/test_bord_deploy.py:560).** Bij een ongewijzigde revisie controleert `bewaak` alleen `/gezondheid`. De bestaande test zet zelfs `.built=nieuw` terwijl de oude image draait en accepteert daarna een gezonde uitkomst. Zo blijft een gezond maar verkeerd image onopgemerkt. **Fix:** vergelijk ook het draaiende image-ID en zijn revisielabel met de vastgelegde uitrol; test een gezonde oude image zonder `.herstel`.

3. **BU-12 — middel — [mijnagents/deploy.sh:245](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:245), [mijnagents/app.py:73](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/app.py:73).** Ontbreekt de bestaande `mijnagents.db`, dan slaat het script de kopie over en bouwt toch. Bij de start kan `init_db()` een lege databank aanmaken; `/gezondheid` kan vervolgens `ok: true` geven met nul agents. **Fix:** eis voor deze productie-uitrol een aanwezige, leesbare databank met de verwachte tabellen; ontbreekt zij, stop vóór de bouw en voeg een test toe.

4. **BU-13 — middel — [mijnagents/deploy.sh:245](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:245), [mijnagents/deploy.sh:287](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:287).** De kopie wordt vóór een bouw van maximaal 30 minuten gemaakt, terwijl het oude bord bijvoorbeeld [agentstatussen blijft schrijven](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/app.py:1412). Moet de databank na een onverenigbare migratie worden teruggezet, dan gaan ook de schrijfacties tijdens die bouw verloren. **Fix:** maak en controleer een tweede, afzonderlijk benoemde kopie direct vóór het vervangen van de container; test de volgorde.

| Punt | Oordeel |
|---|---|
| BU-1 | **Volstaat:** `git archive` levert alleen vastgelegde bronbestanden. |
| BU-2 | **Volstaat:** de grendel vraagt een geslaagde run voor de exacte lokale HEAD-SHA. |
| BU-3 | **Volstaat:** de bouw gebruikt de vastgelegde tree en controleert het imagelabel. |
| BU-4 | **Deels:** de kopie en ruimtecontrole werken volgens de code; zie BU-12 en BU-13. |
| BU-5 | **Volstaat** voor de twee genoemde onderbrekingspunten; BU-10 betreft een andere hersteltoestand. |
| BU-6 | **Deels:** zie BU-10 en BU-11. |
| BU-7 | **Volstaat:** `curl` moet slagen en het volledige JSON-antwoord moet `ok` als booleaanse `true` bevatten. |
| BU-8 | **Volstaat** voor het vastleggen van `:vorige`: gezondheid, draaiend ID en tag worden gekoppeld. |
| BU-9 | **Deels, laag:** het absolute volgende tijdstip staat nu in het foutlog; tijdens de afkoeling blijft de status verder stil. |

**De specifieke uitrolvragen:** Ja, Compose gebruikt hier normaal `appportal-app-mijnagents:latest`: de projectnaam is `appportal`, de dienst heet `app-mijnagents`, en zonder `image:` is de standaardtag `project-service`. `--no-build --force-recreate` gebruikt die lokale image en vervangt de container. Dat volgt ook uit de [Docker-documentatie over standaardtags](https://docs.docker.com/reference/cli/docker/compose/build/) en [`compose up`](https://docs.docker.com/reference/cli/docker/compose/up/). De image-ID-nacontrole blijft terecht.

De eerste ronde kan volgens de code de huidige gezonde image zonder label als `:vorige` taggen en daarna bouwen, starten en `.built` schrijven. Een lopende CI-run blokkeert; een nieuwere push verandert de lokale HEAD niet. Na een volgende `git pull` wordt de nieuwe HEAD afzonderlijk gecontroleerd. De gebruikte SHA-, tak- en gebeurtenisfilters worden door de [GitHub-workflowruns-API](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28) ondersteund. De ruimteformule reserveert ongeveer tweemaal de databankgrootte plus 500 MiB; bij de opgegeven 242 MB en 72 GB vrij is dat ruim voldoende. De volgorde is kopie, `.herstel`, bouw, start, met de beperkingen van BU-12 en BU-13. Afkoeling, verdubbeling en vrijgave via `.mislukt` blijven volgens de code werken; het herstel heeft BU-10 en BU-11.

1. **Gedaan:** werkafspraken v1.3, beide ronde-1-rapporten, `git log`, `git status`, de diff en de betrokken code en tests gelezen. HEAD is `dce3f1b0535f3ec802357876269557a24d6256b8`. Geen bestanden gewijzigd, geen commit gemaakt, geen SSH gebruikt.
2. **Nagekeken:** `dash -n`, `git diff --check` en Python-AST-controle slaagden. Ik telde tien testbestanden, waaronder 35 deploytests en zes CI-tests. De beweerde groene testuitvoering en de actuele Ubuntu-CI-uitkomst kon ik in deze alleen-lezen controle niet onafhankelijk bevestigen.
3. **Open:** Claude kan BU-10 tot BU-13 in de bron herstellen met gerichte regressietests en daarna een nieuwe controle laten doen vóór merge en bewaakte uitrol.