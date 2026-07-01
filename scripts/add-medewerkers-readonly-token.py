"""Create a read-only Authentik service account + API token for the Medewerkers
app's "Toegang (Authentik)" panel, and print the key to put in .env.

RBAC-correct + idempotent: a Role holds the read-only permissions
(view_user + view_group), bound via a Group to the service account. Re-running
reuses everything and reprints the key. The app never writes to Authentik.

Run:  sh scripts/ak-exec.sh scripts/add-medewerkers-readonly-token.py
Then put the printed key in .env as MEDEWERKERS_AUTHENTIK_TOKEN and reload:
    docker compose up -d app-medewerkers
"""
from authentik.core.models import Group, Token, TokenIntents, User, UserTypes
from authentik.rbac.models import Role

NAME = "medewerkers-readonly"
TOKEN_IDENTIFIER = "medewerkers-readonly-token"

sa, sa_created = User.objects.get_or_create(
    username=NAME,
    defaults=dict(name="Medewerkers Read-Only", type=UserTypes.SERVICE_ACCOUNT),
)

# Read-only permissions live on a Role (RBAC), bound via a Group to the SA.
role, _ = Role.objects.get_or_create(name=NAME)
for perm in ("authentik_core.view_user", "authentik_core.view_group"):
    try:
        role.assign_perms(perm)
    except TypeError:
        role.assign_perms([perm])

group, _ = Group.objects.get_or_create(name=NAME)
group.roles.add(role)
sa.ak_groups.add(group)

token, tok_created = Token.objects.get_or_create(
    identifier=TOKEN_IDENTIFIER,
    defaults=dict(
        user=sa,
        intent=TokenIntents.INTENT_API,
        expiring=False,
        description="Medewerkers Toegang-panel (read-only)",
    ),
)

print(f"service account: {'created' if sa_created else 'exists'} ({NAME})")
print(f"role+group: bound ({NAME})")
print(f"token: {'created' if tok_created else 'exists'} ({TOKEN_IDENTIFIER})")
print("MEDEWERKERS_AUTHENTIK_TOKEN=" + token.key)
print("MEDEWERKERS_TOKEN_DONE")
