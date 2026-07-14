from authentik.core.models import Application, User
from authentik.policies.models import PolicyBinding

print("=== USERS & GROUPS ===")
for u in User.objects.all().order_by("username"):
    print(f"- {u.username} <{u.email}> | superuser={u.is_superuser} | groups={sorted(g.name for g in u.ak_groups.all())}")

print("=== APPS & BINDINGS ===")
for app in Application.objects.all().order_by("slug"):
    rows = []
    for b in PolicyBinding.objects.filter(target=app):
        if b.group:
            rows.append("group:" + b.group.name)
        elif b.user:
            rows.append("user:" + b.user.username)
        else:
            rows.append("policy/other")
    print(f"- {app.slug} ({app.name}) | bindings={rows or 'NONE (open to all)'}")
print("DIAG_DONE")
