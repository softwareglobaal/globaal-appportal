"""Tegel FelixArchief (felix.<domein>) in Authentik, met eigen proxy-provider (forward-auth).

Shaniel, 13-10-2026: Shelton krijgt toegang tot de FelixArchief-agent, niet tot Mehdi's bord. Daarom een eigen
domein met een eigen provider: de groep felix geeft alleen deze tegel. De app toont op felix.<domein> alleen /felix.
Toegang: admin, manager en felix. Shelton (username shelton) komt in de groep felix.

Draaien:  docker compose exec -T authentik-server ak shell < scripts/add-felix-app.py
Idempotent.
"""
import os
from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG, NAME, SUB = "felix", "FelixArchief", "felix"
ROLES = ["admin", "manager", "felix"]
LEDEN = ["shelton"]

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
app.meta_description = "Bouwdossiers opzoeken in de percelenpas van de stad Antwerpen en FelixArchief"
app.group = "H-Architects"
app.save()

for gname in ROLES:
    grp, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))

felix = Group.objects.get(name="felix")
for naam in LEDEN:
    u = User.objects.filter(username=naam).first()
    if u:
        felix.users.add(u)
    else:
        print("GEEN GEBRUIKER:", naam)

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
# Zonder save kende de embedded outpost het nieuwe domein na 4 minuten nog niet (auth request 404, nginx 500);
# na een save pakte hij het binnen 2 minuten op (13-10-2026).
outpost.save()
print("APP:", app.slug, "| provider:", "created" if created else "exists", "| roles:", ROLES,
      "| felix-leden:", [u.username for u in felix.users.all()])
print("FELIX_DONE")
