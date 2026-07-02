# Communicatie-dashboard

Telefoonnummers en e-mailadressen van de bedrijvengroep, volledig gelinkt aan de
centrale gebruikersdatabase — **https://communicatie.globaal.be**. Opvolger-in-opbouw
van het telefoonregister; die app draait er ongemoeid naast
(`telefoonregister.globaal.be`) tot de eigenaar akkoord is.

| Tab | Wat |
|---|---|
| **Telefonie** | nummerbeheer: KPI-cijfers als filters, chips (land/status/firma-multiselect/leverancier), zoeken, dubbelcheck op genormaliseerd nummer, live-sync (SSE), Excel-export. Nummer = link naar het detailpaneel |
| **E-mailadressen** | adres + firma + verantwoordelijke (leeg = **OPEN**-markering, het open eindje) + gebruikers (wie op de mailbox ingelogd zijn) |

## Datamodel (Postgres, schema `communicatie`)

Terminologie volgt `DEFINITIEBOEK.md` in de stack-repo:

- **`nummer`** — met **doel** (niet "functie"), **leverancier**, **factuur-firma** (wie
  betaalt), **doorfactuur-firma**, afdeling en **verantwoordelijke** (één) — allemaal
  échte FK's naar `kern.*`; dropdowns uit de centrale lijsten, geen vrije tekst.
- **`nummer_gebruiker`** — de gebruikers met **belvolgorde** (queue van de
  telefooncentrale: `volgorde` 1 neemt eerst op; in de UI herschikbaar met ↑/↓).
- **`geheim`** — PIN/PUK/kaartnummer, 1-op-1 bij een nummer, afgeschermd achter een
  Toon-knop. Wordt **nooit** door andere apps of de AI gelezen.
- **`emailadres`** + **`emailadres_gebruiker`** — zie tab 2.
- **`lijst`** — app-eigen keuzewaarden (Land/Platform/Type). Leveranciers zijn juist
  **centraal** (`kern.leverancier`, beheer via de Lijsten-modal hier: hernoemen +
  aan/uit, geen verwijderen).

Het schema wordt beheerd via `db/migrations/` in de stack-repo (002 t/m 005), niet via
Knex-migraties.

## Links & integraties

- Personen overal in **Zoom-formaat** `Voornaam (Afdeling)` en klikbaar → profiel op
  `organisatie.globaal.be`; firmanamen klikbaar → firma-detailpaneel (alles wat aan de
  firma hangt); nummers klikbaar → nummerdetail.
- **Deep-link**: `/#nummer=<uuid>` opent direct het detailpaneel van dat nummer — zo
  linken het Organisatie-profiel en de organisatie-graph hierheen terug.
- Het Organisatie-dashboard leest dit schema rechtstreeks (portal-rol, read-only) voor
  profiel-secties, firma-tellingen en de knowledge-graph.

## Toegang & rechten

- Achter Authentik **forward-auth**; tegel voor de groepen admin/manager/communicatie
  (`scripts/add-communicatie-app.py` in de stack-repo).
- **Lezen** mag iedereen die binnen is; **schrijven** alleen de groepen in
  `EDITOR_GROUPS` (default `communicatie-editors,admin`) — de server dwingt af (403).
- DB-rol **`communicatie`**: leest kern, schrijft alleen het eigen schema +
  `kern.leverancier` (INSERT/UPDATE).

## Stack & configuratie

Node/Express/Knex (gekopieerd van het telefoonregister, verbouwd naar Postgres).
Compose-service **`app-communicatie`** (poort 3008), nginx-template
`45-communicatie.conf.template`.

| Variabele | Doel |
|---|---|
| `DATABASE_URL` | rol `communicatie`, Node-formaat `postgres://…` (`COMMUNICATIE_DB_URL` in `.env`) |
| `EDITOR_GROUPS` | wie mag bewerken (komma-gescheiden) |
| `BASE_DOMAIN` | domein voor cross-app-links |

## Eenmalige data-import

`scripts/import.js` importeerde de telefoonregister-SQLite (JSON via stdin; zie de
scriptkop voor het commando): leveranciers ge-upsert uit provider-waarden, firma's op
naam gematcht, verantwoordelijke uit de bestaande `persoon_id`-links; zelfde uuid's,
dus idempotent. De rest is curatiewerk in de UI.

## Deployment

Onderdeel van de stack-repo (`globaal-appportal`): wijzigingen deployen met
`git pull && docker compose up -d --build app-communicatie` op de VM. Een eigen repo
met auto-deploy (zoals `globaal-organisatie`) staat als optie in `TODO.md`.
