"""appsync — the auto-onboarding sync motor.

Receives GitHub push webhooks, reads each app repo's appportal.yaml, and
deterministically registers the app into AppPortal (tile + nginx + cert SAN +
Authentik blueprint). Jobs run one at a time (queue.py) as a shared-account
mitigation; the live apply step is delegated to a Deployer (deployer.py).

The webhook signature is verified with HMAC-SHA256 against APPSYNC_WEBHOOK_SECRET.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

from flask import Flask, abort, request

import manifest as manifest_mod
from deployer import Deployer, GitHubDeployer, LoggingDeployer
from jobqueue import SerialWorker
from register import Registry

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("appsync")

REPO_ROOT = os.environ.get("APPSYNC_REPO_ROOT", "/app/portal-repo")
BASE_DOMAIN = os.environ.get("APPSYNC_BASE_DOMAIN", "globaal.be")
WEBHOOK_SECRET = os.environ.get("APPSYNC_WEBHOOK_SECRET", "")
# Only act on pushes to branches Claude Code writes (preview) or main (publish).
WATCH_PREFIXES = tuple(
    p.strip()
    for p in os.environ.get("APPSYNC_WATCH_PREFIXES", "refs/heads/claude/,refs/heads/main").split(",")
    if p.strip()
)
# Repos that are NOT apps and must never be onboarded (matched on the short
# name). The portal repo itself is ignored by default: a webhook accidentally
# added there would otherwise register the whole stack as a bogus "app".
IGNORE_REPOS = set(
    r.strip().split("/")[-1]
    for r in os.environ.get("APPSYNC_IGNORE_REPOS", "globaal-appportal").split(",")
    if r.strip()
)

app = Flask(__name__)
worker = SerialWorker()
worker.start()


def _make_deployer() -> Deployer:
    token = os.environ.get("APPSYNC_GITHUB_TOKEN")
    if os.environ.get("APPSYNC_MODE") == "vm" and token:
        return GitHubDeployer(token)
    if os.environ.get("APPSYNC_MODE") == "vm":
        log.warning("APPSYNC_MODE=vm but APPSYNC_GITHUB_TOKEN unset; log-only mode")
    return LoggingDeployer()


deployer = _make_deployer()


def verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Constant-time check of GitHub's X-Hub-Signature-256 header."""
    if not WEBHOOK_SECRET:
        # Fail closed: an unset secret must never accept unsigned calls.
        log.error("APPSYNC_WEBHOOK_SECRET is not set; rejecting webhook")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _onboard(repo_full_name: str, ref: str) -> None:
    """One queued job: fetch manifest, register, and apply live."""
    branch = ref.split("/", 2)[-1]
    repo_name = repo_full_name.split("/")[-1]
    log.info("onboarding %s@%s", repo_full_name, branch)

    text = deployer.fetch_manifest(repo_full_name, branch)
    try:
        m = manifest_mod.load_manifest_text(text or "", repo_name=repo_name)
    except manifest_mod.ManifestError as exc:
        log.error("skipping %s: bad manifest: %s", repo_full_name, exc)
        return

    written = Registry(REPO_ROOT, BASE_DOMAIN).apply(m)
    log.info("registered %s -> %s", m.id, written)
    deployer.apply(m.id)
    log.info("applied %s live", m.id)


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data()
    if not verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        abort(401)
    if request.headers.get("X-GitHub-Event") == "ping":
        return {"status": "pong"}
    if request.headers.get("X-GitHub-Event") != "push":
        return {"status": "ignored"}

    # Parse from the (already signature-verified) body directly, independent of
    # the Content-Type header GitHub happens to send.
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        abort(400)
    ref = payload.get("ref", "")
    repo_full_name = (payload.get("repository") or {}).get("full_name")
    if not repo_full_name or not ref.startswith(WATCH_PREFIXES):
        return {"status": "ignored", "ref": ref}
    if repo_full_name.split("/")[-1] in IGNORE_REPOS:
        log.info("ignoring push to non-app repo %s", repo_full_name)
        return {"status": "ignored", "repo": repo_full_name, "reason": "not-an-app"}

    worker.submit(lambda: _onboard(repo_full_name, ref))
    return {"status": "queued", "repo": repo_full_name, "ref": ref, "depth": worker.depth()}


@app.route("/healthz")
def healthz():
    return {"status": "ok", "queue_depth": worker.depth()}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
