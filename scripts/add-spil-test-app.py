"""OIDC-koppeling voor de testomgeving van SPIL (spil-test.globaal.be).

Shaniel, 29-10-2026: op vraag van Ashvand (briefje 28-10). SPIL gebruikt
authentik alleen voor de identiteit; rollen en firma's beheert SPIL zelf, dus
geen groepen of extra claims in het token.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-spil-test-app.py

Idempotent. Drukt alleen de client ID af. Het client secret staat in de
admin-UI en gaat rechtstreeks naar secrets/oidc_client_secret op de
SPIL-server, nooit via mail of chat.

Twee dingen voor wie SPIL bouwt:
- `sub` is hashed_user_id. SPIL koppelt gebruikers daarop, dus sub_mode hier
  nooit meer wijzigen: dan krijgt iedereen in SPIL een nieuwe identiteit.
- `amr` na een passkey-login zonder wachtwoord is ["user"], niet "webauthn"
  (authentik/common/oauth/constants.py: AMR_WEBAUTHN = "user"). Wachtwoord plus
  tweede factor geeft ["pwd", "mfa"].

Tegel staat aan op verzoek van Shaniel (30-10-2026), ook al draait SPIL nog
niet: tot dan komt het adres via de wildcard op de VM uit bij authentik.
"""
from authentik.core.models import Application, Group, User
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import (ClientType, GrantType,
                                               OAuth2LogoutMethod,
                                               OAuth2Provider, RedirectURI,
                                               RedirectURIMatchingMode,
                                               ScopeMapping)

SLUG = "spil-test"
NAAM = "SPIL (test)"
BASIS = "https://spil-test.globaal.be"
TERUG = f"{BASIS}/oidc/callback/"
LOGOUT = f"{BASIS}/oidc/backchannel-logout/"
GROEP = "SPIL-test"
LEDEN = ("shaniel", "ashvand")
SCOPES = ("openid", "profile", "email")
GRANTS = [GrantType.AUTHORIZATION_CODE]

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()
# RSA-sleutel, dus RS256; SPIL controleert de tokens via de JWKS-URL.
sleutel = CertificateKeyPair.objects.get(name="authentik Self-signed Certificate")

defaults = dict(authorization_flow=auth_flow, client_type=ClientType.CONFIDENTIAL,
                grant_types=GRANTS)
if inval_flow:
    defaults["invalidation_flow"] = inval_flow

oidc, nieuw = OAuth2Provider.objects.get_or_create(name=f"{SLUG}-oidc", defaults=defaults)
oidc.client_type = ClientType.CONFIDENTIAL
oidc.authorization_flow = auth_flow
if inval_flow:
    oidc.invalidation_flow = inval_flow
# Zonder deze regel blijft grant_types leeg en weigert authentik elk verzoek.
oidc.grant_types = GRANTS
oidc.redirect_uris = [RedirectURI(RedirectURIMatchingMode.STRICT, TERUG)]
oidc.logout_uri = LOGOUT
oidc.logout_method = OAuth2LogoutMethod.BACKCHANNEL
oidc.signing_key = sleutel
oidc.save()

mappings = ScopeMapping.objects.filter(scope_name__in=SCOPES)
oidc.property_mappings.set(mappings)
gevonden = sorted(mappings.values_list("scope_name", flat=True))
print(f"provider {SLUG}-oidc: {'aangemaakt' if nieuw else 'bestond al'}")
print(f"scopes: {', '.join(gevonden)} | sub_mode: {oidc.sub_mode} | sleutel: {sleutel.name}")
if set(gevonden) != set(SCOPES):
    print(f"LET OP: verwacht {SCOPES}, gevonden {gevonden}")

app, app_nieuw = Application.objects.get_or_create(
    slug=SLUG, defaults=dict(name=NAAM, provider=oidc))
app.name = NAAM
app.provider = oidc
app.meta_launch_url = BASIS
app.save()
print(f"app {SLUG}: {'aangemaakt' if app_nieuw else 'bijgewerkt'}")

groep, _ = Group.objects.get_or_create(name=GROEP)
PolicyBinding.objects.get_or_create(target=app, group=groep, defaults=dict(order=0))
for naam in LEDEN:
    groep.users.add(User.objects.get(username=naam))
andere = PolicyBinding.objects.filter(target=app).exclude(group=groep)
if andere.exists():
    print("LET OP: nog andere toegangsregels op deze app:", list(andere))
print(f"toegang: alleen {GROEP}, leden {sorted(u.username for u in groep.users.all())}")

print("SPIL_TEST_CLIENT_ID=" + oidc.client_id)
print("SPIL_TEST_ISSUER=https://auth.globaal.be/application/o/" + SLUG + "/")
print("SPIL_TEST_DONE")
