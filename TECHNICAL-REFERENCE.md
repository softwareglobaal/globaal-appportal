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
| `factorydocs/inventory/finance/maintenance.globaal.be` | `app-*:300x` (stubs) | forward auth |
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
  `factorydocs-proxy`, `inventory-proxy`, `finance-proxy`, `maintenance-proxy`,
  `omv-proxy`, `schuldentracker-proxy`, `factuurrouter-proxy` (voorheen `remy-proxy`),
  `stage-proxy` (= Stagebeoordeling), `kosten-proxy`, `status-proxy`. External host
  = `https://<sub>.globaal.be`. Eigen toegangsgroepen per app naast
  `admin`/`manager`: o.a. `schuldentracker`, `factuurrouter`, `stagebeoordeling`,
  `kosten` (+ `-bewerken` voor schrijfrechten) — zie §12.1.
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
  aan de embedded outpost. Toegang: Mehdi + Angela + akadmin. *(Bij het hernoemen
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
  app + groepen **`schuldentracker`** (zien) en **`schuldentracker-bewerken`**
  (Mehdi, Angela). DNS via de wildcard.
- **Nog open:** (a) back-up van `data/finance.db`, (b) in git/CI/auto-deploy brengen
  (repo `globaal-schuldentracker`), (c) **de OpenAI-key in `.env` roteren** (stond in
  platte tekst, ook in de OneDrive-kopie).

---

## 7. Configuratie & scripts

| Bestand/map | Functie |
|---|---|
| `.env` | alle secrets + `BASE_DOMAIN`, `OMV_UPSTREAM`, `CERTGEN_DISABLE` (gitignored) |
| `.env.production` | sjabloon voor de VM (BASE_DOMAIN=globaal.be) |
| `apps.yaml` | app-catalogus + rol-mapping voor de tegels |
| `docker-compose.yml` | de hele stack |
| `nginx/templates/*.template` | nginx-serverblokken (envsubst met `${BASE_DOMAIN}`) |
| `nginx/snippets/forward-auth.conf` | het forward-auth-blok (gedeeld door de apps) |
| `nginx/templates/40-n8n.conf.template` | n8n-doorsturing (VM-specifiek) |
| `scripts/configure-authentik.sh` | groepen, OIDC, proxy-providers, TOTP, sessies |
| `scripts/setup-authentik.py` | de daadwerkelijke Authentik-config (via `ak shell`) |
| `scripts/add-omv-app.py` | registreert de OMV-provider apart |
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
(`http://172.20.0.1:5000`, het IP dat de nginx-container voor de host ziet) i.p.v.
de hostnaam.

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

| Groep | Geeft toegang tot | Leden |
|---|---|---|
| `schuldentracker` | Schuldentracker | Mehdi, Angela |
| `omv` | OMV Pipeline | (in te vullen) |
| `factuurrouter` | Factuurrouter | Mehdi, Angela, akadmin |
| `kosten` | Kosten-dashboard | Mehdi, Angela, Siyan, akadmin |
| `stagebeoordeling` | Stagebeoordeling (zien) | Raisha, Mehdi, akadmin |
| `stagebeoordeling-bewerken` | Stagebeoordeling (bewerken) | **alleen Raisha** |
| `admin` *(optioneel)* | alle apps | beheerders |

> **Patroon lezen vs. bewerken:** een app kan een tweede groep `<app>-bewerken`
> hebben. De app bindt aan de zien-groep; schrijfacties controleren server-side op
> lidmaatschap van de bewerken-groep (Schuldentracker, Stagebeoordeling).

`apps.yaml` bepaalt de **tegel-zichtbaarheid**; de Authentik group-bindings per
applicatie zijn de **handhaving**. Houd beide in sync.

### 12.2 App-overzicht: Authentik-launcher is de home (Flask-portal afgedankt)
**Besloten en uitgevoerd** (dit was eerder een open keuze): **Authentik's ingebouwde
launcher** (`auth.globaal.be/if/user/`) is hét startdashboard. De oude custom
**Flask-portal** (`portal.globaal.be`) is **afgedankt**:
- nginx stuurt `portal.globaal.be` met een catch-all `return 302` door naar de
  launcher (`nginx/templates/20-portal.conf.template`);
- `scripts/consolidate-launcher.py` heeft de placeholder-apps opgeruimd én de
  **Portal-applicatie + de `portal-oidc`-provider uit Authentik verwijderd**
  (geverifieerd: beide bestaan niet meer).

Gevolg voor nieuwe features: **niet in de Flask-portal bouwen** (die is onbereikbaar
en heeft geen OIDC-provider meer). Een nieuw dashboard is een **forward-auth-app** op
een eigen subdomein dat als **tegel** in de launcher verschijnt — zie §14 voor het
eerste voorbeeld (Medewerkers).

### 12.3 Roadmap — geplande volgende stappen (in volgorde)
1. **Uptime Kuma** opzetten (app-monitoring): online/offline + responstijd per
   app (OMV, Schuldentracker, n8n, portal, auth), bereikbaar op
   `status.globaal.be` achter SSO.
2. **Opruimstap — drift wegwerken + git.** We hebben op twee plekken bewerkt
   (Windows-map én rechtstreeks op de VM), waardoor ze uit elkaar zijn gegroeid.
   Plan: (a) de Windows-map een getrouwe weergave van de VM maken (o.a. het
   ontbrekende `nginx/templates/41-schuldentracker.conf.template`), (b) een
   **git-repo** opzetten als single source of truth — géén code meer in
   OneDrive/Dropbox; de VM haalt updates voortaan via `git pull`.
   ⚠️ Tot dat klaar is: kopieer de Windows-map NIET blind over `~/appportal` op
   de VM — dat zou de werkende VM-config overschrijven.

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
  5050), SSO-shim met lezen/bewerken (`schuldentracker` / `schuldentracker-bewerken`,
  leden Mehdi/Angela). **Nog open:** (a) back-up van `data/finance.db`, (b) in
  git/CI/auto-deploy brengen (`globaal-schuldentracker`), (c) **OpenAI-key in `.env`
  roteren** (stond in platte tekst).
- **Tegels opgeschoond (fase 8):** de 4 placeholder-apps zijn uit `apps.yaml`
  verwijderd. De bijbehorende **stub-containers, nginx-blokken en
  Authentik-providers draaien nog** (onzichtbaar) — volledige opruiming staat
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
> staan als poort. **Live op alle drie de apps** (✅ end-to-end bevestigd
> 2026-06-19): **Stagebeoordeling** en **Kosten** (beide volledig automatisch) en
> **Factuurrouter**. De smoke-test verschilt per app: Stage/Kosten starten de app
> op + `curl` (`/` resp. `/health`); Factuurrouter doet alleen `py_compile` (een
> echte start vereist Gmail-credentials, die niet in CI staan).

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
`kosten.service` op **poort 8090**, achter SSO (groep `kosten`: Mehdi, Angela,
Siyan, akadmin). De **volledige pipeline draait server-side** ("alles op de
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

## 14. Centrale gebruikersdatabase & Medewerkers-app

De **centrale gebruikersdatabase** is de bron van waarheid voor "wie is een persoon";
van daaruit worden mensen aan dashboards gekoppeld. De **Medewerkers-app** is het eerste
dashboard erbovenop én meteen het model voor nieuwe apps (forward-auth tegel).

> Deze sectie beschrijft de **as-built**-realiteit. De bestanden staan sinds 2026-07-01
> op `main`: de branch `vm-as-built-2026-06-26` is verzoend met `main` en opgeruimd
> (drift-opruiming §12.3 afgerond) — VM-realiteit + docs op één branch.

### 14.1 Database `appportal` (in dezelfde Postgres als Authentik)
- Naast de `authentik`-database draait een **tweede database `appportal`** in dezelfde
  `postgresql`-container. Cross-grens (appportal ↔ authentik) loopt via de Authentik-**API**,
  nooit via SQL.
- Schema `kern`: **`persoon`** (de hub), **`afdeling`**, **`firma`** + **`leverancier`**
  (gecontroleerde lookups). Elke
  persoon heeft een onveranderlijke `id` (UUID) — dé FK voor alle dashboards — plus o.a.
  `voornaam`/`achternaam`, `email` (citext, uniek), `afdeling_id`, `rol`
  (Lid/Hoofd/Partner/Management), `hr_nummer`, `locatie`, `in_dienst`, en de
  loginkoppeling `authentik_sub` + `authentik_username` (leeg = geen login).
- Spoke-schema's (bv. `schuldentracker`, `omv`, **`kosten`** — het kosten-dashboard —
  en **`communicatie`** — het Communicatie-dashboard, §14.5) verwijzen met `persoon_id`
  (UUID, `ON DELETE RESTRICT`) naar `kern.persoon`, zodat een 360°-profiel een gewone
  join is. ⚠ Aandachtspunt: `kosten.firma` is een **eigen, tweede
  firmalijst** (text-id's) naast `kern.firma` — sinds migratie 012 overbrugd via
  `kosten.firma.kern_firma_id` (naam-match-backfill; NULL = verzoen-signaal in de
  Second Brain). Volledige verzoening (text-id's weg) kan pas samen met de
  kosten-host-app (repo `globaal-kosten`).
- **Kosten ↔ kern (migratie 012, "de blauwe draad")**: alle `vendor`-teksten uit
  `kosten.software` zijn gebackfilld naar **`kern.leverancier`** (case-insensitief
  samengesmolten met bestaande rijen als Zoom/Microsoft; "Close Call (Xelion)" is
  genormaliseerd naar "Close Call BV"). `kosten.software` en `kosten.charge_actual`
  hebben nu **`leverancier_id`**; een `BEFORE INSERT/UPDATE OF vendor`-trigger
  (`kosten.link_leverancier()`, SECURITY DEFINER) houdt die link automatisch in
  stand — de host-app blijft gewoon vendor-tekst schrijven en maakt via de trigger
  zo nodig zelf een nieuwe leverancier aan. Weergave-afspraak: **per nummer →
  Communicatie (`vaste_prijs`), per gebruiker/licentie → Kosten** (geen dubbeltelling);
  verwacht (`seats × unit_price`) vs. werkelijk (`charge_actual`) is de beoogde
  vergelijking voor signalen.
- **`kern.firma`** — centrale firmalijst (13 bedrijven van de groep): `id` (uuid), `naam`,
  `code` (uniek, 4 hoofdletters), `land`, `actief` (zacht uitzetten), `kbo_nummer`
  (migratie 018 — het firma-detail linkt ermee naar KBO Public Search en de
  NBB-jaarrekeningen; API-verrijking later). Gekoppeld aan
  personen via **`persoon.werkgever_firma_id`** ("in dienst bij" — uniselect, FK) en de
  koppeltabel **`kern.persoon_dienstfirma`** ("diensten voor" — multiselect,
  veel-op-veel). Seed: `db/seed-afdeling-firma.sql`.
- **Per-app DB-rollen** (governance): elke app krijgt een eigen rol met **alleen-lezen**
  op `kern` en rechten op enkel het eigen schema. De Medewerkers-app leest via
  **`portal`** en schrijft via de **smalle schrijfrol `medewerker_writer`** (enkel
  `UPDATE(werkgever_firma_id)` op `persoon` + `INSERT`/`DELETE` op de koppeltabel — meer
  niet). Het kosten-dashboard gebruikt de rol **`kosten`**. Alle rollen staan in
  `db/roles.sql` (placeholders; echte wachtwoorden alleen in `.env` op de VM).
- **Schemabeheer (sinds 2026-07-01):** het schema staat in git onder **`db/`** —
  `000-baseline.sql` (volledige schema-dump als nulpunt), `roles.sql`,
  `seed-afdeling-firma.sql`, en `migrations/NNN-*.sql` voor alles daarna, toegepast met
  `scripts/db-migrate.sh` (tracking in `public.schema_migrations`; dubbel draaien is
  veilig). **Regel: geen ad-hoc `psql`-DDL meer** — elke wijziging is een genummerd,
  gecommit bestand. Verse-deploy-procedure: `db/README.md`. De persoon-seed (34
  namen/e-mails) blijft bewust buiten de repo (lokale ontwerpmap).
- **Backups:** `scripts/db-backup.sh` dumpt nachtelijk (cron, 03:15) `authentik` én
  `appportal` in custom formaat naar `~/backups/` met 14 dagen retentie. **Off-site:**
  staat `S3_BACKUP_BUCKET` in `.env`, dan gaat elke dump **GPG-versleuteld** (AES256,
  passphrase in `~/.backup-passphrase`, chmod 600 + kopie in de wachtwoordkluis) naar
  die S3-bucket; de upload-sleutel mag **alleen PutObject** (gekaapte VM kan off-site
  niets lezen/wissen) en de bucket ruimt zelf op (lifecycle 30 dagen). Vereist awscli +
  gnupg + `aws configure`; terugzetten
  met `pg_restore` (voorbeeld in de scriptkop). Off-site kopie (S3) is een open punt.

### 14.2 Organisatie-dashboard (`organisatie.globaal.be`) — medewerkers + firma's
> Het oude adres `medewerkers.globaal.be` blijft werken via een nginx-**301** naar
> het nieuwe domein (wildcard-DNS + wildcard-cert, dus geen extra stappen). In
> Authentik is alleen de `external_host` van de proxy-provider en de tegel
> aangepast (`scripts/hernoem-medewerkers-naar-organisatie.py`); de slug blijft
> `medewerkers`, net als de compose-service `app-medewerkers` en de map
> `medewerkers/` (interne namen, geen buitenkant).
- **Forward-auth-app** (Flask), **eigen repo `softwareglobaal/globaal-organisatie`**
  (subtree-split uit deze stack-repo, historie behouden), op de VM uitgecheckt als
  `~/appportal/medewerkers/` (pad is historisch; hier gitignored — zelfde patroon als
  telefoonregister). **Auto-deploy:** `deploy.sh` in die repo draait via cron (elke
  2 min): nieuwe commits op main → pull + rebuild, geen handmatige stappen.
  Compose-service **`app-medewerkers`**
  in `docker-compose.override.yml` (poort 3007), nginx-blok
  `nginx/templates/44-medewerkers.conf.template`. Registratie in Authentik
  (proxy-provider + applicatie + group-binding + embedded outpost) via
  `scripts/add-medewerkers-app.py`.
- Toont de **medewerkerslijst**: platte lijst op volledige naam met kolommen
  Naam/Afdeling/Rol/In dienst/Diensten voor/Locatie/HR-nummer; zoeken, filters op
  **afdeling en rol**, en een **groepeer-knop** (Geen / Afdeling / Rol) die in lijst- én
  kaartweergave werkt. Per persoon een **360°-profiel**. Identiteit + RBAC komen uit
  de `X-authentik-*`-headers; alleen **admin/manager** hebben toegang (Authentik
  group-binding + check in de app). Leest `kern.persoon` via de `portal`-rol; de
  connectiestring staat in `.env` als `APPPORTAL_DB_URL`.
- **Firma's-tab:** het dashboard heet **Organisatie** en heeft tabs *Medewerkers* |
  *Firma's*. De Firma's-tab toont de centrale lijst met tellingen (medewerkers in
  dienst, dienstverbanden, nummers, e-mailadressen — de laatste twee via SQL op het
  `communicatie`-schema) en per firma een **profiel** met alles wat eraan hangt
  (personen → profiel-links; nummers → deep-links naar Communicatie). **Beheer**
  (toevoegen, hernoemen, land, zacht uitzetten via `actief`) kan alleen als admin, via
  de schrijfrol (migratie 006: INSERT/UPDATE op `kern.firma` voor `medewerker_writer`),
  met same-origin-check en audit-log (`FIRMA_NIEUW`/`FIRMA_BEHEER`). Firma's toevoegen
  is daarmee een UI-handeling i.p.v. SQL.
- **Graph-tab + AI-laag** (2026-07-02): interactieve **knowledge-graph** van de hele
  organisatie (personen/afdelingen/firma's/leveranciers/nummers/e-mailadressen met
  benoemde relaties; vis-network gevendord; dubbelklik = detailpagina), met **zoekbalk**
  (live-suggesties → zoom naar knoop) en **type-filters** (klikbare legenda-chips met
  tellers; onbekende nieuwe types renderen automatisch grijs mét eigen chip). De graaf
  wordt bij elke load vers uit de DB gebouwd — wijzigingen elders zijn na een F5 zichtbaar.
- **Signalen + dagbriefing (proactieve AI):** `graaf.py` berekent per load de signalen
  (open eindjes) met **ernst** hoog/middel/laag — puur regels, geen AI. Daarbovenop de
  **dagbriefing**: één AI-samenvatting per dag ("wat verdient vandaag aandacht + actie"),
  gegenereerd bij het eerste bezoek, opgeslagen in **`organisatie.briefing`** (migratie
  007, upsert met historie), ververs-knop = admin. De **AI-chat** ("Vraag het de
  organisatie") heeft gespreksgeschiedenis (laatste 12 beurten mee) en krijgt bij elke
  beurt de actuele graaf als systeemcontext — antwoorden komen uit de data; geheimen
  (PIN/PUK) zitten nooit in de graaf; opmaak beperkt tot vet/cursief; audit-logs
  `AI_VRAAG`/`BRIEFING`. Config: `ANTHROPIC_API_KEY` in `.env` (leeg = AI uit, graph
  blijft werken), model via `AI_MODEL` (default `claude-sonnet-5`).
- **Principe: de graph is een weergave van de database, geen invoerkanaal.** Een knoop
  bestaat omdat hij in een echt schema bestaat. De kortstondige "vrije elementen-laag"
  (zelfbediening met vrije tekst) is bewust **teruggedraaid** — botste met de
  terminologie-discipline; de tabellen van migratie 008 blijven ongebruikt liggen.
  Nieuwe organisatie-aspecten volgen het **recept**: migratie met FK's naar kern →
  ±15 regels in `graaf.py` → één kleurregel; invoer via dashboards met dropdowns.
  Eerste verrijking langs die lijn: het **kosten-schema** — software als knopen met
  seat-/account-eigenaar-relaties naar personen, "kosten bij" naar `kern.firma` en
  "geleverd door" naar `kern.leverancier`. Sinds migratie 012 lopen die edges via de
  **echte FK's** (`leverancier_id`, `kosten.firma.kern_firma_id`); naam-matching is
  het vangnet en **mismatches blijven signalen** ("kosten-firma X ontbreekt in kern") —
  de graph spoort zo oude vrije tekst op.
- **Finalisatie** (migratie 018, `organisatie.finalisatie`): het kwaliteitsstempel op
  een knoop — een collega controleert en klikt "Markeer gefinaliseerd" op de
  detailkaart; vastgelegd met **wie + wanneer, append-only** (terugdraaien = nieuwe
  rij; de writer-rol heeft alleen INSERT). Toolbar-knop "Finalisatie" kleurt de graph
  **blauw = gefinaliseerd / rood = nog niet** — voortgangsmeter én curatie-werklijst.
  Geen slot: data blijft bewerkbaar ("wijziging → terug naar rood" is een bewuste v2).
  Finaliseren mag alle staff (admin + manager); audit-event `FINALISEER`. Volledige app-documentatie: **README van
  `globaal-organisatie`**. Vervolgstappen: `TODO.md`.
- **Naamconventie (display vs full):** de medewerkersdatabase toont de **volledige naam**
  (voor- + familienaam — dit is de identiteitsbron); alle *andere* apps tonen personen in
  het **Zoom-formaat `Voornaam (Afdeling)`**, live opgebouwd uit `kern.persoon` +
  `kern.afdeling` (wijzigt iemand van afdeling, dan klopt de weergave overal vanzelf).
- Het **360°-profiel** toont per persoon: **Toegang (Authentik)** — groepen + afgeleide
  apps (§14.3) — en **Telefoonnummers** uit het telefoonregister (§14.4). Beide via
  read-only API-calls, best-effort (ontbreekt de bron → nette fallback, app blijft werken).
- **Firma-koppeling (bewerken):** op het profiel kiest een **admin** de werkgever
  ("In dienst bij", uniselect) en de dienstverbanden ("Diensten voor", multiselect);
  beide dropdowns komen uit `kern.firma` (alleen actieve firma's). Opslaan loopt via de
  aparte schrijf-engine (`APPPORTAL_WRITE_URL` in `.env` → rol `medewerker_writer`);
  zonder die env blijft de app volledig read-only. De **lijst** toont beide als kolommen
  ("In dienst" = firmacode, "Diensten voor" = code-chips). Het schrijf-endpoint is
  **gehard**: same-origin-check (Origin/Referer moet deze host zijn — CSRF-bescherming,
  ook tegen andere *.<domein>-subdomeinen) en een **audit-log** naar stdout
  (`FIRMA_UPDATE user=… persoon=… werkgever=… diensten=…`, plus `WRITE_DENIED`/
  `CSRF_REJECT`), zichtbaar via `docker compose logs app-medewerkers`.

### 14.3 Authentik-koppeling (Toegang-panel)
- Bestaande Authentik-accounts zijn **handmatig gekoppeld** aan hun persoon door
  `authentik_username` + `authentik_sub` (de Authentik-`uuid`) te zetten. Gekoppelde
  profielen tonen "gekoppeld via Authentik". `akadmin` is bewust **niet** gekoppeld
  (break-glass admin, geen persoon; z'n e-mail is losgekoppeld van `mch@h-architects.be`).
- Het profiel-blok **"Toegang (Authentik)"** toont de echte **groepen** van de persoon
  (live uit de Authentik-API, opgezocht op **`authentik_sub`**/uuid — blijft werken als
  een account hernoemd wordt; username is enkel fallback) en de **apps** die die groepen geven
  (afgeleid uit `apps.yaml`: groep ∩ `roles`). Read-only via een eigen service-account
  **`medewerkers-readonly`** (RBAC-rol met `view_user` + `view_group`), aangemaakt met
  `scripts/add-medewerkers-readonly-token.py`. Het token staat in `.env` als
  `MEDEWERKERS_AUTHENTIK_TOKEN`; de app leest het als `AUTHENTIK_API_TOKEN` met
  `AUTHENTIK_API_URL=https://auth.<domein>/api/v3` (intern via de nginx-netwerkalias, dus
  geen hairpin). Best-effort: geen token/API → "koppeling niet geconfigureerd".
- **Nog open:** (a) automatische koppeling bij eerste login bestaat niet meer (liep via de
  afgedankte OIDC-portal) — koppelen gebeurt nu bewust/admin; (b) ontbrekende
  HR-nummers/familienamen/e-mails aanvullen.

### 14.4 Koppeling Telefoonregister ↔ persoon
De eerste échte spoke die naar `kern.persoon(id)` verwijst — het 360°-model in de praktijk.
- **Telefoonregister** (`telefoonregister.globaal.be`, eigen repo
  `softwareglobaal/telefoonregister`, SQLite, service `app-telefoonregister`:3006) kreeg een
  kolom **`numbers.persoon_id`** (uuid, nullable) — een **zachte** verwijzing naar
  `kern.persoon(id)`. Geen echte FK: SQLite ↔ Postgres, integriteit door proces. Migratie
  `20260701_000002_add_persoon_id.js`.
- **Matching:** de bestaande vrije-tekst `assigned_to` is eenmalig, gecureerd gekoppeld
  (8 waarden → 7 personen). Teamlijnen, externen, andere groepsbedrijven en niet-toegewezen
  nummers blijven leeg — koppelen is **opt-in per record**; de dekking groeit mee als
  `kern.persoon` groeit.
- **Profiel → nummers:** het medewerkersprofiel toont een sectie **Telefoonnummers**
  (nummer/doel/status, **nooit** de secrets/PIN/PUK). Sinds het Communicatie-dashboard
  (§14.5) leest `medewerkers/telefoon.py` **rechtstreeks het `communicatie`-schema**
  (portal-rol, SQL): nummers waar de persoon verantwoordelijke óf gebruiker (queue) van
  is. Elk nummer is een **link terug** naar het nummerdetail in Communicatie
  (deep-link `https://communicatie.<domein>/#nummer=<id>`). De oude route via de
  telefoonregister-API is daarmee vervallen. Best-effort.
- **Telefoon → profiel:** in het telefoonregister is **"Toegewezen aan"** een link naar
  `medewerkers.<domein>/<persoon_id>` waar `persoon_id` gezet is (frontend leidt de host af
  uit `location.hostname`). API-uitbreiding: een `?persoon_id=`-filter op `GET /api/numbers`.
- **Los eindje:** de telefoonregister-repo draait op branch `claude/ecstatic-feynman-wctpk1`
  (niet `main`) — zelfde drift-patroon als appportal had; nog te verzoenen.

### 14.5 Communicatie-dashboard (`communicatie.globaal.be`)
De opvolger-in-opbouw van het telefoonregister: telefoonnummers **en** e-mailadressen,
volledig gelinkt aan de centrale lijsten. De app van de collega
(`telefoonregister.globaal.be`) blijft er **ongemoeid naast draaien** tot hij akkoord is.
- **Stack:** kopie van de telefoonregister-codebase (Node/Express/Knex), sinds
  2026-07-02 in een **eigen repo `softwareglobaal/globaal-communicatie`** (subtree-split,
  historie behouden; hier gitignored) — de VM checkt die uit op `~/appportal/communicatie`
  met **auto-deploy** via `deploy.sh` (cron, elke 2 min, log `~/deploy-communicatie.log`).
  App-documentatie: de README in die repo. Service **`app-communicatie`**:3008, nginx-template
  `45-communicatie.conf.template`), maar op **Postgres** — schema **`communicatie`** in de
  appportal-DB met **échte FK's** naar `kern.persoon`/`kern.firma`/`kern.afdeling`/
  `kern.leverancier`. DB-rol **`communicatie`** (leest kern, schrijft eigen schema,
  beheert `kern.leverancier`); connectiestring `COMMUNICATIE_DB_URL` in `.env`
  (Node-formaat `postgres://…`). Schema: migraties **002–004, 011, 013**.
- **Datamodel** (terminologie volgt `DEFINITIEBOEK.md`): `nummer` met **doel** (niet
  "functie"), **leverancier**, **factuur-firma** (wie de leveranciersfactuur krijgt —
  in de praktijk Unabo), **doorfactuur-firma** (aan wie wij doorrekenen),
  **gebruikt-voor-firma** (voor welk bedrijf/dossier het nummer feitelijk werkt;
  migratie 013 — het Contacts-scenario van Mehdi), afdeling en **verantwoordelijke**
  (één; = 1e in belvolgorde, de 2e is de **backup**) — allemaal dropdowns uit kern,
  geen vrije tekst; **vaste prijs** (€ excl. BTW, migratie 011; leeg = onbekend/variabel)
  als eerste facturatie-veld; `nummer_gebruiker` = de **gebruikers** met **belvolgorde** (queue van de
  telefooncentrale: `volgorde`-kolom, 1 neemt eerst op, in de UI herschikbaar);
  **`view_instelling`** = kolomkeuze per Authentik-gebruiker (migratie 013): alles zit
  in het dashboard, de **Mijn view**-knop bepaalt per persoon wat zichtbaar is — elke
  wijziging wordt direct bewaard, geen aparte opslaan-knop ("view van Mehdi" ≠
  "view van Siyan"; ook alleen-lezen-gebruikers). De knop **Keuzelijsten** (voorheen
  "Lijsten") is iets anders: beheer van de dropdown-waarden Land/Platform/Type;
  `geheim` (PIN/PUK/kaartnummer, afgeschermd, 1-op-1); `emailadres` met firma +
  verantwoordelijke (leeg = **"OPEN"**-markering, het open eindje) +
  `emailadres_gebruiker` (wie op de mailbox ingelogd zijn, multi); `lijst`
  (app-eigen keuzewaarden Land/Platform/Type).
- **UI:** AppPortal-huisstijl (zelfde visuele taal als Medewerkers — bewust ontdaan van
  "AI-tells": geen emoji/icoonkaarten/taglines). Personen overal in **Zoom-formaat** en
  klikbaar → medewerkersprofiel; firma's als volledige naam; **firma-filter is
  multi-select**; KPI-cijfers als filters; live-sync (SSE), dubbelcheck op genormaliseerd
  nummer, Excel-export.
- **Toegang:** forward-auth; tegel voor groepen **admin/manager/communicatie**
  (`scripts/add-communicatie-app.py`); bewerken alleen **`communicatie-editors`** + admin
  (env `EDITOR_GROUPS`; server dwingt af met 403).
- **Data:** eenmalig geïmporteerd uit de telefoonregister-SQLite
  (`communicatie/scripts/import.js`, JSON via stdin): leveranciers ge-upsert uit de
  provider-waarden, firma's op naam gematcht, verantwoordelijke uit de bestaande
  `persoon_id`-links; de rest is **curatiewerk in de nieuwe UI** (Siyan). Zelfde uuid's
  behouden, dus her-draaien is idempotent.

> **Ontwerp-/achtergronddocument** (datamodel, flows, governance, tradeoffs):
> `ONTWERP-CENTRALE-GEBRUIKERSDATABASE.md` (lokaal, nog buiten deze repo).

### 14.6 Vermogens-dashboard (`vermogen.globaal.be`)
Skelet-app (meeting 2026-07-02; bank vraagt panden-overzicht, Mehdi levert de data):
tabs **Panden / Verzekeringen / Leningen & leasingen / Syndicus**, elk met een eigen
veldenlijst die per tab aanpasbaar is (de `*_VELDEN`-configs bovenaan `app.py`).
- **Repo `softwareglobaal/globaal-vermogen`** (VM: `~/appportal/vermogen`,
  auto-deploy via cron zoals organisatie/communicatie, log `~/deploy-vermogen.log`).
  Flask/gunicorn, compose-service **`app-vermogen`**:3009, nginx-template
  `46-vermogen.conf.template`, Authentik via `scripts/add-vermogen-app.py`
  (tegel voor admin/manager/vermogen; schrijven = groep `vermogen-editors`).
- **Schema `vermogen`** (migratie 016): `pand` (eigenaar → kern.firma, aankoop,
  huurcontract, syndicus-link), `verzekering` (soort/opzegtermijn/jaarpremie,
  linkbaar aan pand; `object` = tekst voor bv. auto's zolang die geen entiteit zijn),
  `lening` (Lening/Leasing, hoofdsom/rente/maandaflossing, linkbaar aan pand),
  `syndicus` (contact + jaarvergadering). DB-rol **`vermogen`** (roles.sql;
  `VERMOGEN_DB_URL` in `.env`); `portal` leest mee — de Second Brain kan hier later
  vervaldatum-signalen uit halen ("verzekering vervalt < 90 dagen", laag 3).
- Verwijderen is zacht (actief/niet-actief); huurders/verzekeraars/banken zijn nog
  tekstvelden tot de klant-/externe-partij-entiteit bestaat. App-docs: README aldaar.

### 14.7 Draaiboek-platform (`draaiboek.globaal.be`)
Playbook-management (het ★-einddoel; prototype 2026-07-03): een **draaiboek**
(sjabloon: fases → stappen met soorten, afhankelijkheden, condities, termijnen)
wordt per **dossier** als **run** uitgevoerd. Kern van de motor: het
**kickoff-formulier** → `conditie_regel`-evaluatie → labels (bv. `groot_project`
bij ≥ 500 m²) → alleen passende stappen worden als **snapshot** gekopieerd
(sjabloon-wijzigingen raken lopende runs nooit). Afvinken met harde
afhankelijkheids-blokkades, ► eerstvolgende-marker (het sequentiële geheugen),
toewijzen, deadlines, overslaan-met-reden, herhaal-stappen (dupliceren) en
handmatige stappen per run. **`run_stap_log`** is append-only (rol heeft geen
UPDATE) — historie telt én event-bron voor latere automatisering.
- **Repo `softwareglobaal/globaal-draaiboek`** (VM `~/appportal/draaiboek`,
  auto-deploy cron zoals de andere dashboard-repo's). Flask, service
  **`app-draaiboek`**:3010, nginx `47-draaiboek.conf.template`, Authentik via
  `scripts/add-draaiboek-app.py` (groepen admin/manager/draaiboek). Rol
  **`draaiboek`** (roles.sql; `DRAAIBOEK_DB_URL` in `.env`).
- **Schema `draaiboek`** (migratie 022): draaiboek/fase/stap/veld/conditie_regel
  (sjabloon) + dossier/run/run_stap/veldwaarde/run_stap_log (uitvoering); seed:
  het draaiboek **Veiligheidscoördinatie** (KB 25/01/2001, 5 fases / 26 stappen,
  klein-vs-groot-pad). Ontwerp + onderbouwing: `docs/ontwerp-draaiboek-datamodel.md`
  (deep-research 2026-07-03). E2E-tests: `test_e2e.py` in de app-repo.
- Fase 2 (TODO): documentgeneratie VGP/PID (Toolmaster-vervanger),
  sjabloon-beheer-UI, automatisering, Fathom→run-stappen, Second Brain-signalen.

---

*Laatst bijgewerkt: 2026-07-03 — **Draaiboek-platform prototype live** (§14.7:
migratie 022, veiligheidscoördinatie-draaiboek, repo `globaal-draaiboek`; ontwerp
`docs/ontwerp-draaiboek-datamodel.md` op basis van de deep-research). Daarnaast:
**woordenboek** overal (kern.definitie, migraties 015/017/019/021 + beheer-UI 020,
alleen mehdi/akadmin), **finalisatie** (blauw/rood, append-only, migratie 018),
**KBO-links** op firma's, **Vermogens-dashboard** (§14.6, migratie 016),
**kosten↔kern blauwe draad** (migratie 012), **Communicatie**: persoonlijke views
met kolomkiezer/volgorde/sortering (migraties 013/014), terminologie "intern
gefactureerd aan", **off-site backups** naar S3 (GPG, upload-only,
`docs/offsite-backup-setup.md`), **CLAUDE.md-dekking** in alle 9 repo's, en het
**adres-autocomplete-patroon** (eigen `/api/adres`-proxy → Photon/OSM + eigen
dropdown, géén datalist en géén externe scripts — in vermogen en draaiboek; zie
hun README's). Beheer-les: shell-scripts vanaf Windows committen met
`git update-index --chmod=+x`, anders faalt de deploy-cron stil op Permission
denied (overkwam draaiboek/vermogen).*

*Eerder (2026-07-02) — **Graph-tab + proactieve AI-laag** op het
Organisatie-dashboard: knowledge-graph met zoekbalk en type-filters, signalen met
ernst, **dagbriefing** (organisatie.briefing, migratie 007) en AI-chat met
gespreksgeschiedenis op de Claude API (§14.2; app-docs in de README van
`globaal-organisatie`). De app verhuisd naar **eigen repo `globaal-organisatie` met
auto-deploy** (cron, 2 min) en domein **organisatie.globaal.be** (oud adres = 301).
Parkeerlijst: `TODO.md`.
Eerder (2026-07-01, nacht) — **Organisatie-dashboard**: het
medewerkersdashboard heet nu Organisatie en kreeg een **Firma's-tab** (lijst met
tellingen, firmaprofiel met alles wat eraan hangt, admin-beheer; migratie 006;
§14.2). Daarnaast **Communicatie-dashboard live** (§14.5:
telefonie + e-mail op schema `communicatie`, belvolgorde-queue, firma-multiselect,
AppPortal-huisstijl; migraties 002–004, nieuwe centrale lijst `kern.leverancier`) en
**medewerkerslijst v3** (platte lijst, afdeling-kolom, rol-filter, groepeer-knop;
naamconventie display `Voornaam (Afdeling)` vs full name in de bron; §14.2). Eerder
(avond) — **firma-koppeling op personen** (werkgever uni +
diensten-voor multi, admin-bewerking via smalle schrijfrol `medewerker_writer`;
§14.1/§14.2) en **schemabeheer in git** (`db/` met baseline + migratie-runner; regel:
geen ad-hoc DDL; §14.1). Ook `DEFINITIEBOEK.md` (draft terminologie) toegevoegd en
`.gitattributes` (LF-normalisatie). Eerder die dag: **Toegang-panel** (Authentik-groepen
+ afgeleide apps,
§14.3), **koppeling Telefoonregister ↔ persoon** (§14.4 — eerste spoke met `persoon_id`)
en de **centrale firmalijst `kern.firma`** (13 bedrijven, §14.1) live, en de
**drift-opruiming afgerond**: branch `vm-as-built-2026-06-26`
verzoend met `main` en opgeruimd (VM-realiteit + docs op één branch; §12.3). Eerder (2026-06-30): **§14 (centrale gebruikersdatabase + Medewerkers-app)**
toegevoegd en **§12.2** rechtgezet (Authentik-launcher is de home, Flask-portal afgedankt).
Eerder (2026-06-22): **§6 (OMV-pipeline)** uitgebreid met de volledige
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
