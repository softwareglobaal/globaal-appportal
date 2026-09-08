"""Registreer de forward-auth voor het MCP-endpoint van het portaal.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-portal-mcp.py

Idempotent: veilig om opnieuw te draaien.

Alleen de loginstap /oauth/authorize staat achter deze forward-auth; daar wordt
vastgesteld wie er koppelt. /mcp zelf blijft erbuiten, want een MCP-client heeft
geen Authentik-sessie: die stuurt een bearer-token en de dienst controleert dat
zelf.

**Wie erdoor mag is niet hetzelfde als wie wat ziet.** Deze binding bepaalt
alleen wie de connector mag koppelen. Wat iemand daarna te lezen krijgt, komt
bij elke aanroep opnieuw uit Authentik: precies de applicaties waarvan hij ook
de tegel ziet. Iemand toevoegen is dus ongevaarlijk in de zin dat hij daarmee
geen enkele app extra krijgt.

Begonnen met de groep `portaal-mcp` plus admin en manager. Wil je iemand
toelaten, zet hem in die groep; dat is de gewone weg in Authentik en vraagt geen
wijziging hier.

Geen launch-url: dit is geen tegel in de launcher, alleen de poortwachter voor
de connector-koppeling.
"""
from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

SLUG = "portal-mcp"
NAAM = "Portaal via Claude"
HOST = "https://portal-mcp.globaal.be"
GROEPEN = ("portaal-mcp", "admin", "manager")

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=HOST)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow

proxy, nieuw = ProxyProvider.objects.get_or_create(
    name=f"{SLUG}-proxy", defaults=defaults)
proxy.external_host = HOST
# De ORM-create roept set_oauth_defaults() niet aan (de UI-serializer wel);
# zonder deze regel blijft redirect_uris leeg en geeft inloggen een
# "Redirect URI Error". Zie 9.14 in TECHNICAL-REFERENCE.md.
proxy.set_oauth_defaults()
proxy.save()
print(f"proxy {SLUG}-proxy: {'aangemaakt' if nieuw else 'bestond al'}")

app, _ = Application.objects.get_or_create(
    slug=SLUG, defaults=dict(name=NAAM, provider=proxy))
app.provider = proxy
app.save()
print(f"app {SLUG}: forward-auth voor {HOST}")

for naam in GROEPEN:
    groep, groep_nieuw = Group.objects.get_or_create(name=naam)
    binding, binding_nieuw = PolicyBinding.objects.get_or_create(
        target=app, group=groep, defaults=dict(order=0))
    stand = "aangemaakt" if binding_nieuw else "bestond al"
    extra = " (groep nieuw)" if groep_nieuw else ""
    print(f"toegang {naam}: {stand}{extra}")

# .add() en nooit .set([...]): dat laatste zou de andere providers van de
# embedded outpost wissen.
outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("PORTAL_MCP_DONE")
