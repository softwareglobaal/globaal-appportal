"""Registreer de forward-auth voor het MCP-endpoint van RenoVision.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-renovision-mcp.py

Idempotent: veilig om opnieuw te draaien.

Collega's passen hun eigen kopie van RenoVision aan via Claude (aangepaste
connector op https://renovision-mcp.globaal.be/mcp). Alleen de loginstap
/oauth/authorize staat achter deze forward-auth; daar wordt vastgesteld wie er
koppelt, en die naam bepaalt in welke kopie diegene terechtkomt.

Toegang: elke groep die met 'renovision' begint, plus admin. Dat zijn precies
de groepen die `add-renovision-<naam>-app.py` per kopie aanmaakt, dus een
nieuwe collega met een eigen kopie krijgt hier vanzelf toegang. De MCP-server
controleert daarna nog een keer of er echt een kopie voor die gebruiker staat.

Geen launch-url: dit is geen tegel in de launcher, alleen de poortwachter voor
de connector-koppeling.
"""
from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

SLUG = "renovision-mcp"
NAME = "RenoVision via Claude"
HOST = "https://renovision-mcp.globaal.be"

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=HOST)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow

proxy, created = ProxyProvider.objects.get_or_create(
    name=f"{SLUG}-proxy", defaults=defaults)
proxy.external_host = HOST
proxy.set_oauth_defaults()
proxy.save()
print(f"proxy {SLUG}-proxy: {'aangemaakt' if created else 'bestond al'}")

app, _ = Application.objects.get_or_create(
    slug=SLUG, defaults=dict(name=NAME, provider=proxy))
app.provider = proxy
app.save()
print(f"app {SLUG}: forward-auth voor {HOST}")

groepen = sorted(
    set(Group.objects.filter(name__startswith="renovision")
        .values_list("name", flat=True)) | {"admin"})
for naam in groepen:
    g, _ = Group.objects.get_or_create(name=naam)
    PolicyBinding.objects.get_or_create(target=app, group=g, defaults=dict(order=0))
print("toegang: " + ", ".join(groepen))

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("RENOVISION_MCP_DONE")
