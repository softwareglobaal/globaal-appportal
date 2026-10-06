# Codering: uitvoering en permanent toezicht

Versie 1.0, 06-10-2026. Uitgevoerd door Codex voor Mehdi Chegini.

WP1, WP2a en WP3 zijn in de bestaande systemen hersteld en live gecontroleerd. Benamingenwacht en Mappenwacht zijn geregistreerd op mijnagents.globaal.be en delen één index en het beheeradres https://mijnagents.globaal.be/naamstructuur. De SQL voor het groepsregister blijft uitsluitend in proefpakket v0.2.

## Bron en wijzigingen

Het voorstel v0.3, proefontwerp v0.1, oorspronkelijke proefpakket v0.1 en review v1.2 zijn gelezen. De beperkte herstelopdracht v1.0 bepaalde de uitvoeringsgrens. Claude had WP1/WP2a al gedeeltelijk gerealiseerd in `4cb3a04`; dat werk is behouden en aangevuld. Parallelle appportal-commits tot `cd67e90` zijn meegenomen. Geen force-push, reset of vervanging van parallel werk.

| Repository | Commit | Resultaat |
|---|---|---|
| globaal-appportal | `66079db` | Volledige nummerbronnen, vroege H-A-accountgrendel, behouden toegekend nummer, veilige koppelingen; eerste twee toezichtagents |
| globaal-appportal | `c31deeb` | Alle drie Dropbox-roots via bestaande OMV-v2, expliciete namespaces, schaalbare Unicode-index, geldige locatiefixtures |
| contract-systeem | `deb74aa` | Afzonderlijke documentidentiteiten en versies, veilige opslag en transportbewijs, alle renderpaden en leesroutes |

De wijzigingen staan op main. De oorspronkelijke schone checkouts onder `~/dev` zijn met fast-forward bijgewerkt. Op de VM zijn uitsluitend `app-contracten` en `app-mijnagents` gebouwd/uitgerold. Bestaande lokale compose- en nginx-wijzigingen zijn behouden.

Belangrijke bronbestanden: `koppelingen/nummerlezer.py`, `contracten_agent.py`, `koppelingen/bronnen.py`, `koppelingen/pipedrive.py`, `agenda_wacht.py`, `fathom_wacht.py`, `archivaris.py`; voor het toezicht `koppelingen/naamstructuur.py`, `naamstructuur_ronde.py`, de twee runners, planning en werkwijzen; in contract-systeem `contractdocumenten.py`, `webapp/voorbereiding.py`, `webapp/app.py`, `mcp_server.py`, de vier generators en templates.

## Controlebewijs

| Controle | Resultaat |
|---|---|
| Lokale appportal-suite: nummering, koppelingen, benaming en naamstructuur | 104 geslaagd |
| Locatiewacht, aangepaste fictieve nummers en negatieve tegenproef | 20 geslaagd |
| Bestaande mail- en werfbezoekgrendels | 32 en 25 geslaagd |
| Beheergrens, escaping en paginering naamstructuur | geslaagd |
| Contractgrendels | 305 geslaagd, waaronder 25 nieuwe regressies |
| Volledig proefpakket v0.2 | 66 geslaagd, geen xfail |
| Eigen H-A-suite met geïsoleerd proefmodel | 23 geslaagd |
| Agentnorm, beide nieuwe agents afzonderlijk | ieder 14 geslaagd, 0 gezakt |

GitHub CI: [nummering](https://github.com/softwareglobaal/globaal-appportal/actions/runs/37390894880), [agenda](https://github.com/softwareglobaal/globaal-appportal/actions/runs/37392364837), [namen en mappen](https://github.com/softwareglobaal/globaal-appportal/actions/runs/37392364930), [locatie](https://github.com/softwareglobaal/globaal-appportal/actions/runs/37392364895), [contracten](https://github.com/softwareglobaal/contract-systeem/actions/runs/37392034137). De eerdere locatie-CI faalde op fictieve 91xx/92xx-nummers; uitsluitend fixtures zijn hersteld. De productieregel bleef intact.

De onafhankelijke contractreview bevestigde gelijktijdige renders en omgekeerde opslag, behoud van verschillende historische fiches, unieke Word-uitvoer, versiegebonden transportbewijs bij gedeeltelijke verzending en zichtbare formulierproeven. Externe verzending is in de tests nagebootst. De historische Onderteken-route geeft alleen inzage; POST vraagt het bestaande gecontroleerde dealproces met HTTP 409.

Live leescontrole: contract-API, Documentenpagina en handleiding `contractversies` geven HTTP 200; health is ok. Alle 17 bestaande bronfiches bleven byte voor byte gelijk. Er zijn 16 documentidentiteiten: één voorbereiding en één historische fiche verwijzen aantoonbaar naar hetzelfde PandaDoc-document. MCP leest de volledige lijst in drie pagina's van maximaal zeven en bevestigt totaal 16. Er is voor verificatie geen echt contract, nummeraanvraag of bericht aangemaakt.

## Permanente werking

Benamingenwacht draait elke 15 minuten; Mappenwacht op minuut 7, 22, 37 en 52. Ze gebruiken dezelfde metadata en voorstellen, met één gedeeld slot. De cron-daemon is actief, twee regels zijn geplaatst en de automatische Benamingenwacht-ronde van 00:15 UTC is bevestigd. Andere cronregels blijven behouden; de vorige crontab is als lokaal beheerbestand bewaard.

De eerste ronde van 00:11 UTC indexeerde 7.561 unieke items over Dropbox, agenda en gesprekken. 1.066 items uit complete bereiken zijn getoetst; er stonden 397 naamvoorstellen en 0 structuurvoorstellen. Work All en Data uit Mehdi waren toen nog bezig met hun eerste basislijst. Deze telling is een momentopname; de actuele dekking en achterstand staan op het bord. Een onvolledig bereik geldt nooit als geslaagde volledige controle.

Alle drie afgesproken Dropbox-roots zijn bereikbaar met de bestaande OMV-v2-koppeling. De H-A-regelbron v1.7 is gelezen en de bevestigde SHA-256 klopt. Credentials blijven in de bestaande OMV-configuratie en het tokenbestand; de agents schrijven daar niets. Het gezamenlijke overzicht geeft beheer HTTP 200 en een gewone medewerker HTTP 403. Hartslagen en regisseur-integratie zijn actief. Contracten-agent-werkwijze v5 is gepubliceerd met behoud van v4 in de versiegeschiedenis.

Gebruik voor hercontrole:

```sh
cd ~/appportal
~/agents/.venv/bin/python mijnagents-runner/planning/naamstructuur_installeren.py
~/agents/.venv/bin/python mijnagents-runner/controle_agenten.py --agent benamingen-wacht --uitleg
~/agents/.venv/bin/python mijnagents-runner/controle_agenten.py --agent mappen-wacht --uitleg
```

Handleidingen: `Namen en mappen - toezicht v1.1.md` in appportal en `Contractdocumenten - identiteiten en versies v1.0.md` in het contractdashboard. Proefuitvoer staat onder `proefpakket v0.2/resultaten`; de proefservers zijn gestopt en hun bewijs is behouden.

## Wat openstaat en wat Mehdi doet

Open **Namen en mappen** op het agentbord en beoordeel de concrete voorstellen. Afzonderlijke uitvoering volgt na Mehdi's besluit. De eerste volledige mapscan loopt door volgens de planning.

H-A heeft bevestigde structuurregels. Andere firma's krijgen algemene bestandsnaamcontrole; hun structuurboek moet eerst worden bevestigd. Agenda en gesprekken worden via de bestaande index gecontroleerd; contacten en volledige CRM-accountscans vallen buiten dit bereik.

Atomische dossiernummerreserveringen (WP2b), het groepsregister (WP4) en WP5-WP9 zijn niet uitgerold. Nummeruitgifte blijft een bevestigd voorstel; gelijktijdige aanvragen kunnen hetzelfde voorstel krijgen. Het verbeterde groepsmodel is uitsluitend lokaal op PostgreSQL 17 getest; productie gebruikt 16. De algemene bedrijfsaanbevelingen B1-B7 blijven aanbevelingen.
