# CLAUDE.md — werkafspraken voor Claude-sessies in dit platform

Dit bestand wordt door elke Claude-sessie (lokaal én Claude Code in de cloud)
automatisch ingelezen. Het beschrijft hoe de git-workflow en deployment werken,
zodat elke sessie op dezelfde manier werkt. Volledige platformdocumentatie:
`TECHNICAL-REFERENCE.md`; parkeerlijst: `TODO.md`; terminologie: `DEFINITIEBOEK.md`
(machinebron: `kern.definitie`).

## Repo-landschap (GitHub-org `softwareglobaal`)

Stand 2026-07-03 — **elke repo heeft een eigen CLAUDE.md** met de lokale regels;
deze tabel is het overzicht. Let op het verschil in workflow: de
**dashboard-repo's** (bovenste blok) krijgen directe pushes naar `main`; de
**host-app-repo's** (onderste blok) werken via **branch → PR → CI smoke-test →
auto-merge** — in beide gevallen deployt de VM daarna automatisch via cron (2 min).

| Repo | Wat | VM-checkout | Naar main | Deploy |
|---|---|---|---|---|
| **globaal-appportal** (deze) | stack: compose, nginx, db-migraties, docs | `~/appportal` | directe push | **handmatig** (zie onder) |
| globaal-organisatie | Organisatie-dashboard + Second Brain | `~/appportal/medewerkers` | directe push | auto (cron 2 min) |
| globaal-communicatie | Communicatie-dashboard | `~/appportal/communicatie` | directe push | auto (cron 2 min) |
| globaal-vermogen | Vermogens-dashboard | `~/appportal/vermogen` | directe push | auto (cron 2 min) |
| globaal-kosten | Kosten-dashboard (host-app :8090) | `~/kosten` | PR → auto-merge | auto (`~/deploy-kosten.sh`) |
| globaal-factuurrouter | AI-factuurrouteringsagent (§6A, :8787) | `~/factuurrouter` | PR → auto-merge | auto (`~/deploy-factuurrouter.sh`) |
| globaal-stagebeoordeling | Stagebeoordeling (host-app :8088) | `~/stagebeoordeling` | PR → auto-merge | auto (`~/deploy-stagebeoordeling.sh`) |
| globaal-schuldentracker | Schuldentracker (host-app :5050) | `~/Finance/Schuldentracker` | PR → auto-merge | auto (`~/deploy-schuldentracker.sh`) |
| telefoonregister | telefoonregister van de collega — **ongemoeid laten** | eigen checkout | — | — |

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
7. **Shell-scripts committen mét execute-bit**: vanaf Windows krijgt een script
   mode 100644 en dan faalt de deploy-cron stil op "Permission denied". Vóór de
   commit: `git update-index --chmod=+x <script>`; check met
   `git ls-files -s <script>` (moet 100755 zijn). Na een verse VM-clone eenmalig
   `chmod +x` als bootstrap.
8. **Adresvelden krijgen het autocomplete-patroon**: eigen proxy-route
   `/api/adres` (→ Photon/OSM, geen key) + `static/adres.js` + `data-adres` op de
   input, met een eigen dropdown — géén `<datalist>` (browsers filteren die stuk)
   en géén externe scripts in de pagina. Voorbeeld: globaal-draaiboek/-vermogen.
9. **Nieuwe relatie in de database = zelfde sessie ook in de Second Brain**:
   elke migratie die een FK of koppeltabel toevoegt, wordt in dezelfde werksessie
   verwerkt in `graaf.py` (globaal-organisatie) — knoop/edge + kleur/definitie —
   én in de relevante detailpagina's/profielen. "Alles blauw" geldt ook voor de
   graaf; de gebruiker hoort koppelingen nooit zelf te hoeven controleren.
