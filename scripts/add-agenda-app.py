from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider
import secrets

BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

access_grp, _ = Group.objects.get_or_create(name="agenda-bekijken")
full_grp, _ = Group.objects.get_or_create(name="agenda-volledig")
arch_grp, _ = Group.objects.get_or_create(name="agenda-architect")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://agenda.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="agenda-proxy", defaults=defaults)
proxy.external_host = f"https://agenda.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="agenda",
    defaults=dict(name="Beschikbaarheid Mehdi", provider=proxy,
                  meta_launch_url=f"https://agenda.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://agenda.{BASE}"
app.save()

PolicyBinding.objects.get_or_create(target=app, group=access_grp, defaults=dict(order=0))

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)

u, new = User.objects.get_or_create(username="mehdi", defaults=dict(name="Mehdi"))
if new:
    pw = secrets.token_urlsafe(12)
    u.set_password(pw); u.save()
    print(f"USER mehdi aangemaakt - tijdelijk wachtwoord: {pw}")
else:
    print("USER mehdi bestond al")
u.groups.add(access_grp)
u.groups.add(full_grp)
print("AGENDA_DONE")
