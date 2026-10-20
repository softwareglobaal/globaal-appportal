"""Vul de groep `mail` voor het maildashboard (mijnagents.globaal.be/mail).

Mehdi, 20-10-2026: "kunnen we dit ook delen met Angela en Shaniel, zodat zij het ook kunnen bekijken";
gekozen: kijken en mee afhandelen (alle postvakken, ook hotmail; Opgelost, Doorgezet, Ruis en Helemaal weg
klikken, met hun naam erbij).

Draaien (vanuit ~/appportal), door Mehdi zelf, want het geeft toegang:
  sh scripts/ak-exec.sh scripts/mail-groep-vullen.py

Wat het doet, en niets meer:
- maakt de groep `mail` als die er nog niet is;
- bindt die groep aan de tegel mijnagents, naast admin, agents en manager (die blijven);
- zet angela en shaniel in de groep.
Het bord zelf (mijnagents/app.py, MAIL_GROEP) laat wie alleen in `mail` zit enkel /mail zien; de rest van het
bord blijft voor hen dicht. Idempotent. Maakt geen gebruikers aan: wie geen account heeft, wordt gemeld.
Terugdraaien: de leden uit de groep halen in Authentik (Directory > Groups > mail).
"""
from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding

GROEP = "mail"
LEDEN = ("angela", "shaniel")

groep, gemaakt = Group.objects.get_or_create(name=GROEP)
print(f"groep {GROEP}: {'aangemaakt' if gemaakt else 'bestond al'}")

app = Application.objects.filter(slug="mijnagents").first()
if app is None:
    raise SystemExit("tegel mijnagents niet gevonden")

if PolicyBinding.objects.filter(target=app, group=groep).exists():
    print(f"   binding {GROEP} op mijnagents: bestond al")
else:
    volgende = max([b.order for b in PolicyBinding.objects.filter(target=app)] + [0]) + 1
    PolicyBinding.objects.create(target=app, group=groep, order=volgende)
    print(f"   binding {GROEP} op mijnagents: aangemaakt (order {volgende})")
print("   bindingen nu:", ", ".join(sorted(b.group.name for b in PolicyBinding.objects.filter(target=app) if b.group)))

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
print("MAIL_GROEP_DONE")
