from authentik.core.models import User, Group
u = User.objects.get(username="akadmin")
g = Group.objects.get(name="manager")
u.groups.add(g)
print(f"akadmin in groepen: {[x.name for x in u.groups.all()]}")
