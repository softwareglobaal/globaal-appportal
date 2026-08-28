from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
NAAM = "raisha"
HOST = f"https://renovision-{NAAM}.{BASE}"

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name=f"renovision-{NAAM}")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=HOST)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(
    name=f"renovision-{NAAM}-proxy", defaults=defaults)
proxy.external_host = HOST
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug=f"renovision-{NAAM}",
    defaults=dict(name="RenoVision (Raisha)", provider=proxy,
                  meta_launch_url=HOST))
app.provider = proxy
app.meta_launch_url = HOST
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)

u = User.objects.filter(username=NAAM).first()
if u is None:
    print(f"LET OP: gebruiker {NAAM} bestaat niet, groep niet toegekend")
else:
    u.groups.add(grp)
    print(f"USER {NAAM} in groep renovision-{NAAM}")

print("RENOVISION_RAISHA_DONE")
