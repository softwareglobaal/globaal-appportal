"""Registreer de PROEF van het Communicatie-dashboard in Authentik.

Draaien (vanuit ~/appportal):
  docker compose cp scripts/add-communicatie-proef-app.py authentik-server:/tmp/cp.py
  docker compose exec authentik-server ak shell -c "exec(open('/tmp/cp.py').read())"

Idempotent. Zelfde groepen als de live app (admin/manager/communicatie), zodat
wie live mag kijken ook de proef kan bekijken. Geen eigen editors-groep: de
proef leest EDITOR_GROUPS net als live.
"""
import os

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG = "communicatie-proef"
NAME = "Communicatie (proef)"
ROLES = ("admin", "manager", "communicatie")

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
proxy.external_host = f"https://{SLUG}.{BASE_DOMAIN}"
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
print("embedded outpost: communicatie-proef-proxy toegevoegd")
print("COMMUNICATIE_PROEF_APP_DONE")
