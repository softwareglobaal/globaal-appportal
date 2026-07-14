"""Registreer het Communicatie-dashboard in Authentik (forward-auth proxy-provider).

Draaien (vanuit ~/appportal):
  docker compose cp scripts/add-communicatie-app.py authentik-server:/tmp/c.py
  docker compose exec authentik-server ak shell -c "exec(open('/tmp/c.py').read())"

Idempotent: veilig om opnieuw te draaien. Maakt de tegel 'Communicatie' in de
launcher, toegankelijk voor de groepen admin/manager/communicatie. Maakt ook de
groep 'communicatie-editors' aan (bewerken; leden voeg je toe in Authentik).
"""
import os

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG = "communicatie"
NAME = "Communicatie"
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
proxy.set_oauth_defaults()  # genereert de juiste redirect_uris voor de external_host
proxy.save()
print(f"proxy {SLUG}-proxy: {'created' if created else 'exists'}")

app, _ = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME, provider=proxy))
app.provider = proxy
app.meta_launch_url = f"https://{SLUG}.{BASE_DOMAIN}"  # klikbaar in de launcher
app.save()
print(f"app {SLUG}: launch-url https://{SLUG}.{BASE_DOMAIN}")

for gname in ROLES:
    g, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=g, defaults=dict(order=0))
print(f"group-bindings: {', '.join(ROLES)}")

# Editors-groep: wie mag bewerken (gecheckt door de app zelf via EDITOR_GROUPS).
Group.objects.get_or_create(name="communicatie-editors")
print("groep communicatie-editors: aanwezig")

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("embedded outpost: communicatie-proxy toegevoegd")
print("COMMUNICATIE_APP_DONE")
