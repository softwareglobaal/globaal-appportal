"""VM-side effects: fetch the repo and make the registration live.

Fase 1 keeps this behind a small interface. In the CI sandbox there is no
Docker daemon, no Authentik and no checkout of the app repos, so the default
``LoggingDeployer`` only records what *would* happen. On the VM, ``ShellDeployer``
runs the real commands. The deterministic registration (register.py) is fully
exercised either way; only these final apply steps differ per environment.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("appsync.deployer")


class Deployer:
    """Interface for turning a written registration into a live app."""

    def fetch_manifest(self, repo_full_name: str, ref: str) -> str | None:
        """Return the raw appportal.yaml from the repo at ref (or None)."""
        raise NotImplementedError

    def apply(self, app_id: str) -> None:
        """Regenerate certs, reload nginx, (re)start the app, apply blueprints."""
        raise NotImplementedError


class LoggingDeployer(Deployer):
    """Default for non-VM environments: log intent, touch nothing."""

    def fetch_manifest(self, repo_full_name: str, ref: str) -> str | None:
        log.info("would fetch appportal.yaml from %s@%s", repo_full_name, ref)
        return None

    def apply(self, app_id: str) -> None:
        log.info(
            "would: regenerate certs, reload nginx, (re)start app-%s, apply blueprint",
            app_id,
        )


class ShellDeployer(Deployer):
    """Runs the real commands on the VM (where the stack and a git client live)."""

    def __init__(self, repo_root: str | Path, checkout_root: str | Path):
        self.root = Path(repo_root)
        # Where app repos are cloned/pulled, e.g. /srv/appportal/apps/<id>.
        self.checkout_root = Path(checkout_root)

    def fetch_manifest(self, repo_full_name: str, ref: str) -> str | None:
        dest = self.checkout_root / repo_full_name.split("/")[-1]
        url = f"https://github.com/{repo_full_name}.git"
        if dest.is_dir():
            self._run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", ref])
            self._run(["git", "-C", str(dest), "checkout", "-f", "FETCH_HEAD"])
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            self._run(["git", "clone", "--depth", "1", "--branch", ref, url, str(dest)])
        manifest = dest / "appportal.yaml"
        return manifest.read_text(encoding="utf-8") if manifest.is_file() else None

    def apply(self, app_id: str) -> None:
        # certgen reads certs/extra-subdomains; re-run it, then reload nginx so
        # the new server block and SAN take effect, then bring the app up.
        self._run(["docker", "compose", "up", "-d", "certgen"], cwd=self.root)
        self._run(["docker", "compose", "exec", "-T", "nginx", "nginx", "-s", "reload"],
                  cwd=self.root)
        self._run(["docker", "compose", "up", "-d", f"app-{app_id}"], cwd=self.root)

    def _run(self, cmd: list[str], cwd: Path | None = None) -> None:
        log.info("run: %s", " ".join(cmd))
        subprocess.run(cmd, cwd=cwd, check=True)
