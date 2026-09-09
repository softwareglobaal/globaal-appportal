"""Registreer de OIDC-koppeling voor het MCP-endpoint van het portaal.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-portal-mcp.py

Idempotent: veilig om opnieuw te draaien. Drukt aan het eind de client-gegevens
af; die horen in /home/ubuntu/portal-mcp.env en nergens anders.

**Waarom OIDC en niet de forward-auth.** De eerste opzet zette /oauth/authorize
achter de forward-auth, net als bij vermogen, renovision en pipedrive. Dat werkt,
maar het neemt klakkeloos over wie er toevallig in die browser is ingelogd. Op
een gedeelde PC koppelt de tweede collega dan als de eerste, ziet hij diens
applicaties, en er komt geen enkele foutmelding: het ziet er precies uit alsof
het werkt.

Als OIDC-client kunnen we `prompt=login` meesturen. Authentik dwingt dan een
verse authenticatie, ook als er al een geldige sessie is
(`/authentik/providers/oauth2/views/authorize.py`: "If prompt=login, we need to
re-authenticate the user regardless"). Wie koppelt typt dus zelf zijn
wachtwoord, en de identiteit komt uit een token dat bij die inlog hoort in
plaats van uit een proxy-header.

De toegangsregels blijven waar ze waren: de policy-bindings hangen aan de
**applicatie**, niet aan de provider, en die blijven bij het omzetten gewoon
staan. Wie mag koppelen zet je dus nog steeds met een groep.

Geen launch-url: dit is geen tegel in de launcher.
"""
from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import (ClientTypes, OAuth2Provider,
                                               RedirectURI,
                                               RedirectURIMatchingMode,
                                               ScopeMapping)
from authentik.providers.proxy.models import ProxyProvider

SLUG = "portal-mcp"
NAAM = "Portaal via Claude"
TERUG = "https://portal-mcp.globaal.be/oauth/terug"
GROEPEN = ("portaal-mcp", "admin", "manager")
SCOPES = ("openid", "profile", "email")

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

defaults = dict(authorization_flow=auth_flow, client_type=ClientTypes.CONFIDENTIAL)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow

oidc, nieuw = OAuth2Provider.objects.get_or_create(
    name=f"{SLUG}-oidc", defaults=defaults)

# Alleen dit ene adres, letterlijk vergeleken. Geen regex: een te ruime regex
# is de klassieke manier waarop een autorisatiecode bij een vreemde belandt.
oidc.redirect_uris = [RedirectURI(RedirectURIMatchingMode.STRICT, TERUG)]
oidc.authorization_flow = auth_flow
if inval_flow:
    oidc.invalidation_flow = inval_flow
oidc.save()

# Zonder scope-mappings komen er geen claims terug en weten we de naam niet.
mappings = ScopeMapping.objects.filter(scope_name__in=SCOPES)
oidc.property_mappings.set(mappings)
gevonden = sorted(mappings.values_list("scope_name", flat=True))
print(f"provider {SLUG}-oidc: {'aangemaakt' if nieuw else 'bestond al'}")
print(f"scopes: {', '.join(gevonden)}")
if set(gevonden) != set(SCOPES):
    print(f"LET OP: verwacht {SCOPES}, gevonden {gevonden}")

app, app_nieuw = Application.objects.get_or_create(
    slug=SLUG, defaults=dict(name=NAAM, provider=oidc))
oude = app.provider
app.provider = oidc
app.save()
print(f"app {SLUG}: {'aangemaakt' if app_nieuw else 'bijgewerkt'}, provider is nu OIDC")

# De forward-auth van de eerste opzet opruimen: uit de outpost halen en, als
# geen enkele applicatie hem meer gebruikt, weggooien. Blijft hij staan, dan
# blijft de oude weg naast de nieuwe bestaan en dat is precies wat we niet
# willen: een tweede deur die geen herinlog afdwingt.
proxy = ProxyProvider.objects.filter(name=f"{SLUG}-proxy").first()
if proxy:
    outpost = Outpost.objects.filter(
        managed="goauthentik.io/outposts/embedded").first()
    if outpost:
        outpost.providers.remove(proxy)
        outpost.save()
    if not Application.objects.filter(provider=proxy).exists():
        proxy.delete()
        print("oude forward-auth-provider verwijderd")
    else:
        print("LET OP: de oude proxy-provider hangt nog aan een applicatie")
elif oude is not None and oude.pk != oidc.pk:
    print(f"vorige provider was {oude}")

for naam in GROEPEN:
    groep, groep_nieuw = Group.objects.get_or_create(name=naam)
    _, binding_nieuw = PolicyBinding.objects.get_or_create(
        target=app, group=groep, defaults=dict(order=0))
    stand = "aangemaakt" if binding_nieuw else "bestond al"
    print(f"toegang {naam}: {stand}{' (groep nieuw)' if groep_nieuw else ''}")

print("PORTAL_MCP_CLIENT_ID=" + oidc.client_id)
print("PORTAL_MCP_CLIENT_SECRET=" + oidc.client_secret)
print("PORTAL_MCP_OIDC_DONE")
