# Opdracht Codex ronde 1: de bewaakte borduitrol van mijnagents

Van Claude, 16-10-2026. Rondenaam: "Borduitrol mijnagents: bewaakte deploy.sh (ronde 1)". Bevindingen nummeren vanaf BU-1.
Dit is optie B uit jouw ontwerpronde CX10 (werfverslag, `codex-10-ontwerp-borduitrol.md`), als eigen taak.

## Rol en grenzen

Werkafspraken Claude en Codex v1.3. Alleen lezen: code, `git log`, `git diff`, tests als de sandbox het toelaat. Niets
wijzigen, niets committen, geen SSH of netwerk naar *.globaal.be, geen live systemen.

## Wat je controleert

| Repo | Worktree | Tak | Basis (origin/main) | Nu |
|---|---|---|---|---|
| softwareglobaal/globaal-appportal | `/Users/mehdichegini/dev/_bord-uitrol` | `bord-uitrol` | `a663822` | `6fb73fb8c0101619030c1a72a87cc5b29659a19d` |

Kernbestanden: `mijnagents/deploy.sh`, `mijnagents/test_bord_deploy.py`, `.github/workflows/bord-uitrol-grendels.yml`.
Diff: `git -C /Users/mehdichegini/dev/_bord-uitrol diff a663822..6fb73fb`.
Ter vergelijking: de werfapp-uitrol `/Users/mehdichegini/dev/globaal-werfverslag/deploy.sh` en `runner/deploy-ci.py`, en
de twee eerdere pogingen `git -C /Users/mehdichegini/dev/globaal-appportal show 866428b 7a1932b`.
Jouw eerdere rapporten: `/Users/mehdichegini/dev/_werf-app/docs/codex/codex-7-werfketen.md` tot `codex-10-ontwerp-borduitrol.md`.

## Feiten (gemeten door Claude op 16-10-2026, alleen lezend op de VM)

- Cron: `*/2 * * * * sh /home/ubuntu/appportal/mijnagents/deploy.sh >> /home/ubuntu/deploy-mijnagents.log 2>&1`.
  `/bin/sh` is dash; `/usr/bin/flock`, `/usr/bin/timeout`, `/usr/bin/curl` bestaan. Docker 29.5.3, compose v5.1.4, overlay2.
- De dienst `app-mijnagents` staat in `docker-compose.override.yml` met `build: ./mijnagents`, `container_name: app-mijnagents`,
  `restart: unless-stopped`, poort `127.0.0.1:3022`. Geen `image:`-regel: de image heet `appportal-app-mijnagents:latest`.
  `docker inspect -f '{{.Image}}' app-mijnagents` en `docker image inspect -f '{{.Id}}' appportal-app-mijnagents:latest`
  geven allebei `sha256:d7b9ef03...`; `docker image inspect` op dat volle ID werkt ook.
- `git status --porcelain -- mijnagents` op de VM is leeg; `.built` = `git rev-parse HEAD:mijnagents` = `f6810eb2...`.
- `~/deploy-mijnagents.log` toont dezelfde revisie twee keer kort na elkaar uitgerold (13-10 08:30:59 en 08:33:25 voor
  `11b50af2`, 09:40:12 en 09:41:27 voor `1d5becdb`): twee overlappende rondes zonder slot.
- Niets trekt `~/appportal` vanzelf bij: de `git pull --ff-only` op de VM is een aparte, handmatige stap.
- GitHub Actions draait in deze (publieke) repo; op de tak liep `bord-uitrol-grendels` bij het schrijven.

## Beweringen van Claude (ga ze onafhankelijk na)

1. Eén `flock -n` op `mijnagents-data/.deploy.lock` dekt de hele ronde: van het lezen van de markeringen tot na de
   gezondheidscontrole en de terugrol (CX9-1).
2. Elke docker-aanroep loopt via `dk`: `timeout -k 10 <limiet> docker ... 9>&-`. Het slot-fd gaat niet mee naar docker of
   naar processen die docker achterlaat; de test `test_slot_gaat_niet_mee_naar_docker` faalt zonder `9>&-` (op de CI met
   GNU timeout; op de Mac met een vervanger die `close_fds=False` gebruikt).
3. `.built` verschuift alleen als `/gezondheid` twee keer na elkaar `"ok": true` geeft én de container het image-ID van
   de net gebouwde `:latest` draait (CX7-1, CX10-2 deels).
4. De terugrolimage is het image-ID van het draaiende bord als dat gezond is (getagd als `:vorige`, met nacontrole van de
   tag; een tagfout = geen bouw, geen `.mislukt`). Is het bord voor de bouw al ongezond, dan het ID achter `:vorige`.
5. `terug` schrijft `.mislukt`, zet het ID terug als `:latest` (met nacontrole), en doet `--force-recreate` tenzij de
   container dat ID nog draait en gezond is; daarna gezondheid én image-ID. `.herstel` (`<id> <revisie> <poging>`) staat er
   vanaf vlak voor de bouw tot na een gezonde uitrol of een gelukt herstel. Een volgende ronde herstelt eerst (CX9-2).
6. Lukt dat herstel niet, dan wordt dezelfde revisie niet opnieuw gebouwd, maar een nieuwere revisie wel (er is dan geen
   gezond bord om te beschermen); de terugrolimage blijft dezelfde.
7. `.mislukt` = `<revisie> <epoch> <poging>`: afkoeling 30 min, verdubbelend tot hoogstens 6 uur; een nieuwe revisie
   wacht niet; `rm .mislukt` is de zichtbare vrijgave (CX9-3, CX10 antwoord 3).
8. Docker onbereikbaar of een vuile werkboom `mijnagents/`: exit 1 zonder `.mislukt` of `.herstel`.
9. 22 tests groen lokaal met dash (en Python-vervangers voor flock en timeout, want die ontbreken op de Mac). Elke test faalt
   op het productiescript of op een gerichte mutatie: zonder slot, slot-fd mee naar docker, zonder imagecontrole, zonder
   afkoeling of altijd afkoeling, zonder verdubbeling, tagfout genegeerd (voor de bouw en bij de terugrol), zonder
   herstelvoorrang, zonder werkboomcontrole, zonder tijdslimiet.

## Aandachtspunten

- Kan een volgorde van gebeurtenissen nog een ongezonde image als terugrolimage vastleggen, of een goede revisie blijvend
  blokkeren? Denk aan: herstarts van de VM midden in een ronde, `git pull` tijdens een bouw, een gezonde uitrol waarvan het
  schrijven van `.built` faalt, een `.herstel` van een oudere revisie.
- Klopt de werking van `docker compose up -d --build` en `--no-build --force-recreate` met deze compose-opzet; wat als compose
  de container niet vervangt?
- POSIX/dash: `set -eu` in functies, `read` zonder slotnewline, `&&`-lijsten, aanhalingstekens, `exec 9>`.
- Wat zou een volgende sessie of Mehdi zien bij elke fout (logregels, bestanden)? Is de vrijgave zichtbaar genoeg?
- Testen de tests wat ze beweren? Is de nep-docker trouw genoeg aan echte docker op de punten die ertoe doen?
- Ontbreekt iets wat de werfapp-uitrol wel heeft en hier hoog of middel zou zijn (de CI-grendel op de exacte SHA vóór de
  bouw, een databankkopie)? Merk op: de VM trekt deze repo niet vanzelf bij; de pull is handmatig.

## Antwoordvorm

Beslissing eerst (klaar, klaar met kanttekeningen, niet klaar). Dan BU-n met ernst (hoog, middel, laag), `bestand:regel`,
wat er misgaat met een concreet voorbeeld, en de voorgestelde fix. Dan per bewering 1 tot 9 kort: klopt, deels of niet.
Afsluiten met de drie punten: wat gedaan, wat nagekeken met resultaat, wat open met de volgende stap.
