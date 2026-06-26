import os
from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")
SLUG, NAME, SUB, GROUP = "kosten", "Kosten", "kosten", "kosten"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
defaults = dict(authorization_flow=auth_flow, mode="forward_single", external_host=f"https://{SUB}.{BASE_DOMAIN}")
if inval_flow: defaults["invalidation_flow"] = inval_flow
proxy, created = ProxyProvider.objects.get_or_create(name=f"{SLUG}-proxy", defaults=defaults)
proxy.set_oauth_defaults(); proxy.save()
app, _ = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME, provider=proxy))
if app.provider_id != proxy.pk: app.provider = proxy; app.save()
group, _ = Group.objects.get_or_create(name=GROUP)
PolicyBinding.objects.get_or_create(target=app, group=group, defaults=dict(order=0))
for uname in ["mehdi", "siyan", "angela", "akadmin"]:
    u = User.objects.filter(username__iexact=uname).first()
    if u: group.users.add(u); print("toegevoegd:", u.username)
    else: print("niet gevonden (later toevoegen):", uname)
outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
print(f"kosten app: {'created' if created else 'exists'} | groep={GROUP}")
print("KOSTEN_APP_DONE")
