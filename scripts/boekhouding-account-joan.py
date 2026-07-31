"""Maakt het portal-account voor Joan Cabenda en zet haar in de groep boekhouding.

Draaien (vanuit ~/appportal):
  sh scripts/ak-exec.sh scripts/boekhouding-account-joan.py

Bewust geen wachtwoord: het account krijgt een onbruikbaar wachtwoord en een
eenmalige herstellink, zodat Joan haar eigen wachtwoord zet en niemand anders
het ooit gezien heeft. De link wordt naar /tmp/joan-herstellink.txt op de VM
geschreven en niet afgedrukt.

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
    print("LET OP: geen herstelflow gevonden, geen link gemaakt. "
          "Zet het wachtwoord dan via de Authentik-beheerpagina.")
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
