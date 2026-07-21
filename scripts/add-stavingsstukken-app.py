# Stavingsstukken-cockpit (stavingsstukken.globaal.be) als forward-auth-tegel.
# Draaien:  sh scripts/ak-exec.sh scripts/add-stavingsstukken-app.py
#
# Toegang via de groep "stavingsstukken" (plus admin). Maakt ook de accounts
# mukesh en ashvand aan (EPB-team) met een tijdelijk wachtwoord; die twee
# komen ALLEEN in de groep stavingsstukken en zien dus alleen deze tegel.
import secrets

from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = "globaal.be"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name="stavingsstukken")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=f"https://stavingsstukken.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="stavingsstukken-proxy", defaults=defaults)
proxy.external_host = f"https://stavingsstukken.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="stavingsstukken",
    defaults=dict(name="Stavingsstukken-cockpit", provider=proxy,
                  meta_launch_url=f"https://stavingsstukken.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://stavingsstukken.{BASE}"
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))
admin_grp = Group.objects.filter(name="admin").first()
if admin_grp:
    PolicyBinding.objects.get_or_create(target=app, group=admin_grp, defaults=dict(order=1))

for uname, naam in (("mukesh", "Mukesh"), ("ashvand", "Ashvand")):
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
print("STAVINGSSTUKKEN_DONE")
