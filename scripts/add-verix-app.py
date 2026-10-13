"""Tegel Verix (verix.<domein>) in Authentik, met eigen proxy-provider (forward-auth).

Shaniel, 13-10-2026: Verix (predalwapening nazien) live zetten voor de groep verix plus admin, en Samad erin.
De app heeft zelf geen login, dus deze binding is de enige afscherming.

Draaien:  sh scripts/ak-exec.sh scripts/add-verix-app.py
Idempotent. Samad wordt alleen toegevoegd als er precies een gebruiker op "samad" past; anders staan de
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
SLUG, NAME, SUB = "verix", "Verix", "verix"
ROLES = ["admin", "verix"]
ZOEK = "samad"

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
app.meta_description = "Wapening van predallen nazien tegen de plannen van constructeur en leverancier"
app.save()

for gname in ROLES:
    grp, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

verix = Group.objects.get(name="verix")
kandidaten = list(User.objects.filter(
    Q(username__icontains=ZOEK) | Q(email__icontains=ZOEK) | Q(name__icontains=ZOEK)).filter(is_active=True))
if len(kandidaten) == 1:
    verix.users.add(kandidaten[0])
else:
    print("SAMAD NIET TOEGEVOEGD, kandidaten:", [(u.username, u.email, u.name) for u in kandidaten])

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
# Zonder save kent de embedded outpost het nieuwe domein niet (zie add-felix-app.py).
outpost.save()
print("APP:", app.slug, "| provider:", "created" if created else "exists", "| roles:", ROLES,
      "| verix-leden:", [u.username for u in verix.users.all()])
print("VERIX_DONE")
