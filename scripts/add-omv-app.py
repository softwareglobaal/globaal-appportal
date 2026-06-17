"""Add ONLY the OMV Pipeline forward-auth app to Authentik.

Surgical on purpose: creates the omv proxy provider + application + group
bindings and assigns it to the embedded outpost, WITHOUT touching the MFA/TOTP
stage, session settings, or other providers (so it won't undo a temporary
TOTP-disabled state). Idempotent.

Run: sh scripts/ak-exec.sh scripts/add-omv-app.py
"""
import os

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")
SLUG, NAME, SUB, ROLES = "omv", "OMV Pipeline", "omv", ["admin", "manager"]

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

defaults = dict(
    authorization_flow=auth_flow,
    mode="forward_single",
    external_host=f"https://{SUB}.{BASE_DOMAIN}",
)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, created = ProxyProvider.objects.get_or_create(name=f"{SLUG}-proxy", defaults=defaults)
proxy.set_oauth_defaults()
proxy.save()
app, _ = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME, provider=proxy))
if app.provider_id != proxy.pk:
    app.provider = proxy
    app.save()

for gname in ROLES:
    group = Group.objects.filter(name=gname).first()
    if group:
        PolicyBinding.objects.get_or_create(target=app, group=group, defaults=dict(order=0))

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)  # .add() keeps the other apps assigned
print(f"omv proxy provider: {'created' if created else 'exists'}, groups={ROLES}, outpost updated")
print("OMV_APP_DONE")
