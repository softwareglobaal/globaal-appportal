"""Fetching the app manifest from GitHub.

The webhook payload does not carry file contents, so to read a repo's
``appportal.yaml`` appsync fetches it from GitHub. Writing the artifacts is
done by register.py; making them *live* (reissue cert + reload nginx) is done
by a host-side watcher (scripts/appsync-apply.sh via systemd), NOT from inside
this container — that keeps the Docker socket out of appsync.

Two implementations:
  * LoggingDeployer  — default / CI: cannot reach GitHub, logs intent. With no
    manifest, register falls back to inferring defaults from the repo name.
  * GitHubDeployer    — on the VM (APPSYNC_MODE=vm): reads appportal.yaml via the
    GitHub contents API using APPSYNC_GITHUB_TOKEN.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger("appsync.deployer")


class Deployer:
    def fetch_manifest(self, repo_full_name: str, ref: str) -> str | None:
        """Return the raw appportal.yaml at ref, or None if absent."""
        raise NotImplementedError

    def apply(self, app_id: str) -> None:
        """Signal that registration files changed (host watcher applies them)."""
        raise NotImplementedError


class LoggingDeployer(Deployer):
    """Default for non-VM environments: log intent, touch nothing external."""

    def fetch_manifest(self, repo_full_name: str, ref: str) -> str | None:
        log.info("would fetch appportal.yaml from %s@%s", repo_full_name, ref)
        return None

    def apply(self, app_id: str) -> None:
        log.info("registration written for %s (log-only mode; host would apply)", app_id)


class GitHubDeployer(Deployer):
    """Reads appportal.yaml from GitHub; the host watcher reloads nginx/certs."""

    def __init__(self, token: str, api_base: str = "https://api.github.com"):
        self._token = token
        self._api = api_base.rstrip("/")

    def fetch_manifest(self, repo_full_name: str, ref: str) -> str | None:
        path = urllib.parse.quote("appportal.yaml")
        ref_q = urllib.parse.quote(ref, safe="")
        url = f"{self._api}/repos/{repo_full_name}/contents/{path}?ref={ref_q}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github.raw+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                log.info("no appportal.yaml in %s@%s; will infer from name",
                         repo_full_name, ref)
                return None
            log.error("GitHub fetch failed for %s@%s: HTTP %s",
                      repo_full_name, ref, exc.code)
            raise
        except urllib.error.URLError as exc:
            log.error("GitHub fetch error for %s@%s: %s", repo_full_name, ref, exc)
            raise

    def apply(self, app_id: str) -> None:
        # The artifacts (apps.d, nginx template, cert SAN, blueprint) are already
        # on disk; the host path-watcher reissues the cert and reloads nginx, and
        # Authentik auto-discovers the new blueprint. Nothing to do from here.
        log.info("registration written for %s; host watcher will apply", app_id)
