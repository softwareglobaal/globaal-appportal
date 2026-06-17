from authentik.core.models import Application
from authentik.providers.proxy.models import ProxyProvider
from authentik.providers.oauth2.models import OAuth2Provider
BASE = "globaal.be"

# 1. Placeholder-apps + providers verwijderen (ontruimt de launcher)
for slug in ("factorydocs", "inventory", "finance", "maintenance"):
    Application.objects.filter(slug=slug).delete()
    ProxyProvider.objects.filter(name=f"{slug}-proxy").delete()
    print(f"verwijderd: {slug}")

# 2. Launch-URLs goedzetten op de echte apps (klikbaar in de launcher)
for slug in ("omv", "schuldentracker", "status"):
    a = Application.objects.filter(slug=slug).first()
    if a:
        a.meta_launch_url = f"https://{slug}.{BASE}"
        a.save()
        print(f"launch-url: {slug} -> https://{slug}.{BASE}")

# 3. De custom 'Portal' uitfaseren: app + OIDC-provider weg
Application.objects.filter(slug="portal").delete()
OAuth2Provider.objects.filter(name="portal-oidc").delete()
print("Portal-app + portal-oidc verwijderd")
print("CONSOLIDATE_DONE")
