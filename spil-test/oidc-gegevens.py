"""Client ID en secret van SPIL (test) voor spil-test/setup.sh. Niet los draaien:
de uitvoer bevat het secret en hoort niet op een scherm of in een chat."""
from authentik.providers.oauth2.models import OAuth2Provider

p = OAuth2Provider.objects.get(name="spil-test-oidc")
print("CLIENT_ID=" + p.client_id)
print("CLIENT_SECRET=" + p.client_secret)
