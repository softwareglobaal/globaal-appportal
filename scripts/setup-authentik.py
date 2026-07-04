"""One-time Authentik configuration, applied programmatically.

This mirrors README section 2 (groups, portal OIDC provider, per-app
forward-auth proxy providers, embedded-outpost assignment, group bindings).
Run it inside the authentik-server container:

    docker compose cp scripts/setup-authentik.py authentik-server:/tmp/setup.py
    docker compose exec authentik-server ak shell -c "exec(open('/tmp/setup.py').read())"

Idempotent: safe to re-run.
"""
import os

from authentik.core.models import Application, Group
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import OAuth2Provider
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")

APPS = [
    # (slug, name, subdomain, groups)
    ("factorydocs", "FactoryDocs", "factorydocs", ["admin", "manager"]),
    ("inventory", "InventoryTracker", "inventory", ["admin", "manager"]),
    ("finance", "FinanceDashboard", "finance", ["manager"]),
    ("maintenance", "MaintenanceLog", "maintenance", ["admin", "manager"]),
    ("omv", "OMV Pipeline", "omv", ["admin", "manager"]),
]

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
# The portal's end-session must end the WHOLE authentik session (single
# logout), not just the portal's own OAuth session - hence the global
# invalidation flow, not the provider one.
global_inval_flow = Flow.objects.filter(slug="default-invalidation-flow").first()
signing_key = CertificateKeyPair.objects.filter(
    name="authentik Self-signed Certificate"
).first()

groups = {}
for gname in ("admin", "manager"):
    groups[gname], created = Group.objects.get_or_create(name=gname)
    print(f"group {gname}: {'created' if created else 'exists'}")

# --- portal OIDC provider + application -------------------------------------
oidc_defaults = dict(
    authorization_flow=auth_flow,
    client_type="confidential",
    signing_key=signing_key,
)
if global_inval_flow:
    oidc_defaults["invalidation_flow"] = global_inval_flow
oidc, created = OAuth2Provider.objects.get_or_create(
    name="portal-oidc", defaults=oidc_defaults
)
if global_inval_flow and oidc.invalidation_flow_id != global_inval_flow.pk:
    oidc.invalidation_flow = global_inval_flow
try:
    from authentik.providers.oauth2.models import RedirectURI, RedirectURIMatchingMode

    oidc.redirect_uris = [
        RedirectURI(
            RedirectURIMatchingMode.STRICT,
            f"https://portal.{BASE_DOMAIN}/auth/callback",
        )
    ]
except ImportError:  # older field format
    oidc.redirect_uris = f"https://portal.{BASE_DOMAIN}/auth/callback"
# The UI preselects these; the ORM default is an empty list, which makes
# every authorize request fail with error=invalid_request.
if hasattr(oidc, "grant_types"):
    oidc.grant_types = ["authorization_code", "refresh_token"]
oidc.save()
# Scope mappings: the UI adds these defaults automatically, the ORM does not.
# Without them every requested scope is dropped and authorize requests fail
# with error=invalid_request.
from authentik.providers.oauth2.models import ScopeMapping

oidc.property_mappings.set(
    ScopeMapping.objects.filter(
        managed__in=[
            "goauthentik.io/providers/oauth2/scope-openid",
            "goauthentik.io/providers/oauth2/scope-profile",
            "goauthentik.io/providers/oauth2/scope-email",
        ]
    )
)
Application.objects.get_or_create(
    slug="portal", defaults=dict(name="Portal", provider=oidc)
)
print(f"portal oidc provider: {'created' if created else 'exists'}")
print(f"OIDC_CLIENT_ID={oidc.client_id}")
print(f"OIDC_CLIENT_SECRET={oidc.client_secret}")

# --- per-app forward-auth proxy providers + applications ---------------------
proxies = []
for slug, name, sub, roles in APPS:
    proxy_defaults = dict(
        authorization_flow=auth_flow,
        mode="forward_single",
        external_host=f"https://{sub}.{BASE_DOMAIN}",
    )
    if inval_flow:
        proxy_defaults["invalidation_flow"] = inval_flow
    proxy, created = ProxyProvider.objects.get_or_create(
        name=f"{slug}-proxy", defaults=proxy_defaults
    )
    proxy.set_oauth_defaults()
    proxy.save()
    proxies.append(proxy)
    app, _ = Application.objects.get_or_create(
        slug=slug, defaults=dict(name=name, provider=proxy)
    )
    for gname in roles:
        PolicyBinding.objects.get_or_create(
            target=app, group=groups[gname], defaults=dict(order=0)
        )
    print(f"app {slug}: {'created' if created else 'exists'}, groups={roles}")

# --- enforce TOTP 2FA (README 2.3) -------------------------------------------
from authentik.stages.authenticator_totp.models import AuthenticatorTOTPStage
from authentik.stages.authenticator_validate.models import AuthenticatorValidateStage

mfa = AuthenticatorValidateStage.objects.filter(
    name="default-authentication-mfa-validation"
).first()
totp_setup = AuthenticatorTOTPStage.objects.filter(
    name="default-authenticator-totp-setup"
).first()
if mfa and totp_setup:
    mfa.not_configured_action = "configure"
    mfa.save()
    mfa.configuration_stages.set([totp_setup])
    print("mfa: users without an authenticator are forced to enroll TOTP")

# --- cap the Authentik session at 8 hours (README 2.4) ------------------------
from authentik.stages.user_login.models import UserLoginStage

UserLoginStage.objects.filter(name="default-authentication-login").update(
    session_duration="hours=8"
)
print("session duration: hours=8 on default-authentication-login")

# --- assign all proxy providers to the embedded outpost ----------------------
outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(*proxies)
cfg = outpost.config
cfg.authentik_host = f"https://auth.{BASE_DOMAIN}"
cfg.authentik_host_insecure = False
outpost.config = cfg
outpost.save()
print("embedded outpost: providers assigned, authentik_host set")
print("SETUP_DONE")
