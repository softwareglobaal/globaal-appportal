from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name="locatie")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://locatie.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="locatie-proxy", defaults=defaults)
proxy.external_host = f"https://locatie.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(slug="locatie",
    defaults=dict(name="Locatielogboek", provider=proxy,
                  meta_launch_url=f"https://locatie.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://locatie.{BASE}"
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))
Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first().providers.add(proxy)

u = User.objects.filter(username="mehdi").first()
if u:
    u.groups.add(grp)
    print("mehdi toegevoegd aan groep locatie")
else:
    print("LET OP: gebruiker mehdi niet gevonden")
print("LOCATIE_DONE")
