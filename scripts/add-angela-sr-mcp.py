"""Registreer de forward-auth voor het MCP-endpoint van angela.sr.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-angela-sr-mcp.py

Idempotent: veilig om opnieuw te draaien. Angela beheert de site via Claude
(custom connector op https://angela.sr/mcp); de OAuth-loginstap
/oauth/authorize staat in de vhost achter deze forward-auth. Toegang: de
groepen angela en admin. De user angela bestaat al en wordt lid van de
groep angela. Geen launch-url: dit is geen tegel in de launcher, alleen
de poortwachter voor de connector-koppeling.
"""
from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

SLUG = "angela-sr"
NAME = "Angela.sr via Claude"
ROLES = ("admin", "angela")

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

proxy_defaults = dict(
    authorization_flow=auth_flow,
    mode="forward_single",
    external_host="https://angela.sr",
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
app.save()
print(f"app {SLUG}: forward-auth voor https://angela.sr")

for gname in ROLES:
    g, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=g, defaults=dict(order=0))
print(f"group-bindings: {', '.join(ROLES)}")

angela = User.objects.filter(username="angela").first()
groep = Group.objects.get(name="angela")
if angela:
    angela.ak_groups.add(groep)
    print("user angela: lid van groep angela")
else:
    print("LET OP: user angela bestaat niet; maak die aan en zet hem in groep angela")

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("embedded outpost: angela-sr-proxy toegevoegd")
print("ANGELA_SR_MCP_DONE")
