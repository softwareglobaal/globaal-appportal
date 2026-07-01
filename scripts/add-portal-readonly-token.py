"""Create a read-only Authentik service account + API token for the portal's
Access overview page, and print the key to put in .env as AUTHENTIK_API_TOKEN.

Surgical and idempotent: re-running reuses the same service account and token
(and prints the existing key), and touches nothing else. The account gets only
view_user + view_group — enough to list groups and their members; the portal
never writes to Authentik.

Run:  sh scripts/ak-exec.sh scripts/add-portal-readonly-token.py
Then put the printed key in .env as AUTHENTIK_API_TOKEN and reload the portal:
    docker compose up -d portal
"""
from authentik.core.models import Token, TokenIntents, User, UserTypes
from guardian.shortcuts import assign_perm

USERNAME = "portal-readonly"
TOKEN_IDENTIFIER = "portal-readonly-token"

sa, created = User.objects.get_or_create(
    username=USERNAME,
    defaults=dict(name="Portal Read-Only", type=UserTypes.SERVICE_ACCOUNT),
)

# Read-only: only enough to list groups and their members. Never writes.
for perm in ("authentik_core.view_user", "authentik_core.view_group"):
    assign_perm(perm, sa)

token, tok_created = Token.objects.get_or_create(
    identifier=TOKEN_IDENTIFIER,
    defaults=dict(
        user=sa,
        intent=TokenIntents.INTENT_API,
        expiring=False,
        description="Portal Access overview (read-only)",
    ),
)

print(f"service account: {'created' if created else 'exists'} ({USERNAME})")
print(f"token: {'created' if tok_created else 'exists'} ({TOKEN_IDENTIFIER})")
print("AUTHENTIK_API_TOKEN=" + token.key)
print("PORTAL_TOKEN_DONE")
