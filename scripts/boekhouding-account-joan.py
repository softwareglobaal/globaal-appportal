"""Maakt het portal-account voor Joan Cabenda en zet haar in de groep boekhouding.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/boekhouding-account-joan.py

Bewust geen wachtwoord in de code of in chat. Is er een self-service
herstelflow, dan krijgt Joan een eenmalige herstellink en zet ze haar eigen
wachtwoord. Is die er niet, dan wordt hier een startwachtwoord gegenereerd. In
beide gevallen landt het resultaat in een bestand op de VM met rechten 600 en
wordt het niet afgedrukt.

Idempotent: opnieuw draaien maakt geen tweede account, maar wel een verse link.
"""
import os

from authentik.core.models import Group, Token, TokenIntents, User
from authentik.flows.models import Flow

BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "globaal.be")
USERNAME = "joan"
NAAM = "Joan Cabenda"
GROEPEN = ("boekhouding",)
LINKBESTAND = "/tmp/joan-herstellink.txt"
WACHTWOORDBESTAND = "/tmp/joan-startwachtwoord.txt"

gebruiker, gemaakt = User.objects.get_or_create(
    username=USERNAME, defaults=dict(name=NAAM))
gebruiker.name = NAAM
gebruiker.is_active = True
if gemaakt:
    # Geen bruikbaar wachtwoord: aanmelden kan pas na de herstelflow.
    gebruiker.set_unusable_password()
gebruiker.save()
print(f"account {USERNAME}: {'aangemaakt' if gemaakt else 'bestond al'} ({gebruiker.name})")

for naam in GROEPEN:
    groep, _ = Group.objects.get_or_create(name=naam)
    groep.users.add(gebruiker)
    groep.save()
print("groepen:", ", ".join(g.name for g in gebruiker.ak_groups.all()) or "geen")

herstel = (Flow.objects.filter(slug="default-recovery-flow").first()
           or Flow.objects.filter(designation="recovery").first())
if not herstel:
    # Deze Authentik heeft geen self-service herstelflow. Dan een gegenereerd
    # startwachtwoord dat de VM niet verlaat: het staat in een bestand dat
    # alleen de beheerder kan lezen, en Joan wijzigt het na de eerste keer.
    import secrets
    import string

    tekens = string.ascii_letters + string.digits
    wachtwoord = "".join(secrets.choice(tekens) for _ in range(20))
    gebruiker.set_password(wachtwoord)
    gebruiker.save()
    with open(WACHTWOORDBESTAND, "w", encoding="utf-8") as f:
        f.write(f"startwachtwoord voor {USERNAME} ({NAAM}): {wachtwoord}\n"
                f"aanmelden op https://{BASE_DOMAIN} en meteen wijzigen.\n")
    os.chmod(WACHTWOORDBESTAND, 0o600)
    print(f"geen herstelflow op deze Authentik; startwachtwoord gezet en "
          f"geschreven naar {WACHTWOORDBESTAND}")
else:
    token = Token.objects.create(
        user=gebruiker, intent=TokenIntents.INTENT_RECOVERY,
        description=f"herstellink {USERNAME} (boekhouding)", expiring=True)
    link = f"https://auth.{BASE_DOMAIN}/if/flow/{herstel.slug}/?token={token.key}"
    with open(LINKBESTAND, "w", encoding="utf-8") as f:
        f.write(link + "\n")
    os.chmod(LINKBESTAND, 0o600)
    print(f"herstellink geschreven naar {LINKBESTAND} (flow {herstel.slug}, "
          f"vervalt vanzelf)")
print("JOAN_ACCOUNT_DONE")
