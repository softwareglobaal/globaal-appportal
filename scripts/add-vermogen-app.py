"""Registreer het Vermogens-dashboard in Authentik (forward-auth proxy-provider).

Draaien (vanuit ~/appportal):
  docker compose cp scripts/add-vermogen-app.py authentik-server:/tmp/v.py
  docker compose exec authentik-server ak shell -c "exec(open('/tmp/v.py').read())"

Idempotent: veilig om opnieuw te draaien. Maakt de tegel 'Vermogen' in de
launcher, toegankelijk voor de groepen admin/manager/vermogen. Maakt ook de
groep 'vermogen-editors' aan (bewerken; leden voeg je toe in Authentik -
Mehdi hoort daarin, hij levert de data).
"""
import os

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG = "vermogen"
NAME = "Vermogen"
ROLES = ("admin", "manager", "vermogen")

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
Group.objects.get_or_create(name="vermogen-editors")
print("groep vermogen-editors: aanwezig")

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("embedded outpost: vermogen-proxy toegevoegd")
print("VERMOGEN_APP_DONE")
