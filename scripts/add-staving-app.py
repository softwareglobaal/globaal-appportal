# Staving (staving.globaal.be), de nieuwe stavingsstukken-automation, als forward-auth-tegel.
# Draaien:  sh scripts/ak-exec.sh scripts/add-staving-app.py
#
# Zelfde groep als de oude cockpit ("stavingsstukken", plus admin): Isaiah, Mukesh en
# Ashvand komen er dus meteen bij, zonder nieuwe accounts. Sessieduur van de proxy staat
# hier bewust op acht uur: op 03-09-2026 verloor Isaiah zijn invoer omdat de standaard
# van een uur verliep terwijl hij in een formulier zat.
from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
HOST = f"https://staving.{BASE}"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name="stavingsstukken")

defaults = dict(authorization_flow=auth_flow, mode="forward_single", external_host=HOST)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="staving-proxy", defaults=defaults)
proxy.external_host = HOST
proxy.access_token_validity = "hours=8"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="staving",
    defaults=dict(name="Staving (nieuw)", provider=proxy, meta_launch_url=HOST,
                  meta_description="Bulk in, gesorteerd uit: de nieuwe stavingsstukken-automation"))
app.provider = proxy
app.meta_launch_url = HOST
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))
admin_grp = Group.objects.filter(name="admin").first()
if admin_grp:
    PolicyBinding.objects.get_or_create(target=app, group=admin_grp, defaults=dict(order=1))

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)
print("STAVING_DONE", proxy.pk, app.pk, "token", proxy.access_token_validity)
