"""Vul de groep `db-alles` voor Organisatie kosten.

Draaien (vanuit ~/appportal), na scripts/app-registreren.py organisatiekosten:
  sh scripts/ak-exec.sh scripts/organisatiekosten-groep-vullen.py

Idempotent. Maakt geen gebruikers aan: wie geen account heeft, wordt gemeld en
overgeslagen.

db-alles geeft volledige toegang: het groepsoverzicht en alle firma's. Later
komt er per firma een groep (db-tknb, ...), die enkel die firma laat zien.
Siyan staat er expliciet in: niet iedereen met volle toegang zit in admin.
"""
from authentik.core.models import Application, Group, User

GROEP = "db-alles"
LEDEN = ("siyan", "angela", "mehdi")

groep, gemaakt = Group.objects.get_or_create(name=GROEP)
print(f"groep {GROEP}: {'aangemaakt' if gemaakt else 'bestond al'}")

if Application.objects.filter(slug="organisatiekosten").first() is None:
    raise SystemExit("tegel organisatiekosten bestaat nog niet, "
                     "draai eerst scripts/app-registreren.py organisatiekosten")

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

# Wie niet gevonden werd: toon de gebruikersnamen die erop lijken.
for naam in LEDEN:
    if not User.objects.filter(username=naam).exists():
        lijkt = User.objects.filter(username__icontains=naam[:4]) | User.objects.filter(name__icontains=naam[:4])
        print(f"   {naam} niet gevonden; lijkt op:", ", ".join(sorted({u.username for u in lijkt})) or "niemand")
print("ORGANISATIEKOSTEN_GROEP_DONE")
