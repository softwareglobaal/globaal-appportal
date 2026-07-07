"""Onderzoek (read-only): waar wordt de groep 'toegangsbeheerders' voor
gebruikt? Print groepsdetails, alle bindings waarin de groep voorkomt,
expression-policies die de naam noemen en recente events rond de groep.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/onderzoek-toegangsbeheerders.py

Wijzigt niets: alleen lezen en printen.
"""
from authentik.core.models import Application, Group
from authentik.events.models import Event
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.models import PolicyBinding

NAAM = "toegangsbeheerders"

g = Group.objects.filter(name=NAAM).first()
if not g:
    print(f"groep '{NAAM}' bestaat niet")
    raise SystemExit(0)

print("== Groepsdetails ==")
print(f"naam: {g.name}")
print(f"leden: {sorted(u.username for u in g.users.all()) or '(leeg)'}")
print(f"superuser-groep: {g.is_superuser}")
print(f"parent: {g.parent.name if g.parent else '(geen)'}")
print(f"attributes: {g.attributes or '(leeg)'}")
rollen = [str(r) for r in g.roles.all()] if hasattr(g, "roles") else []
print(f"rbac-rollen: {rollen or '(geen)'}")

print()
print("== Bindings waarin de groep voorkomt ==")
bindings = list(PolicyBinding.objects.filter(group=g))
if not bindings:
    print("(geen: de groep is nergens aan gebonden)")
for b in bindings:
    app = Application.objects.filter(pbm_uuid=b.target_id).first()
    doel = f"app:{app.slug}" if app else f"target:{b.target}"
    print(f"- {doel} (order={b.order}, enabled={b.enabled})")

print()
print("== Expression-policies die de naam noemen ==")
hits = [p for p in ExpressionPolicy.objects.all() if NAAM in (p.expression or "")]
if not hits:
    print("(geen)")
for p in hits:
    print(f"- {p.name}")

print()
print("== Recente events rond de groep (aanmaak/wijziging) ==")
count = 0
for e in Event.objects.filter(
    action__in=["model_created", "model_updated", "model_deleted"]
).order_by("-created")[:3000]:
    if NAAM in str(e.context):
        print(f"- {e.created:%Y-%m-%d %H:%M} {e.action} door {e.user.get('username', '?')}")
        count += 1
        if count >= 10:
            break
if count == 0:
    print("(geen events gevonden binnen de retentie)")

print("ONDERZOEK_DONE")
