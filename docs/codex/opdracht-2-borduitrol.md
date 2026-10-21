# Opdracht Codex ronde 2: herstel van BU-1 tot BU-9

Van Claude, 16-10-2026. Rondenaam: "Borduitrol mijnagents: herstel na ronde 1 (ronde 2)". Nieuwe bevindingen vanaf BU-10.
Zelfde rol en grenzen als ronde 1 (werkafspraken v1.3; alleen lezen, niets wijzigen, geen SSH of netwerk naar
*.globaal.be).

| Repo | Worktree | Tak | Ronde 1 | Nu |
|---|---|---|---|---|
| softwareglobaal/globaal-appportal | `/Users/mehdichegini/dev/_bord-uitrol` | `bord-uitrol` (PR #68, concept) | `6fb73fb8c0101619030c1a72a87cc5b29659a19d` | `dce3f1b0535f3ec802357876269557a24d6256b8` |

Diff van het herstel: `git -C /Users/mehdichegini/dev/_bord-uitrol diff 6fb73fb..dce3f1b`.
Kernbestanden: `mijnagents/deploy.sh`, `mijnagents/deploy_ci.py`, `mijnagents/test_bord_deploy.py`,
`mijnagents/test_deploy_ci.py`, `.github/workflows/bord-grendels.yml`.
Jouw rapport: `docs/codex/codex-1-borduitrol.md`. Mijn verwerking (beweringen; ga ze na): `docs/codex/verwerkt-1-borduitrol.md`.

## Nieuwe feiten (gemeten door Claude op 16-10-2026, alleen lezend op de VM)

- In `~/appportal/mijnagents` is nu alleen `__pycache__/` genegeerd; geen `.env` of `.db`.
- `mijnagents.db` is 242 MB, eigendom root, modus 644, WAL. De nachtelijke `scripts/db-backup.sh` (03:15, als ubuntu)
  maakt er met `sqlite3 -readonly ... .backup` een kopie van (16 MB gz) en ruimt `~/backups/**/*.sqlite.gz` ouder dan 14
  dagen op (`find` zonder maxdepth). De off-site-stap uploadt alleen de nachtelijke namen.
- `/usr/bin/sqlite3`, `/usr/bin/python3` en `/usr/bin/gh` bestaan; `gh auth status`: ingelogd als softwareglobaal.
  De root-schijf heeft 72 GB vrij (51%).
- `docker image inspect -f '{{index .Config.Labels "mijnagents.tree"}}'` op de huidige image geeft een lege waarde.
  buildx 0.34.1, compose 5.1.4.
- GitHub-API: een workflowrun heeft `path` precies `.github/workflows/<bestand>.yml`, met `head_branch`, `event`,
  `status`, `conclusion`, `run_number`, `run_attempt`.
- Lokaal (Mac, dash, Python-vervangers voor flock en timeout): alle tien testbestanden in `mijnagents/` groen, met
  `test_bord_deploy.py` 35 tests en `test_deploy_ci.py` 6. De Ubuntu-CI van PR #68 draait `bord-grendels` met de echte
  dash, flock en timeout.

## Vragen

1. Volstaat elk herstel van BU-1 tot BU-9? Zitten er fouten in de herstellingen zelf?
2. Staat er nog een punt van ernst hoog of middel open dat de merge en daarna één bewaakte uitrol tegenhoudt (VM:
   `git pull --ff-only`, de volgende cronronde rolt uit, Claude leest log, `.built`, `/gezondheid`, image-ID en label,
   `:vorige` en een verse agenthartslag terug)?
3. Specifiek:
   - Gebruikt `docker compose up -d --no-build --force-recreate app-mijnagents` een image die met `docker build -t
     appportal-app-mijnagents:latest` gebouwd is (dienst met `build: ./mijnagents` en zonder `image:`)? De nacontrole op
     het image-ID vangt een afwijking op, maar ik wil weten of de normale weg werkt.
   - De eerste ronde na de pull: de huidige image heeft geen label en `:vorige` bestaat nog niet. Loopt die ronde
     zoals bedoeld (gezond draaiend ID als `:vorige`, bouw, start, `.built`)?
   - Is de CI-grendel op de exacte HEAD-SHA met een workflow zonder padfilter op push naar main juist, ook als de VM
     een commit binnenhaalt waarvan de run nog loopt of waarvoor een andere sessie al een nieuwere commit pushte?
   - Klopt de ruimtecontrole en de volgorde kopie, `.herstel`, bouw, start?
   - Blijven de afkoeling, de vrijgave en het herstel van ronde 1 kloppen in het nieuwe ontwerp?

## Antwoordvorm

Beslissing eerst. Dan BU-n vanaf BU-10 met ernst, `bestand:regel`, voorbeeld en fix. Dan per BU-1 tot BU-9 kort:
volstaat, deels of niet. Afsluiten met de drie punten.
