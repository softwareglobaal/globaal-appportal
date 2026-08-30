"""Registreer het Panden dashboard als eigen tegel in Authentik.

Draaien (vanuit ~/appportal):
  docker compose cp scripts/add-panden-dashboard-app.py authentik-server:/tmp/p.py
  docker compose exec authentik-server ak shell -c "exec(open('/tmp/p.py').read())"

Idempotent: veilig om opnieuw te draaien. Maakt de tegel 'Panden dashboard' in de
launcher voor de groepen admin/manager/vermogen.

Geen eigen proxy-provider: de pagina zit op vermogen.globaal.be en valt dus al
onder de bestaande vermogen-proxy uit add-vermogen-app.py. Een applicatie zonder
provider is in Authentik enkel een link met rechten erop, precies wat hier nodig is.
"""
import os

from authentik.core.models import Application, Group
from authentik.policies.models import PolicyBinding

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
SLUG = "panden-dashboard"
NAME = "Panden dashboard"
URL = f"https://vermogen.{BASE_DOMAIN}/panden-dashboard"
ROLES = ("admin", "manager", "vermogen")

app, created = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=NAME))
app.name = NAME
app.meta_launch_url = URL
app.meta_description = ("Het berekende overzicht van de panden: DSCR, cashflow, "
                        "kredieten, waarborgen, huur en een fiche per pand.")
app.save()
print(f"app {SLUG}: {'created' if created else 'exists'}, launch-url {URL}")

for gname in ROLES:
    g, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=g, defaults=dict(order=0))
print(f"group-bindings: {', '.join(ROLES)}")
