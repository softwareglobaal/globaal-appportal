"""Verhuis de Medewerkers-app in Authentik naar organisatie.<domein>.

Draaien (vanuit ~/appportal):
  docker compose cp scripts/hernoem-medewerkers-naar-organisatie.py authentik-server:/tmp/o.py
  docker compose exec authentik-server ak shell -c "exec(open('/tmp/o.py').read())"

Idempotent. Past de proxy-provider (external_host), de tegel-naam en de
launch-url aan; slug blijft 'medewerkers' (interne id, geen buitenkant).
Het oude domein blijft werken via een nginx-301 naar het nieuwe.
"""
import os

from authentik.core.models import Application
from authentik.providers.proxy.models import ProxyProvider

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
NIEUW = f"https://organisatie.{BASE_DOMAIN}"

proxy = ProxyProvider.objects.get(name="medewerkers-proxy")
proxy.external_host = NIEUW
proxy.set_oauth_defaults()
proxy.save()
print(f"proxy medewerkers-proxy: external_host -> {NIEUW}")

app = Application.objects.get(slug="medewerkers")
app.name = "Organisatie"
app.meta_launch_url = NIEUW
app.save()
print(f"tegel: {app.name} -> {NIEUW}")
print("ORGANISATIE_RENAME_DONE")
