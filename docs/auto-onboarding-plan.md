# Auto-onboarding — apps automatisch koppelen aan AppPortal

*Laatst bijgewerkt: 2026-06-25*

## In één zin
Een gebruiker vibe-codet z'n app met **Claude Code** (abonnement, niet de API);
zodra die naar de GitHub-repo gepusht wordt, **synchroniseert de server zichzelf**
— subdomein, TLS, reverse-proxy, SSO en portaal-tegel verschijnen automatisch,
zonder dat iemand iets aan git, config of de VM aanraakt.

## 1. Het probleem
Een app aan AppPortal koppelen is vandaag handwerk (README §3): docker-compose-
service, nginx-server-block, cert-SAN, `apps.yaml`-tegel en Authentik
(proxy-provider + application + outpost + group-binding). Eén persoon doet dat
voor iedereen → bottleneck. De makers zijn bovendien **niet-technisch** en mogen
git/terminal/config nooit zien.

## 2. De aanpak — twee gescheiden helften

```
AUTHORING  (mens + Claude Code, abonnement)      SYNC  (kale infra, géén API)
──────────────────────────────────────────      ───────────────────────────────
portaal-knop ──pre-filled deeplink──►            GitHub push (claude/* branch)
claude.ai/code  (gedeeld account)                        │  webhook (HMAC)
   gebruiker typt wat hij wil                             ▼
   Claude werkt in cloud-VM ──push branch──►       appsync-listener (deze service)
                                                     • leest appportal.yaml uit de repo
                                                     • START-TEST (draait de app?)
                                                     • PREVIEW op <id>-preview.<domain>
portaal-tegel  [Bekijken] [Publiceren] ◄───────────  • meldt "preview klaar"
   maker klikt Publiceren ──merge→main──►          live op <id>.<domain> + tegel + SSO
```

De dure AI-stap blijft op het **abonnement** (interactieve Claude Code). De
sync-helft is **webhooks + deterministische generatie** en kost per saldo niets
per token.

## 3. Beslissingen (vastgelegd in eerdere afstemming)
- **Vibe-coding tool:** Claude Code (app / "Code op het web"), **niet de API**.
- **Account:** één gedeeld Max-account **met mitigaties** (zie §6).
- **Bron:** vibe-coding tool pusht zelf; **1 repo per app**.
- **Toegang:** **maker + admins** (privé). Identiteit komt uit het **portaal**
  (Authentik-SSO), niet uit het gedeelde Claude/GitHub-account.
- **Live-flow:** **preview, dan 1 klik publiceren** (sluit aan op
  `docs/mvp-self-service-bewerking.md`).

## 4. Het manifest (`appportal.yaml` in elke app-repo)
Convention-over-configuration: de niet-technische gebruiker schrijft dit **niet**;
het komt uit het repo-template (Fase 2). Ontbreekt het, dan leidt `appsync` veilige
defaults af uit de repo-naam.

```yaml
# appportal.yaml — auto-onboarding manifest
id: stagebeoordeling          # stabiel; == subdomein; [a-z0-9-]
name: Stagebeoordeling        # tegel-titel
description: Beoordeling van stagedossiers
subdomain: stagebeoordeling   # default = id
port: 8080                    # interne poort waarop de app luistert
roles: [stagebeoordeling, admin]   # default = [<id>, admin]  → maker-groep + admins
maker: angela                 # optioneel: Authentik-username die toegang krijgt
```

## 5. Architectuur van `appsync` (deze Fase-1 build)

```
appsync/
  app.py          # Flask webhook-ontvanger: HMAC-verificatie, push parsen, job in queue
  manifest.py     # manifest laden / valideren / afleiden uit repo-naam
  generator.py    # PURE renderers (geen side-effects, volledig getest):
                  #   app-entry · nginx-block · cert-SAN-merge · Authentik-blueprint
  register.py     # idempotent toepassen op de repo-werkboom (apps.d/, nginx-, cert-, blueprint-bestanden)
  queue.py        # geserialiseerde FIFO-worker (mitigatie gedeeld account)
  deployer.py     # VM-zijde: git pull + docker/nginx reload + blueprint-apply (interface; op de VM scherpgesteld)
  tests/          # pytest — de hele deterministische kern draait lokaal, zonder Docker/Authentik
```

**Single source of truth = `apps.d/`.** Elke auto-onboarded app is één bestand
`apps.d/<id>.yaml`. Daaruit worden afgeleid:
- de portaal-tegel (de portal merget `apps.yaml` + `apps.d/*.yaml`, live, geen restart);
- `nginx/templates/50-autoapps.conf.template` (alle auto-app server-blocks);
- `certs/extra-subdomains` (extra SAN's voor de TLS-cert);
- `authentik/blueprints/<id>.yaml` (proxy-provider + application + group-binding + outpost).

Rollback = het bestand `apps.d/<id>.yaml` verwijderen en regenereren.

## 6. Mitigaties voor het gedeelde Max-account
1. **Serialiseren** — `queue.py` draait nooit twee Claude Code-sessies tegelijk
   (gedeelde 5-uurs/week-pool niet in één klap leegtrekken; minder detectie-risico).
2. **Eén login-context** — bij voorkeur de **Routine-API** (portaal vuurt
   server-side onder één token; gebruikers loggen niet zelf op claude.ai in).
   v1 mag starten met de pre-filled deeplink + gedeelde browsercontext.
3. **Pool-bewaking** — bij uitputting een nette "even geduld"-melding; de queue
   pikt het later op.
4. **Attributie in het portaal** — Authentik-SSO bepaalt `repo ↔ maker`.

> Routine-API-bevinding: `POST …/routines/{id}/fire` accepteert een **dynamische
> instructie** (`text`), maar **niet een dynamische repo** per call — de repo zit
> vast in de routine. Voor "1 repo per app" betekent dat: één routine per app,
> aangemaakt bij onboarding. Research-preview met dagcaps → latere upgrade.

## 7. Fasering
- **Fase 1 (deze build):** de sync-motor. `appsync`-service: webhook → manifest →
  deterministische generatie van tegel/nginx/cert/blueprint + queue. Portal merget
  `apps.d/`. Volledig geteste kern; VM-zijde (git pull, docker/nginx reload,
  blueprint-apply) als duidelijke interface, op de VM scherp te stellen.
- **Fase 2:** de naadloze voorkant — "Nieuwe app"/"Pas aan"-knoppen in het portaal
  die een repo uit een template maken en een pre-filled Claude Code-deeplink openen;
  start-test + preview-subdomein; `[Bekijken]/[Publiceren]`-tegel.
- **Fase 3:** Routines voor 0-touch/geplande taken; Authentik-Blueprints als enige
  identity-config (volledige GitOps).

## 8. Wat in Fase 1 nog niet leeft (eerlijk)
- De daadwerkelijke `git clone/pull` + `docker compose up` + `nginx -s reload` +
  blueprint-apply draaien op de **VM**, niet in de CI-sandbox — `deployer.py` is de
  interface daarvoor en wordt op de VM gevalideerd.
- Preview-runner en de `[Publiceren]`-tegel zijn Fase 2.
- Authentik-blueprint-discovery vereist de blueprints-mount (toegevoegd in compose,
  te valideren op een live Authentik).
```
