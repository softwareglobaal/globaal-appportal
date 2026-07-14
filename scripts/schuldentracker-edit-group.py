from authentik.core.models import Group, User
g, _ = Group.objects.get_or_create(name="schuldentracker-bewerken")
angela = User.objects.filter(username="angela").first()
if angela:
    angela.groups.add(g)
    print(f"angela -> groepen: {[x.name for x in angela.groups.all()]}")
else:
    print("LET OP: gebruiker 'angela' niet gevonden")
print("EDIT_GROUP_DONE")
