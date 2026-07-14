"""Stagebeoordeling: forward-auth app + 2 groepen.
- 'stagebeoordeling'         = toegang/zien (app-binding hieraan)
- 'stagebeoordeling-bewerken'= bewerkrechten (alleen Raisha)
Run: sh scripts/ak-exec.sh scripts/add-stage-app.py
"""
import os
from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")
SLUG, NAME, SUB = "stage", "Stagebeoordeling", "stage"
VIEW_GROUP, EDIT_GROUP = "stagebeoordeling", "stagebeoordeling-bewerken"

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
defaults = dict(authorization_flow=auth_flow, mode="forward_single", external_host=f"https://{SUB}.{BASE_DOMAIN}")
if inval_flow: defaults["invalidation_flow"] = inval_flow
proxy, created = ProxyProvider.objects.get_or_create(name=f"{SLUG}-proxy", defaults=defaults)
proxy.set_oauth_defaults(); proxy.save()

app, _ = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME, provider=proxy))
if app.provider_id != proxy.pk: app.provider = proxy; app.save()

view_group, _ = Group.objects.get_or_create(name=VIEW_GROUP)
edit_group, _ = Group.objects.get_or_create(name=EDIT_GROUP)
PolicyBinding.objects.get_or_create(target=app, group=view_group, defaults=dict(order=0))

raisha = User.objects.filter(username__iexact="raisha").first()
if raisha:
    view_group.users.add(raisha); edit_group.users.add(raisha)
    print("Raisha toegevoegd aan beide groepen.")
else:
    print("LET OP: user 'raisha' bestaat nog niet -> maak die eerst aan (stap 1) en draai dit opnieuw.")
akadmin = User.objects.filter(username="akadmin").first()
if akadmin: view_group.users.add(akadmin)

outpost = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
print(f"stage app: {'created' if created else 'exists'} | view={VIEW_GROUP} edit={EDIT_GROUP}")
print("STAGE_APP_DONE")
