# Interne wervingspagina van Elevait (intern.elevaitnv.com) als
# forward-auth-app. Draaien:  sh scripts/ak-exec.sh scripts/add-elevait-intern-app.py
#
# Toegang uitsluitend via de groep "elevait" (plus admin); daarin zitten
# alleen akadmin en mehdi. Bewust geen bredere binding: de pagina bevat
# kandidaatgegevens.
from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

HOST = "https://intern.elevaitnv.com"
auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

grp, _ = Group.objects.get_or_create(name="elevait")

defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                external_host=HOST)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, _ = ProxyProvider.objects.get_or_create(name="elevait-intern-proxy",
                                               defaults=defaults)
proxy.external_host = HOST
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(
    slug="elevait-intern",
    defaults=dict(name="Elevait intern", provider=proxy, meta_launch_url=HOST))
app.provider = proxy
app.meta_launch_url = HOST
app.save()

PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))
admin_grp = Group.objects.filter(name="admin").first()
if admin_grp:
    PolicyBinding.objects.get_or_create(target=app, group=admin_grp,
                                        defaults=dict(order=1))

for uname in ("akadmin", "mehdi"):
    u = User.objects.filter(username=uname).first()
    if u:
        u.groups.add(grp)
        print(f"USER {uname} in groep elevait")
    else:
        print(f"LET OP: gebruiker {uname} niet gevonden")

o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
o.providers.add(proxy)
print("ELEVAIT_INTERN_DONE")
