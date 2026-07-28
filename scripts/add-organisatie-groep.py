# Staf-toegang tot het organisatie-dashboard zonder de beheerkant.
#
# Draaien:  sh scripts/ak-exec.sh scripts/add-organisatie-groep.py
#
# Waarom een eigen groep: 'hr' geeft er het HR-dashboard bij (personeelsdata)
# en 'manager' geeft elf apps waaronder Vermogen. Wie alleen het
# organisatie-dashboard nodig heeft, hoort in 'organisatie': die ziet
# medewerkers, firma's, disciplines en het woordenboek, maar niet financien,
# relaties, signalen, ontwikkeling of de graaf (die blijven admin en manager).
#
# De app moet de groep ook als staf herkennen: ORGANISATIE_STAFF_GROUPS staat
# daarom op "hr,organisatie" in docker-compose.override.yml.
from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding

LEDEN = ["siyan"]

grp, nieuw = Group.objects.get_or_create(name="organisatie")
print(f"GROEP organisatie {'aangemaakt' if nieuw else 'bestond al'}")

app = Application.objects.filter(slug="medewerkers").first()
if not app:
    raise SystemExit("applicatie 'medewerkers' niet gevonden")
binding, nieuw_b = PolicyBinding.objects.get_or_create(
    target=app, group=grp, defaults=dict(order=2))
print(f"BINDING op {app.name} {'toegevoegd' if nieuw_b else 'bestond al'}")

for uname in LEDEN:
    u = User.objects.filter(username=uname).first()
    if not u:
        print(f"LET OP: gebruiker {uname} bestaat niet")
        continue
    u.groups.add(grp)
    print(f"USER {uname} zit nu in: {sorted(g.name for g in u.groups.all())}")

print("ORGANISATIE_GROEP_DONE")
