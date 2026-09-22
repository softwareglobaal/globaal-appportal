"""Registreer de Octopus-tegel in Authentik (forward-auth proxy-provider).

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-octopus-app.py

Dit is een tweede naam voor dezelfde app als add-boekhouding-app.py. De
MCP-server gaat over Octopus en heet naar buiten octopus.<domein>; de oude
naam boekhouding.<domein> blijft bestaan zodat bestaande koppelingen en
bladwijzers blijven werken. Forward-auth werkt per external_host, vandaar een
eigen provider voor de tweede naam.

Idempotent: veilig om opnieuw te draaien. Toegang via dezelfde groepen als de
Boekhouding-tegel; de app controleert daarnaast zelf nog eens op de groep.
"""
import os

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG = "octopus"
NAME = "Octopus"
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
print("embedded outpost: octopus-proxy toegevoegd")
print("OCTOPUS_APP_DONE")
