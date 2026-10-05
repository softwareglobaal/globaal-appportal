from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
HOST = f"https://bouwsoft.{BASE}"

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

# Bouwsoft-kloon (softwareglobaal/globaal-bouwsoft-kloon): schermen voor de groep
# bouwsoft en admins. De API (/api/) zit buiten de SSO en heeft een eigen token.
grp, _ = Group.objects.get_or_create(name="bouwsoft")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=HOST)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="bouwsoft-proxy", defaults=defaults)
proxy.external_host = HOST
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="bouwsoft",
    defaults=dict(name="Bouwsoft-kloon", provider=proxy, meta_launch_url=HOST))
app.provider = proxy
app.meta_launch_url = HOST
app.meta_description = "Kloon van Bouwsoft met fictief testdossier"
app.save()

for naam in ("bouwsoft", "admin"):
    g = Group.objects.filter(name=naam).first()
    if g:
        PolicyBinding.objects.get_or_create(target=app, group=g,
                                            defaults=dict(order=0))

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)

print("BOUWSOFT_APP_DONE")
