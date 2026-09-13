"""Tegel Werfverslagen in de Authentik-bibliotheek: dezelfde proxy als Mehdi Agents, opent /werfverslagen.
Alleen admin en manager (de pagina zelf laat de groep agents ook niet toe)."""
import os
from authentik.core.models import Application, Group
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

BASE = os.environ.get("BASE_DOMAIN", "globaal.be")
proxy = ProxyProvider.objects.get(name="mijnagents-proxy")
url = f"https://mijnagents.{BASE}/werfverslagen"
app, created = Application.objects.get_or_create(slug="werfverslagen", defaults=dict(name="Werfverslagen", provider=proxy, meta_launch_url=url,
                                                 meta_description="H-Architects: per dossier en werfbezoek de keuzes, bijlagen, proef, herkomst en controle"))
app.provider = proxy
app.meta_launch_url = url
app.group = "H-Architects"
app.save()
for gname in ("admin", "manager"):
    grp, _ = Group.objects.get_or_create(name=gname)
    PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0))
print("APP:", app.slug, "created" if created else "exists", url)
