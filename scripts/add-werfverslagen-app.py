"""Tegel Werfverslagen in de Authentik-bibliotheek: een koppeling zonder eigen provider (een proxy hoort bij één
tegel), opent /werfverslagen; de forward-auth van mijnagents bewaakt de toegang.
Alleen admin en manager (de pagina zelf laat de groep agents ook niet toe)."""
import os
from authentik.core.models import Application, Group
from authentik.policies.models import PolicyBinding

BASE = os.environ.get("BASE_DOMAIN", "globaal.be")
url = f"https://mijnagents.{BASE}/werfverslagen"
app, created = Application.objects.get_or_create(slug="werfverslagen", defaults=dict(name="Werfverslagen", provider=None, meta_launch_url=url,
                                                 meta_description="H-Architects: per dossier en werfbezoek de keuzes, bijlagen, proef, herkomst en controle"))
app.meta_launch_url = url
app.group = "H-Architects"
app.save()
for gname in ("admin", "manager"):
    grp, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))
print("APP:", app.slug, "created" if created else "exists", url)
