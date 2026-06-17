from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding

admin = Group.objects.get(name="admin")

# akadmin in de admin-groep
ak = User.objects.get(username="akadmin")
ak.groups.add(admin)
print(f"akadmin zit nu in: {[g.name for g in ak.groups.all()]}")

# Elke app aan de admin-groep binden -> admins zien alles
for slug in ("omv", "schuldentracker", "status"):
    app = Application.objects.filter(slug=slug).first()
    if app:
        PolicyBinding.objects.get_or_create(target=app, group=admin, defaults=dict(order=0))
        print(f"{slug} -> gebonden aan admin")
print("AKADMIN_ALL_DONE")
