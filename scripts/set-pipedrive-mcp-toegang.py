"""Zet de toegang tot het Pipedrive-MCP-endpoint op een vaste lijst personen.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/set-pipedrive-mcp-toegang.py

Idempotent: veilig om opnieuw te draaien.

Sinds 03-09-2026 mag alleen **mehdi** met deze koppeling werken. De eerste opzet
bond vier groepen aan de app (pipedrive, pipedrive-editors, sales, admin),
waardoor elf mensen van sales konden meelezen in de verkoopadministratie van
vijf firma's. Dit script vervangt dat door bindingen op naam.

Wat het doet:
  1. alle bestaande bindingen op de app weghalen (groep of gebruiker);
  2. een binding per naam uit TOEGANG zetten;
  3. de lege groepen pipedrive en pipedrive-editors opruimen, zodat niemand
     denkt dat lidmaatschap daarvan nog toegang geeft.

De server kijkt daarnaast zelf nog een keer: `MCP_GEBRUIKERS` in
~/pipedrive-mcp.env moet dezelfde namen bevatten. Twee poorten, want een
verruiming in Authentik hoort niet meteen de Pipedrive-gegevens te openen.
"""
from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding

SLUG = "pipedrive-mcp"
TOEGANG = ["mehdi"]
OPRUIMEN = ["pipedrive", "pipedrive-editors"]

app = Application.objects.get(slug=SLUG)

weg = []
for b in PolicyBinding.objects.filter(target=app):
    weg.append(b.group.name if b.group else (b.user.username if b.user else "policy"))
    b.delete()
print("verwijderde bindingen: " + (", ".join(sorted(weg)) or "geen"))

for naam in TOEGANG:
    u = User.objects.filter(username=naam).first()
    if not u:
        print(f"LET OP: gebruiker {naam} niet gevonden, geen binding gemaakt")
        continue
    PolicyBinding.objects.get_or_create(target=app, user=u, defaults=dict(order=0))
    print(f"toegang: {naam}")

for naam in OPRUIMEN:
    g = Group.objects.filter(name=naam).first()
    if not g:
        continue
    leden = list(g.users.all())
    if leden:
        print(f"groep {naam} NIET verwijderd, er zitten nog leden in: "
              + ", ".join(u.username for u in leden))
        continue
    g.delete()
    print(f"lege groep {naam} verwijderd")

blijft = [(b.user.username if b.user else (b.group.name if b.group else "policy"))
          for b in PolicyBinding.objects.filter(target=app)]
print("stand: " + (", ".join(sorted(blijft)) or "NIEMAND"))
print("PIPEDRIVE_MCP_TOEGANG_DONE")
