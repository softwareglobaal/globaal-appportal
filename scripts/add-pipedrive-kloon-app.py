"""Tegel Pipedrive-kloon (pipedrive.<domein>) in Authentik, met eigen proxy-provider (forward-auth).

De nachtelijke Pipedrive-backup van de vijf firma's in de Pipedrive-kloon (code: ~/pipedrive-kloon). Bevat
persoonsgegevens van klanten, dus smal: admin, manager en de groep pipedrive-kloon. Die groep begint leeg; iemand
toegang geven = in die groep zetten (docs/TOEGANG-GEVEN.md).

Draaien:  sh scripts/ak-exec.sh scripts/add-pipedrive-kloon-app.py
Idempotent. Zelfde opbouw als add-felix-app.py.
"""
import os
from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG, NAME, SUB = "pipedrive-kloon", "Pipedrive-kloon", "pipedrive"
ROLES = ["admin", "manager", "pipedrive-kloon"]

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
defaults = dict(authorization_flow=auth_flow, mode="forward_single", external_host=f"https://{SUB}.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, created = ProxyProvider.objects.get_or_create(name=f"{SLUG}-proxy", defaults=defaults)
proxy.external_host = f"https://{SUB}.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME, provider=proxy, meta_launch_url=f"https://{SUB}.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://{SUB}.{BASE}"
app.meta_description = "De Pipedrive-backup van de vijf firma's, elke nacht ververst"
app.save()

for gname in ROLES:
    grp, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
# Zonder save kende de embedded outpost een nieuw domein na 4 minuten nog niet (add-felix-app.py, 13-10-2026).
outpost.save()
print("APP:", app.slug, "| provider:", "created" if created else "exists", "| roles:", ROLES)
print("PIPEDRIVE_KLOON_DONE")
