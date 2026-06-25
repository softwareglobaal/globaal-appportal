# appsync — auto-onboarding sync motor

Receives GitHub push webhooks and registers apps into AppPortal automatically:
portal tile + nginx server block + TLS SAN + Authentik blueprint — no manual
work per app. See `../docs/auto-onboarding-plan.md` for the full design.

## Flow
```
GitHub push (claude/* or main)  ──webhook (HMAC)──►  appsync /webhook
   → read appportal.yaml from the repo (or infer from the repo name)
   → queue one job (jobs are serialized: shared-account mitigation)
   → register.py writes, idempotently, from apps.d as the source of truth:
        apps.d/<id>.yaml                        (portal tile, merged live)
        nginx/templates/50-autoapps.conf.template
        certs/extra-subdomains                  (folded into the TLS cert)
        authentik/blueprints/<id>.yaml          (proxy + app + group binding)
   → deployer.apply(): on the VM, reissue cert + reload nginx + (re)start app
```

## Configuration (env)
| Var | Meaning |
|-----|---------|
| `APPSYNC_WEBHOOK_SECRET` | HMAC secret; must match the GitHub webhook secret. |
| `APPSYNC_REPO_ROOT` | Where the portal repo working tree is mounted (default `/app/portal-repo`). |
| `APPSYNC_WATCH_PREFIXES` | Comma-separated ref prefixes that trigger a sync. |
| `APPSYNC_MODE` | Empty = safe log-only apply; `vm` = run live commands. |
| `APPSYNC_CHECKOUT_ROOT` | (vm mode) where app repos are cloned. |

## GitHub setup
Add an **organization webhook**: payload URL `https://sync.<BASE_DOMAIN>/webhook`,
content type `application/json`, secret = `APPSYNC_WEBHOOK_SECRET`, events =
*Pushes*. One org webhook covers every current and future app repo.

## Develop / test
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest tests -q
```
The whole deterministic core (manifest → generate → register, and the webhook
HMAC check) runs without Docker or Authentik. The live apply step
(`deployer.ShellDeployer`) only runs on the VM.
