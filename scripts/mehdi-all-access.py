"""Geef user 'mehdi' toegang tot ALLE app-groepen, zodat hij elke tegel ziet.
Behoudt read-only in Schuldentracker (slaat 'schuldentracker-bewerken' over).
Matcht op USERNAME (niet e-mail -- mehdi heeft geen e-mail). Idempotent.
"""
from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding

USERNAME = "mehdi"
EXCLUDE_GROUPS = {"schuldentracker-bewerken"}

user = User.objects.filter(username=USERNAME).first()
if not user:
    print("MEHDI_NOT_FOUND")
    raise SystemExit(1)

groups = set()
for app in Application.objects.all():
    for b in PolicyBinding.objects.filter(target=app):
        if b.group:
            groups.add(b.group)

for g in groups:
    if g.name in EXCLUDE_GROUPS:
        continue
    g.users.add(user)

print(f"{user.username} zit nu in: {sorted(x.name for x in Group.objects.filter(users=user))}")
print("MEHDI_FIX_DONE")
