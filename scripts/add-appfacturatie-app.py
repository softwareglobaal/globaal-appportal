"""Tegel Facturatie (Joan) (appfacturatie.<domein>) in Authentik, met eigen proxy-provider (forward-auth).

Shaniel, 22-10-2026: de facturatie-app van Joan (joanhds/APP-Facturatie) op de VM. Authentik is de enige
aanmelding; de app neemt de naam over uit X-authentik-username en bepaalt zelf de rechten (users.json).
Toegang = groep app-facturatie of admin. Niet te verwarren met de tegel Facturatie (Cockpit, add-facturatie-app.py).

Draaien:  sh scripts/ak-exec.sh scripts/add-appfacturatie-app.py
Idempotent. Joan wordt alleen toegevoegd als er precies een gebruiker op "joan" past; anders staan de
kandidaten in de uitvoer.
"""
import os
from django.db.models import Q
from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG, NAME, SUB = "app-facturatie", "Facturatie (Joan)", "appfacturatie"
ROLES = ["admin", "app-facturatie"]
ZOEK = "joan"

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
defaults = dict(authorization_flow=auth_flow, mode="forward_single", external_host=f"https://{SUB}.{BASE}")
if inval_flow:
    defaults["invalidation_flow"] = inval_flow
proxy, created = ProxyProvider.objects.get_or_create(name=f"{SLUG}-proxy", defaults=defaults)
proxy.external_host = f"https://{SUB}.{BASE}"
proxy.set_oauth_defaults()
proxy.save()

app, _ = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME, provider=proxy, meta_launch_url=f"https://{SUB}.{BASE}"))
app.provider = proxy
app.meta_launch_url = f"https://{SUB}.{BASE}"
app.meta_description = "Facturen, rappels, betalingen en HA Contracten (app van Joan)"
app.save()

for gname in ROLES:
    grp, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

groep = Group.objects.get(name="app-facturatie")
kandidaten = list(User.objects.filter(
    Q(username__icontains=ZOEK) | Q(email__icontains=ZOEK) | Q(name__icontains=ZOEK)).filter(is_active=True))
if len(kandidaten) == 1:
    groep.users.add(kandidaten[0])
else:
    print("JOAN NIET TOEGEVOEGD, kandidaten:", [(u.username, u.email, u.name) for u in kandidaten])

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
# Zonder save kent de embedded outpost het nieuwe domein niet (zie add-felix-app.py).
outpost.save()
print("APP:", app.slug, "| provider:", "created" if created else "exists", "| roles:", ROLES,
      "| leden:", [(u.username, u.email) for u in groep.users.all()])
print("APPFACTURATIE_DONE")
