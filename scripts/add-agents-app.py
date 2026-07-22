import os
from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG, NAME, SUB = "agents", "Agents", "agents"
ROLES = ["admin", "manager", "agents"]
# Wie expliciet toegang moet hebben (naast admin/manager).
EXTRA_USERS = ["akadmin", "mehdi"]

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://{SUB}.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, created = ProxyProvider.objects.get_or_create(name=f"{SLUG}-proxy", defaults=defaults)
proxy.external_host = f"https://{SUB}.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(slug=SLUG,
    defaults=dict(name=NAME, provider=proxy, meta_launch_url=f"https://{SUB}.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://{SUB}.{BASE}"
app.save()

for gname in ROLES:
    grp, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first().providers.add(proxy)

own = Group.objects.get(name="agents")
for uname in EXTRA_USERS:
    u = User.objects.filter(username=uname).first()
    if u:
        u.groups.add(own)
        print(uname, "-> agents OK")
    else:
        print("LET OP: user", uname, "niet gevonden")

print("APP:", app.slug, "| provider:", "created" if created else "exists", "| roles:", ROLES)
print("AGENTS_DONE")
