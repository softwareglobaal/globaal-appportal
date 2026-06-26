# AppPortal — Technisch Referentiedocument (as-built)

Dit document beschrijft het AppPortal-platform **zoals het nu daadwerkelijk
draait** in productie. Het is bedoeld als projectdocumentatie: iemand die het
project niet kent, moet hiermee de volledige opzet kunnen begrijpen, beheren en
problemen kunnen oplossen.

> Begeleidende documenten:
> - [README.md](README.md) — beknopte introductie + lokale opzet.
> - [DEPLOY-AWS.md](DEPLOY-AWS.md) — schoon deploy-draaiboek voor een AWS-VM.
> - [vm/CUTOVER.md](vm/CUTOVER.md) — draaiboek voor de overgang op de bestaande VM.
>
> **Dit document is de leidende "as-built" referentie** en bevat details en
> fixes die in de andere docs (deels) ontbreken.

---

## 1. Wat is AppPortal?

AppPortal is een intern applicatieplatform met **single sign-on (SSO)**.
Medewerkers loggen één keer in via een centrale identiteitsprovider
(Authentik, met verplichte TOTP-2FA), komen op een portal-pagina die alleen de
applicatie-tegels toont waar hun rol recht op heeft, en klikken vervolgens door
naar die applicaties **zonder opnieuw in te loggen**.

Kernprincipes:
- **Authentik** beheert álle authenticatie: wachtwoorden, 2FA, sessies, gebruikers.
- De **portal** (Flask) doet zelf geen wachtwoordbeheer; hij authenticeert via
  OIDC tegen Authentik en toont tegels op basis van Authentik-groepen.
- **Applicaties** zien nooit een loginscherm. Nginx valideert elke aanvraag
  tegen Authentik (forward auth) en geeft de identiteit door via HTTP-headers.
- **Eén publieke ingang**: nginx op poort 80/443, TLS-getermineerd. De
  applicaties zijn alleen intern (Docker-netwerk) bereikbaar.

---

## 2. Architectuur

```
                        Internet
                           │  HTTPS (DNS-only via Cloudflare)
                           ▼
        ┌──────────────────────────────────────────────┐
        │  nginx  (de enige publieke ingang, poort 80/443) │
        │   ├─ auth.globaal.be      → Authentik (IdP)       │
        │   ├─ portal.globaal.be    → Flask-portal (OIDC)   │
        │   ├─ omv.globaal.be       → OMV-app (forward auth)│
        │   ├─ factorydocs/… .be    → stub-apps (forward auth)│
        │   └─ n8n.globaal.be       → n8n (gewone doorsturing)│
        └──────────────────────────────────────────────┘
                 │              │                  │
                 ▼              ▼                  ▼
            Authentik       Flask-portal      backend-apps
          (+ embedded     (Authlib OIDC,     (stubs, OMV op
           outpost)        apps.yaml)         de host, n8n)
                 │
                 ▼
            PostgreSQL (Authentik-database, intern)
```

### 2.1 Login-flow (portal)
1. Browser → `https://portal.globaal.be`. Geen sessie → redirect naar `/login`.
2. Portal start een OIDC-flow → redirect naar `https://auth.globaal.be/...`.
3. Authentik toont login → wachtwoord → **TOTP** → (eerste keer: TOTP instellen).
4. Authentik stuurt terug naar `https://portal.globaal.be/auth/callback` met een
   code; de portal wisselt die in voor een token + `groups`-claim.
5. De portal toont de tegels waarvoor `groups ∩ rollen` (uit `apps.yaml`) matcht.

### 2.2 Doorklik-flow (forward auth)
1. Gebruiker klikt een tegel → redirect naar bv. `https://omv.globaal.be`.
2. Nginx doet een interne sub-aanvraag (`auth_request`) naar Authentik's
   **embedded outpost**.
3. Outpost kent de bestaande Authentik-sessie → antwoordt "toegestaan" en geeft
   identiteits-headers terug (`X-authentik-username`, `-email`, `-groups`, …).
4. Nginx zet die headers door naar de applicatie en proxyt de aanvraag.
5. De applicatie vertrouwt die headers → de gebruiker is meteen ingelogd.
   (Geen sessie? → de outpost stuurt naar de Authentik-login.)

### 2.3 Single logout
Uitloggen in de portal beëindigt de **hele Authentik-sessie** (via de globale
invalidation-flow). Omdat forward auth élke aanvraag opnieuw controleert, is
daarna ook elke app meteen vergrendeld.

---

## 3. De productieomgeving (zoals het nu draait)

### 3.1 De server
- **AWS EC2-VM**, Ubuntu (kernel 6.x), hostnaam `ip-172-31-19-35`.
- Publiek IP: **`54.80.98.233`**. Privé IP: `172.31.19.35`.
- Root-schijf vergroot naar **40 GB** (oorspronkelijk ~19 GB; zat vol — zie §9.7).
- **Docker Engine (CE)** draait native op de host (geen Docker Desktop).
- Deze VM host méér dan AppPortal (zie §3.4); AppPortal's nginx is de enige
  publieke webingang.

### 3.2 Domein & DNS — let op: Cloudflare
Het domein **`globaal.be`** wordt **niet** bij one.com beheerd qua DNS, maar bij
**Cloudflare** (one.com is registrar/mailhost). Wijzigingen moeten dus in het
**Cloudflare-dashboard** gebeuren. De relevante records (as-built):

| Naam | Type | Inhoud | Proxy | Doel |
|---|---|---|---|---|
| `*.globaal.be` | A | `54.80.98.233` | **DNS only** | alle AppPortal-hostnames → VM |
| `*.globaal.be` | AAAA | *(verwijderd)* | — | IPv6-wildcard weggehaald (zie §9.5) |
| `data.globaal.be` | A | `54.80.98.233` | DNS only | oude OMV-URL (direct naar VM) |
| `n8n.globaal.be` | A | `54.80.98.233` | DNS only | n8n |
| `www.globaal.be` | A/AAAA | one.com-hosting | Proxied | hoofdwebsite (los van AppPortal) |
| `ha-customgpt` | Tunnel | Cloudflare-tunnel | Proxied | ongebruikt (mag opgeruimd) |
| `globaal.be` | MX/TXT | one.com mail, SPF, DMARC | DNS only | e-mail (niet aanraken) |
| `*._domainkey` | CNAME | DKIM | DNS only | e-mail (niet aanraken) |

> **Cruciaal:** de AppPortal-hostnames staan op **DNS only** (grijs wolkje).
> Daardoor gaat verkeer **rechtstreeks** naar de VM, waar onze nginx zelf de
> HTTPS + Let's Encrypt + forward-auth afhandelt. Zou je ze "Proxied" (oranje)
> zetten, dan zit Cloudflare ertussen en moet je SSL-modus en origin-certs apart
> regelen — dat willen we hier niet.

### 3.3 De AppPortal-stack (Docker Compose)
Projectmap op de VM: `~/appportal`. Compose-projectnaam: **`appportal`**
(daardoor heten de volumes `appportal_*`, los van de mapnaam).

| Service | Image | Poort (host) | Rol |
|---|---|---|---|
| `nginx` | nginx:1.27-alpine | **80, 443** | enige publieke ingang, reverse proxy |
| `authentik-server` | ghcr.io/goauthentik/server:2026.5.3 | intern | IdP + embedded outpost |
| `authentik-worker` | idem | intern | achtergrondtaken |
| `postgresql` | postgres:16-alpine | intern | Authentik-database |
| `portal` | (build ./portal) | intern | Flask OIDC-portal |
| `app-factorydocs/-inventory/-finance/-maintenance` | (build ./stubapp) | intern | demo-stub-apps (poorten 3001–3004) |
| `app-omv` | (build ./omv-demo) | intern | demo-stub (ongebruikt op de VM, zie §3.5) |
| `app-telefoonregister` | (build ./telefoonregister) | intern | **echte** app — Telefoonregister (Node.js, poort 3006; via `docker-compose.override.yml`, zie §6D) |
| `certgen` | alpine:3.20 | — | eenmalig: zelf-ondertekend cert (lokaal/dev) |

Netwerk: één bridge `appnet`. Volumes: `appportal_postgres-data`,
`appportal_authentik-data`, `appportal_authentik-certs` (deze bevatten alle
Authentik-config en de database — dit is de te back-uppen state).

### 3.4 Mede-bewoners op de VM (geen onderdeel van de stack)
Deze draaien apart en lopen **niet** via AppPortal's nginx — ze worden door de
cutover niet geraakt:
- **n8n** — Docker-container `n8n-n8n-1`, luistert op `127.0.0.1:5678`. Wél
  gekoppeld aan `appnet` zodat AppPortal's nginx 'm kan proxyen (zie §3.5).
- **OMV Pipeline** — Flask-app op de host (zie §6), `0.0.0.0:5000`.
- **Factuurrouter** — AI-factuurrouteringsagent op de host (zie §6A),
  `~/factuurrouter`; watcher (`factuurrouter.service`) + dashboard
  (`factuurrouter-dashboard.service`, `0.0.0.0:8787`).
- **Stagebeoordeling** — stagiaire-beoordelingsdashboard op de host (zie §6B),
  `~/stagebeoordeling`, `0.0.0.0:8088`, SQLite, systemd-service.
- **Schuldentracker** — schuldendossier-tracker op de host (zie §6C),
  Flask-app, `0.0.0.0:5050`, systemd `schuldentracker.service`.
- **Kosten** — software-kostendashboard op de host (zie §13.4), `~/kosten`,
  `0.0.0.0:8090`, systemd `kosten.service`.
- **CHAOS Taskforce** — UNABO-werkstroomdashboard (zie §6E), `~/chaos`,
  `0.0.0.0:8095`, systemd `chaos.service`.
- **Beschikbaarheid Mehdi (agenda)** — Google-Calendar-beschikbaarheid (zie §6F),
  `~/globaal-calendar-mehdi`, `0.0.0.0:5060`, systemd `agenda.service`.
- **RenoVision AI** — analyse van bouwtekeningen (zie §6G), eigen docker-compose
  onder `~/globaal-renovision` (8100) + sandbox `~/globaal-renovision-mehdi` (8101),
  MongoDB-backend.
- **HR-/urendashboard (DeskTime)** — zie §13.5, `~/hr-dashboard`, `0.0.0.0:8089`
  (service actief; nog niet achter SSO).
- **cloudflared-tunnel** — routeert alleen `ha-customgpt.globaal.be` (ongebruikt).
- **Host-PostgreSQL** — `127.0.0.1:5432` (los van de Authentik-DB in Docker).
- Overige projecten in `/home/ubuntu` (barsten_en_scheuren, Finance/Schuldentracker,
  PDF_PARSER, tkn-knowledge-platform) — draaien via screen/tunnel.
- **Host-nginx (apt)** — was de oude reverse proxy; nu **gestopt + disabled**
  (vervangen door AppPortal's nginx). Dit is tevens de rollback (zie §8.4).

### 3.5 Hostname-routing (as-built)

| Hostname | Gaat naar | Auth |
|---|---|---|
| `portal.globaal.be` | `portal:8000` (Flask) | OIDC-login |
| `auth.globaal.be` | `authentik-server:9000` | n.v.t. (de IdP zelf) |
| `omv.globaal.be` | de echte OMV-app op de host, `http://<host-gateway-ip>:5000` | forward auth + SSO-shim |
| `factuurrouter.globaal.be` | Factuurrouter-dashboard op de host, `http://172.17.0.1:8787` | forward auth (oude `remy.globaal.be` → 301 hierheen) |
| `stage.globaal.be` | Stagebeoordeling op de host, `http://172.17.0.1:8088` | forward auth (Raisha = bewerken, rest = lezen) |
| `kosten.globaal.be` | Kosten-dashboard op de host, `http://172.17.0.1:8090` | forward auth (groep `kosten`) |
| `telefoonregister.globaal.be` | `app-telefoonregister:3006` (container in de stack) | forward auth (`telefoonregister` zien, `-editors` bewerken) |
| `chaos.globaal.be` | CHAOS-dashboard op de host, `http://172.17.0.1:8095` | forward auth (groep `chaos`) |
| `agenda.globaal.be` | Beschikbaarheid Mehdi op de host, `http://172.17.0.1:5060` | forward auth (`agenda-bekijken`/`-volledig`/`-architect`) |
| `renovision.globaal.be` | RenoVision (gedeeld) op de host, `http://172.17.0.1:8100` | forward auth (`renovision`/`-bewerken`) |
| `renovision-mehdi.globaal.be` | RenoVision (Mehdi-sandbox), `http://172.17.0.1:8101` | forward auth (`renovision-mehdi`/`-bewerken`) |
| `status.globaal.be` | Uptime Kuma, `http://uptime-kuma:3001` | forward auth (`admin`/`manager`) |
| `factorydocs/inventory/finance/maintenance.globaal.be` | `app-*:300x` (demo-stubs; Authentik-providers verwijderd, containers draaien nog) | forward auth |
| `n8n.globaal.be` | `n8n-n8n-1:5678` | gewone doorsturing (n8n's eigen login) |
| `data.globaal.be` | *(geen server-blok)* | n.v.t. — vervangen door `omv.globaal.be` |

---

## 4. Authentik (identiteitsprovider)

- **Versie:** 2026.5.3 (PostgreSQL-only; Redis is sinds Authentik 2025.10 niet
  meer nodig). Community-editie.
- **Admin-account:** `akadmin` (bootstrap-wachtwoord uit `.env`). *Voor de
  eerste test tijdelijk in de groep `manager` gezet.*
- **Groepen:** `admin` en `manager` (sturen de tegel-zichtbaarheid én de
  toegang).
- **Portal-OIDC-provider** (`portal-oidc`): confidential client, redirect-URI
  `https://portal.globaal.be/auth/callback`, scopes openid/profile/email,
  grant types authorization_code + refresh_token, **invalidation flow =
  `default-invalidation-flow`** (nodig voor single logout).
- **Proxy-providers** (forward auth, "single application") per app:
  `omv-proxy`, `schuldentracker-proxy`, `factuurrouter-proxy` (voorheen `remy-proxy`),
  `stage-proxy` (= Stagebeoordeling), `kosten-proxy`, `status-proxy` (Uptime Kuma),
  `Telefoonregister`, `chaos-proxy`, `agenda-proxy`, `renovision-proxy` en
  `renovision-mehdi-proxy`. External host = `https://<sub>.globaal.be`. *(De oude
  stub-providers `factorydocs/inventory/finance/maintenance-proxy` zijn verwijderd;
  de stub-containers draaien nog — zie §12.4.)* Eigen toegangsgroepen per app naast
  `admin`/`manager`: o.a. `schuldentracker`, `factuurrouter`, `stagebeoordeling`,
  `kosten`, `chaos`, `telefoonregister`, `agenda-bekijken`, `renovision`
  (+ `-bewerken`/`-editors`/`-volledig` voor schrijf-/detailrechten) — zie §12.1.
- **Embedded outpost:** alle proxy-providers zijn toegewezen; `authentik_host =
  https://auth.globaal.be`.
- **Toegangscontrole:** group-bindings per applicatie (FinanceDashboard alleen
  `manager`; de rest `admin` + `manager`). Dit is de échte handhaving; `apps.yaml`
  regelt alleen de tegel-zichtbaarheid.
- **TOTP verplicht:** stage `default-authentication-mfa-validation` → niet
  geconfigureerd = forceren + TOTP-setup-stage.
- **Sessieduur:** 8 uur (`default-authentication-login`).

De Authentik-config wordt aangemaakt door de scripts (zie §7), niet handmatig.

---

## 5. De Flask-portal

Map: `portal/`. Draait onder gunicorn op poort 8000 (intern).
- **OIDC** via Authlib; metadata-URL
  `https://auth.globaal.be/application/o/portal/.well-known/openid-configuration`.
- **`apps.yaml`** definieert de apps (id, naam, subdomein, rollen, status). Bij
  elke paginalading opnieuw gelezen — apps toevoegen kan zonder herstart.
- **Tegel-filtering:** `set(gebruiker.groups) & set(app.roles)`.
- **Routes:** `/` (tegels), `/login`, `/auth/callback`, `/go/<app_id>`
  (rol-check + redirect), `/logout` (single logout), `/healthz`.
- **Logging:** auth-events en doorkliks naar `logs/portal/portal.log`.
- **Sessie:** signed cookie, Secure + HttpOnly, max 8 uur.

---

## 6. De OMV Pipeline-integratie

De echte OMV-app (Flask + SocketIO dashboard van de datapijplijn) draait **op de
host**, niet in de stack. Het is de **OMV-scraper/-pipeline**: een end-to-end keten
die de Vlaamse **Omgevingsvergunning**-data (OMV) scrapet, verrijkt en ontsluit.

### 6.1 Wat de pipeline doet (scrape → download → merge → extract)
1. **Scrapen** — `scraper.py` haalt per **gemeente** dossiers uit de **Vlaamse
   Omgevingsloket-API** (`omgevingsloketinzage.omgeving.vlaanderen.be`) en schrijft
   ze naar SQLite (`scraper.db`). Gebruikt `curl_cffi` (browser-impersonatie) +
   `tenacity`-retries; optioneel beperkt tot gemeenten via
   `SCRAPER_GEMEENTE_WHITELIST`. Draait via een **VPN** (zie §6.3).
2. **PDF's downloaden** — `PDF_Downloader.py` haalt de dossier-/beroep-PDF's op en
   zet ze in **Dropbox** (week-mappen `YYYY_weekW_to_current`). Lookback via
   `DOWNLOADER_LOOKBACK_HOURS/DAYS` (default: vorige week).
3. **Mergen** — `new_merger.py`/`merger.py` voegen de PDF's per project samen in
   Dropbox, met **paginatelling-validatie** (verwachte vs. gemergede pagina's uit
   de `nota`/`plannen`-submappen → bij mismatch `ERROR_MERGE_MISMATCH`, publicatie
   geblokkeerd). Schrijft een `merged_manifest.jsonl`.
4. **Extraheren** — `part_1_v3_omv_db_fixed24_evidence_map.py` haalt met **OpenAI
   `gpt-5-mini` + regels + evidence-mapping** velden uit de gemergede PDF's
   (kolomdefinities in `field_spec.json`, sjabloon `4OMV_Master_Template_v3.xlsx`)
   → SQLite (`omv_dossiers.db`) + Excel (`OMV_Database_..._FILLED.xlsx`), inclusief
   geocoding (`pyproj`, lat/lon uit `scraper.db`).

### 6.2 Dashboard (`app.py`)
**Flask + SocketIO**, met **eigen login + TOTP** (`pyotp`/`qrcode`) en live-logs.
Start/monitort de pijplijn; de **Merger-modus** is de bron van waarheid (niet
`.env`): **Merge** (merge + extract), **MergeOnly**, **ExtractOnly** (uit manifest)
en **Manifest** (alleen manifest bouwen). Plus een gemeente-selector, een
**Data-tab** (query op `omv_dossiers.db` met kolomkiezer, export en edit-overrides)
en een Merged-PDF-statustabel met regenerate/validate-acties.

### 6.3 Data & secrets (gevoelig — blijft VM-only, nooit in git)
- **Secrets:** `.env` (`FLASK_SECRET_KEY`, **Dropbox `APP_KEY`/`APP_SECRET`**,
  `OPENAI_API_KEY`, dashboard-credentials, **`OMV_PROXY`** — zie §6.5),
  **`dropbox_tokens.json`** (OAuth-refresh, meerdere kopieën). De **VPN-config**
  `ubuntu_server-NL-FREE-15.conf` is een **verlaten poging** (wordt níét gebruikt —
  de scraper gaat via een SOCKS-proxy, zie §6.5; bevat wel een private key →
  behandelen als secret).
- **Data/state:** `scraper.db` + `omv_dossiers.db`, de gescrapte **PDF's** en
  Excel-exports (`output/` / Dropbox) en caches (geocode, pagecount, fingerprint)
  + manifests. ⚠️ Niets hiervan hoort in GitHub; back-up van de DB's is wenselijk.

### 6.4 Host, service & SSO-koppeling
- **Code:** `/home/ubuntu/omv_pipeline/v1/app.py`. Luistert op `0.0.0.0:5000`.
- **Draait als systemd-service** `omv.service` (auto-start na reboot, herstart
  bij crash):
  - `WorkingDirectory=/home/ubuntu/omv_pipeline/v1`
  - `ExecStart=/home/ubuntu/omv_pipeline/.venv/bin/python app.py`
  - `Environment=AUTH_MODE=sso`
  - De secrets staan in `/home/ubuntu/omv_pipeline/.env`; de app leest die via
    `v1/.env` → **symlink** naar `../.env` (zie §9.8).
- **SSO-koppeling via een shim:** `omv-demo/sso_auth.py` is gekopieerd naar
  `v1/sso_auth.py`, en in `v1/app.py` staan twee regels vóór `if __name__ ==
  '__main__':`:
  ```python
  from sso_auth import init_sso
  init_sso(app)
  ```
  Met `AUTH_MODE=sso` vertrouwt de app de `X-authentik-*`-headers en slaat z'n
  **eigen login + TOTP over**. Zonder header (directe toegang) blijft de eigen
  login werken — dus achterwaarts veilig.
- **Nginx-koppeling:** het `omv.globaal.be`-blok gebruikt forward auth en
  proxyt naar de host via de env-variabele `OMV_UPSTREAM` (zie §9.9).

> n8n is op vergelijkbare wijze gekoppeld, maar **zonder** SSO-shim: het
> `n8n.globaal.be`-blok is een gewone doorsturing en n8n houdt z'n eigen login.
> SSO voor n8n kan later op dezelfde manier als OMV.

### 6.5 ⚠️ Anti-blokkering: hoe de scraper de geblokkeerde API bereikt

**Lees dit eerst bij scraper-problemen.** De Vlaamse Omgevingsloket-API blokkeert
het AWS-datacenter-IP op **twee lagen**; beide moeten omzeild worden, anders krijg
je eindeloze `RetryError` op élke gemeente. Dit kostte een lange zoektocht — hier
de oplossing én de valkuilen.

**Laag 1 — IP-blok (TCP-timeout).** Het datacenter-IP `54.80.98.233` wordt **stil
gedropt** (time-out, geen weigering). Fix: OMV-verkeer via een **residentiële
SOCKS5h-proxy** — `OMV_PROXY=socks5h://localhost:1080` in `v1/.env`. Dat is een
**SSH-tunnel naar een fysiek Ubuntu-kastje bij de gebruiker thuis** (dezelfde proxy
als de DOV/barsten-scheuren-scraper). Alleen de OMV-host gaat via de proxy.

**Laag 2 — anti-bot (Anubis proof-of-work).** De site serveert een JS-challenge
("Making sure you're not a bot" / `.within.website`). Een **Playwright
headless-Chromium lost de PoW op** en oogst de `techaro.lol-anubis-auth`-cookie, die
in de echte API-call meegaat (`requests` + **pysocks** via dezelfde proxy).

**De drie valkuilen die ons vastzetten:**
1. **Playwright sync-API crasht in een achtergrond-thread** ("Execution context
   destroyed"). De Flask-SocketIO-service (`async_mode='threading'`) draait de
   pijplijn in een thread. → Los Anubis op in een **apart subprocess**
   (`omv_anubis_worker.py`), niet in-process.
2. **Headers (de gemeenste).** Stuur naar de OMV-host **alléén een schone
   Chrome-headerset** (`BROWSER_HEADERS` + `Content-Type`, geforceerde `User-Agent`).
   De eigen `Host`/`Origin`/`Referer` van de scraper lieten Anubis **opnieuw
   challengen — zelfs mét geldige auth-cookie**.
3. **`curl_cffi` doet SOCKS onbetrouwbaar** → voor de proxy-call `requests`+`pysocks`
   (SOCKS5h) gebruiken.

**Implementatie:** `v1/omv_http.py` (`wrap_curl_session` leest `OMV_PROXY` **per
request** + doet de Anubis-bootstrap/cookie-injectie); `v1/scraper.py` monkeypatcht
bovenaan `requests.get/post` zodat OMV-URLs door die gewrapte sessie lopen. Vereist
`pysocks` én de Playwright-browser (`playwright install chromium`). Repo:
`globaal-omv-pipeline`.

**Troubleshooting-volgorde bij `RetryError`:**
1. **Tunnel op?** `ss -tlnp | grep 1080` — leeg = de SSH-tunnel naar het thuiskastje
   ligt eruit (**dé #1-oorzaak**); herstart 'm.
2. **Proxy-test:** `curl -x socks5h://localhost:1080 https://omgevingsloketinzage.omgeving.vlaanderen.be/`
   → HTTP 200 = IP-blok omzeild. (HTML met "bot" = enkel Anubis nog, dat doet de code.)
3. **Playwright-browser aanwezig?** `ls ~/.cache/ms-playwright/` — leeg →
   `…/.venv/bin/python -m playwright install chromium`.
4. **Dropbox-token** kan los verlopen zijn (`invalid_access_token`) → raakt de
   downloader/merge-stap, niet de scraper.

> Dit is een **kwetsbare keten** (gratis residentiële tunnel + anti-bot dat kan
> wijzigen). Aanrader: een healthcheck + auto-herstart op de SSH-tunnel — dat is nu
> het enige single-point-of-failure van de scraper.

---

## 6A. Factuurrouter — AI-factuurrouteringsagent

**Factuurrouter** (URL `factuurrouter.globaal.be`; voorheen "Remy" — die werknaam
is overal verwijderd) is een AI-agent die gescande facturen uit de mailbox
`scanfacturen@gmail.com` leest, de firma herkent en automatisch naar de juiste
boekhouding-mailbox routeert. Draait **op de host** onder `~/factuurrouter` (net
als OMV, niet in de stack). De oude URL `remy.globaal.be` stuurt met een 301 door.

### 6A.1 Werking
- **Watcher** (`factuurrouter.service`): pollt elke 20 s de inbox op nieuwe
  PDF-facturen, doet OCR (poppler + tesseract nld/eng), laat **OpenAI `gpt-5-mini`**
  de firma + bestemming bepalen, en schrijft het resultaat naar `~/factuurrouter/output/`.
- **Review-dashboard** (`factuurrouter-dashboard.service`, poort 8787): toont de
  **geblokkeerde** facturen (twijfel/conflict) voor manuele beoordeling, met
  knoppen om door te sturen, geblokkeerd te houden of naar de prullenbak te
  verplaatsen — plus een log van automatisch verzonden mails.
- Een factuur is **"uitgevoerd"** (gerouteerd) of **"geblokkeerd"** (mens nodig).
  Geblokkeerde items handel je af in het dashboard; *gerouteerde* items worden
  alleen écht verstuurd als `auto_send_ai_approved` aanstaat (zie 6A.4).

### 6A.2 Gmail-toegang via de officiële Google API (geen `gog` meer)
Oorspronkelijk gebruikte de agent de externe CLI **`gog`** (van openclaw — géén
Google-product). Die is **volledig vervangen** door Google's eigen Gmail API in
`~/factuurrouter/src/gmail_api.py` (libraries `google-api-python-client`, `google-auth`,
`google-auth-oauthlib`).
- **Authenticatie:** OAuth. Het **token** staat in `~/credentials/gmail_token.json`
  (scopes `gmail.modify` + `gmail.send`), de **client-secret** in
  `~/credentials/gog_client_secret.json`. Google Cloud-project
  `quiet-pagoda-490411-b0`, consent-scherm op **"In production"** (anders verloopt
  het token na 7 dagen).
- **De server logt zelf nooit in op Google.** Het token is **eenmalig op een
  laptop** aangemaakt met `~/factuurrouter/authorize_gmail.py` (browser-consent op
  `scanfacturen@gmail.com`) en naar de server gekopieerd; het ververst zichzelf.

### 6A.3 Systemd-services + SSO-koppeling
- **`factuurrouter.service`** (watcher) en **`factuurrouter-dashboard.service`**
  (dashboard, `--host 0.0.0.0 --port 8787`), beide `User=ubuntu`. Het token-pad
  staat als `Environment=GMAIL_TOKEN_PATH=…` in de units; `OPENAI_API_KEY` leest
  de agent uit `~/factuurrouter/.env`.
- **Nginx:** server-blok `factuurrouter.globaal.be` in `30-apps.conf.template` met
  forward auth; upstream **`http://172.17.0.1:8787`** (host-gateway-IP, zoals OMV).
  Een extra blok stuurt `remy.globaal.be` met een 301 door naar de nieuwe URL.
- **ufw:** `sudo ufw allow 8787/tcp` was nodig zodat de nginx-container de host op
  8787 mag bereiken (zie §9.12). Extern blijft 8787 dicht via de AWS-security-group.
- **Authentik:** proxy-provider `factuurrouter-proxy` + applicatie
  **"Factuurrouter"** (slug `factuurrouter`) + groep **`factuurrouter`**, toegewezen
  aan de embedded outpost. Toegang (as-built): akadmin + Mehdi. *(Bij het hernoemen
  van `external_host` via de ORM moet je `provider.set_oauth_defaults()` draaien,
  anders blijven de OAuth-`redirect_uris` op de oude host staan — zie §9.14.)*
- DNS: gedekt door de bestaande wildcard `*.globaal.be` — geen apart record nodig.

### 6A.4 auto_send (de go-live-schakelaar)
`~/factuurrouter/config/settings.json` → **`auto_send_ai_approved`** staat bewust op
**`false`** (dry-run): de agent classificeert en vult de wachtrij, maar verstuurt
niets automatisch. Pas na controle in het dashboard op `true` zetten voor échte
auto-forward. (De `forwarded_message_ids.json`-lijst voorkomt dat eerder
verzonden mails opnieuw worden verstuurd.)

### 6A.5 Robuustheid & data
- **Wachtrij is cumulatief** (`write_run_outputs(..., append_latest=True)`): het
  dashboard reset niet meer naar nul bij een run/herstart; items verdwijnen pas
  als ze in het dashboard afgehandeld zijn.
- **Verzonden-log** `output/reports/auto_forward_log.jsonl` is *append-only*.
- **Dashboard gehard:** Gmail-service wordt *lazy* opgebouwd (kijken werkt ook bij
  stukke auth) en alle JSON-reads zijn defensief (corrupt/half-geschreven bestand
  laat de pagina niet 500'en); knop-acties zitten in `try/except`.
- **Alle state in `~/factuurrouter/output/`** (wachtrij, review-state, logs, PDF's).
  ⚠️ **Nog géén back-up** — dit is het grootste openstaande risico.
- Hulpscripts: `mehdi-all-access.py`, `fix_pdfs.py` (ontbrekende PDF's opnieuw uit
  Gmail halen), `prune_ghosts.py`. De code staat in git (repo `globaal-factuurrouter`).

### 6A.6 Valkuilen (uit de migratie van de oude machine)
- De **gedownloade PDF's kwamen niet mee** (alleen metadata) → opnieuw uit Gmail
  gehaald met `fix_pdfs.py`. Enkele oude mails waren **permanent uit Gmail
  verwijderd** (prullenbak na 30 dagen automatisch geleegd) → opgeschoond met
  `prune_ghosts.py`.
- `mehdi-all-access.py` matchte eerst op e-mail, maar `akadmin` heeft hetzelfde
  e-mailadres (`mch@h-architects.be`) en `mehdi` heeft er geen → **match op
  username**, niet op e-mail.

---

## 6B. Stagebeoordeling — stagiaire-beoordelingsdashboard

**Stagebeoordeling** (`stage.globaal.be`) is een webdashboard om stagiaires te
scoren op 5 criteria (1–5) plus interesse, aanbevolen afdeling, eindoordeel en
notities. **Centrale opslag**: iedereen ziet dezelfde data. Draait **op de host**
onder `~/stagebeoordeling`.

### 6B.1 Opzet (bewust simpel)
- **Eén Python-bestand** `server.py` op **pure standaardbibliotheek**
  (`http.server` + `sqlite3`) — géén pip-dependencies, geen venv. Serveert
  `index.html` + een kleine JSON-API.
- **Opslag:** SQLite-bestand `~/stagebeoordeling/stagebeoordeling.db` (tabel
  `evaluations`: één rij per stagiair met een JSON-blob + `updated_by`/`updated_at`).
  Dit is de centrale bron van waarheid → identieke data voor elke bezoeker.
- **Frontend:** `index.html` laadt via `GET /api/data` en slaat wijzigingen direct
  op via `POST /api/save`; alleen-lezen kijkers verversen elke 20 s automatisch.
- **Systemd:** `stagebeoordeling.service` (`User=ubuntu`,
  `ExecStart=/usr/bin/python3 …/server.py`, `STAGE_PORT=8088`).

### 6B.2 Toegang — lezen vs. bewerken (zoals Schuldentracker)
- **Alleen `Raisha` mag beoordelen** (schrijven); iedereen anders is **alleen-lezen**.
- Twee Authentik-groepen: **`stagebeoordeling`** (toegang/zien — hier bindt de app
  aan) en **`stagebeoordeling-bewerken`** (bewerkrechten — alleen Raisha).
- **Server-side afgedwongen:** een `POST /api/save` zonder de groep
  `stagebeoordeling-bewerken` krijgt **403**. De frontend leest `/api/me`,
  schakelt de invulvelden uit en toont een alleen-lezen-banner voor niet-bewerkers
  (dubbele laag). Identiteit komt uit de `X-authentik-username`/`-groups`-headers.
- Leden (as-built): `stagebeoordeling` = Raisha, akadmin, Mehdi (read-only);
  `stagebeoordeling-bewerken` = Raisha.

### 6B.3 Nginx / SSO
Server-blok `stage.globaal.be` in `30-apps.conf.template` (forward auth), upstream
`http://172.17.0.1:8088`; `sudo ufw allow 8088/tcp` (zie §9.12). Authentik-app
"Stagebeoordeling" (slug `stage`) via `scripts/add-stage-app.py`. DNS via de
wildcard `*.globaal.be`. ⚠️ **De SQLite-DB hoort in de back-uproutine.**

---

## 6C. Schuldentracker — schuldendossier-tracker

**Schuldentracker** (`schuldentracker.globaal.be`) volgt een portefeuille
**schuldendossiers** (deurwaarders/schuldeisers) over meerdere Belgische firma's;
het vervangt een Excel-deurwaarderstracker. Draait **op de host** als Flask-app
(systemd-service `schuldentracker`, `FINANCE_HOST=0.0.0.0`, `FINANCE_PORT=5050`).

### 6C.1 Werking
- **Flask + SQLite** (stdlib `sqlite3`), server-rendered Jinja + inline SVG-charts,
  geen frontend-framework/buildstap. Eén groot `app.py` + `db.py` (schema +
  idempotente migraties) + `importers.py` (imports/matching) + `letter_extraction.py`
  (OpenAI).
- **Databronnen:** (a) een Excel-**werkmap** (dossiers), (b) **KBC-bankafschriften**
  (CSV + getekende betaalopdracht-PDF's) met automatische matching op
  referentie/IBAN, (c) **schuldeiserbrieven** die **OpenAI `gpt-5-mini`** naar
  gestructureerde JSON ontleedt (review vóór toepassen). Een reductiepad-grafiek
  toont of men op schema ligt om schuldenvrij te worden.
- **Per-firma scope** via `ALLOWED_COMPANY_PREFIXES` in `importers.py`.

### 6C.2 Data & secrets (gevoelig — financieel)
- **`data/finance.db`** (SQLite) = álle dossier-/betaaldata → **blijft VM-only**,
  nooit in git. ⚠️ **Back-up ontbreekt nog** — net als bij de andere apps het
  grootste risico.
- **`.env`**: `OPENAI_API_KEY` (+ `OPENAI_LETTER_MODEL=gpt-5-mini`,
  `FINANCE_HOST/PORT`, optioneel `FINANCE_WORKBOOK_PATH`). **`data/.secret_key`** =
  de Flask-sessiesleutel (gepersisteerd zodat sessies een herstart overleven).
- De **Excel-werkmap** met echte schulddata staat buiten de app-map en wordt
  read-only ingelezen.

### 6C.3 Auth — eigen login + SSO-shim, lezen vs. bewerken
- De app heeft een **eigen login + 2FA** (`auth.py`, `pyotp`/`qrcode`), maar achter
  AppPortal draait hij met **`AUTH_MODE=sso`**: de shim `sso_auth.py` leest
  `X-authentik-username`, zoekt de bijhorende DB-gebruiker
  (`auth.get_user_by_username`) en logt die in zonder de eigen login/2FA.
- **Lezen vs. bewerken** (zoals Stagebeoordeling): `can_edit` = lidmaatschap van de
  groep **`schuldentracker-bewerken`**. Niet-bewerkers krijgen **403** op elke
  schrijf-methode (POST/PUT/PATCH/DELETE); de UI verbergt de bewerkknoppen.

### 6C.4 Nginx / SSO / openstaand
- Nginx-blok `41-schuldentracker.conf.template` (forward auth), upstream
  `http://172.17.0.1:5050`; `sudo ufw allow 5050/tcp`. Authentik: proxy-provider +
  app + groepen **`schuldentracker`** (zien: akadmin, Angela, Mehdi) en
  **`schuldentracker-bewerken`** (bewerken: **alleen Angela**). DNS via de wildcard.
- **Nog open:** (a) back-up van `data/finance.db`, (b) in git/CI/auto-deploy brengen
  (repo `globaal-schuldentracker`), (c) **de OpenAI-key in `.env` roteren** (stond in
  platte tekst, ook in de OneDrive-kopie).

---

## 6D. Telefoonregister — centraal telefoonnummer-register

**Telefoonregister** (`telefoonregister.globaal.be`) is de centrale **single source
of truth** voor alle telefoonnummers van de bedrijvengroep (België & Suriname):
een database-app met live sync die meerdere collega's tegelijk gebruiken en
bijwerken. De Excel is enkel de startdata; de waarheid leeft in de database.
**Draait — anders dan de meeste host-apps — als container ín de stack**
(`app-telefoonregister`, intern poort 3006), gedefinieerd in
`docker-compose.override.yml`. Repo: `softwareglobaal/telefoonregister`.

### 6D.1 Werking
- **Node.js** (**Express** + **Knex**), standaard **SQLite** (`better-sqlite3`);
  kan zonder codewijziging naar PostgreSQL (Knex is db-agnostisch). Data in het
  Docker-volume `appportal_telefoonregister-data` (`/app/data`).
- **Voorkant**: lijst met 4 velden (Telefoonnummer, Toegewezen aan, Functie,
  Status); detail achter de klik. **Live sync** via Server-Sent Events —
  wijzigingen verschijnen vrijwel meteen bij iedereen.
- **Datamodel**: `numbers` (voor- en achterkantvelden), `secrets` (afgeschermd:
  kaartnummer, PIN/PUK — 1-op-1 bij een nummer), `lists` (bewerkbare
  dropdown-waarden). Status Actief/Niet-actief/Onbekend (niet-actief behoudt
  historiek, verwijdert niets).
- **Excel-export** (`GET /api/export`) met dezelfde structuur als de import —
  geen vendor-lock-in. Eenmalige seed-import uit `seed/…import.xlsx` bij een lege
  tabel (herstart dupliceert niets).

### 6D.2 Auth — lezen vs. bewerken
- **Geen eigen login.** De app leest de gebruiker uit de forward-auth-header
  (`X-Authentik-Username`, met fallbacks). Iedereen die de proxy passeert mag
  **lezen**; **schrijven** is beperkt tot de groep **`telefoonregister-editors`**
  (commit "Schrijfrechten beperken tot editors-groep"). Hetzelfde lezen/bewerken-
  patroon als Schuldentracker/Stagebeoordeling.
- Twee Authentik-groepen: **`telefoonregister`** (zien) en
  **`telefoonregister-editors`** (bewerken).

### 6D.3 Nginx / SSO / data
- Nginx-blok `35-telefoonregister.conf.template` (forward auth), upstream
  `http://app-telefoonregister:3006` — **in-netwerk, géén host-gateway-IP**, want
  het is een container in de stack. Authentik proxy-provider + app
  **"Telefoonregister"**. DNS via de wildcard.
- ⚠️ De SQLite in het volume `appportal_telefoonregister-data` hoort in de
  back-uproutine.

---

## 6E. CHAOS Taskforce — UNABO-werkstroomdashboard

**CHAOS Taskforce** (`chaos.globaal.be`) is een intern dashboard voor de
**UNABO-werkstroom**: een **Planning**-tab (juridische harmonisatie + facturatie;
taken met eigenaar/status/deadline, tijdlijn en voortgang) en een **Openstaande
facturen**-tab (tellers, matrix per firma/type, aging-overzicht, sorteerbare
tabel). Iedereen werkt op dezelfde gedeelde versie; wijzigingen syncen
automatisch (~30 s). Draait **op de host** onder `~/chaos` (systemd
`chaos.service`, poort 8095). Repo: `softwareglobaal/chaos-taskforce`
(**privé** — bevat klant-persoonsgegevens).

### 6E.1 Opzet (bewust simpel)
- **Eén `server.py`** op pure standaardbibliotheek (geen dependencies, geen venv)
  + **één `index.html`** (volledig dashboard, geen buildstap).
- **Gedeelde opslag** `data/state.json` (live planning-data) — **gitignored**,
  hoort niet in git. De factuurgegevens zitten in het dashboard ingebakken; een
  nieuwe maandexport laad je per browser in ("Excel opnieuw inladen", lokaal).
- **Eigen sync-mechanisme** (`server-sync.sh`/`auto-push.sh`) i.p.v. de standaard
  `deploy-<app>.sh`-cron: automatische pull vanaf GitHub naar de server.
- Auth: forward auth, groep **`chaos`**. ⚠️ Repo privé houden; GitHub Pages uit
  (persoonsgegevens). Back-up van `data/state.json` is wenselijk.

---

## 6F. Beschikbaarheid Mehdi (agenda) — Google-Calendar-beschikbaarheid

**Beschikbaarheid Mehdi** (`agenda.globaal.be`) is een **read-only** dashboard dat
meerdere Google Calendars van Mehdi samenvoegt tot één beschikbaarheidsoverzicht
(dag/week), zodat collega's zien wanneer hij vrij of bezet is. Draait **op de
host** onder `~/globaal-calendar-mehdi` (Flask, systemd `agenda.service`, poort
5060). Repo: `softwareglobaal/globaal-calendar-mehdi`; in CI/CD via
`deploy-agenda.sh` (met `pip install` bij wijzigingen).

### 6F.1 Werking & auth
- **Flask** + **Google Calendar API** (read-only, OAuth-refresh-token, eenmalig
  consent via `get_refresh_token.py`). `calendar_service.py` merget de kalenders
  naar vrij/bezet met cache.
- **Geen eigen login** — identiteit uit de `X-authentik-*`-headers (`sso_auth.py`).
- **Toegang per kalender** via `calendars.yaml` (`full_detail_groups`): wie in zo'n
  groep zit ziet **details** (titel/locatie), anders enkel een **"Bezet"**-blok.
  Drie Authentik-groepen: **`agenda-bekijken`** (toegang/tegel-rol),
  **`agenda-volledig`** (ziet overal details — Mehdi), **`agenda-architect`**
  (optioneel, details van specifieke architect-kalenders; route `/calendars`).
- Secrets in `.env` (Google client-id/secret + refresh-token) — VM-only.

---

## 6G. RenoVision AI — analyse van bouwtekeningen

**RenoVision AI** (`renovision.globaal.be`) is een **AI-platform voor het
analyseren van architecturale tekeningpakketten** (PDF/DWG/DXF) bij renovatie-,
uitbreidings- en vergunningsprojecten. Het classificeert tekeningpagina's
(Bestaande/Nieuwe/Vergunde toestand; plannen, snedes, geveltekeningen), vergelijkt
toestanden, detecteert wijzigingen (toegevoegde/verwijderde ruimtes, muur-/dak-/
trapaanpassingen, uitbreidingen) en genereert gestructureerde rapporten.
Combineert computer vision, OCR en **AI-vision-modellen (Claude/OpenAI)**;
meertalig (NL/FR/EN/DE). Repo: `softwareglobaal/globaal-renovision`.

### 6G.1 Opzet & twee instanties
- **Stack**: frontend (yarn/React) + backend + **MongoDB**, als **eigen
  docker-compose** op de host onder `~/globaal-renovision` (containers
  `renovision-web`/`-backend`/`-mongo`). **Auto-deploy**: de VM pollt `origin/main`
  en herbouwt de containers bij wijziging.
- **Twee geïsoleerde instanties**:
  - **renovision** — de gedeelde instantie, poort 8100, groepen **`renovision`**
    (zien) + **`renovision-bewerken`**.
  - **renovision-mehdi** — een aparte **sandbox** voor Mehdi,
    `~/globaal-renovision-mehdi`, poort 8101, groepen **`renovision-mehdi`**
    (+`-bewerken`); image-namen per compose-project ge-namespaced zodat de twee
    elkaar niet raken.
- Nginx-blokken in `30-apps.conf.template` met **`client_max_body_size 200m`**
  (grote tekening-uploads). Forward auth; aparte Authentik proxy-providers
  `renovision-proxy` en `renovision-mehdi-proxy`.

---

## 7. Configuratie & scripts

| Bestand/map | Functie |
|---|---|
| `.env` | alle secrets + `BASE_DOMAIN`, `OMV_UPSTREAM`, `CERTGEN_DISABLE` (gitignored) |
| `.env.production` | sjabloon voor de VM (BASE_DOMAIN=globaal.be) |
| `apps.yaml` | app-catalogus + rol-mapping voor de tegels (omv, schuldentracker, chaos, agenda, telefoonregister) |
| `docker-compose.yml` | de hele stack |
| `docker-compose.override.yml` | extra in-stack service `app-telefoonregister` + volume (zie §6D) |
| `nginx/templates/*.template` | nginx-serverblokken (envsubst met `${BASE_DOMAIN}`) |
| `nginx/snippets/forward-auth.conf` | het forward-auth-blok (gedeeld door de apps) |
| `nginx/templates/40-n8n.conf.template` | n8n-doorsturing (VM-specifiek) |
| `scripts/configure-authentik.sh` | groepen, OIDC, proxy-providers, TOTP, sessies |
| `scripts/setup-authentik.py` | de daadwerkelijke Authentik-config (via `ak shell`) |
| `scripts/add-omv-app.py` | registreert de OMV-provider apart |
| `scripts/add-*-app.py` | per-app Authentik-registratie (o.a. `add-kosten-app.py`, `add-agenda-app.py`, `add-stage-app.py`, `add-schuldentracker.py`, `add-monitoring.py`) |
| `scripts/fix-domains.py` | corrigeert providers/redirect/host naar het echte domein (zie §9.6) |
| `scripts/ak-exec.sh` | helper om een python-bestand in de authentik-container te draaien |
| `vm/omv.service` | het systemd-servicebestand voor OMV |

---

## 8. Hoe het gedeployed is (samenvatting)

Volledige draaiboeken: [DEPLOY-AWS.md](DEPLOY-AWS.md) en [vm/CUTOVER.md](vm/CUTOVER.md).
Kort, in volgorde:

1. **OMV als service** opzetten op de host (`omv.service` + shim + symlink).
2. **Project** naar de VM (`~/appportal`), `.env` uit `.env.production`, secrets
   genereren.
3. **Images bouwen + opwarmen** (`docker compose build`, `up -d`) terwijl de
   host-nginx OMV/n8n nog bediende.
4. **Authentik configureren** (`configure-authentik.sh` + `add-omv-app.py`),
   OIDC-credentials in `.env`, portal herstarten.
5. **DNS in Cloudflare:** wildcard A → VM (DNS-only), AAAA-wildcard verwijderd.
6. **n8n** aan `appnet` koppelen + `40-n8n.conf.template` toevoegen.
7. **Cutover:** host-nginx stoppen + disablen, `docker compose up -d` (AppPortal's
   nginx pakt 80/443).

### 8.4 Rollback
Gaat er iets mis met de cutover:
```bash
docker compose stop nginx
sudo systemctl enable --now nginx     # de oude host-nginx terug
```

### Certificaat-status — Let's Encrypt wildcard
De stack draait op een **Let's Encrypt wildcard-certificaat** `*.globaal.be`
(+ `globaal.be`) dat **álle** app-subdomeinen dekt, ook toekomstige — bij een
nieuwe app hoef je dus niets aan DNS of certificaten te doen.

- **Validatie via DNS-01** (de enige methode voor een wildcard), met de
  **Cloudflare-DNS-plugin** van certbot. Een *scoped* Cloudflare API-token
  (`Zone:DNS:Edit` op `globaal.be`) staat in `/etc/letsencrypt/cloudflare.ini`
  (chmod 600). De DNS-records blijven **DNS-only** — Cloudflare zit niet in het
  verkeer, doet enkel de validatie.
- **Plaatsing:** certbot's `fullchain.pem`/`privkey.pem` worden naar
  `~/appportal/certs/` gekopieerd (de map die nginx mount); **`CERTGEN_DISABLE=1`**
  zodat het oude zelf-ondertekende cert niet terugkomt; en de
  `REQUESTS_CA_BUNDLE`-regel is uit de `portal`-service gehaald (die vertrouwt het
  echte cert nu via de systeem-CA's — anders breekt de interne OIDC-call naar auth).
- **Auto-vernieuwing:** de certbot systemd-timer verlengt automatisch (~elke 60
  dagen); de deploy-hook `/etc/letsencrypt/renewal-hooks/deploy/appportal.sh`
  kopieert het verlengde cert naar `~/appportal/certs/` en herlaadt nginx. Test:
  `sudo certbot renew --dry-run`.

---

## 9. Troubleshooting-logboek (echte problemen + oplossingen)

Dit zijn de problemen die we tijdens bouw en deploy zijn tegengekomen, met de
oplossing. Bewaard zodat ze niet opnieuw uitgezocht hoeven te worden.

**9.1 Stub-image build-race** — vier app-services bouwden tegelijk dezelfde
image → "image already exists". *Fix:* één service bouwt de image, de andere
gebruiken `image:` + `pull_policy: never`.

**9.2 Authentik te vroeg "unhealthy"** — eerste boot doet DB-migraties (paar
minuten). *Fix:* `start_period: 300s` op de healthcheck.

**9.3 nginx 502 na herstart** — nginx cachete container-IP's. *Fix:* variabele
`proxy_pass $var` + `resolver 127.0.0.11` zodat namen per aanvraag opnieuw
worden opgezocht.

**9.4 Schijf vol op de VM** — Authentik-image (~1,5 GB) paste niet ("no space
left on device"). *Fix:* EBS-volume vergroot naar 40 GB, daarna
`sudo growpart /dev/nvme0n1 1` + `sudo resize2fs /dev/nvme0n1p1`.

**9.5 DNS: Cloudflare-wildcard + IPv6-val** — `portal.globaal.be` loste op naar
Cloudflare i.p.v. de VM. Oorzaak: het domein draait op **Cloudflare**, de
wildcard stond **Proxied** naar one.com, en er was een **`AAAA *`-wildcard**
(IPv6 wint van IPv4). *Fix:* in Cloudflare de wildcard-`A` → `54.80.98.233` op
**DNS only**, en de wildcard-`AAAA` **verwijderd**.

**9.6 Forward auth gaf 404 → nginx 500** — de outpost kende de apps als
`*.localhost` i.p.v. `*.globaal.be`. Oorzaak: de Authentik-container had
`BASE_DOMAIN` niet in z'n omgeving, dus de config-scripts vielen terug op
`localhost`. *Fix:* `BASE_DOMAIN` toegevoegd aan de `authentik-server`/`-worker`
environment, en `scripts/fix-domains.py` gedraaid om de bestaande
`external_host`, de portal-redirect-URI en `authentik_host` te corrigeren.

**9.7 nginx bond 80/443 niet** — na het "opwarmen" (toen de host-nginx de
poorten nog had) bleef de poort-koppeling kapot. *Fix:*
`docker compose up -d --force-recreate nginx`.

**9.8 OMV-service crashte: "Missing FLASK_SECRET_KEY"** — de app leest `.env`
naast `app.py` (`v1/.env`), maar de echte `.env` staat in de projectroot;
`systemd`'s `EnvironmentFile` weigerde bovendien de `OPENAI_API_KEY`-regel.
*Fix:* `EnvironmentFile` weggelaten en een **symlink** `v1/.env → ../.env` gemaakt
zodat de app z'n secrets zelf inleest.

**9.8b OMV-service: "Werkzeug not designed for production"** — nieuwere
flask-socketio weigert de dev-server. *Fix:* `allow_unsafe_werkzeug=True`
toegevoegd aan de `socketio.run(...)`-regel (acceptabel voor een intern dashboard).

**9.9 OMV gaf 502 via de portal** — nginx kon `host.docker.internal` niet
opzoeken (die naam staat in `/etc/hosts`, niet in de Docker-DNS die de resolver
gebruikt). *Fix:* `OMV_UPSTREAM` op het **host-gateway-IP** gezet
(`http://172.17.0.1:5000`, het docker0-IP dat de nginx-container voor de host
ziet) i.p.v. de hostnaam. Dit is hetzelfde host-gateway-IP dat álle host-apps
gebruiken (Factuurrouter 8787, Stage 8088, Schuldentracker 5050, Kosten 8090,
CHAOS 8095, Agenda 5060, RenoVision 8100/8101).

**9.10 AWS-VM kan z'n eigen publieke IP niet bereiken** — `curl` vanaf de VM naar
`https://portal.globaal.be` faalde, terwijl het van buitenaf wél werkt. Dit is
een AWS-eigenaardigheid (geen hairpin naar het eigen publieke IP). *Test* daarom
met `--resolve <host>:443:127.0.0.1` of gewoon vanuit een externe browser.

**9.11 Portal toonde "No applications are assigned to your role"** — de
ingelogde gebruiker (`akadmin`) zat in geen van de groepen `admin`/`manager`.
*Fix:* gebruiker aan een groep toevoegen en **opnieuw inloggen** (de groepen
zitten in het login-token).

**9.12 Host-app achter nginx gaf 504 (Factuurrouter)** — de nginx-container kon de
host-app op `172.17.0.1:8787` niet bereiken: de app bond op `127.0.0.1` én ufw
liet poort 8787 niet door. *Fix:* de app op **`0.0.0.0`** laten binden **en**
`sudo ufw allow 8787/tcp` (zoals 5000 voor OMV). Extern blijft de poort dicht via
de AWS-security-group. Dezelfde twee stappen gelden voor élke nieuwe host-app
achter de portal.

**9.13 Oude per-host certbot-certs blokkeerden de renewal** — `certbot renew`
faalde op `data.globaal.be` en `n8n.globaal.be` met `bind() to 0.0.0.0:443 failed
(Address already in use)`. Oorzaak: dat zijn **legacy-certs van vóór de cutover**,
aangemaakt met certbot's **nginx-/standalone-methode** die bij elke verlenging
poort 80/443 wil overnemen — maar die poorten zijn nu permanent van de Docker-nginx.
Beide certs zijn bovendien overbodig (`data.globaal.be` heeft geen nginx-blok meer;
`n8n.globaal.be` wordt gedekt door het wildcard). *Fix:* eerst verifiëren dat de
draaiende nginx ze niet gebruikt (`grep -rn ssl_certificate ~/appportal/nginx/`
toont alleen het wildcard in `/etc/nginx/certs/`, en `systemctl is-active nginx` =
inactive), daarna de twee legacy-certs verwijderen met
`sudo certbot delete --cert-name <naam>`. Daarna verwerkt `certbot renew` alleen
nog het wildcard (DNS-01 — geen poorten nodig).

**9.14 Proxy-provider hernoemd → "Redirect URI Error"** — bij het hernoemen van een
app (Remy → Factuurrouter) is de `external_host` van de proxy-provider via de
Django-ORM (`ak shell`) aangepast. Daarna gaf de app **"Redirect URI Error
(redirect_uri)"**: een kale `.save()` regenereert de OAuth-`redirect_uris` niet (dat
doet normaal de API-laag), dus die wezen nog naar de oude host. *Fix:* in `ak shell`
`p.set_oauth_defaults(); p.save()` op de provider, daarna `docker compose restart
authentik-server` zodat de embedded outpost de nieuwe host oppikt.

Overige ingebouwde fixes: wildcard-certificaten matchen geen single-label
domeinen → expliciete SAN's per host; `certgen` overschreef echte certs →
`CERTGEN_DISABLE=1` in productie; single logout → globale invalidation-flow;
ORM-aangemaakte OIDC-provider had lege grant types/scope-mappings → expliciet
gezet.

---

## 10. Beveiliging

- **Authenticatie** ligt volledig bij Authentik (wachtwoorden, TOTP, sessies).
- **Forward auth** vertrouwt `X-authentik-*`-headers; dit is alleen veilig omdat
  de apps **uitsluitend via nginx** bereikbaar zijn (nginx overschrijft
  client-headers met die van de outpost). De OMV-app op `:5000` is extern
  geblokkeerd door de AWS-security-group (alleen 22/80/443 open).
- **Single logout** via de globale invalidation-flow.
- **Cookies** Secure + HttpOnly; HTTP → HTTPS-redirect.
- **Secrets** staan momenteel **hardcoded in `.env`-bestanden** (bewuste keuze
  voor nu — zie §11). Op termijn naar een secrets-manager (aanbeveling: AWS SSM
  Parameter Store voor weinig onderhoud, of zelf-gehost Infisical).
- **Let op:** `/home/ubuntu/omv_pipeline/.env` bevat live secrets (Dropbox,
  OpenAI, TOTP). Rouleren/verplaatsen aanbevolen.

---

## 11. Onderhoud

- **Logs:** `docker compose logs -f <service>`; portal-events in
  `logs/portal/portal.log`; OMV via `journalctl -u omv`.
- **Herstarten:** `docker compose up -d` (stack) / `sudo systemctl restart omv`.
- **Updaten:** image-tag in `docker-compose.yml` aanpassen, dan
  `docker compose pull && docker compose up -d`.
- **Back-up** (belangrijkste — bevat gebruikers, groepen, 2FA):
  ```bash
  docker run --rm -v appportal_postgres-data:/data -v $PWD:/backup alpine \
    tar czf /backup/postgres-backup-$(date +%F).tar.gz -C /data .
  ```
- **Certificaten:** Let's Encrypt wildcard `*.globaal.be` via certbot +
  **Cloudflare-DNS-01**. Verlengt automatisch (systemd-timer); de deploy-hook
  `/etc/letsencrypt/renewal-hooks/deploy/appportal.sh` kopieert het cert naar
  `~/appportal/certs/` en herlaadt nginx. Handmatig testen: `sudo certbot renew
  --dry-run`. Token: `/etc/letsencrypt/cloudflare.ini`. Zie §8.
- **Een app toevoegen:** README.md §3 (compose-service, nginx-blok, `apps.yaml`,
  Authentik-provider). Met de wildcard-DNS hoeft er geen DNS-record bij.

---

## 12. Toegangsmodel & openstaande punten

### 12.1 Toegangsmodel — één groep per applicatie
Toegang is **per applicatie**, niet per afdeling. Voor elke app bestaat een
eigen Authentik-groep; een gebruiker zit in de groepen voor de apps die hij mag
gebruiken. Zo kan iemand wel bij app X maar niet bij app Y, ongeacht z'n
afdeling. (Voorbeeld: Siyan zit organisatorisch bij management, maar niet in de
groep `schuldentracker`, dus ziet die app niet.)

| Groep | Geeft toegang tot | Leden (as-built 2026-06-26) |
|---|---|---|
| `schuldentracker` / `-bewerken` | Schuldentracker (zien / bewerken) | akadmin, Angela, Mehdi · **bewerken: alleen Angela** |
| `factuurrouter` | Factuurrouter | akadmin, Mehdi |
| `kosten` | Kosten-dashboard | akadmin, Angela, Mehdi |
| `stagebeoordeling` / `-bewerken` | Stagebeoordeling (zien / bewerken) | akadmin, Mehdi, Raisha · **bewerken: alleen Raisha** |
| `telefoonregister` / `-editors` | Telefoonregister (zien / bewerken) | akadmin, Angela, Mehdi, Siyan · **bewerken: akadmin, Siyan** |
| `chaos` | CHAOS Taskforce | Angela, Mehdi, Siyan |
| `agenda-bekijken` / `-volledig` / `-architect` | Beschikbaarheid Mehdi (toegang / details overal / architect-kalenders) | bekijken: Angela, Matthew, Mehdi, Siyan · volledig: Angela, Mehdi, Siyan · architect: — |
| `renovision` / `-bewerken` | RenoVision (gedeeld) | akadmin, Mehdi, Samad · **bewerken: akadmin, Samad** |
| `renovision-mehdi` / `-bewerken` | RenoVision (Mehdi-sandbox) | akadmin, Mehdi |
| `admin` *(optioneel)* | alle apps | beheerders |

> **OMV** gebruikt `admin`/`manager` (er is géén aparte `omv`-groep).
> **`status.globaal.be`** (Uptime Kuma) is gebonden aan **`admin`/`manager`**.
> De groep `manager` = akadmin, Mehdi. Er bestaat daarnaast een meta-groep
> **`toegangsbeheerders`** (lid: Siyan).

> **Patroon lezen vs. bewerken:** een app kan een tweede groep `<app>-bewerken`
> hebben. De app bindt aan de zien-groep; schrijfacties controleren server-side op
> lidmaatschap van de bewerken-groep (Schuldentracker, Stagebeoordeling).

`apps.yaml` bepaalt de **tegel-zichtbaarheid**; de Authentik group-bindings per
applicatie zijn de **handhaving**. Houd beide in sync.

### 12.2 Twee app-overzichten (ontwerpkeuze, open)
Er bestaan momenteel twee "applicaties"-pagina's: onze **eigen Flask-portal**
(`portal.globaal.be`, eenvoudig, custom) én **Authentik's ingebouwde launcher**
(`auth.globaal.be/if/user/`, gepolijst, onderhoudsvrij). De eigen portal is
gebouwd omdat de oorspronkelijke opdracht dat voorschreef. Op termijn één van de
twee kiezen (Authentik's launcher is de eenvoudigste, onderhoudsvrije optie).

### 12.3 Roadmap — geplande volgende stappen (in volgorde)
1. **Uptime Kuma** — ✅ **opgezet en live** op `status.globaal.be` achter SSO
   (container `uptime-kuma`, intern poort 3001, nginx-blok
   `42-status.conf.template`). De monitoring per app (OMV, Schuldentracker, n8n,
   portal, auth, …) verder uitbreiden/finetunen.
2. **Opruimstap — drift wegwerken + git.** ⏳ Grotendeels gedaan: de app-repo's
   staan op GitHub (org `softwareglobaal`) en de meeste apps deployen via
   `git pull`. **Nog open voor de appportal-stack zélf:** er is **geen
   `deploy-appportal.sh`-cron**, dus directe VM-edits aan `~/appportal` (nginx,
   `apps.yaml`, compose) vloeien niet automatisch terug naar git en kunnen
   ongemerkt afwijken. Houd `~/appportal` voortaan strikt via branch → PR → `main`
   in sync. *(Deze as-built is op 2026-06-26 bijgewerkt vanaf de drift-branch
   `vm-as-built-2026-06-26`, die de niet-gecommitte VM-config ving:
   kosten/status-nginxblokken, `remy`→`factuurrouter` 301-redirect, de
   telefoonregister-service en de chaos/agenda/renovision-blokken.)*

### 12.4 Overige openstaande punten
- **Factuurrouter:** ✅ gekoppeld — zie §6A. AI-factuurrouter op de host, achter
  SSO op `factuurrouter.globaal.be`, groep `factuurrouter`. `gog` vervangen door de
  officiële Gmail API, en de werknaam "Remy" is overal (code, map, services, URL,
  Authentik, repo `globaal-factuurrouter`) verwijderd. In git + CI/auto-deploy net
  als Stage/Kosten. **Nog open:** (a) `auto_send_ai_approved` op `true` zetten na
  controle (go-live), (b) **back-up van `~/factuurrouter/output/`**.
- **Stagebeoordeling:** ✅ gekoppeld — zie §6B. Stagiaire-beoordelingsdashboard op
  `stage.globaal.be`, centrale SQLite-opslag, Raisha bewerkt / rest leest. **Nog
  open:** SQLite-DB (`~/stagebeoordeling/stagebeoordeling.db`) in de back-uproutine
  opnemen.
- **Schuldentracker:** ✅ gekoppeld — **nu met eigen sectie §6C**. Flask-schulden-
  dossier-tracker op `schuldentracker.globaal.be` (systemd `schuldentracker`, poort
  5050), SSO-shim met lezen/bewerken (`schuldentracker`: akadmin/Angela/Mehdi /
  `schuldentracker-bewerken`: alleen Angela). **Nog open:** (a) back-up van
  `data/finance.db`, (b) in
  git/CI/auto-deploy brengen (`globaal-schuldentracker`), (c) **OpenAI-key in `.env`
  roteren** (stond in platte tekst).
- **Nieuwe apps gedocumenteerd (2026-06-26):** Telefoonregister (§6D), CHAOS
  Taskforce (§6E), Beschikbaarheid Mehdi/agenda (§6F) en RenoVision AI (§6G) zijn
  toegevoegd aan de as-built. **Nog open:** back-ups van hun data
  (Telefoonregister-volume, `chaos/data/state.json`, RenoVision-MongoDB) en — voor
  chaos/renovision — opname in het standaard `deploy-<app>.sh`-CI/CD-patroon (ze
  hebben nu een eigen sync-/rebuild-mechanisme).
- **Tegels opgeschoond (fase 8):** de 4 placeholder-apps zijn uit `apps.yaml`
  verwijderd en hun **Authentik-providers zijn intussen verwijderd**. De
  **stub-containers en hun nginx-blokken draaien nog** (onzichtbaar, zonder
  forward-auth-provider) — volledige opruiming (containers + nginx-blokken) staat
  nog open.
- **Certificaten:** ✅ **Let's Encrypt wildcard** `*.globaal.be` (DNS-01 via een
  Cloudflare API-token), automatische verlenging — geen browser-waarschuwing meer.
  Zie §8. Oude per-host certs (`data.globaal.be`, `n8n.globaal.be`) opgeruimd omdat
  hun renewal-methode botste met de Docker-nginx — zie §9.13. *(Optionele hardening:
  AWS-security-group beperken / cert-vervaldatum laten monitoren door Uptime Kuma.)*
- **OMV via de portal** — `OMV_UPSTREAM` op host-gateway-IP gezet (§9.9); de
  doorklik in de browser nog definitief te bevestigen.
- **Secrets-manager** uitgesteld — nu hardcoded `.env`.
- **`data.globaal.be`** wijst nog naar de VM maar heeft geen nginx-blok meer;
  desgewenst een redirect naar `omv.globaal.be`.
- **n8n nog zonder SSO** — werkt met z'n eigen login; kan later achter SSO.
- **cloudflared-tunnel + `ha-customgpt`-record** zijn ongebruikt en mogen weg.
- **`akadmin` in groep `manager`** was voor de test — vervangen door echte
  gebruikers in de juiste app-groepen, en `akadmin` daarna uit de app-groepen.

---

## 13. Git-fundament, CI/CD & self-service-AI

Dit hoofdstuk beschrijft hoe code voortaan beheerd en uitgerold wordt, en hoe
management apps zélf kan aanpassen zonder tussenkomst van de ontwikkelaar (de
"bottleneck" wegnemen). Dit is de opvolger van het ad-hoc kopiëren/scppen van
losse bestanden naar de VM.

### 13.1 Git als single source of truth
- **GitHub-organisatie:** `softwareglobaal`. Elke app is een eigen repo
  (`globaal-kosten`, `globaal-stagebeoordeling`, …). `main` = de **gepubliceerde**
  versie die op de VM draait; elke poging/aanpassing gebeurt in een **branch** →
  PR → `main`.
- **De VM is de bron van waarheid**, niet de Windows/OneDrive-map. Op de VM is
  elke app-map (`~/kosten`, `~/stagebeoordeling`, …) een git-repo met
  `origin git@github.com:softwareglobaal/<repo>.git`.
- **Eén SSH-sleutel op accountniveau** (`~/.ssh/github_softwareglobaal`, via
  `~/.ssh/config` voor `Host github.com`) geeft toegang tot álle repos van de org —
  een nieuwe repo werkt meteen, zonder per-repo deploy-key.
- **`.gitignore` per app sluit gevoelige data uit** en houdt die VM-only:
  bank-/financiële data (`statements/`, `*.csv`, `*.json`, gegenereerde
  `Software_overzicht.html`, `m365_*`), secrets (`.env*`, tokens, certs),
  `.venv/`, `__pycache__/`, `*.db`. **Financiële en persoonsdata komen nooit in
  GitHub.** (Let op: `.gitignore` ontkoppelt geen bestand dat al getrackt wordt —
  gebruik dan eenmalig `git rm -r --cached <pad>`.)
- **`CLAUDE.md` per repo** legt de spelregels vast voor wie de code bewerkt (raak
  secrets/data niet aan, houd de app werkend, wijzigingen via PR naar `main`).

### 13.2 Claude Code on the web (zelf code bewerken)
Management bewerkt apps via **claude.ai/code** (research preview; vereist een
Pro/Max/Team-seat). De koppeling loopt via de **GitHub-connector/-App** die per
repo toegang krijgt. Workflow: typ de wens in gewone taal in een tekstvak → Claude
maakt een **branch + Pull Request** met de wijziging → de PR wordt (zie §13.3)
gecontroleerd en gemerged → de VM rolt het uit. Geen technische kennis,
terminal of `git` nodig aan de kant van de gebruiker.

### 13.3 CI/CD — automatische check, merge & deploy
Doel: de handmatige stap "PR op GitHub goedkeuren + op de VM `git pull` doen"
wegnemen, zodat de lus van wens → live volledig automatisch verloopt.

**Stap 1 — Check + auto-merge (GitHub Action in de repo).** Bestand
`.github/workflows/ci.yml`, draait bij elke PR naar `main`:
- **Smoke-test** ("start de app nog op?"): `python -m py_compile server.py`,
  daarna de server kort opstarten en `curl` op `/` — vangt syntaxfouten én
  opstart-crashes.
- **Auto-merge bij groen:** `gh pr merge <nr> --squash --delete-branch` (met de
  ingebouwde `GITHUB_TOKEN`, `permissions: contents+pull-requests: write`).
  Faalt de check → de PR blijft open met een rood vinkje; niets wordt uitgerold.

**Stap 2 — Auto-deploy (pull-based op de VM).** Géén inbound toegang of
SSH-sleutel voor GitHub op de server. Een **cron-job** (elke 2 min) draait
`~/deploy-<app>.sh`: `git fetch`; als `main` voorligt → `git checkout -qf main` +
`git reset --hard origin/main` + `sudo /usr/bin/systemctl restart <app>.service`.
De `reset --hard` maakt de VM een exacte spiegel van `main` (raakt gitignored
data/secrets niet) en is bestand tegen een verkeerde branch-checkout. **Test
wijzigingen nooit in de live deploy-map** maar in een wegwerp-kloon. Een **scoped sudoers-regel**
(`/etc/sudoers.d/<app>-deploy`) geeft `ubuntu` enkel het recht díé ene service te
herstarten. Deploy-log: `~/deploy-<app>.log`.

> **Resultaat:** tekst in claude.ai/code → PR → check ✅ → auto-merge → binnen 2
> min live. **Risicogestuurd uitrollen:** laag-risico apps (Stagebeoordeling)
> mogen volledig automatisch; voor **financiële apps (Kosten)** blijft de check
> staan als poort. **Live via `deploy-<app>.sh`-cron (elke 2 min) op zes apps**
> (✅ end-to-end bevestigd): **Stagebeoordeling**, **Kosten**, **Factuurrouter**,
> **Schuldentracker**, **OMV** en **Agenda**. De smoke-test verschilt per app:
> Stage/Kosten starten de app op + `curl` (`/` resp. `/health`); Factuurrouter doet
> alleen `py_compile` (een echte start vereist Gmail-credentials, die niet in CI
> staan); Agenda draait extra `pip install` bij wijzigingen. **CHAOS** en
> **RenoVision** deployen via een **eigen mechanisme** (resp. `server-sync.sh`
> pull-sync en docker-rebuild-bij-pull), nog niet via het cron-patroon. De
> **appportal-stack zelf** heeft nog géén auto-deploy (zie §12.3).

**Geleerde valkuilen bij de opzet (Stagebeoordeling):**
- De `permissions:`-blok in `ci.yml` (`contents: write` + `pull-requests: write`)
  is nodig én voldoende: hij **overschrijft** de account-standaard, die voor
  persoonlijke repos op **read-only** staat. De UI-knop "Workflow permissions"
  (repo → Settings → Actions → General, helemaal onderaan) hoeft dus niet om.
- Een workflow draait **niet met terugwerkende kracht** op een al-open PR; hij
  moet eerst op `main` staan, daarna een **nieuwe** PR.
- Branch-protection is op een **gratis privé-repo niet beschikbaar** (vereist Pro)
  — geen blokkade, maar ook geen vangnet; de smoke-test-job is hier de poort.
- Auto-deploy = `~/deploy-<app>.sh` via cron (`*/2`) + sudoers-drop-in
  (`/etc/sudoers.d/<app>-deploy`) voor de wachtwoordloze restart; de deploy-log
  vult zich pas bij de eerstvolgende cron-run ná een merge.

### 13.4 Kosten-dashboard (software-uitgaven) — `kosten.globaal.be`
Interactief overzicht van software-/abonnementskosten uit **KBC/VISA
kredietkaart-afschriften**. Repo `globaal-kosten`, VM-map `~/kosten`, systemd
`kosten.service` op **poort 8090**, achter SSO (groep `kosten`: akadmin, Angela,
Mehdi). De **volledige pipeline draait server-side** ("alles op de
server"):
- `extract_cc.py` — PyMuPDF leest de PDF-afschriften in `statements/`, classificeert
  per firma/leverancier → `cc_transactions_clean.csv`.
- `recon.py` — reconciliatie (vorig saldo + Σ regels == afrekening) als bewijs dat
  elke transactie precies één keer geteld is.
- `build_dashboard.py` — genereert `Software_overzicht.html`.
- `server.py` — serveert het dashboard met een **"Ververs nu"-knop**; die POST
  `/ververs` draait `extract_cc.py` + `build_dashboard.py` opnieuw via subprocess
  (`sys.executable`) — geen laptop nodig. Padkeuze via env
  `CC_STATEMENTS_DIR` (default `./statements`).
- **Data blijft VM-only** (zie `.gitignore`, §13.1): de afschriften, CSV's en de
  gegenereerde HTML staan níét in GitHub.

### 13.5 HR-/urendashboard (DeskTime) — `hr.globaal.be` *(in opzet)*
Leesbaar urenoverzicht uit de **DeskTime-API**. VM-map `~/hr-dashboard`,
stdlib `http.server` + SQLite-cache, **poort 8089**. Periode-keuze loopt van de
16e (vorige maand) t/m de 15e (huidige). "Gewerkte tijd" = `desktimeTime` (keuze
gebruiker). De API-respons is **datum-genest** (`employees → "YYYY-MM-DD" → <id>`,
camelCase-velden `desktimeTime`/`atWorkTime`/`productiveTime`/`productivity`).
**Nog open:** achter SSO zetten (nginx-blok + Authentik-provider + groep `hr`) en
in git/CI onderbrengen. ⚠️ De eerder in chat geplakte DeskTime-API-sleutel zou
geregenereerd moeten worden.

### 13.6 Factuurrouter in git/CI — `globaal-factuurrouter`
De Factuurrouter (§6A) zit sinds de hernoeming ook in het fundament: repo
`globaal-factuurrouter` (privé), `~/factuurrouter` op de VM, twee services. De
`.gitignore` houdt secrets en factuur-state **VM-only**: `.env`, `gmail_token.json`,
`output/` (PDF's, logs) en `Transcripts/`. De smoke-test is bewust licht
(`py_compile`) omdat het dashboard Gmail-credentials nodig heeft om echt te starten;
de auto-deploy herstart **beide** services (`factuurrouter.service` +
`factuurrouter-dashboard.service`).

---

*Laatst bijgewerkt: 2026-06-26 — **as-built gesynchroniseerd met de live VM**.
Niet-gecommitte VM-config gevangen (kosten/status-nginxblokken,
`remy`→`factuurrouter` 301-redirect, telefoonregister-service,
chaos/agenda/renovision) en als git-bron verzoend. Vier nieuwe app-secties
toegevoegd: **§6D Telefoonregister**, **§6E CHAOS Taskforce**, **§6F
Beschikbaarheid Mehdi (agenda)** en **§6G RenoVision AI**. Tabellen §3.3–§3.5
(stack, mede-bewoners, hostname-routing), §4 (Authentik-providers/groepen) en
§12.1 (toegangsmodel) bijgewerkt; §12.3 (Uptime Kuma live), §12.4 (stub-providers
verwijderd) en §13.3 (zes auto-deploy-apps) gecorrigeerd. Geconstateerd dat de
appportal-stack zelf nog géén auto-deploy heeft — de #1 bron van toekomstige
drift.*

*Eerder, 2026-06-22 — **§6 (OMV-pipeline)** uitgebreid met de volledige
scrape→download→merge→extract-keten (§6.1–6.5), inclusief **§6.5 anti-blokkering**
(residentiële SOCKS-proxy + Anubis-bootstrap + troubleshooting — voorkomt herhaling
van de "RetryError"-zoektocht).
**Schuldentracker** kreeg een eigen sectie §6C
(Flask-schuldendossier-tracker, eigen login + SSO-shim met lezen/bewerken; nog in
git/CI te brengen). Eerder (2026-06-19): het **git-fundament** (GitHub-org `softwareglobaal`, VM = bron
van waarheid) met **Claude Code on the web** + **CI/CD** (auto-check → auto-merge →
auto-deploy) live op **Stagebeoordeling, Kosten én Factuurrouter**; het
**Kosten-dashboard** (`kosten.globaal.be`); het **HR-/DeskTime-dashboard** (in opzet);
en de hernoeming **Remy → Factuurrouter** (`factuurrouter.globaal.be`, repo
`globaal-factuurrouter`) waarbij de werknaam overal is verwijderd — zie §6A en §13.*
