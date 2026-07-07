# Plan: group-based toegang via Authentik Blueprints (GitOps)

Status: vastgesteld na brainstorm-sessie 2026-07-07 (Mehdi + Claude). Nog niet
in uitvoering. Dit document vervangt de oorspronkelijke opdrachttekst: alle
correcties uit de sessie zijn verwerkt. Uitvoering start pas na expliciet
akkoord, stap voor stap, met bevestiging vóór (a) de compose-wijziging en
(b) uitrol voorbij de testapp.

## 1. Besluiten uit de sessie

1. **Naamconventie**: per applicatie exact twee Authentik-groepen:
   `app-{appnaam}-read` en `app-{appnaam}-edit`. `{appnaam}` lowercase,
   alleen `a-z0-9-`. Edit impliceert read (afgedwongen in de helper, niet via
   dubbel lidmaatschap); een gebruiker zit nooit in beide groepen.
2. **akadmin blijft de beheerder** en is meteen het break-glass-account:
   superuser in Authentik, staat buiten alle app-groepen en wordt in dit
   traject nergens aangeraakt. Het gedrag van `scripts/akadmin-all-access.py`
   (akadmin aan groepen/bindings koppelen) wordt teruggedraaid.
3. **De groep `manager` verdwijnt.** Leden worden niet naar `admin` verhuisd
   (dat zou stille rechtenverhoging zijn: admin heeft bewerkrechten en extra
   apps die manager niet heeft), maar opnieuw en expliciet per app toegewezen.
4. **Ook `admin` verdwijnt op termijn als toegangsgroep.** Toegang bestaat
   alleen nog per app. De twee plekken waar `admin` nu bewerkrechten geeft
   (`EDITOR_GROUPS: communicatie-editors,admin` en
   `EDITOR_GROUPS: vermogen-editors,admin` in docker-compose.override.yml)
   worden vervangen door de nieuwe edit-groepen.
5. **Schone lei**: elke gebruiker wordt opnieuw toegewezen aan de read- of
   edit-groep van elke app die hij nodig heeft. Niets wordt automatisch
   overgenomen uit de oude groepen.

## 2. Definities: wat read en edit betekenen

Drie lagen, elk met een eigen slot:

| Laag | Wat | Wie regelt het |
|---|---|---|
| Gebruiken | data bekijken en bewerken in de app | Authentik-groepen (read/edit) |
| Bouwen | code wijzigen, deployen | GitHub + VM, geen Authentik |
| Beheren | gebruikers, groepen, SSO | akadmin in Authentik |

Write access gaat dus nooit over de code; dat regelen GitHub-toegang en de
deploy-pipeline.

- **`app-{naam}-read`**: je ziet de app in het startscherm en mag alles
  bekijken, zoeken en downloaden. Je kunt niets veranderen, ook niet via een
  omweg buiten de knoppen om.
- **`app-{naam}-edit`**: alles van read, plus aanmaken, wijzigen, verwijderen,
  uploaden en het starten van acties of processen (een scrape aftrappen, een
  draaiboek-run starten, een factuur doorsturen of e-mail versturen: alles met
  extern gevolg is edit).

Lakmoesproef: verandert er iets nadat jij op de knop drukte? Dan is het edit.
Technisch valt de grens samen met HTTP: GET/HEAD = read,
POST/PUT/PATCH/DELETE = edit. Hygiëne-eis die daarbij hoort: een app mag nooit
iets wijzigen op een GET-request.

**Nested model**: Authentik bepaalt read of edit; fijnere nuances (wie mag
finaliseren, wie mag verwijderen) zijn de verantwoordelijkheid van de app
zelf, bovenop edit, nooit als achterdeur eromheen. Bestaande in-app-rollen
(zoals finaliseren in draaiboek) blijven dus bestaan.

**Flexibiliteit met een hek eromheen**: het model is additief uitbreidbaar
(een nieuw platformbreed niveau zoals `app-{naam}-admin` kan later, bestaande
apps merken daar niets van omdat de helper onbekende groepen negeert), maar
uitbreidingen gebeuren alleen platformbreed en gedocumenteerd via dit
conventiedocument plus het validatiescript, nooit per app een afwijkende
groepsnaam.

## 3. Correcties op de oorspronkelijke opdracht (geverifieerd)

Geverifieerd tegen de stack (Authentik 2026.5.3) en de blueprint-docs van die
versie:

1. **De spoke-apps zijn geen OIDC-apps maar forward-auth proxy-apps.**
   Identiteit en groepen komen binnen als `X-authentik-groups`-header (soms
   met `|`, soms met `,` gescheiden; zie `omv-demo/sso_auth.py`). De
   Flask-helper leest dus de header, geen OIDC-token.
2. **Geen extra scope-mapping nodig**: de standaard `profile`-scope van
   Authentik levert de groups-claim al mee (relevant voor eventuele
   OIDC-clients). `blueprints/mappings/` vervalt op een comment na die dit
   vastlegt.
3. **Korte access-tokens lossen verouderde rechten niet op** bij forward-auth:
   de headers worden bepaald bij het inloggen op de app-sessie; een
   groepswijziging werkt pas door na herlogin. Offboarding = account
   deactiveren in Authentik (maakt alle sessies direct onbruikbaar), niet
   alleen uit groepen halen.
4. **Groepshiërarchie (parent groups) is geen alternatief** voor
   edit-impliceert-read: de forward-auth-header bevat alleen directe
   lidmaatschappen (goauthentik issue 6477). Vlakke groepen + logica in de
   helper.
5. **De Authentik-launcher is de home** (`auth.<domein>/if/user/`); de oude
   Flask-portal is afgedankt en `apps.yaml` is legacy. Tegel-zichtbaarheid =
   PolicyBindings op de Application. Er is dus geen apart
   portaal-zichtbaarheidsprobleem: binding regelt zichtbaarheid én toegang.
6. **Blueprint-mechaniek bevestigd** voor 2026.5.3: extra `.yaml` in
   `/blueprints` (mount in de worker-container) wordt automatisch ontdekt,
   file-watch past wijzigingen direct toe, hersync elke 60 minuten.
   Idempotentie via `identifiers` + `state` (present/created/must_created/
   absent); een blueprint is één atomaire transactie. Let op: een
   blueprint-bestand verwijderen laat de aangemaakte objecten bestaan;
   opruimen gaat expliciet via `state: absent`.
7. **Backup kan met `ak export_blueprint`** in de worker-container, aangevuld
   met een `pg_dump` van de Authentik-database.

## 4. Stappenplan

### Stap 0 - Veiligheid (vóór elke wijziging)

1. Bevestig akadmin als break-glass: superuser, buiten alle app-groepen.
   Draai het akadmin-all-access-gedrag terug (akadmin uit `admin`/`manager`,
   bindings blijven via de nieuwe groepen lopen).
2. Backup: `ak export_blueprint` + `pg_dump` van de Authentik-database,
   bewaard buiten de repo.
3. **Inventarisatie eerst**: draai `scripts/inventariseer-groepen.py` via
   `sh scripts/ak-exec.sh scripts/inventariseer-groepen.py` (read-only) en
   plak de output terug. Op basis van de echte ledenlijst wordt de
   hertoewijzing per persoon uitgetekend en door Mehdi goedgekeurd.
4. Alles wordt eerst toegepast op een dummy-app `testapp`; uitrol naar echte
   apps pas na expliciete bevestiging.

### Stap 1 - Repo en structuur

Beslispunt bij start (zie §7): aparte private repo `appportal-infra` of een
map `authentik/blueprints/` in deze repo. De compose-wijziging (de mount) zit
hoe dan ook in deze repo. Structuur (in beide varianten):

```
blueprints/
  groups/{appnaam}.yaml        de twee groepen per app
  policies/{appnaam}-access.yaml  PolicyBindings (zichtbaarheid + toegang)
scripts/
  validate-naming.py           conventie-check (CI-kandidaat)
  sync-check.py                stub, bewust uitgesteld
shared/
  appportal_auth/              Flask-helper (zie stap 5)
docs/
  conventies.md                §2 van dit plan + blueprint-afspraken
  nieuwe-app-toevoegen.md      checklist nieuwe spoke-app
  onboarding-offboarding.md    medewerker erbij/eruit (deactiveren!)
  bouwers-handleiding.md       voor niet-technische bouwers
```

### Stap 2 - Blueprints

- Per app één bestand in `blueprints/groups/` met de twee groepen
  (`model: authentik_core.group`, `identifiers: {name: ...}`,
  `state: present`).
- Per app één bestand in `blueprints/policies/` dat de bindings legt:
  `model: authentik_policies.policybinding`, target via
  `!Find [authentik_core.application, [slug, {appnaam}]]`, identifiers op
  target + group (of target + order), beide groepen gebonden aan de app.
- Geen scope-mapping-blueprint (zie §3.2).
- Opruimen van oude groepen/bindings gebeurt in dezelfde bestanden met
  `state: absent`, pas in de laatste migratiefase.

### Stap 3 - Volume-mount (GitOps)

1. Checkout van de blueprint-bron op de VM (locatie afhankelijk van het
   repo-besluit; bij map-in-deze-repo is `~/appportal` er al).
2. docker-compose.yml: mount `./authentik/blueprints` (of de infra-checkout)
   op `/blueprints/custom` in de **worker**-container (server mag ook, worker
   is degene die toepast). Alleen na bevestiging.
3. `docker compose up -d authentik-worker`, daarna in de UI controleren dat de
   blueprints als applied verschijnen.
4. Workflow documenteren: wijziging in git, `git pull` op de VM, file-watch
   past direct toe (hersync elke 60 min als vangnet).

### Stap 4 - Sessies en offboarding

- Vastleggen in `docs/onboarding-offboarding.md`: rechten wijzigen werkt pas
  door na herlogin van die gebruiker; vertrek = account deactiveren.
- Access-token-geldigheid van de OIDC-provider(s) kort zetten is alleen
  relevant voor OIDC-clients; voor de forward-auth-apps is de sessieduur
  (nu 8 uur) de bepalende knop. Gekozen waarden + rationale in
  `docs/conventies.md`.

### Stap 5 - Flask-helper (`appportal_auth`)

1. Leest `X-authentik-groups` (accepteert `|` en `,` als scheiding), fail-closed:
   header afwezig, leeg of geen van beide groepen = 403. Nooit doorlaten bij
   twijfel.
2. `@require_read("appnaam")` en `@require_edit("appnaam")`; elke schrijfroute
   (POST/PUT/PATCH/DELETE) draagt `@require_edit`. Mechanisch controleerbaar:
   test dat elke niet-GET-route beschermd is.
3. Edit impliceert read in de helper-logica.
4. Jinja-helper `can_edit` voor het verbergen van knoppen (cosmetica; de
   server-side check is de handhaving).
5. Versienummer in het bestand; onbekende groepen worden genegeerd
   (additieve uitbreidbaarheid).
6. Unit tests inclusief fail-closed-scenario's (ontbrekende header, lege
   groepen, verkeerde appnaam, beide scheidingstekens).

### Stap 6 - Validatie

`validate-naming.py`: valideert groepsnamen in de blueprint-YAMLs (en
optioneel live via een read-only API-token) tegen de conventie-regex, exit
code niet-nul bij afwijking. Checkt ook dat compose-envs
(`EDITOR_GROUPS`, `TOEGANG_GROEPEN`) geen verdwenen groepsnamen meer noemen.

### Stap 7 - Documentatie

De vier docs-bestanden uit stap 1. `conventies.md` bevat §2 van dit plan
integraal, plus: bestand weg is niet groep weg (state: absent), en de
afspraak dat modeluitbreidingen alleen platformbreed gebeuren.
`bouwers-handleiding.md`: kort, copy-paste-voorbeelden, expliciet de
waarschuwing dat launcher-zichtbaarheid geen beveiliging is; de decorator in
de app is de echte poort.

### Stap 8 - Migratie en test

Volgorde per app (nooit eerst slopen):

1. Nieuwe groepen aanmaken en binden (blueprint), naast de oude.
2. Leden toewijzen volgens de goedgekeurde hertoewijzing.
3. App omzetten op de helper; edit-check van de app (env of hardcoded) naar
   de nieuwe edit-groep.
4. Testen: read-lid ziet de app en kan niet schrijven (ook een directe POST
   buiten de UI om testen), edit-lid kan schrijven, buitenstaander ziet de
   tegel niet én krijgt 403 op de directe URL.
5. Oude groepen/bindings op `state: absent`.

Eerst volledig doorlopen met `testapp`; daarna app voor app, met bevestiging.
Mee te nemen in de migratie: de testscripts (`create-test-users.py`,
`e2e-test.py`, `full-journey.py`, `omv-verify.py`, `logout-probe.py`,
`totp-probe.py`) draaien op `testmanager` en moeten omgezet worden naar
testgebruikers in de nieuwe groepen; docs (README, TECHNICAL-REFERENCE §4 en
§12, DEPLOY.md) in dezelfde push bijwerken.

## 5. Wat dit plan bewust niet oplost

- **Dagelijkse toewijzing blijft handwerk in de Authentik-UI** (Directory,
  Groups). Ledenlijsten horen niet in git (PII, elke mutatie een commit). De
  uniforme naamgeving maakt een latere toewijs-UI of een sync met de
  medewerkersdatabase wel triviaal.
- Sync medewerkersdatabase - Authentik-groepen: stub in `sync-check.py`.
- Claim-filtering per provider; aparte read/write databasecredentials per app.
- `apps.yaml`/Flask-portal opruimen uit compose (legacy sinds de launcher).

## 6. Openstaande beslispunten (vóór de bouw)

1. **Repo**: aparte `appportal-infra` (scheiding van wie infra mag wijzigen,
   eigen CI) of map in deze repo (één checkout, één pull-moment, eenvoudiger).
   Aanbeveling: map in deze repo, tenzij toegangsscheiding gewenst is.
2. **Helper-distributie**: gevendorde single-file `appportal_auth.py` met
   versienummer per spoke-repo (aanbeveling; drift wordt door `sync-check.py`
   gesignaleerd) of pip-install uit een private repo (vereist credentials in
   elke Docker-build).

## 7. Bijlage: inventarisatie 2026-07-07 en hertoewijzingsvoorstel

Inventarisatie gedraaid op de VM (output in de sessie van 2026-07-07).
Kernfeiten:

- `manager` en `admin` bevatten allebei alleen akadmin en mehdi. Niemand
  anders is van die groepen afhankelijk; opheffen kost geen enkele collega
  toegang.
- **omv-v2 heeft geen enkele binding** en is daardoor toegankelijk voor elke
  ingelogde gebruiker. Direct beslissen: binden of verwijderen.
- Er bestaan apps/groepen die niet in de repo-docs staan: renovision,
  renovision-mehdi (beide met -bewerken), agenda-architect/-volledig,
  toegangsbeheerders (alleen siyan; doel onbekend). §12.1 van
  TECHNICAL-REFERENCE is verouderd.
- draaiboek en draaiboek-editors zijn leeg; alleen admin/manager (= mehdi)
  kan er nu in.
- telefoonregister is de repo van de collega (ongemoeid laten): de groepen
  `telefoonregister`/`telefoonregister-editors` migreren vereist wijzigingen
  in die app. Mogelijk uitzonderen of pas na overleg.

Voorstel (ter goedkeuring; akadmin staat bewust nergens, superuser =
break-glass; uitgangspunt is de huidige effectieve toegang, apps zonder
edit-onderscheid vandaag zijn als edit overgenomen):

| App | app-{naam}-read | app-{naam}-edit |
|---|---|---|
| omv | - | mehdi |
| schuldentracker | mehdi | angela |
| chaos | - | angela, mehdi, siyan |
| agenda | angela, matthew, siyan | mehdi |
| telefoonregister | (uitzonderen? zie boven) | |
| facturatie | - | mehdi |
| barstenscheuren | - | matthew, mehdi |
| vermogen | - | mehdi |
| draaiboek | - | mehdi |
| communicatie | mehdi | siyan |
| kosten | angela | mehdi |
| factuurrouter | - | mehdi |
| stagebeoordeling | mehdi | raisha |
| medewerkers | - | mehdi |
| status | mehdi | - |
| renovision | mehdi | samad |
| renovision-mehdi | - | mehdi |
| omv-v2 | (binden of verwijderen) | |

In-app-verfijning die blijft bestaan naast het read/edit-model (nested):
agenda-volledig en agenda-architect (kijk-tiers van de agenda-app). Het
validatiescript moet zulke gedocumenteerde in-app-groepen toestaan.

Open vragen bij dit voorstel: (a) omv-v2 binden of weg, (b) doel van
`toegangsbeheerders`, (c) telefoonregister meenemen of uitzonderen,
(d) klopt de edit-inschatting voor chaos/kosten/barstenscheuren (apps zonder
edit-onderscheid vandaag), (e) appnaam per app bevestigen (slug `stage` vs
naam `stagebeoordeling`, `medewerkers` vs `organisatie`, `status` vs
`monitoring`).
