from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider
BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://status.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="status-proxy", defaults=defaults)
proxy.external_host = f"https://status.{BASE}"
proxy.set_oauth_defaults(); proxy.save()
app, _ = Application.objects.get_or_create(
    slug="status",
    defaults=dict(name="Status / Monitoring", provider=proxy,
                  meta_launch_url=f"https://status.{BASE}"))
app.provider = proxy; app.meta_launch_url = f"https://status.{BASE}"; app.save()
for gname in ("admin", "manager"):
    g = Group.objects.filter(name=gname).first()
    if g:
        PolicyBinding.objects.get_or_create(target=app, group=g, defaults=dict(order=0))
o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)
print("MONITORING_DONE")
