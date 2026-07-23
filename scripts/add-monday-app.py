# Monday-zandbak (monday.globaal.be) als forward-auth-tegel.
# Draaien:  sh scripts/ak-exec.sh scripts/add-monday-app.py
#
# Toegang via de groep "monday" (plus admin). Zet akadmin, mehdi en ashvand
# in die groep. Bestaande accounts houden hun wachtwoord; ontbrekende worden
# aangemaakt met een tijdelijk wachtwoord (wordt geprint).
import secrets

from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name="monday")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://monday.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="monday-proxy", defaults=defaults)
proxy.external_host = f"https://monday.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="monday",
    defaults=dict(name="Monday-zandbak", provider=proxy,
                  meta_launch_url=f"https://monday.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://monday.{BASE}"
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))
admin_grp = Group.objects.filter(name="admin").first()
if admin_grp:
    PolicyBinding.objects.get_or_create(target=app, group=admin_grp, defaults=dict(order=1))

for uname, naam in (("akadmin", "akadmin"), ("mehdi", "Mehdi"), ("ashvand", "Ashvand")):
    u, new = User.objects.get_or_create(username=uname, defaults=dict(name=naam))
    if new:
        pw = secrets.token_urlsafe(12)
        u.set_password(pw)
        u.save()
        print(f"USER {uname} aangemaakt - tijdelijk wachtwoord: {pw}")
    else:
        print(f"USER {uname} bestond al")
    u.groups.add(grp)

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)
print("MONDAY_DONE")
