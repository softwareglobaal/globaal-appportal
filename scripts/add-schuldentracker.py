from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider
import secrets

BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name="schuldentracker")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://schuldentracker.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="schuldentracker-proxy", defaults=defaults)
proxy.external_host = f"https://schuldentracker.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="schuldentracker",
    defaults=dict(name="Schuldentracker", provider=proxy,
                  meta_launch_url=f"https://schuldentracker.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://schuldentracker.{BASE}"
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)

for uname in ("mehdi", "angela"):
    u, new = User.objects.get_or_create(username=uname, defaults=dict(name=uname.title()))
    if new:
        pw = secrets.token_urlsafe(12)
        u.set_password(pw)
        u.save()
        print(f"USER {uname} aangemaakt - tijdelijk wachtwoord: {pw}")
    else:
        print(f"USER {uname} bestond al")
    u.groups.add(grp)
print("SCHULDENTRACKER_DONE")
