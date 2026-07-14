from authentik.providers.oauth2.models import OAuth2Provider
from authentik.providers.proxy.models import ProxyProvider
from authentik.outposts.models import Outpost
BASE = "globaal.be"
SUBS = {"factorydocs-proxy":"factorydocs","inventory-proxy":"inventory","finance-proxy":"finance","maintenance-proxy":"maintenance","omv-proxy":"omv"}
for name, sub in SUBS.items():
    p = ProxyProvider.objects.filter(name=name).first()
    if p:
        p.external_host = f"https://{sub}.{BASE}"
        p.save()
        print(f"{name} -> {p.external_host}")
oidc = OAuth2Provider.objects.filter(name="portal-oidc").first()
if oidc:
    try:
        from authentik.providers.oauth2.models import RedirectURI, RedirectURIMatchingMode
        oidc.redirect_uris = [RedirectURI(RedirectURIMatchingMode.STRICT, f"https://portal.{BASE}/auth/callback")]
    except Exception:
        oidc.redirect_uris = f"https://portal.{BASE}/auth/callback"
    oidc.save()
    print(f"portal-oidc -> https://portal.{BASE}/auth/callback")
o = Outpost.objects.filter(managed="goauthentik.io/outposts/embedded").first()
cfg = o.config
cfg.authentik_host = f"https://auth.{BASE}"
o.config = cfg
o.save()
print(f"outpost authentik_host -> https://auth.{BASE}")
print("DOMAINS_FIXED")
