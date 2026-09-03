"""Registreer de forward-auth voor het MCP-endpoint van Pipedrive.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-pipedrive-mcp.py

Idempotent: veilig om opnieuw te draaien.

Alleen de loginstap /oauth/authorize staat achter deze forward-auth; daar wordt
vastgesteld wie er koppelt.

**Toegang gaat op naam, niet per groep**: dit script maakt alleen de app en de
provider. Wie erbij mag zet je met `scripts/set-pipedrive-mcp-toegang.py`
(sinds 03-09-2026 alleen mehdi), en dezelfde namen horen in `MCP_GEBRUIKERS` in
~/pipedrive-mcp.env te staan - de server toetst zelf nog een keer. De eerste
opzet bond hier de groepen sales en admin aan, waarmee elf mensen konden
meelezen in de verkoopadministratie; dat was te ruim.

Geen launch-url: dit is geen tegel in de launcher, alleen de poortwachter voor
de connector-koppeling.
"""
from authentik.core.models import Application
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

SLUG = "pipedrive-mcp"
NAME = "Pipedrive via Claude"
HOST = "https://pipedrive-mcp.globaal.be"

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

bindingen = PolicyBinding.objects.filter(target=app).count()
if not bindingen:
    print("LET OP: nog niemand heeft toegang. Draai "
          "scripts/set-pipedrive-mcp-toegang.py")

# .add() en nooit .set([...]): dat laatste zou de andere providers van de
# embedded outpost wissen.
outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("PIPEDRIVE_MCP_DONE")
