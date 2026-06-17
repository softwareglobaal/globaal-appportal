"""Creates two demo users for verifying role-based tiles and SSO click-through.

    testadmin   / member of group: admin    (sees 3 tiles, no FinanceDashboard)
    testmanager / member of group: manager  (sees all 4 tiles)

Both get the password printed at the end. Delete these users before real use.
Run: sh scripts/ak-exec.sh scripts/create-test-users.py
"""
from authentik.core.models import Group, User

PASSWORD = "AppPortal-Demo-2026!"

for uname, gname in [("testadmin", "admin"), ("testmanager", "manager")]:
    user, created = User.objects.get_or_create(
        username=uname,
        defaults=dict(name=uname.title(), email=f"{uname}@example.com"),
    )
    user.set_password(PASSWORD)
    user.save()
    user.groups.add(Group.objects.get(name=gname))
    print(f"user {uname}: {'created' if created else 'updated'}, group={gname}")
print(f"password for both: {PASSWORD}")
print("USERS_DONE")
