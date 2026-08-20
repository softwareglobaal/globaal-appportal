"""Vul de groep `intercompany` en bind hem aan de tegel.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/intercompany-groep-vullen.py

Idempotent.

Waarom een eigen groep en niet `boekhouding`: die groep opent ook
boekhouding.globaal.be en quickbooks.globaal.be. Wie alleen de onderlinge
facturatie hoeft te zien, hoort niet meteen de klantfacturatie van Joan en het
tweede boekhoudpakket erbij te krijgen.

Mehdi heeft via admin en manager sowieso al toegang; hij staat hier toch in
zodat die toegang blijft als zijn rol ooit verandert.
"""
from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding

GROEP = "intercompany"
LEDEN = ("angela", "mehdi")

groep, gemaakt = Group.objects.get_or_create(name=GROEP)
print(f"groep {GROEP}: {'aangemaakt' if gemaakt else 'bestond al'}")

app = Application.objects.filter(slug="intercompany").first()
if app is None:
    raise SystemExit("tegel intercompany bestaat nog niet, "
                     "draai eerst scripts/add-intercompany-app.py")
_, nieuw = PolicyBinding.objects.get_or_create(target=app, group=groep,
                                               defaults=dict(order=0))
print(f"binding op de tegel: {'toegevoegd' if nieuw else 'bestond al'}")

for naam in LEDEN:
    u = User.objects.filter(username=naam).first()
    if u is None:
        print(f"   {naam}: GEEN ACCOUNT GEVONDEN, overgeslagen")
        continue
    if u.ak_groups.filter(name=GROEP).exists():
        print(f"   {naam}: zat er al in")
        continue
    u.ak_groups.add(groep)
    print(f"   {naam}: toegevoegd")

print("leden nu:", ", ".join(sorted(u.username for u in groep.users.all())))
print("INTERCOMPANY_GROEP_DONE")
