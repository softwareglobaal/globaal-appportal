"""Registreer de Items-tegel in Authentik (forward-auth proxy-provider).

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-items-app.py

Idempotent: veilig om opnieuw te draaien. Maakt de tegel 'Items' in de launcher,
toegankelijk voor de groepen admin/manager/items. De beheer-app leest de gebruiker
uit de X-authentik-* headers; bewerken is niet extra afgeschermd (EDITOR_GROUPS
leeg), dus iedereen die de tegel mag openen mag ook bewerken.
"""
import os

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG = "items"
NAME = "Items"
ROLES = ("admin", "manager", "items")

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
print("embedded outpost: items-proxy toegevoegd")
print("ITEMS_APP_DONE")
