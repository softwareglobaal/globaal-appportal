"""Manifest loading, validation and inference for auto-onboarding.

Each app repo carries an ``appportal.yaml`` (seeded by the repo template in
phase 2). Non-technical makers never write it by hand; when it is missing we
infer safe defaults from the repo name so a push still onboards cleanly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

# A subdomain / id must be a single DNS label: lowercase, digits, hyphens.
_SLUG_RE = re.compile(r"[^a-z0-9-]+")
_VALID_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

# Reserved hostnames already owned by the platform — an app may never claim them.
RESERVED_SUBDOMAINS = {"auth", "portal", "n8n", "status", "www"}


class ManifestError(ValueError):
    """Raised when a manifest cannot be loaded or validated."""


def slugify(value: str) -> str:
    """Turn an arbitrary repo/app name into a valid DNS-label id."""
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


@dataclass
class Manifest:
    id: str
    name: str
    subdomain: str
    port: int
    description: str = ""
    roles: list[str] = field(default_factory=list)
    maker: str | None = None
    # Upstream the reverse proxy points at. Default = the app's own container.
    upstream: str | None = None

    def resolved_upstream(self) -> str:
        return self.upstream or f"app-{self.id}:{self.port}"


def _default_roles(app_id: str) -> list[str]:
    # Access = maker's own per-app group + admins. The maker is added to the
    # <id> group (see authentik blueprint); admins reach every app via "admin".
    return [app_id, "admin"]


def load_manifest(data: dict | None, *, repo_name: str) -> Manifest:
    """Build a validated Manifest from raw YAML data (or infer from repo_name).

    ``repo_name`` is the GitHub repo's short name (without owner), used both as
    a fallback and to default the id/subdomain.
    """
    data = dict(data or {})

    app_id = str(data.get("id") or slugify(repo_name))
    if not app_id:
        raise ManifestError(f"cannot derive an id from repo name {repo_name!r}")
    if not _VALID_ID_RE.match(app_id):
        raise ManifestError(
            f"invalid id {app_id!r}: use lowercase letters, digits and hyphens"
        )

    subdomain = str(data.get("subdomain") or app_id)
    if not _VALID_ID_RE.match(subdomain):
        raise ManifestError(f"invalid subdomain {subdomain!r}")
    if subdomain in RESERVED_SUBDOMAINS:
        raise ManifestError(f"subdomain {subdomain!r} is reserved by the platform")

    raw_port = data.get("port")
    if raw_port is None:
        raise ManifestError("manifest is missing required field 'port'")
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        raise ManifestError(f"port must be an integer, got {raw_port!r}")
    if not (1 <= port <= 65535):
        raise ManifestError(f"port {port} out of range")

    roles = data.get("roles")
    if roles is None:
        roles = _default_roles(app_id)
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        raise ManifestError("roles must be a list of strings")
    if not roles:
        raise ManifestError("roles must not be empty (an app with no roles is invisible)")

    name = str(data.get("name") or repo_name.replace("-", " ").title())
    upstream = data.get("upstream")
    if upstream is not None and not isinstance(upstream, str):
        raise ManifestError("upstream must be a string host:port")

    maker = data.get("maker")
    if maker is not None and not isinstance(maker, str):
        raise ManifestError("maker must be a string (Authentik username)")

    return Manifest(
        id=app_id,
        name=name,
        subdomain=subdomain,
        port=port,
        description=str(data.get("description") or ""),
        roles=roles,
        maker=maker,
        upstream=upstream,
    )


def load_manifest_text(text: str, *, repo_name: str) -> Manifest:
    """Parse appportal.yaml text into a validated Manifest."""
    try:
        data = yaml.safe_load(text) if text and text.strip() else None
    except yaml.YAMLError as exc:
        raise ManifestError(f"appportal.yaml is not valid YAML: {exc}") from exc
    if data is not None and not isinstance(data, dict):
        raise ManifestError("appportal.yaml must be a mapping at the top level")
    return load_manifest(data, repo_name=repo_name)
