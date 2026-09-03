"""Registreer de forward-auth voor het MCP-endpoint van Pipedrive.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-pipedrive-mcp.py

Idempotent: veilig om opnieuw te draaien.

Collega's benaderen de vijf Pipedrive-administraties via Claude (aangepaste
connector op https://pipedrive-mcp.globaal.be/mcp). Alleen de loginstap
/oauth/authorize staat achter deze forward-auth; daar wordt vastgesteld wie er
koppelt en welke groepen diegene heeft. Die groepen gaan mee in het token:
`pipedrive-editors` of `admin` mag ook schrijven, de rest leest alleen.

Twee groepen, dus:
  pipedrive          - lezen (deals, contacten, activiteiten, notities)
  pipedrive-editors  - lezen en wijzigen

Geen launch-url: dit is geen tegel in de launcher, alleen de poortwachter voor
de connector-koppeling.
"""
from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

SLUG = "pipedrive-mcp"
NAME = "Pipedrive via Claude"
HOST = "https://pipedrive-mcp.globaal.be"
GROEPEN = ["pipedrive", "pipedrive-editors", "sales", "admin"]

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=HOST)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow

proxy, created = ProxyProvider.objects.get_or_create(
    name=f"{SLUG}-proxy", defaults=defaults)
proxy.external_host = HOST
# De ORM-create roept set_oauth_defaults() niet aan (de UI-serializer wel);
# zonder deze regel blijft redirect_uris leeg en geeft inloggen een
# "Redirect URI Error". Zie de sales-app, waar dat een keer misging.
proxy.set_oauth_defaults()
proxy.save()
print(f"proxy {SLUG}-proxy: {'aangemaakt' if created else 'bestond al'}")

app, _ = Application.objects.get_or_create(
    slug=SLUG, defaults=dict(name=NAME, provider=proxy))
app.provider = proxy
app.save()
print(f"app {SLUG}: forward-auth voor {HOST}")

for naam in GROEPEN:
    g, _ = Group.objects.get_or_create(name=naam)
    PolicyBinding.objects.get_or_create(target=app, group=g, defaults=dict(order=0))
print("toegang: " + ", ".join(GROEPEN))

# .add() en nooit .set([...]): dat laatste zou de andere providers van de
# embedded outpost wissen.
outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("PIPEDRIVE_MCP_DONE")
