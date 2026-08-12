"""Registreer de QuickBooks-connector in Authentik (forward-auth proxy-provider).

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-quickbooks-app.py

Idempotent. Dezelfde groep als de boekhouding-tegel (`boekhouding`), want het
zijn dezelfde mensen: dit is het tweede boekhoudsysteem naast Octopus, voor HDS.
Geen aparte groep dus, anders moet elk nieuw personeelslid twee keer toegevoegd
worden voor hetzelfde werk.

Let op: de tegel verschijnt hiermee in de launcher. De pagina's /privacy en
/terms blijven publiek; die gaan in nginx buiten de forward-auth om.
"""
import os

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG = "quickbooks"
NAME = "QuickBooks"
ROLES = ("admin", "manager", "boekhouding")

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

proxy_defaults = dict(
    authorization_flow=auth_flow,
    mode="forward_single",
    external_host=f"https://{SLUG}.{BASE_DOMAIN}",
)
if inval_flow:
    proxy_defaults["invalidation_flow"] = inval_flow
proxy, created = ProxyProvider.objects.get_or_create(
    name=f"{SLUG}-proxy", defaults=proxy_defaults
)
proxy.set_oauth_defaults()
proxy.save()
print(f"proxy {SLUG}-proxy: {'created' if created else 'exists'}")

app, _ = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME, provider=proxy))
app.provider = proxy
app.meta_launch_url = f"https://{SLUG}.{BASE_DOMAIN}"
app.save()
print(f"app {SLUG}: launch-url https://{SLUG}.{BASE_DOMAIN}")

for gname in ROLES:
    g, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=g, defaults=dict(order=0))
print(f"group-bindings: {', '.join(ROLES)}")

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("embedded outpost: quickbooks-proxy toegevoegd")
print("QUICKBOOKS_APP_DONE")
