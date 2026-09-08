"""Read-only serviceaccount voor de portal-MCP, met een API-token.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/add-portal-mcp-token.py

Idempotent: opnieuw draaien hergebruikt hetzelfde account en token en drukt de
bestaande sleutel af.

Waarvoor: de portal-MCP moet kunnen zien welke applicaties er zijn en wie ze
mag openen. Dat is precies wat dit account mag, en niets meer. Vier kijkrechten:

  view_application    de cataloog zelf
  view_policybinding  welke groep of persoon aan welke app gebonden is
  view_group          de groepen van de ingelogde gebruiker
  view_user           de gebruiker opzoeken

Let op `view_application`: zonder dat recht geeft
`core/applications/?superuser_full_list=true` een lege lijst terug in plaats
van een foutmelding, want Authentik toont dan alleen de apps die het account
zelf mag openen. Dat is nul. Een lege cataloog ziet er niet uit als een
rechtenprobleem, dus dit is de plek waar dat vastligt.

Het account is uitdrukkelijk geen superuser: het leest de rechten, het staat er
niet boven. Schrijven naar Authentik doet de MCP nooit.
"""
from authentik.core.models import Token, TokenIntents, User, UserTypes
from guardian.shortcuts import assign_perm

GEBRUIKERSNAAM = "portal-mcp-readonly"
TOKEN_NAAM = "portal-mcp-readonly-token"

RECHTEN = (
    "authentik_core.view_application",
    "authentik_policies.view_policybinding",
    "authentik_core.view_group",
    "authentik_core.view_user",
)

account, nieuw = User.objects.get_or_create(
    username=GEBRUIKERSNAAM,
    defaults=dict(name="Portal MCP (alleen lezen)", type=UserTypes.SERVICE_ACCOUNT),
)

for recht in RECHTEN:
    assign_perm(recht, account)

token, token_nieuw = Token.objects.get_or_create(
    identifier=TOKEN_NAAM,
    defaults=dict(
        user=account,
        intent=TokenIntents.INTENT_API,
        expiring=False,
        description="Portal-MCP cataloog en rechten (alleen lezen)",
    ),
)

print(f"serviceaccount: {'aangemaakt' if nieuw else 'bestond al'} ({GEBRUIKERSNAAM})")
print(f"token: {'aangemaakt' if token_nieuw else 'bestond al'} ({TOKEN_NAAM})")
print("rechten: " + ", ".join(RECHTEN))
print("PORTAL_MCP_AUTHENTIK_TOKEN=" + token.key)
print("PORTAL_MCP_TOKEN_DONE")
