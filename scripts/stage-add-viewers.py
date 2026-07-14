from authentik.core.models import Group, User
g = Group.objects.get(name="stagebeoordeling")
for uname in ["mehdi", "akadmin"]:
    u = User.objects.filter(username__iexact=uname).first()
    if u:
        g.users.add(u); print("toegevoegd (read-only):", u.username)
    else:
        print("niet gevonden:", uname)
print("VIEWERS_DONE")
