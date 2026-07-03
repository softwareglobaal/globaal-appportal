# CLAUDE.md — werkafspraken voor Claude-sessies in dit platform

Dit bestand wordt door elke Claude-sessie (lokaal én Claude Code in de cloud)
automatisch ingelezen. Het beschrijft hoe de git-workflow en deployment werken,
zodat elke sessie op dezelfde manier werkt. Volledige platformdocumentatie:
`TECHNICAL-REFERENCE.md`; parkeerlijst: `TODO.md`; terminologie: `DEFINITIEBOEK.md`
(machinebron: `kern.definitie`).

## Repo-landschap (GitHub-org `softwareglobaal`)

Stand 2026-07-03; kolom **CLAUDE.md** = heeft de repo een eigen
werkafspraken-bestand (sessies in een repo zónder ⚠-vinkje: lees déze).

| Repo | Wat | VM-checkout | Deploy | CLAUDE.md |
|---|---|---|---|---|
| **globaal-appportal** (deze) | stack: compose, nginx, db-migraties, docs | `~/appportal` | **handmatig** (zie onder) | ✓ |
| globaal-organisatie | Organisatie-dashboard + Second Brain | `~/appportal/medewerkers` | **auto** (cron 2 min) | ✓ |
| globaal-communicatie | Communicatie-dashboard | `~/appportal/communicatie` | **auto** (cron 2 min) | ✓ |
| globaal-vermogen | Vermogens-dashboard | `~/appportal/vermogen` | **auto** (cron 2 min) | ✓ |
| globaal-kosten | Kosten-dashboard (host-app, systemd :8090) | `~/kosten` | eigen deploy-script/cron | ⚠ nog niet |
| globaal-factuurrouter | AI-factuurrouteringsagent (host-app, §6A) | `~/factuurrouter` | eigen deploy + CI/CD | ⚠ nog niet |
| globaal-stagebeoordeling | Stagebeoordeling (host-app) | `~/stagebeoordeling` | eigen deploy + CI/CD | ⚠ nog niet |
| globaal-schuldentracker | Schuldentracker (host-app) | — | — | ⚠ nog niet |
| telefoonregister | telefoonregister van de collega — **ongemoeid laten** | eigen checkout | — | bewust niet |

## Git-workflow: hoe Claude pullt en pusht

- **Claude commit en pusht rechtstreeks naar `main`** vanaf een lokale kloon
  (credentials via Git Credential Manager op de werkmachine; cloud-sessies via de
  GitHub-koppeling van Claude Code). Er is geen PR-flow voor dit dagelijkse werk.
- **Altijd eerst `git pull --rebase origin main`** vóór het pushen — de VM en
  andere sessies pushen ook naar dezelfde branch; een geweigerde push betekent
  vrijwel altijd: eerst rebasen, dan opnieuw.
- **Push naar main = productie** bij de app-repos: op de VM draait per app-repo
  een cron (elke 2 min) die `deploy.sh` uitvoert — nieuwe commits worden gepulld
  en de compose-service wordt herbouwd. Logs: `~/deploy-organisatie.log`,
  `~/deploy-communicatie.log`, `~/deploy-vermogen.log`. Commit dus geen
  half werk naar main.
- **De stack-repo (deze) heeft géén auto-deploy.** De beheerder pullt handmatig
  op de VM (`cd ~/appportal && git pull`) en draait daarna wat de wijziging
  vraagt: migraties via `sh scripts/db-migrate.sh`, compose-wijzigingen via
  `docker compose up -d <service>`, nginx-templates via
  `docker compose up -d --force-recreate nginx`.
- Claude heeft **geen SSH-toegang tot de VM**: VM-commando's worden aan de
  gebruiker gegeven, die output terugplakt. Repos aanmaken op GitHub doet de
  gebruiker (web-UI); daarna kloont/pusht Claude zelf.

## Vaste regels

1. **Geen ad-hoc DDL** — elk schemawijziging is een genummerde migratie in
   `db/migrations/NNN-*.sql`, toegepast met `scripts/db-migrate.sh` (tracking in
   `public.schema_migrations`). Eenmalige data-fixes mogen als los SQL-blok voor
   de gebruiker, mét preview-query vooraf.
2. **Documentatie in sync in dezelfde push**: TECHNICAL-REFERENCE.md (stack),
   README van de app-repo, TODO.md (afvinken/parkeren), DEFINITIEBOEK.md +
   `kern.definitie` bij terminologie.
3. **Frontend-code eerst écht parsen vóór de push** (V8, bv. py-mini-racer;
   Jinja-templates eerst renderen en dan de inline scripts parsen) — auto-deploy
   zet elke push vrijwel direct live, een syntaxfout = productie stuk.
4. **Code patchen via bestands-tools, nooit via shell-heredocs** — heredocs
   kunnen backslash-escapes verminken (heeft al eens productie gebroken).
5. **Secrets nooit in git of chat**: wachtwoorden/API-keys gaan via `.env` op de
   VM (nano) of `read -s`; in repos alleen `CHANGE_ME`-placeholders.
6. **Commits in het Nederlands**, kort en beschrijvend (`feat:`/`fix:`/`docs:`/
   `TODO:`-stijl zoals de historie); `.gitattributes` normaliseert naar LF.
