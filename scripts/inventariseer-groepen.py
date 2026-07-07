"""Inventarisatie (read-only): alle groepen met leden, alle app-bindings, en
een focus op de groepen 'admin' en 'manager'. Voorbereiding op de migratie
naar app-{naam}-read/-edit (zie docs/plan-groepstoegang-blueprints.md).

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/inventariseer-groepen.py

Wijzigt niets: alleen lezen en printen. Output terugplakken in de sessie,
dan wordt de hertoewijzing per persoon uitgetekend.
"""
from authentik.core.models import Application, Group, User, UserTypes
from authentik.policies.models import PolicyBinding

print("== Alle groepen en hun leden ==")
for g in Group.objects.order_by("name"):
    leden = sorted(u.username for u in g.users.all())
    print(f"- {g.name}: {', '.join(leden) if leden else '(leeg)'}")

print()
print("== Bindings per applicatie ==")
for app in Application.objects.order_by("slug"):
    doelen = []
    for b in PolicyBinding.objects.filter(target=app):
        if b.group:
            doelen.append(b.group.name)
        elif b.user:
            doelen.append(f"user:{b.user.username}")
        elif b.policy:
            doelen.append(f"policy:{b.policy.name}")
    print(f"- {app.slug}: {', '.join(sorted(doelen)) if doelen else '(geen bindings)'}")

print()
print("== Focus: admin en manager ==")
for name in ("admin", "manager"):
    g = Group.objects.filter(name=name).first()
    if not g:
        print(f"- groep '{name}' bestaat niet")
        continue
    leden = sorted(u.username for u in g.users.all())
    apps = []
    for b in PolicyBinding.objects.filter(group=g):
        a = Application.objects.filter(pbm_uuid=b.target_id).first()
        apps.append(a.slug if a else f"(ander doel: {b.target})")
    print(f"- {name}: leden = {', '.join(leden) if leden else '(leeg)'}")
    print(f"  gebonden aan: {', '.join(sorted(apps)) if apps else '(geen)'}")

print()
print("== Actieve gebruikers zonder enige groep ==")
for u in User.objects.filter(is_active=True).order_by("username"):
    if u.type in (UserTypes.SERVICE_ACCOUNT, UserTypes.INTERNAL_SERVICE_ACCOUNT):
        continue
    if u.username == "akadmin":
        continue
    if not u.groups.exists():
        print(f"- {u.username} ({u.name})")

print("INVENTARIS_DONE")
