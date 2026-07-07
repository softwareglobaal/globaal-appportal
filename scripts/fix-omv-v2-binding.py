"""Beveiligingsfix: bind de applicatie 'omv-v2' aan de groep 'admin', zodat
niet langer elke ingelogde gebruiker erbij kan (een app zonder binding is
voor iedereen toegankelijk). Voorlopige maatregel, besloten 2026-07-07;
gaat later mee in de app-{naam}-read/-edit-migratie
(docs/plan-groepstoegang-blueprints.md).

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/fix-omv-v2-binding.py

Idempotent: veilig om opnieuw te draaien.
"""
from authentik.core.models import Application, Group
from authentik.policies.models import PolicyBinding

app = Application.objects.filter(slug="omv-v2").first()
if not app:
    print("app 'omv-v2' bestaat niet (niets te doen)")
    raise SystemExit(0)

admin = Group.objects.get(name="admin")
_, created = PolicyBinding.objects.get_or_create(
    target=app, group=admin, defaults=dict(order=0)
)
print(f"binding omv-v2 -> admin: {'aangemaakt' if created else 'bestond al'}")

print("bindings op omv-v2 nu:")
for b in PolicyBinding.objects.filter(target=app):
    wie = b.group.name if b.group else (b.user.username if b.user else str(b.policy))
    print(f"- {wie} (order={b.order}, enabled={b.enabled})")
print("OMV_V2_FIX_DONE")
