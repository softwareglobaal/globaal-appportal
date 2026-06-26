# AppPortal

Internal application platform: employees log in **once** through
[Authentik](https://goauthentik.io/) (with TOTP 2FA), land on a portal showing
only the application tiles their role permits, and click through to those
applications without logging in again.

```
Browser ──HTTPS──> Nginx (only public entry, TLS)
                    ├── auth.<domain>      → Authentik (identity provider)
                    ├── portal.<domain>    → Flask portal (OIDC client)
                    └── <app>.<domain>     → stub apps, guarded by Authentik
                                             forward auth (nginx auth_request)
```

- **Authentik** owns all authentication: passwords, TOTP, sessions, users.
- **Portal** (Flask + Authlib) authenticates via OIDC and filters tiles by the
  user's Authentik groups (`admin`, `manager`) using [apps.yaml](apps.yaml).
- **Apps** never see a login. Nginx validates every request against
  Authentik's embedded outpost (forward auth) and passes the identity in
  `X-authentik-*` headers. No tokens ever appear in URLs.
- **Single logout**: portal logout ends the Authentik session, which instantly
  locks every app (forward auth re-checks each request).

Hostnames: `auth.`, `portal.`, `factorydocs.`, `inventory.`, `finance.`,
`maintenance.` under `BASE_DOMAIN` (default `localhost`).

---

## 1. First-time startup

Prerequisites: Docker with Compose v2.

```bash
cd AppPortal
cp .env.example .env
# Edit .env: set every CHANGE_ME (generate with: openssl rand -base64 48)
# Pick BASE_DOMAIN: localhost for local use, or <ip-with-dashes>.sslip.io
# for an AWS VM (e.g. 52-1-2-3.sslip.io — resolves automatically, no DNS).

docker compose up -d
docker compose ps          # wait until everything is healthy (first boot ~2 min)
```

**Wait until `authentik-server` shows `(healthy)` before logging in.** Its
first boot runs database migrations that take a couple of minutes; the portal
is configured to wait for that health state, so OIDC discovery never runs
against a half-migrated Authentik.

The one-shot `certgen` container generates a local CA plus a wildcard TLS
certificate into `certs/`. **Import `certs/ca.crt` into your browser/OS trust
store** to avoid certificate warnings (one import covers all hostnames).

Only ports 80 and 443 are published; the apps are reachable solely through
nginx on the internal Docker network.

## 2. One-time Authentik configuration

Do these once, in this order. Authentik UI: `https://auth.<BASE_DOMAIN>`,
user `akadmin`, password = `AUTHENTIK_BOOTSTRAP_PASSWORD` from `.env`.

> **Scripted alternative** — `sh scripts/configure-authentik.sh` (run inside
> WSL/Linux from this directory) applies steps 2.1 and 2.3–2.7 automatically
> and prints the `OIDC_CLIENT_ID`/`OIDC_CLIENT_SECRET` values for `.env`.
> Creating real users (2.2) is always manual.
> `sh scripts/ak-exec.sh scripts/create-test-users.py` creates two demo
> users (`testadmin`/`testmanager`) — delete them before real use.

### 2.1 Create the groups

*Directory → Groups → Create*: create `admin` and `manager`
(names must match `roles:` in [apps.yaml](apps.yaml) exactly).

### 2.2 Create the users

*Directory → Users → Create* for each employee (no self-registration exists —
verify under *System → Brands → default* that no enrollment flow is set,
which is the default). After creating a user:

- *User details → Groups tab → Add to existing group* → `admin` or `manager`.
- *Set password* (or create an enrollment link to let them set their own).

### 2.3 Enforce TOTP 2FA

*Flows and Stages → Stages → `default-authentication-mfa-validation`* (edit):

- **Not configured action**: *Force the user to configure an authenticator*
- **Configuration stages**: select `default-authenticator-totp-setup`

Every user now has to enroll a TOTP app at their first login.

### 2.4 Cap the Authentik session at 8 hours

*Flows and Stages → Stages → `default-authentication-login`* (edit):

- **Session duration**: `hours=8`

This matches the portal's own 8-hour session so neither outlives the other.

### 2.5 Create the portal's OIDC provider + application

1. *Applications → Providers → Create* → **OAuth2/OpenID Provider**:
   - Name: `portal-oidc`
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - **Invalidation flow: `default-invalidation-flow`** — this is what makes
     portal logout end the whole Authentik session (single logout). The
     preselected `default-provider-invalidation-flow` only ends the portal's
     own OAuth session.
   - Client type: **Confidential**
   - Redirect URI (strict): `https://portal.<BASE_DOMAIN>/auth/callback`
   - Note the **Client ID** and **Client Secret**.
2. *Applications → Applications → Create*:
   - Name: `Portal`, **Slug: `portal`** (must be exactly `portal` — it is part
     of the OIDC discovery and logout URLs), Provider: `portal-oidc`.
3. Put the credentials in `.env` (`OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`) and
   reload the portal:

   ```bash
   docker compose up -d portal
   ```

### 2.6 Create a forward-auth proxy provider per app

For **each** of the four apps (FactoryDocs, InventoryTracker,
FinanceDashboard, MaintenanceLog):

1. *Applications → Providers → Create* → **Proxy Provider**:
   - Name: e.g. `factorydocs-proxy`
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Mode: **Forward auth (single application)**
   - External host: `https://factorydocs.<BASE_DOMAIN>`
2. *Applications → Applications → Create*:
   - Name: `FactoryDocs`, slug: `factorydocs`, Provider: `factorydocs-proxy`.

Repeat with `inventory`, `finance`, `maintenance` and ports/hosts to match.

Then — **easy to forget** — assign all four providers to the embedded outpost:

*Applications → Outposts → `authentik Embedded Outpost` (edit)*:
- Add all four applications to **Applications**.
- In the configuration YAML, set `authentik_host: https://auth.<BASE_DOMAIN>`
  so login redirects go to the public hostname.

### 2.7 Restrict each app to its roles

apps.yaml only controls which **tiles are shown**; this step is the actual
**enforcement** (it also blocks users who type an app URL directly):

For each application under *Applications → Applications → <app> →
Policy / Group / User Bindings → Bind existing Group*:

| Application      | Bind groups        |
|------------------|--------------------|
| FactoryDocs      | `admin`, `manager` |
| InventoryTracker | `admin`, `manager` |
| FinanceDashboard | `manager` only     |
| MaintenanceLog   | `admin`, `manager` |

(With at least one binding present, only members of bound groups get access.)

### 2.8 Smoke test

1. Open `https://portal.<BASE_DOMAIN>` in a private window → you are sent to
   Authentik → log in as a test user → enroll TOTP → you land on the portal.
2. An `admin` user sees 3 tiles, a `manager` sees 4.
3. Click a tile → the app opens showing your username, **no second login**.
4. As `admin`, open `https://finance.<BASE_DOMAIN>` directly → Authentik
   denies access (group binding).
5. *Log out* in the portal → opening the portal **or any app** requires
   logging in again (single logout).
6. Auth events and app redirects are in `logs/portal/portal.log`.

### 2.9 Access overview (who can use which app) — optional

The portal has an admin-only **Access overview** page (`/access`, linked from
the top of the portal for `admin` users). For every app in
[apps.yaml](apps.yaml) it lists the users who can open it, reconstructed from
the Authentik group(s) bound to that app — something Authentik's own admin UI
does not show as a single screen. It reflects **access only**; in-app roles
stay each application's own concern.

It needs a read-only Authentik API token:

1. *Directory → Users → Create a service account* (e.g. `portal-readonly`).
   Add it to a group, or grant it the *Can view Group* / *Can view User*
   permissions (read-only is enough — it never writes).
2. *Directory → Tokens and App passwords → Create* → assign it to that service
   account, intent **API**. Copy the token key.
3. Put it in `.env` as `AUTHENTIK_API_TOKEN=...` and reload:
   `docker compose up -d portal`.

Leave `AUTHENTIK_API_TOKEN` empty to keep the page disabled (it then shows a
"not configured" notice instead of querying Authentik).

---

## 3. Add a fifth application later

Example: `TimeTracker` on internal port 3006, managers only.
(Ports 3001–3005 are in use: factorydocs/inventory/finance/maintenance/omv.)

1. **docker-compose.yml** — add a service (copy `app-maintenance`, reuse the
   stub image or point `build:` at the real app):

   ```yaml
   app-timetracker:
     image: appportal-stubapp
     pull_policy: never
     restart: unless-stopped
     environment:
       APP_NAME: TimeTracker
       PORT: "3006"
       BASE_DOMAIN: ${BASE_DOMAIN}
     networks: [appnet]
   ```

2. **nginx/templates/30-apps.conf.template** — copy a server block; set
   `server_name timetracker.${BASE_DOMAIN};` and
   `set $app_upstream http://app-timetracker:3006;`.
3. **certs**: add the new subdomain to the cert by extending the default
   `SUBDOMAINS` list in `scripts/generate-certs.sh` (or set `CERT_SUBDOMAINS`
   in `.env`); the existing CA is reused, so no browser re-import is needed.
4. **apps.yaml** — add an entry with `id`, `name`, `subdomain: timetracker`
   and `roles: [manager]`. (Picked up automatically, no restart needed.)
5. **Authentik** — repeat §2.6 (proxy provider + application + add to the
   embedded outpost) and §2.7 (group binding) for the new app. (You can copy
   `scripts/add-omv-app.py` as a template for scripting this.)
6. Apply: `docker compose up -d certgen app-timetracker && docker compose restart nginx`

No portal code changes are required.

## 3a. OMV Pipeline (placeholder → real app)

The **OMV Pipeline** tile is already wired as the fifth app, but its upstream
is a placeholder stub (`app-omv`) — the real Flask/SocketIO dashboard runs on
the Linux data server. Everything around it is done: the `omv` subdomain,
TLS SAN, forward-auth server block, Authentik proxy provider/application,
group binding (admin + manager), and outpost assignment.

To make the tile open the **real** OMV dashboard:

1. **Network**: ensure the OMV server is reachable from wherever the portal
   runs (the AWS VM in production). Note its `host:port`.
2. **nginx/templates/30-apps.conf.template** — in the `omv` server block,
   change `set $app_upstream http://app-omv:3005;` to
   `set $app_upstream http://<omv-server-ip>:<port>;`, then
   `docker compose restart nginx`.
3. **Remove the stub**: delete the `app-omv` service from docker-compose.yml
   (and its `depends_on`/alias lines) once the real upstream is in place.
4. **SSO integration (one-time code change in the OMV app)**: the OMV app has
   its own login + TOTP. To use the portal's single sign-on instead, make the
   OMV Flask app trust the `X-authentik-username`/`-email`/`-groups` headers
   that forward auth injects, and disable its own `/login` + TOTP gate. Until
   that change lands, users would face a second login at the OMV app.

## 4. Operations notes

- **Logs**: `logs/portal/portal.log` (AUTH_LOGIN, AUTH_LOGOUT, APP_REDIRECT,
  ACCESS_DENIED) — also visible via `docker compose logs portal`.
- **Verification scripts** (run from this directory, inside WSL/Linux):
  `sh scripts/smoke-test.sh` (endpoints + TLS), `sh scripts/flow-test.sh`
  (OIDC and forward-auth redirect chains),
  `docker compose exec -T portal python < scripts/e2e-test.py` (full login
  journey — only works before TOTP enforcement; afterwards use
  `docker compose exec -T portal python < scripts/totp-probe.py`).
- **Secrets** live only in `.env` (gitignored). Never commit it.
- **Sessions**: portal cookie is Secure + HttpOnly, capped at 8h; Authentik
  session capped at 8h (§2.4). HTTP always redirects to HTTPS.
- **Let's Encrypt later**: replace `certs/fullchain.pem` and
  `certs/privkey.pem` with certbot output (same filenames), remove the
  `REQUESTS_CA_BUNDLE` line from the portal service, then
  `docker compose restart nginx portal`.
- **Backup**: the Docker volumes `postgres-data` (all Authentik config/users)
  and `authentik-data` are the state that matters.
