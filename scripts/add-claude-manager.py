"""Registreer de OIDC-koppeling voor de Claude Code Manager (manager.globaal.be).

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-claude-manager.py

Idempotent. Zelfde opzet als add-portal-mcp.py: OIDC-client met een strikt
terugadres, zodat de dienst `prompt=login` kan meesturen.

Anders dan add-portal-mcp.py drukt dit script de client-gegevens NIET af: die
gaan naar /tmp/claude-manager-client.env in de container, en de aanroeper
haalt ze daar op en wist ze. Zo komen ze niet in een terminal- of chatlog.

Toegang: alleen de groep `claude-manager`. De dienst zelf laat daarbovenop
alleen de namen in MANAGER_GEBRUIKERS toe.
"""
import os

from authentik.core.models import Application, Group, User
from authentik.flows.models import Flow
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import (ClientType, GrantType,
                                               OAuth2Provider,
                                               RedirectURI,
                                               RedirectURIMatchingMode,
                                               ScopeMapping)

SLUG = "claude-manager"
NAAM = "Claude Code Manager"
TERUG = "https://manager.globaal.be/oauth/terug"
GROEP = "claude-manager"
LEDEN = ("shaniel",)
SCOPES = ("openid", "profile", "email")
UIT = "/tmp/claude-manager-client.env"

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
GRANTS = [GrantType.AUTHORIZATION_CODE]

defaults = dict(authorization_flow=auth_flow, client_type=ClientType.CONFIDENTIAL,
                grant_types=GRANTS)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow

oidc, nieuw = OAuth2Provider.objects.get_or_create(
    name=f"{SLUG}-oidc", defaults=defaults)
oidc.redirect_uris = [RedirectURI(RedirectURIMatchingMode.STRICT, TERUG)]
oidc.authorization_flow = auth_flow
# Zonder deze regel blijft grant_types leeg en weigert Authentik elk verzoek
# met "invalid_request" (zie add-portal-mcp.py).
oidc.grant_types = GRANTS
if inval_flow:
    oidc.invalidation_flow = inval_flow
oidc.save()

mappings = ScopeMapping.objects.filter(scope_name__in=SCOPES)
oidc.property_mappings.set(mappings)
gevonden = sorted(mappings.values_list("scope_name", flat=True))
print(f"provider {SLUG}-oidc: {'aangemaakt' if nieuw else 'bestond al'}")
print(f"scopes: {', '.join(gevonden)}")

app, app_nieuw = Application.objects.get_or_create(
    slug=SLUG, defaults=dict(name=NAAM, provider=oidc))
app.provider = oidc
app.save()
print(f"app {SLUG}: {'aangemaakt' if app_nieuw else 'bijgewerkt'}")

groep, _ = Group.objects.get_or_create(name=GROEP)
PolicyBinding.objects.get_or_create(target=app, group=groep,
                                    defaults=dict(order=0))
for naam in LEDEN:
    gebruiker = User.objects.filter(username=naam).first()
    if gebruiker is None:
        print(f"LET OP: gebruiker {naam} bestaat niet")
        continue
    groep.users.add(gebruiker)
print(f"groep {GROEP}: {', '.join(groep.users.values_list('username', flat=True))}")

with open(UIT, "w") as f:
    f.write(f"MANAGER_CLIENT_ID={oidc.client_id}\n")
    f.write(f"MANAGER_CLIENT_SECRET={oidc.client_secret}\n")
os.chmod(UIT, 0o600)
print(f"client-gegevens in {UIT} (container authentik-server)")
print("CLAUDE_MANAGER_OIDC_DONE")
