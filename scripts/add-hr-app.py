# HR-dashboard (hr.globaal.be) als forward-auth-tegel in Authentik.
# Draaien:  sh scripts/ak-exec.sh scripts/add-hr-app.py
#
# Toegang loopt via de groep "hr" (bestaat al als STAFF_GROUPS-waarde in de
# organisatie-app). Vertrouwelijke personeelsdata: bewust GEEN brede toegang,
# alleen leden die je expliciet aan de groep toevoegt, plus admin.
from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

hr_grp, _ = Group.objects.get_or_create(name="hr")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://hr.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="hr-proxy", defaults=defaults)
proxy.external_host = f"https://hr.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="hr",
    defaults=dict(name="HR-dashboard (HDS)", provider=proxy,
                  meta_launch_url=f"https://hr.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://hr.{BASE}"
app.save()

PolicyBinding.objects.get_or_create(target=app, group=hr_grp, defaults=dict(order=0))
for naam in ("admin", "manager"):
    grp = Group.objects.filter(name=naam).first()
    if grp:
        PolicyBinding.objects.get_or_create(target=app, group=grp,
                                            defaults=dict(order=1))

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)
print("HR_DONE")
