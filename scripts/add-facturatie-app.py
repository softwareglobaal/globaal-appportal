from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name="facturatie")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://facturatie.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="facturatie-proxy", defaults=defaults)
proxy.external_host = f"https://facturatie.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="facturatie",
    defaults=dict(name="Facturatie", provider=proxy,
                  meta_launch_url=f"https://facturatie.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://facturatie.{BASE}"
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)

for uname in ("mehdi", "akadmin"):
    u = User.objects.filter(username=uname).first()
    if u:
        u.groups.add(grp)
        print(f"USER {uname} -> groep facturatie")
    else:
        print(f"USER {uname} niet gevonden (sla over)")
print("FACTURATIE_DONE")
