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
   → host watcher (vm/appsync-apply.path) reissues cert + reloads nginx;
     Authentik auto-discovers the new blueprint; the portal shows the tile
```

Making it live is deliberately split: appsync (a container) only **writes
files** and reads manifests from GitHub. Reissuing the TLS cert and reloading
nginx happen on the **host** via a systemd path-watcher
(`vm/appsync-apply.path` → `scripts/appsync-apply.sh`), so the Docker socket
never has to be mounted into appsync.

## Configuration (env)
| Var | Meaning |
|-----|---------|
| `APPSYNC_WEBHOOK_SECRET` | HMAC secret; must match the GitHub webhook secret. |
| `APPSYNC_REPO_ROOT` | Where the portal repo working tree is mounted (default `/app/portal-repo`). |
| `APPSYNC_BASE_DOMAIN` | Base domain baked into Authentik blueprints (defaults to `BASE_DOMAIN`). |
| `APPSYNC_WATCH_PREFIXES` | Comma-separated ref prefixes that trigger a sync. |
| `APPSYNC_MODE` | Empty = log-only (infer manifests); `vm` = read appportal.yaml from GitHub. |
| `APPSYNC_GITHUB_TOKEN` | (vm mode) token with `contents:read` to fetch appportal.yaml. |

## GitHub setup
Add an **organization webhook** (Settings → Webhooks → Add webhook):
- Payload URL: `https://sync.<BASE_DOMAIN>/webhook`
- Content type: `application/json`
- Secret: `APPSYNC_WEBHOOK_SECRET`
- Events: *Just the push event*

One org webhook covers every current and future app repo. The endpoint needs a
**publicly trusted TLS cert** (Let's Encrypt — see the main README): GitHub
rejects the local self-signed CA. As an interim, you can disable SSL
verification on the webhook (HMAC still protects payload integrity).

## Develop / test
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest tests -q
```
The whole deterministic core (manifest → generate → register, and the webhook
HMAC check) runs without Docker or Authentik. The live apply step
(`deployer.ShellDeployer`) only runs on the VM.
